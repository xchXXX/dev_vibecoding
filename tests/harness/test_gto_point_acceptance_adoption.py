"""Independent contracts for existing observations, batches and semantic scope."""
from copy import deepcopy
import hashlib
import json
import sys
import unittest

import test_control_plane as legacy
import test_gto_workflow as workflow
from test_gto_acceptance_batches import BatchHarness
from test_gto_point_acceptance import PointHarness


class PointBatchAdoptionTest(BatchHarness, unittest.TestCase):
    setUp = PointHarness.setUp

    def test_unchanged_batch_does_not_require_an_additional_applicability_reviewer(self):
        attempt, batch = self.historical()
        batch.pop('applicability_review')
        before = deepcopy(self.state()['acceptance_gate']['attempts'])
        self.accepted('record-acceptance-evidence-batch', batch)
        self.assertEqual(before, self.state()['acceptance_gate']['attempts'])
        self.assertEqual(1, len(self.state()['acceptance_gate']['evidence_batches']))

    def test_passed_unit_survives_its_source_attempts_mixed_product_failure(self):
        self.begin()
        attempt = self.attempt()
        batch = self.make_batch(attempt, 0)
        # CASE-01 really has its archived PASS; CASE-02 has an independent FAIL.
        normalized_ref = batch['units'][0]['score']
        normalized = self.read_json(normalized_ref)
        source_ref = normalized['records'][0]['source_score']
        scores = self.read_json(source_ref)
        scores['results'][1]['result'] = 'FAIL'
        self.write_json(source_ref['path'], scores)
        normalized['records'][0]['source_score'] = self.ref(source_ref['path'], '/results/0')
        self.write_json(normalized_ref['path'], normalized)
        batch['units'][0]['score'] = self.ref(normalized_ref['path'], '/records/0')
        self.review_batch(batch, attempt)
        finding = workflow.WorkflowTest.new_finding(self, 'UNIT-FAIL', 'accept-001')
        self.run_ctl('record-acceptance-findings', subtask_id=attempt['subtask_id'],
                     result={'written_by': 'accept-001', 'findings': [finding]})
        raw = batch['units'][0]['raw']['path']
        result = legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'product_failure', 'real_call_count': 2, 'duration_seconds': 1,
            'failed_stage': 'check', 'finding_id': 'UNIT-FAIL', 'mode': 'full',
            'scope_acceptance_ids': [self.batch_acceptance_id], 'evidence_by_acceptance_id': {},
            'evidence_refs': [raw, source_ref['path'], normalized_ref['path']],
            'usage_evidence': workflow.usage('accept-001', 'acceptance')})
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=result)
        original = deepcopy(self.state()['acceptance_gate']['attempts'][0])
        self.accepted('record-acceptance-evidence-batch', batch)
        self.assertEqual(original, self.state()['acceptance_gate']['attempts'][0])
        self.assertEqual('product_failure', original['outcome'])
        self.assertEqual(['CASE-01'], [u['unit_id'] for u in self.state()['acceptance_gate']['evidence_batches'][0]['units']])
        self.assertEqual('open', self.state()['findings']['UNIT-FAIL']['status'])
        from test_gto_plan_preflight_contract import load_controller
        controller = load_controller()
        from acceptance_batches import point_coverage
        state = self.state()
        self.assertEqual(1, len(state['acceptance_gate']['attempts']))
        projection = point_coverage(self.repo, state, self.batch_acceptance_id, controller._candidate_records)
        self.assertEqual('not_run', projection['status'], projection)
        self.assertIn('Incomplete required units', projection['reason'])


