"""Public persisted lifecycle gates for independently sourced evidence batches."""
from copy import deepcopy
import unittest

import test_control_plane as legacy
from test_gto_acceptance_retest_contract import BlackboxLifecycleTest
from test_gto_acceptance_batches import BatchHarness, digest


class BatchCoverageCliTest(BatchHarness, unittest.TestCase):
    def test_complete_delta_rebind_preserves_history_and_rejects_omitted_paths(self):
        self.begin(extra_code_files=True)
        first = self.attempt()
        old = self.make_batch(first, 0, terminal=True)
        self.accepted('record-acceptance-evidence-batch', old)
        preserved = deepcopy(self.state()['acceptance_gate']['evidence_batches'])
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')
        (self.repo / 'extra-code/deleted.json').unlink()
        self.write_json('extra-code/added.json', {'new': True})
        self.write_json('extra-code/modified.json', {'version': 2})
        result = self.work_result('integration')
        result['changed_files'] = ['extra-code/deleted.json', 'extra-code/added.json', 'extra-code/modified.json']
        self.run_ctl('record-subtask-result', subtask_id=integration['subtask_id'], result=result)
        self.run_ctl('freeze-candidate')
        second = self.attempt()
        current = second['coverage_snapshot']
        before = first['coverage_snapshot']
        delta = [{'path': p, 'before': before.get(p), 'after': current.get(p)}
                 for p in sorted(set(before) | set(current)) if before.get(p) != current.get(p)]
        self.assertEqual(set(result['changed_files']), {d['path'] for d in delta})
        self.assertTrue(any(d['before'] is None for d in delta))
        self.assertTrue(any(d['after'] is None for d in delta))
        rebound = deepcopy(old)
        rebound['batch_id'] = 'old-unit-rebound-to-current'
        review_changes = {'current_coverage_sha256': digest(current), 'delta_sha256': digest(delta),
                          'changed_paths': [d['path'] for d in delta]}
        for omitted in delta:
            incomplete = [d for d in delta if d != omitted]
            self.review_batch(rebound, first, **{**review_changes, 'delta_sha256': digest(incomplete),
                'changed_paths': [d['path'] for d in incomplete]})
            failure = self.rejected('record-acceptance-evidence-batch', rebound)
            self.assertRegex(' '.join(failure['errors']).lower(), 'delta|bind')
        self.review_batch(rebound, first, **review_changes)
        self.accepted('record-acceptance-evidence-batch', rebound)
        new = self.make_batch(second, 1)
        self.accepted('record-acceptance-evidence-batch', new)
        self.finish_partial(second, new)
        self.rejected('record-acceptance-coverage', self.coverage([old, new]))
        self.accepted('record-acceptance-coverage', self.coverage([rebound, new]))
        self.assertEqual(preserved, self.state()['acceptance_gate']['evidence_batches'][:1])
        self.accepted('validate')

    def test_existing_historical_batch_does_not_block_new_candidate_batch(self):
        first, old = self.historical()
        self.accepted('record-acceptance-evidence-batch', old)
        old_registered = deepcopy(self.state()['acceptance_gate']['evidence_batches'])
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')
        source = self.repo / 'candidate-source.py'
        source.write_text(source.read_text() + '\n# A real candidate delta.\n')
        result = self.work_result('integration')
        result['changed_files'] = ['candidate-source.py']
        self.run_ctl('record-subtask-result', subtask_id=integration['subtask_id'], result=result)
        self.run_ctl('freeze-candidate')
        second = self.attempt()
        self.assertNotEqual(first['candidate_id'], second['candidate_id'])
        new = self.make_batch(second, 1)
        # A disjoint current unit has valid current applicability. The old
        # batch must remain historical, not block all new registrations.
        self.accepted('record-acceptance-evidence-batch', new)
        self.assertEqual(old_registered, self.state()['acceptance_gate']['evidence_batches'][:1])

    def complete(self):
        first, old = self.historical(required_evidence=True)
        self.accepted('record-acceptance-evidence-batch', old)
        second = self.attempt()
        new = self.make_batch(second, 1)
        self.accepted('record-acceptance-evidence-batch', new)
        self.finish_partial(second, new)
        receipt = self.coverage([old, new])
        self.accepted('record-acceptance-coverage', receipt)
        return first, second, old, new, receipt

    def test_split_coverage_closes_without_rewriting_history_or_cost(self):
        first, second, old, new, receipt = self.complete()
        state = self.state()
        attempts = state['acceptance_gate']['attempts']
        self.assertEqual(['environment_failure', 'partial_pass'], [a['outcome'] for a in attempts])
        self.assertEqual(3, sum(a['real_call_count'] for a in attempts))
        self.assertEqual(5, sum(a['duration_seconds'] for a in attempts))
        self.assertFalse(state['acceptance_gate']['coverage_receipts'][-1]['same_round_full_execution'])
        before = self.artifacts()
        self.accepted('record-acceptance-coverage', receipt)
        self.assertEqual(before, self.artifacts())
        self.accepted('validate')
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.assertEqual('completed', self.run_ctl('finalize-task')['status'])

    def test_missing_or_pending_units_cannot_claim_complete_coverage(self):
        _, old = self.historical()
        self.accepted('record-acceptance-evidence-batch', old)
        self.rejected('record-acceptance-coverage', self.coverage([old]))
        second = self.attempt()
        new = self.make_batch(second, 1)
        self.accepted('record-acceptance-evidence-batch', new)
        self.rejected('record-acceptance-coverage', self.coverage([old, new]))
        self.rejected('finalize-task')

    def test_overlap_and_foreign_candidate_coverage_rejected(self):
        _, _, old, new, receipt = self.complete()
        for update in ({'coverage_id': 'duplicate-unit', 'batch_ids': [old['batch_id'], old['batch_id']]},
                       {'coverage_id': 'stale', 'candidate_id': 'candidate-other'},
                       {'coverage_id': 'wrong-author', 'written_by': 'impl-001'}):
            value = deepcopy(receipt)
            value.update(update)
            self.rejected('record-acceptance-coverage', value)

    def test_registered_evidence_is_rechecked_by_validate_and_finalize(self):
        _, _, old, new, _ = self.complete()
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        targets = [old['units'][0]['raw']['path'], old['units'][0]['score']['path'],
                   old['applicability_review']['path'], old['contract']['path'],
                   'candidate-config.json', 'candidate-source.py']
        score = self.read_json(old['units'][0]['score'])['records'][0]
        targets.append(score['source_score']['path'])
        proof = self.read_json(old['applicability_review'])['evidence_refs'][0]['path']
        targets.append(proof)
        for path in targets:
            with self.subTest(path=path):
                target = self.repo / path
                original = target.read_bytes()
                try:
                    target.write_bytes(original + b'\n ')
                    self.rejected('validate')
                    failure = self.rejected('finalize-task')
                    self.assertRegex(' '.join(failure.get('errors', [])).lower(),
                                     'hash|batch|candidate|evidence|coverage')
                finally:
                    target.write_bytes(original)
        self.assertEqual('completed', self.accepted('finalize-task')['status'])

    def test_partial_cannot_claim_more_executed_units_than_batch(self):
        _, old = self.historical()
        self.accepted('record-acceptance-evidence-batch', old)
        attempt = self.attempt()
        new = self.make_batch(attempt, 1)
        self.accepted('record-acceptance-evidence-batch', new)
        evidence = {'outcome': 'partial_pass', 'mode': 'partial', 'real_call_count': 1,
                    'duration_seconds': 1, 'failed_stage': 'none', 'executed_unit_ids': ['CASE-01', 'CASE-02'],
                    'evidence_batch_ids': [new['batch_id']], 'scope_acceptance_ids': ['REAL-PATH-001'],
                    'evidence_refs': [new['units'][0]['raw']['path']],
                    'evidence_by_acceptance_id': {'REAL-PATH-001': [new['units'][0]['raw']['path']]}}
        from test_gto_workflow import usage
        evidence['usage_evidence'] = usage('accept-001', 'acceptance')
        self.rejected('record-subtask-result', legacy.result('completed', 'accept-001', 'tester',
                      expensive_acceptance=evidence), subtask_id=attempt['subtask_id'])

    def test_required_evidence_key_cannot_be_missing_or_owned_by_old_attempt(self):
        _, old = self.historical(required_evidence=True)
        self.accepted('record-acceptance-evidence-batch', old)
        attempt = self.attempt()
        new = self.make_batch(attempt, 1)
        self.accepted('record-acceptance-evidence-batch', new)
        from test_gto_workflow import usage
        evidence = {'outcome': 'partial_pass', 'mode': 'partial', 'real_call_count': 1,
                    'duration_seconds': 1, 'failed_stage': 'none', 'executed_unit_ids': ['CASE-02'],
                    'evidence_batch_ids': [new['batch_id']], 'scope_acceptance_ids': ['REAL-PATH-001'],
                    'evidence_refs': [new['units'][0]['raw']['path']],
                    'evidence_by_acceptance_id': {'REAL-PATH-001': [new['units'][0]['raw']['path']]},
                    'usage_evidence': usage('accept-001', 'acceptance')}
        result = legacy.result('completed', 'accept-001', 'tester', expensive_acceptance=evidence)
        self.rejected('record-subtask-result', result, subtask_id=attempt['subtask_id'])
        result['review_evidence'] = {'acceptance_output_index': old['units'][0]['raw']['path']}
        self.rejected('record-subtask-result', result, subtask_id=attempt['subtask_id'])

    def test_new_failure_and_open_finding_cannot_be_hidden_by_prior_coverage(self):
        _, _, _, _, coverage = self.complete()
        attempt = self.attempt()
        import test_gto_workflow as workflow
        finding = workflow.WorkflowTest.new_finding(self, 'LATER-FAILURE', 'accept-001')
        finding['review_owner'] = {'platform_agent_id': 'review-001', 'agent_key': 'reviewer'}
        finding['acceptance_ids'] = ['REAL-PATH-001']
        self.run_ctl('record-acceptance-findings', subtask_id=attempt['subtask_id'],
                     result={'written_by': 'accept-001', 'findings': [finding]})
        evidence = {'outcome': 'product_failure', 'finding_id': 'LATER-FAILURE',
                    'real_call_count': 0, 'duration_seconds': 1, 'failed_stage': 'assertion',
                    'evidence_refs': ['.artifacts/later-failure.json'], 'evidence_by_acceptance_id': {},
                    'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'],
                    'usage_evidence': workflow.usage('accept-001', 'acceptance')}
        self.write_json('.artifacts/later-failure.json', {'outcome': 'fail'})
        result = legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance=evidence)
        result['review_evidence'] = {'acceptance_output_index': '.artifacts/later-failure.json'}
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=result)
        coverage['coverage_id'] = 'replayed-after-failure'
        self.rejected('record-acceptance-coverage', coverage)
        self.rejected('finalize-task')


