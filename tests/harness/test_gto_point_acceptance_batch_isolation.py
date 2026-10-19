"""Independent review regressions: per-point batch units and consumed evidence."""
from copy import deepcopy
import unittest

import test_control_plane as legacy
import test_gto_workflow as workflow
from test_gto_acceptance_batches import BatchHarness
from test_gto_point_acceptance import PointHarness


class MultiPointBatchHarness(BatchHarness):
    setUp = PointHarness.setUp

    def init_task(self, payload):
        gate = payload['acceptance_gate']
        gate['acceptance_items'][0]['paths'] = ['candidate-source.py']
        independent = deepcopy(gate['acceptance_items'][0])
        independent.update(acceptance_id='SECOND-POINT', paths=['docs/contract.md'])
        gate['acceptance_items'].append(independent)
        if getattr(self, 'extra_unit', False):
            self.cases.append({'id': 'CASE-03', 'input': 'Question 3', 'state': {'mode': 'ready'}})
            self.write_json('candidate-config.json', {'cases': self.cases})
            self.git('add', 'candidate-config.json')
            self.git('commit', '-m', 'Freeze third independent unit')
        return legacy.ControlPlaneContractTest.init_task(self, payload)

    def prepare_batches(self, *, extra_unit=False):
        self.extra_unit = extra_unit
        self.begin()
        contract = self.read_json(self.contract_ref)
        contract['required_units'][-1]['acceptance_id'] = 'SECOND-POINT'
        self.contract_ref = self.write_json('.artifacts/multi-point-contract.json', contract)
        attempt = self.attempt()
        units, evidence = [], []
        for index in range(len(self.cases)):
            batch = self.make_batch(attempt, index)
            unit = deepcopy(batch['units'][0])
            unit['acceptance_id'] = contract['required_units'][index]['acceptance_id']
            prefix = f'.artifacts/isolated-unit-{index}'
            raw = self.write_json(prefix + '-raw.json', self.read_json(unit['raw']))
            unit['raw'] = {**raw, 'pointer': unit['raw']['pointer']}
            unit['input'] = {**raw, 'pointers': unit['input']['pointers']}
            normalized = self.read_json(unit['score'])
            original_score = normalized['records'][0]['source_score']
            source_score = self.write_json(prefix + '-source-score.json', self.read_json(original_score))
            normalized['records'][0]['source_score'] = {**source_score, 'pointer': original_score['pointer']}
            normalized['records'][0]['raw_sha256'] = raw['sha256']
            normalized_ref = self.write_json(prefix + '-score.json', normalized)
            unit['score'] = {**normalized_ref, 'pointer': '/records/0'}
            units.append(unit)
            evidence.extend([raw['path'], source_score['path'], normalized_ref['path']])
        terminal = legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'environment_failure', 'real_call_count': len(units), 'duration_seconds': 1,
            'failed_stage': 'evidence_capture', 'mode': 'full',
            'scope_acceptance_ids': [self.batch_acceptance_id, 'SECOND-POINT'],
            'evidence_refs': evidence, 'evidence_by_acceptance_id': {},
            'usage_evidence': workflow.usage('accept-001', 'acceptance')})
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=terminal)
        batch = {'batch_id': 'independent-points', 'source_attempt_id': attempt['attempt_id'],
            'written_by': 'accept-001', 'written_role': 'tester', 'contract': deepcopy(self.contract_ref), 'units': units}
        return attempt, batch

    def complete_batches(self):
        source, batch = self.prepare_batches()
        self.accepted('record-acceptance-evidence-batch', batch)
        self.accepted('record-acceptance-coverage', self.coverage([batch]))
        self.assertTrue(self.accepted('acceptance-status')['complete'])
        return source, batch


