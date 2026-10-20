"""Public batch scope judgments and actual-execution failure barriers.

Synthetic batch records remain labeled fixtures; the controller, source/score
checks, snapshots and persisted transitions are real and never mocked.
"""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import test_control_plane as legacy
import test_gto_workflow as workflow
from test_gto_acceptance_batches import BatchHarness, digest
from test_gto_point_acceptance import PointHarness


class PointBatchHistoryTest(BatchHarness, unittest.TestCase):
    setUp = PointHarness.setUp

    def changed_comment(self):
        source, old = self.historical()
        old.pop('applicability_review')
        self.accepted('record-acceptance-evidence-batch', old)
        original_units = {ref['path']: (self.repo / ref['path']).read_bytes()
                          for unit in old['units'] for key, ref in unit.items()
                          if key in {'raw', 'input', 'score'}}
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')
        source_path = self.repo / 'candidate-source.py'
        source_path.write_text(source_path.read_text() + '\n# Explanation only; executable behavior unchanged.\n')
        result = self.work_result('integration')
        result['changed_files'] = ['candidate-source.py']
        self.run_ctl('record-subtask-result', subtask_id=integration['subtask_id'], result=result)
        self.run_ctl('freeze-candidate')
        current = self.attempt()
        before, after = source['coverage_snapshot'], current['coverage_snapshot']
        delta = [{'path': path, 'before': before.get(path), 'after': after.get(path)}
                 for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
        self.assertEqual(['candidate-source.py'], [item['path'] for item in delta])
        rebound = deepcopy(old)
        rebound['batch_id'] = 'same-unit-original-acceptor-judgment'
        self.review_batch(rebound, source, written_by='accept-001', written_role='tester',
            current_coverage_sha256=digest(after), delta_sha256=digest(delta),
            changed_paths=['candidate-source.py'])
        return source, rebound, original_units

    def test_original_batch_acceptor_can_bind_comment_only_delta_without_new_reviewer(self):
        _, batch, original_units = self.changed_comment()
        attempts_before = deepcopy(self.state()['acceptance_gate']['attempts'])
        self.accepted('record-acceptance-evidence-batch', batch)
        self.assertEqual(attempts_before, self.state()['acceptance_gate']['attempts'])
        self.assertEqual(original_units, {path: (self.repo / path).read_bytes() for path in original_units})
        self.assertEqual(1, len([task for task in self.state()['subtasks']
                                 if task['stage'] == 'pre_acceptance_review']))

    def test_new_reviewer_cannot_replace_original_batch_authors_semantic_judgment(self):
        _, batch, original_units = self.changed_comment()
        judgment = self.read_json(batch['applicability_review'])
        judgment.update(written_by='review-001', written_role='reviewer')
        batch['applicability_review'] = self.write_json('.artifacts/foreign-semantic-judgment.json', judgment)
        rejected = self.rejected('record-acceptance-evidence-batch', batch)
        self.assertRegex(str(rejected).lower(), 'original|author|writer|identity|acceptor')
        self.assertEqual(original_units, {path: (self.repo / path).read_bytes() for path in original_units})

    def completed_batches(self):
        first, old = self.historical()
        old.pop('applicability_review')
        self.accepted('record-acceptance-evidence-batch', old)
        second = self.attempt()
        new = self.make_batch(second, 1)
        new.pop('applicability_review')
        self.accepted('record-acceptance-evidence-batch', new)
        self.finish_partial(second, new)
        self.accepted('record-acceptance-coverage', self.coverage([old, new]))
        return first, second, old, new

    def later_attempt(self):
        response = self.accepted('create-subtask-attempt', {'scope_acceptance_ids': [self.batch_acceptance_id]},
            subtask_id='EXPENSIVE-001', attempt_kind='ordinary', approval_by='user',
            approval_reason='Synthetic test explicitly authorizes observing a later result.')
        attempt = response['attempt']
        self.bind(attempt['subtask_id'], agent='accept-001', role='tester')
        return attempt

    def retains_coverage_after_unexecuted(self, status):
        first, second, old, new = self.completed_batches()
        original = deepcopy(self.state()['acceptance_gate']['attempts'])
        attempt = self.later_attempt()
        reference = self.write_json('.artifacts/not-executed.json', {
            'status': status, 'executed': False, 'reason': 'Unavailable fixture transport; no business unit executed.'})
        result = legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'environment_failure', 'real_call_count': 0, 'duration_seconds': 1,
            'failed_stage': 'environment', 'mode': 'scoped', 'scope_acceptance_ids': [self.batch_acceptance_id],
            'point_results': [{'acceptance_id': self.batch_acceptance_id, 'status': status,
                               'evidence_refs': [], 'reason': 'No business execution occurred.'}],
            'evidence_refs': [reference['path']], 'evidence_by_acceptance_id': {},
            'usage_evidence': workflow.usage('accept-001', 'unexecuted')})
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=result)
        coverage = self.coverage([old, new])
        coverage['coverage_id'] = 'coverage-after-unexecuted'
        self.accepted('record-acceptance-coverage', coverage)
        projected = self.accepted('acceptance-status')
        self.assertEqual('pass', projected['points'][self.batch_acceptance_id]['status'],
                         'Public point coverage must include retained valid batch units after not_run/blocked.')
        state = self.state()
        self.assertEqual(original, state['acceptance_gate']['attempts'][:2])
        self.assertEqual('environment_failure', state['acceptance_gate']['attempts'][-1]['outcome'])
        self.assertEqual(3, sum(item['real_call_count'] for item in state['acceptance_gate']['attempts']))
        self.assertEqual({first['attempt_id'], second['attempt_id']},
            {unit['source_attempt_id'] for unit in state['acceptance_gate']['coverage_receipts'][-1]['unit_sources']})

    def test_later_not_run_environment_result_preserves_valid_historical_units(self):
        self.retains_coverage_after_unexecuted('not_run')

    def test_later_blocked_environment_result_preserves_valid_historical_units(self):
        self.retains_coverage_after_unexecuted('blocked')

    def test_later_actual_failure_still_blocks_old_complete_batch_coverage(self):
        _, _, old, new = self.completed_batches()
        attempt = self.later_attempt()
        failed = self.write_json('.artifacts/later-actual-failure.json', {
            'unit_id': 'CASE-02', 'acceptance_id': self.batch_acceptance_id, 'executed': True,
            'input': self.cases[1], 'actual': 'wrong answer', 'expected': 'correct answer', 'status': 'fail'})
        finding = workflow.WorkflowTest.new_finding(self, 'LATER-FAIL', 'accept-001')
        finding['regression_proof']['evidence_refs'] = [failed['path']]
        self.run_ctl('record-acceptance-findings', subtask_id=attempt['subtask_id'],
                     result={'written_by': 'accept-001', 'findings': [finding]})
        result = legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'product_failure', 'finding_id': 'LATER-FAIL', 'real_call_count': 1,
            'duration_seconds': 1, 'failed_stage': 'check', 'mode': 'scoped',
            'scope_acceptance_ids': [self.batch_acceptance_id],
            'point_results': [{'acceptance_id': self.batch_acceptance_id, 'status': 'fail',
                               'evidence_refs': [failed['path']]}],
            'evidence_refs': [failed['path']], 'evidence_by_acceptance_id': {},
            'usage_evidence': workflow.usage('accept-001', 'actual-failure')})
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=result)
        coverage = self.coverage([old, new])
        coverage['coverage_id'] = 'coverage-after-actual-failure'
        rejection = self.rejected('record-acceptance-coverage', coverage)
        self.assertRegex(str(rejection).lower(), 'fail|later')
        self.assertEqual('product_failure', self.state()['acceptance_gate']['attempts'][-1]['outcome'])