class PreparationObservationAdoptionTest(PointHarness, unittest.TestCase):
    def test_adopting_older_preparation_cannot_hide_a_later_real_failure(self):
        source, refs, usage, manifest = self.prepare_observation()
        later = self.attempt(['CHECK-01'])
        from runtime_evidence import run_command, acceptance_binding, digest
        raw = '.artifacts/later-failure.json'
        observation = {'acceptance_id': 'CHECK-01', 'status': 'fail',
                       'input': 'environment-dependent operation', 'actual': 'unavailable', 'expected': 'available'}
        script = ('import json; from pathlib import Path; value=' + repr(observation) + '; '
                  'Path(' + repr(raw) + ').write_text(json.dumps(value)); '
                  'counter=Path(".artifacts/executions.jsonl"); '
                  'counter.write_text(counter.read_text()+json.dumps(value)+"\\n")')
        run = run_command(self.repo / '.artifacts/runs', [sys.executable, '-c', script], cwd=self.repo,
            binding=acceptance_binding(self.state(), later['subtask_id']), evidence_paths=[raw])
        later_usage = deepcopy(usage)
        later_usage[0].update(entry='python3 -c <environment observation>', scope=['CHECK-01'],
                              result='Actual environment-dependent check failed.', evidence_refs=[raw])
        receipt = legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'environment_failure', 'real_call_count': 1, 'duration_seconds': 1,
            'failed_stage': 'environment', 'mode': 'scoped', 'scope_acceptance_ids': ['CHECK-01'],
            'point_results': [{'acceptance_id': 'CHECK-01', 'status': 'fail', 'evidence_refs': [raw]}],
            'evidence_refs': [raw], 'evidence_by_acceptance_id': {}, 'usage_evidence': later_usage,
            'run_evidence': {'path': (run / 'manifest.json').relative_to(self.repo).as_posix(),
                             'sha256': digest((run / 'manifest.json').read_bytes())}})
        self.register(later, receipt)
        self.assertEqual('fail', self.coverage()['points']['CHECK-01']['status'])
        original_attempts = deepcopy(self.state()['acceptance_gate']['attempts'])
        target = self.attempt()
        self.register(target, self.adoption(source, refs, usage, manifest))
        status = self.coverage()
        self.assertFalse(status['complete'], 'Later registration of an old observation is not a newer execution.')
        self.assertEqual('fail', status['points']['CHECK-01']['status'])
        self.assertEqual(later['attempt_id'], status['points']['CHECK-01']['source_attempt_id'])
        self.assertEqual('pass', status['points']['CHECK-02']['status'])
        self.assertEqual(original_attempts, self.state()['acceptance_gate']['attempts'][:2])
        self.assertEqual([2, 1, 0], [a['real_call_count'] for a in self.state()['acceptance_gate']['attempts']])
        self.assertEqual(3, self.count())

    def prepare_observation(self, *, readiness_only=False):
        self.begin()
        # Public kind selection uses the same controller but the existing helper
        # does not expose --attempt-kind, so use the batch CLI argument adapter.
        self.call = BatchHarness.call.__get__(self)
        process, response = self.call('create-subtask-attempt', subtask_id='EXPENSIVE-001', attempt_kind='preparation')
        self.assertEqual(0, process.returncode, response)
        attempt = response['attempt']
        self.bind(attempt['subtask_id'], agent='accept-001', role='tester')
        from test_gto_plan_preflight_contract import load_controller
        load_controller()
        from runtime_evidence import run_command, acceptance_binding, digest
        output = f'.artifacts/observations/{attempt["attempt_id"]}'
        refs = [f'{output}/{ident}.json' for ident in self.ids]
        inputs = [f'inputs/{ident}.json' for ident in self.ids]
        command = [sys.executable, 'candidate-source.py', json.dumps(self.ids), output]
        if readiness_only:
            script = ('from pathlib import Path; import json; '
                      'paths=json.loads(' + repr(json.dumps(refs)) + '); '
                      '[(Path(p).parent.mkdir(parents=True,exist_ok=True), '
                      'Path(p).write_text(json.dumps({"ready": True, "deployment": "available"}))) for p in paths]')
            command = [sys.executable, '-c', script]
        run = run_command(self.repo / '.artifacts/preparation-runs', command, cwd=self.repo,
            binding=acceptance_binding(self.state(), attempt['subtask_id']), evidence_paths=refs + inputs)
        manifest = {'path': (run / 'manifest.json').relative_to(self.repo).as_posix(),
                    'sha256': digest((run / 'manifest.json').read_bytes())}
        usage = [{'written_by': 'accept-001', 'environment': 'wsl', 'tool': 'CLI',
                  'entry': 'python3 -c <readiness fixture>' if readiness_only else 'python3 candidate-source.py <scope> <output>',
                  'scope': self.ids,
                  'result': 'Readiness facts only; no business checks executed.' if readiness_only else
                            'Two actual checks passed during preparation.', 'evidence_refs': refs,
                  'ui_applicability': 'not_applicable', 'ui_not_applicable_reason': 'CLI fixture.'}]
        preparation = legacy.result('completed', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'pass', 'real_call_count': 0 if readiness_only else 2, 'duration_seconds': 1, 'failed_stage': 'none',
            'mode': 'full', 'scope_acceptance_ids': [], 'evidence_by_acceptance_id': {},
            'evidence_refs': refs, 'usage_evidence': usage, 'run_evidence': manifest,
            'preparation': {'checks': {key: refs for key in
                ('deployment', 'version', 'environment', 'input_and_session', 'evidence_capture')},
                'business_input_refs': inputs}})
        self.register(attempt, preparation)
        return attempt, refs, usage, manifest

    def adoption(self, source, refs, usage, manifest):
        return legacy.result('completed', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'pass', 'real_call_count': 0, 'duration_seconds': 0, 'failed_stage': 'none',
            'mode': 'full', 'scope_acceptance_ids': self.ids,
            'point_results': [{'acceptance_id': ident, 'status': 'pass', 'evidence_refs': [ref]}
                              for ident, ref in zip(self.ids, refs)],
            'evidence_by_acceptance_id': {ident: [ref] for ident, ref in zip(self.ids, refs)},
            'evidence_refs': refs, 'usage_evidence': usage, 'run_evidence': manifest,
            'source_preparation_attempt_id': source['attempt_id']})

    def test_formal_observations_from_preparation_are_adopted_without_second_execution(self):
        source, refs, usage, manifest = self.prepare_observation()
        self.assertFalse(self.coverage()['complete'], 'Preparation readiness alone is not business acceptance.')
        original = deepcopy(self.state()['acceptance_gate']['attempts'][0])
        target = self.attempt()
        self.register(target, self.adoption(source, refs, usage, manifest))
        status = self.coverage()
        self.assertTrue(status['complete'], status)
        self.assertEqual(2, self.count())
        self.assertEqual(2, sum(a['real_call_count'] for a in self.state()['acceptance_gate']['attempts']))
        self.assertEqual(original, self.state()['acceptance_gate']['attempts'][0])

    def test_preparation_adoption_rejects_wrong_source_or_uncaptured_evidence(self):
        source, refs, usage, manifest = self.prepare_observation()
        target = self.attempt()
        good = self.adoption(source, refs, usage, manifest)
        wrong = deepcopy(good)
        wrong['expensive_acceptance']['source_preparation_attempt_id'] = 'attempt-foreign'
        self.register(target, wrong, ok=False)
        fake = self.repo / '.artifacts/uncaptured.json'
        fake.write_text('{"status":"pass"}')
        wrong = deepcopy(good)
        wrong['expensive_acceptance']['point_results'][0]['evidence_refs'] = ['.artifacts/uncaptured.json']
        self.register(target, wrong, ok=False)
        self.assertEqual(2, self.count())
        self.assertFalse(self.coverage()['complete'])

    def test_readiness_only_output_cannot_be_relabelled_as_formal_point_pass(self):
        source, refs, usage, manifest = self.prepare_observation(readiness_only=True)
        target = self.attempt()
        before = self.state()
        rejection = self.register(target, self.adoption(source, refs, usage, manifest), ok=False)
        self.assertRegex(str(rejection).lower(), 'observation|execut|point|formal|input|output')
        self.assertEqual(before, self.state())
        self.assertFalse(self.coverage()['complete'])
        self.assertEqual(0, self.count())