class BlackboxBatchCliTest(BatchHarness, unittest.TestCase):
    def prepare_blackbox(self):
        attempt = self.attempt('preparation')
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'],
                     result=BlackboxLifecycleTest.receipt(self, 'preparation'))

    def test_blackbox_batches_keep_required_evidence_and_ordinary_gate(self):
        self.begin(blackbox=True, required_evidence=True)
        self.prepare_blackbox()
        first = self.attempt()
        old = self.make_batch(first, 0, terminal=True)
        self.accepted('record-acceptance-evidence-batch', old)
        self.prepare_blackbox()
        second = self.attempt()
        new = self.make_batch(second, 1)
        self.accepted('record-acceptance-evidence-batch', new)
        result = self.partial_result(new)
        for field in ('session_ids', 'input_refs', 'trace_refs'):
            bad = deepcopy(result)
            del bad['expensive_acceptance']['blackbox'][field]
            failure = self.rejected('record-subtask-result', bad, subtask_id=second['subtask_id'])
            self.assertRegex(' '.join(failure['errors']).lower(), 'blackbox|session|trace|input')
        for evidence in ({}, {'blackbox_output_index': old['units'][0]['raw']['path']},
                         {'functional_output_index': new['units'][0]['raw']['path']}):
            bad = deepcopy(result)
            bad['review_evidence'] = evidence
            self.rejected('record-subtask-result', bad, subtask_id=second['subtask_id'])
        self.finish_partial(second, new)
        coverage = self.coverage([old, new])
        wrong_kind = {**coverage, 'kind': 'ordinary'}
        self.rejected('record-acceptance-coverage', wrong_kind)
        self.accepted('record-acceptance-coverage', coverage)
        failure = self.rejected('finalize-task')
        self.assertIn('ordinary', ' '.join(failure['errors']).lower())
        ordinary = self.attempt('ordinary')
        # Preparation evidence is immutable after its run has been recorded.
        preparation_bytes = (self.repo / '.artifacts/observation.log').read_bytes()
        ordinary_path = '.artifacts/ordinary-observation.json'
        self.write_json(ordinary_path, {'functional': 'independent synthetic observation'})
        ordinary_result = BlackboxLifecycleTest.receipt(self, 'ordinary')
        ordinary_result['expensive_acceptance']['evidence_refs'] = [ordinary_path]
        ordinary_result['expensive_acceptance']['evidence_by_acceptance_id'] = {'REAL-PATH-001': [ordinary_path]}
        ordinary_result['review_evidence'] = {'blackbox_output_index': ordinary_path}
        failure = self.rejected('record-subtask-result', deepcopy(ordinary_result), subtask_id=ordinary['subtask_id'])
        self.assertIn('functional_output_index', ' '.join(failure['errors']))
        ordinary_result['review_evidence'] = {'functional_output_index': ordinary_path}
        self.run_ctl('record-subtask-result', subtask_id=ordinary['subtask_id'], result=ordinary_result)
        self.accepted('validate')
        self.assertEqual(preparation_bytes, (self.repo / '.artifacts/observation.log').read_bytes())
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.assertEqual('completed', self.accepted('finalize-task')['status'])
        self.assertEqual('environment_failure', self.state()['acceptance_gate']['attempts'][1]['outcome'])

    def test_effect_failure_cannot_be_reclassified_by_batch_or_coverage(self):
        self.begin(blackbox=True)
        self.prepare_blackbox()
        attempt = self.attempt()
        batch = self.make_batch(attempt, 0)
        result = BlackboxLifecycleTest.receipt(self, 'blackbox', 'effect_failure')
        result['expensive_acceptance']['evidence_refs'] = [batch['units'][0]['raw']['path']]
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=result)
        failure = self.rejected('record-acceptance-evidence-batch', batch)
        self.assertRegex(' '.join(failure['errors']).lower(), 'effect|failed')
        self.rejected('record-acceptance-coverage', self.coverage([batch]))
        self.rejected('create-subtask-attempt', subtask_id='EXPENSIVE-001', attempt_kind='blackbox',
                      approval_by='user', approval_reason='Budget alone does not authorize effect retry.')
        self.rejected('finalize-task')
        self.assertEqual('effect_failure', self.state()['acceptance_gate']['attempts'][-1]['outcome'])


if __name__ == '__main__':
    unittest.main()