class BatchRegistrationTargetTest(unittest.TestCase):
    def test_candidate_rebound_preserves_target_for_unit_and_raw_deduplication(self):
        from test_gto_plan_preflight_contract import load_controller
        load_controller()
        import acceptance_batches as batches

        # Isolate registration identity from already-covered file/content
        # verification. Historical metadata knows the source; fresh validation
        # knows the semantic review target. No filesystem or business execution.
        def validated(repo, state, payload, current_records, *, require_current_applicability=True,
                      selected_acceptance_ids=None):
            return {'kind': 'ordinary',
                'target_candidate_id': state['acceptance_gate']['current_candidate']['candidate_id']
                    if require_current_applicability else 'candidate-A',
                'unit_ids': [unit['unit_id'] for unit in payload['units']],
                'raw_identities': [(unit['raw']['path'], unit['raw']['pointer']) for unit in payload['units']]}

        initial = {'batch_id': 'initial-A', 'source_attempt_id': 'observed-A',
            'written_by': 'source-observer', 'written_role': 'tester',
            'contract': {'path': '.artifacts/contract.json', 'sha256': 'a' * 64},
            'units': [{'unit_id': 'UNIT-1', 'acceptance_id': 'POINT-1',
                       'raw': {'path': '.artifacts/raw.json', 'pointer': '/records/0', 'sha256': 'b' * 64}}]}
        state = {'acceptance_gate': {'current_candidate': {'candidate_id': 'candidate-A'}}}
        records = lambda repo, state: {}
        with patch.object(batches, 'validate_batch', side_effect=validated):
            self.assertFalse(batches.add_batch(Path('.'), state, initial, records)[0])
            state['acceptance_gate']['current_candidate']['candidate_id'] = 'candidate-B'
            rebound = deepcopy(initial)
            rebound['batch_id'] = 'rebound-B'
            self.assertFalse(batches.add_batch(Path('.'), state, rebound, records)[0],
                             'The same observed unit may be legitimately rebound to a different candidate.')
            self.assertEqual(2, len(state['acceptance_gate']['evidence_batches']))
            for duplicate in ('unit', 'raw'):
                with self.subTest(duplicate=duplicate):
                    candidate_state = deepcopy(state)
                    payload = deepcopy(rebound)
                    payload['batch_id'] = 'duplicate-' + duplicate
                    if duplicate == 'unit':
                        payload['units'][0]['raw']['path'] = '.artifacts/different-raw.json'
                    else:
                        payload['units'][0]['unit_id'] = 'UNIT-2'
                    before = deepcopy(candidate_state)
                    with self.assertRaisesRegex(batches.BatchEvidenceError, 'repeated'):
                        batches.add_batch(Path('.'), candidate_state, payload, records)
                    self.assertEqual(before, candidate_state, 'Duplicate rejection must be atomic.')


if __name__ == '__main__':
    unittest.main()