class IndependentBatchPointsTest(MultiPointBatchHarness, unittest.TestCase):
    def test_only_changed_point_invalidates_and_new_point_can_complete_with_old_independent_units(self):
        source, _ = self.complete_batches()
        original = deepcopy(self.state()['acceptance_gate']['attempts'][0])
        changed = self.repo / 'candidate-source.py'
        changed.write_text(changed.read_text() + '\n# Only the first point dependency changes.\n')
        status = self.accepted('acceptance-status')
        self.assertNotEqual('pass', status['points'][self.batch_acceptance_id]['status'])
        self.assertEqual('pass', status['points']['SECOND-POINT']['status'])
        self.assertEqual([self.batch_acceptance_id], status['rerun_acceptance_ids'])
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')
        integrated = self.work_result('integration')
        integrated['changed_files'] = ['candidate-source.py']
        self.run_ctl('record-subtask-result', subtask_id=integration['subtask_id'], result=integrated)
        self.run_ctl('freeze-candidate')
        response = self.accepted('create-subtask-attempt', {'scope_acceptance_ids': [self.batch_acceptance_id]},
            subtask_id='EXPENSIVE-001', attempt_kind='ordinary')
        current = response['attempt']
        self.bind(current['subtask_id'], agent='accept-001', role='tester')
        raw = self.write_json('.artifacts/new-first-point.json', {'acceptance_id': self.batch_acceptance_id,
            'status': 'pass', 'input': 'current first-point input', 'actual': True, 'expected': True})
        result = legacy.result('completed', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'partial_pass', 'real_call_count': 1, 'duration_seconds': 1, 'failed_stage': 'none',
            'mode': 'scoped', 'scope_acceptance_ids': [self.batch_acceptance_id],
            'point_results': [{'acceptance_id': self.batch_acceptance_id, 'status': 'pass', 'evidence_refs': [raw['path']]}],
            'evidence_refs': [raw['path']], 'evidence_by_acceptance_id': {self.batch_acceptance_id: [raw['path']]},
            'usage_evidence': workflow.usage('accept-001', 'new-first-point')})
        self.run_ctl('record-subtask-result', subtask_id=current['subtask_id'], result=result)
        status = self.accepted('acceptance-status')
        self.assertTrue(status['complete'])
        self.assertEqual('pass', status['points']['SECOND-POINT']['status'])
        self.assertEqual(original, self.state()['acceptance_gate']['attempts'][0])
        self.assertEqual(3, sum(a['real_call_count'] for a in self.state()['acceptance_gate']['attempts']))
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.assertEqual('completed', self.run_ctl('finalize-task')['status'])

    def test_complete_second_point_units_contribute_before_whole_kind_receipt(self):
        source, batch = self.prepare_batches(extra_unit=True)
        partial = deepcopy(batch)
        partial['units'] = [batch['units'][0], batch['units'][2]]
        self.accepted('record-acceptance-evidence-batch', partial)
        status = self.accepted('acceptance-status')
        self.assertEqual('pass', status['points']['SECOND-POINT']['status'])
        self.assertNotEqual('pass', status['points'][self.batch_acceptance_id]['status'],
                            'One of two required units cannot complete the first point.')
        self.assertFalse(status['complete'])
        self.assertFalse(self.state()['acceptance_gate'].get('coverage_receipts'))
        missing = deepcopy(batch)
        missing.update(batch_id='missing-first-point-unit', units=[batch['units'][1]])
        self.accepted('record-acceptance-evidence-batch', missing)
        self.assertTrue(self.accepted('acceptance-status')['complete'])
        self.assertEqual(3, sum(a['real_call_count'] for a in self.state()['acceptance_gate']['attempts']))

    def test_bad_adopted_raw_input_and_score_invalidate_only_their_point(self):
        _, batch = self.complete_batches()
        unit = batch['units'][0]
        for key in ('raw', 'input', 'score'):
            with self.subTest(reference=key):
                path = self.repo / unit[key]['path']
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b'\nchanged retained evidence')
                    status = self.accepted('acceptance-status')
                    self.assertNotEqual('pass', status['points'][self.batch_acceptance_id]['status'])
                    self.assertEqual('pass', status['points']['SECOND-POINT']['status'])
                    self.assertFalse(status['complete'])
                    self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator', ok=False)
                finally:
                    path.write_bytes(original)
        self.assertTrue(self.accepted('acceptance-status')['complete'])