class PointSemanticImpactTest(PointHarness, unittest.TestCase):
    def impact_case(self):
        self.begin()
        source = self.attempt()
        self.register(source, self.observe(source, self.ids))
        path = self.repo / 'candidate-source.py'
        before = path.read_bytes()
        path.write_bytes(before + b'\n# An explanatory comment; check logic and inputs are unchanged.\n')
        proof = self.repo / '.artifacts/semantic-impact.json'
        proof.write_text(json.dumps({'source_attempt_id': source['attempt_id'],
            'before_sha256': hashlib.sha256(before).hexdigest(),
            'after_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'changed_paths': ['candidate-source.py'], 'judgment': 'Only a comment was appended.'}))
        return source, {'written_by': 'accept-001', 'written_role': 'tester',
            'source_attempt_id': source['attempt_id'], 'point_ids': self.ids,
            'changed_paths': ['candidate-source.py'], 'reason': 'Only a comment changed; executed conditions are identical.',
            'evidence_refs': ['.artifacts/semantic-impact.json']}

    def test_original_acceptor_can_preserve_semantically_unaffected_points(self):
        source, receipt = self.impact_case()
        before = deepcopy(self.state()['acceptance_gate']['attempts'])
        self.run_ctl('record-acceptance-impact', result=receipt)
        status = self.coverage()
        self.assertTrue(status['complete'])
        self.assertEqual({source['attempt_id']}, {p['source_attempt_id'] for p in status['points'].values()})
        self.assertEqual(before, self.state()['acceptance_gate']['attempts'])
        self.assertEqual(2, self.count())

    def test_semantic_impact_rejects_foreign_author_and_hidden_delta(self):
        _, receipt = self.impact_case()
        for update in ({'written_by': 'review-001', 'written_role': 'reviewer'}, {'changed_paths': []}):
            with self.subTest(update=update):
                before = self.state()
                rejection = self.run_ctl('record-acceptance-impact', result={**receipt, **update}, ok=False)
                self.assertNotIn('invalid choice', str(rejection), 'Absent action is not negative gate proof.')
                self.assertEqual(before, self.state())
        self.assertFalse(self.coverage()['complete'])
        self.assertEqual(2, self.count())


if __name__ == '__main__':
    unittest.main()