class UnadoptedBatchEvidenceTest(BatchHarness, unittest.TestCase):
    setUp = PointHarness.setUp

    def test_superseded_batch_review_corruption_warns_without_blocking_current_point(self):
        _, old = self.historical()
        self.accepted('record-acceptance-evidence-batch', old)
        review_path = old['applicability_review']['path']
        proof_path = self.read_json(old['applicability_review'])['evidence_refs'][0]['path']
        current = self.attempt()
        raw = self.write_json('.artifacts/replacement-point.json', {
            'acceptance_id': self.batch_acceptance_id, 'status': 'pass',
            'input': self.cases, 'actual': True, 'expected': True})
        result = legacy.result('completed', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'pass', 'real_call_count': 1, 'duration_seconds': 1, 'failed_stage': 'none',
            'mode': 'full', 'scope_acceptance_ids': [self.batch_acceptance_id],
            'point_results': [{'acceptance_id': self.batch_acceptance_id, 'status': 'pass',
                               'evidence_refs': [raw['path']]}],
            'evidence_refs': [raw['path']], 'evidence_by_acceptance_id': {self.batch_acceptance_id: [raw['path']]},
            'usage_evidence': workflow.usage('accept-001', 'replacement')})
        self.run_ctl('record-subtask-result', subtask_id=current['subtask_id'], result=result)
        self.assertTrue(self.accepted('acceptance-status')['complete'])
        original = deepcopy(self.state()['acceptance_gate']['attempts'])
        # The original batch is no longer consumed. Keep the broken historical
        # files in place; do not repair them by inventing hashes or replaying work.
        (self.repo / proof_path).write_text('Damaged superseded historical proof.')
        status = self.accepted('acceptance-status')
        self.assertTrue(status['complete'], status)
        self.accepted('validate')
        self.assertIn(proof_path, str(status.get('evidence_warnings', [])))
        (self.repo / review_path).write_text('Damaged superseded applicability review.')
        status = self.accepted('acceptance-status')
        self.assertTrue(status['complete'], status)
        self.assertIn(review_path, str(status.get('evidence_warnings', [])))
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.assertEqual('completed', self.run_ctl('finalize-task')['status'])
        self.assertEqual(original, self.state()['acceptance_gate']['attempts'])
        self.assertEqual(3, sum(a['real_call_count'] for a in original))

    def test_unadopted_debug_damage_warns_but_does_not_block_documentation_or_finalize(self):
        _, old = self.historical()
        old.pop('applicability_review')
        self.accepted('record-acceptance-evidence-batch', old)
        second = self.attempt()
        new = self.make_batch(second, 1)
        new.pop('applicability_review')
        self.accepted('record-acceptance-evidence-batch', new)
        result = self.partial_result(new)
        debug = '.artifacts/unadopted-debug.json'
        self.write_json(debug, {'diagnostic': 'No adopted unit refers to this file.'})
        result['expensive_acceptance']['evidence_refs'].append(debug)
        self.accepted('record-subtask-result', result, subtask_id=second['subtask_id'])
        self.accepted('record-acceptance-coverage', self.coverage([old, new]))
        self.assertTrue(self.accepted('acceptance-status')['complete'])
        original_attempts = deepcopy(self.state()['acceptance_gate']['attempts'])
        (self.repo / debug).write_text('Damaged unadopted diagnostic evidence.')
        status = self.accepted('acceptance-status')
        self.assertTrue(status['complete'])
        self.assertIn(debug, str(status.get('evidence_warnings', [])), 'Historical corruption must remain visible.')
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.assertEqual('completed', self.run_ctl('finalize-task')['status'])
        self.assertEqual(original_attempts, self.state()['acceptance_gate']['attempts'])
        self.assertEqual(3, sum(a['real_call_count'] for a in original_attempts))


if __name__ == '__main__':
    unittest.main()
