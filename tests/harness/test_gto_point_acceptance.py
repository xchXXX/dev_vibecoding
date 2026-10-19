"""Independent public CLI acceptance tests; fixture observations are real subprocesses.

Only test identities and governance receipts are synthetic. No production function
is mocked, no state is hand-edited, and coverage expectations are literal.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import uuid

import test_control_plane as legacy
import test_gto_workflow as workflow


class PointHarness:
    run_ctl = legacy.ControlPlaneContractTest.run_ctl
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state
    git = legacy.ControlPlaneContractTest.git
    init_git_checkout = legacy.ControlPlaneContractTest.init_git_checkout
    bind = workflow.WorkflowTest.bind
    work_result = workflow.WorkflowTest.work_result
    integrate = workflow.WorkflowTest.integrate
    review_payload = workflow.WorkflowTest.review_payload
    review = workflow.WorkflowTest.review
    reintegrate = workflow.WorkflowTest.reintegrate

    def setUp(self):
        root = legacy.REPO_ROOT / '.tmp/scoped-acceptance-testing'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.repo = Path(self.temp.name)
        self.input_dir = self.repo / '.tmp/receipts'
        self.input_dir.mkdir(parents=True)
        self._json_input_index = 0
        self.addCleanup(lambda: PointHarness._cleanup_consumer(self))

    def _cleanup_consumer(self):
        result = getattr(getattr(self, '_outcome', None), 'result', None)
        problems = list(getattr(result, 'failures', [])) + list(getattr(result, 'errors', []))
        failed = any(test is self or getattr(test, 'test_case', None) is self for test, _ in problems)
        if failed:
            test_id = ''.join(c if c.isalnum() or c in '._-' else '_' for c in self.id())
            destination = (legacy.REPO_ROOT / '.artifacts/scoped-acceptance/testing/failures'
                           / f'{test_id}-{uuid.uuid4().hex}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Preserve original bytes, including state and run manifests, before
            # TemporaryDirectory removes this entirely synthetic consumer.
            shutil.copytree(self.repo, destination)
            print(f'Failed synthetic consumer retained at: {destination}', file=sys.stderr)
        self.temp.cleanup()

    def begin(self, count=2, *, failing=False, depends=False):
        self.ids = [f'CHECK-{number:02}' for number in range(1, count + 1)]
        self.paths = ['candidate-source.py', 'candidate-config.json', 'docs/contract.md',
                      *[f'inputs/{ident}.json' for ident in self.ids if int(ident[-2:]) < 9]]
        if count >= 9:
            self.paths.append('inputs/shared.json')
        self.init_git_checkout(*self.paths)
        fixture = legacy.REPO_ROOT / 'tests/fixtures/gto-point-acceptance/check_points.py'
        shutil.copyfile(fixture, self.repo / 'candidate-source.py')
        for ident in self.ids:
            number = int(ident[-2:])
            if number < 9:
                (self.repo / f'inputs/{ident}.json').write_text(json.dumps({ident: True}))
        if count >= 9:
            (self.repo / 'inputs/shared.json').write_text(json.dumps(
                {ident: not (failing and ident == 'CHECK-10') for ident in self.ids if int(ident[-2:]) >= 9}))
        self.git('add', '.')
        self.git('commit', '-m', 'portable check fixture')
        contract = workflow.workflow_contract()
        gate = contract['acceptance_gate']
        gate['candidate_inputs']['code_paths'] += ['inputs']
        gate['acceptance_items'] = [{'acceptance_id': ident, 'evidence_refs': [],
            'paths': ['candidate-source.py', 'inputs/shared.json' if int(ident[-2:]) >= 9 else f'inputs/{ident}.json']}
            for ident in self.ids]
        if depends:
            gate['acceptance_items'][1]['depends_on'] = ['CHECK-01']
        contract['subtasks'][0]['write_paths'].append('inputs')
        contract['subtasks'][1]['write_paths'].append('inputs')
        workflow.add_requirement_checklist(contract, 'WORK-001')
        self.init_task(contract)
        self.run_ctl('prepare-workspace')
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001',
                     result=self.review_payload(covered=self.paths))
        self.run_ctl('freeze-candidate')

    def attempt(self, scope=None, *, bind=True):
        kwargs = {} if scope is None else {'result': {'scope_acceptance_ids': scope}}
        if len(self.state()['acceptance_gate']['attempts']) >= 2:
            kwargs.update(approval_by='user', approval_reason='Synthetic fixture authorizes this additional test round.')
        value = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001', **kwargs)
        attempt = value['attempt']
        if bind:
            self.bind(value['subtask_id'], agent='accept-001', role='tester')
        return attempt

    def observe(self, attempt, scope, *, failed=None, unexecuted=None):
        # A real process executes each requested point exactly once. Registration
        # retries must reuse this receipt rather than call observe again.
        from test_gto_plan_preflight_contract import load_controller
        load_controller()
        from runtime_evidence import run_command, acceptance_binding, digest
        unexecuted = unexecuted or {}
        executed = [ident for ident in scope if ident not in unexecuted]
        output = f'.artifacts/observations/{attempt["attempt_id"]}'
        refs = {ident: [f'{output}/{ident}.json'] for ident in executed}
        run = run_command(self.repo / '.artifacts/runs',
            [sys.executable, 'candidate-source.py', json.dumps(executed), output], cwd=self.repo,
            binding=acceptance_binding(self.state(), attempt['subtask_id']),
            evidence_paths=[ref for values in refs.values() for ref in values])
        points = []
        for ident in scope:
            if ident in unexecuted:
                points.append({'acceptance_id': ident, 'status': unexecuted[ident],
                               'evidence_refs': [], 'reason': 'Selected check was not executed.'})
            else:
                points.append({'acceptance_id': ident,
                    'status': json.loads((self.repo / refs[ident][0]).read_text())['status'],
                    'evidence_refs': refs[ident]})
        has_failure = any(point['status'] == 'fail' for point in points)
        outcome = 'product_failure' if has_failure else ('partial_pass' if unexecuted or len(scope) < len(self.ids) else 'pass')
        evidence = {'outcome': outcome, 'real_call_count': len(executed),
            'duration_seconds': 1, 'failed_stage': 'check' if has_failure else 'none',
            'mode': 'full' if len(scope) == len(self.ids) else 'scoped', 'scope_acceptance_ids': scope,
            'point_results': points, 'evidence_refs': [ref for values in refs.values() for ref in values],
            'evidence_by_acceptance_id': {p['acceptance_id']: p['evidence_refs'] for p in points if p['status'] == 'pass'},
            'usage_evidence': [{'written_by': 'accept-001', 'environment': 'wsl', 'tool': 'CLI',
                'entry': 'python3 candidate-source.py <scope> <output>', 'scope': scope,
                'result': outcome, 'evidence_refs': [ref for values in refs.values() for ref in values],
                'ui_applicability': 'not_applicable', 'ui_not_applicable_reason': 'The fixture is a CLI.'}],
            'run_evidence': {'path': (run / 'manifest.json').relative_to(self.repo).as_posix(),
                             'sha256': digest((run / 'manifest.json').read_bytes())}}
        if has_failure:
            finding = workflow.WorkflowTest.new_finding(self, failed or 'POINT-FAIL', 'accept-001')
            failure_paths = sorted({'inputs/shared.json' if int(p['acceptance_id'][-2:]) >= 9
                else f'inputs/{p["acceptance_id"]}.json' for p in points if p['status'] == 'fail'})
            finding.update(paths=failure_paths,
                           acceptance_ids=[p['acceptance_id'] for p in points if p['status'] == 'fail'])
            finding['regression_proof'].update(command='python3 candidate-source.py <scope> <output>',
                scope=failure_paths, evidence_refs=evidence['evidence_refs'])
            self.run_ctl('record-acceptance-findings', subtask_id=attempt['subtask_id'],
                         result={'written_by': 'accept-001', 'findings': [finding]})
            evidence['finding_id'] = finding['finding_id']
        return legacy.result('blocked' if has_failure else 'completed', 'accept-001', 'tester',
                             expensive_acceptance=evidence)

    def register(self, attempt, receipt, *, ok=True):
        return self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=receipt, ok=ok)

    def coverage(self):
        return self.run_ctl('acceptance-status')

    def count(self):
        path = self.repo / '.artifacts/executions.jsonl'
        return len(path.read_text().splitlines()) if path.exists() else 0


class PointAcceptanceTest(PointHarness, unittest.TestCase):
    def test_three_independent_scopes_keep_non_adjacent_historical_sources(self):
        self.begin(3)
        attempts = []
        for ident in self.ids:
            attempt = self.attempt([ident])
            self.register(attempt, self.observe(attempt, [ident]))
            attempts.append(attempt)
        status = self.coverage()
        self.assertTrue(status['complete'])
        self.assertEqual([a['attempt_id'] for a in attempts],
                         [status['points'][ident]['source_attempt_id'] for ident in self.ids])
        self.assertEqual(3, self.count())

    def test_later_real_failure_blocks_old_pass_even_after_old_input_is_restored(self):
        self.begin()
        first = self.attempt()
        self.register(first, self.observe(first, self.ids))
        original = (self.repo / 'inputs/CHECK-01.json').read_bytes()
        (self.repo / 'inputs/CHECK-01.json').write_text('{"CHECK-01": false}')
        self.reintegrate()
        # Acceptance already started: the existing acceptor checks the changed
        # scope directly; an empty re-review hop would fail before this test's target.
        self.run_ctl('freeze-candidate')
        second = self.attempt(['CHECK-01'])
        self.register(second, self.observe(second, ['CHECK-01']))
        self.assertEqual('fail', self.coverage()['points']['CHECK-01']['status'])
        (self.repo / 'inputs/CHECK-01.json').write_bytes(original)
        self.assertNotEqual('pass', self.coverage()['points']['CHECK-01']['status'],
                            'A newer actual failure must remain a barrier to historical success.')
        self.assertEqual('pass', self.coverage()['points']['CHECK-02']['status'])

    def test_evidence_tamper_invalidates_only_its_point_and_does_not_execute(self):
        self.begin()
        attempt = self.attempt()
        receipt = self.observe(attempt, self.ids)
        self.register(attempt, receipt)
        evidence = self.repo / receipt['expensive_acceptance']['point_results'][0]['evidence_refs'][0]
        for replacement in ('modified observation', None):
            with self.subTest(replacement=replacement):
                original = evidence.read_bytes()
                if replacement is None:
                    evidence.unlink()
                else:
                    evidence.write_text(replacement)
                status = self.coverage()
                self.assertEqual('invalid', status['points']['CHECK-01']['status'])
                self.assertEqual('pass', status['points']['CHECK-02']['status'])
                self.assertEqual(2, self.count())
                evidence.write_bytes(original)

    def test_related_input_delete_and_change_invalidate_only_dependency_closure(self):
        self.begin(3, depends=True)
        attempt = self.attempt()
        self.register(attempt, self.observe(attempt, self.ids))
        changed = self.repo / 'inputs/CHECK-01.json'
        original = changed.read_bytes()
        for value in (None, '{"CHECK-01": true, "new_input": 1}'):
            with self.subTest(value=value):
                if value is None:
                    changed.unlink()
                else:
                    changed.write_text(value)
                status = self.coverage()
                self.assertEqual(['CHECK-01', 'CHECK-02'], status['rerun_acceptance_ids'])
                self.assertEqual('pass', status['points']['CHECK-03']['status'])
                changed.write_bytes(original)
        (self.repo / 'unrelated.txt').write_text('unrelated file')
        (self.repo / 'docs/contract.md').write_text('Wording change outside point dependencies.')
        self.assertTrue(self.coverage()['complete'])
        self.assertEqual(3, self.count())

    def test_changed_common_judgment_invalidates_all_consumers(self):
        self.begin()
        attempt = self.attempt()
        self.register(attempt, self.observe(attempt, self.ids))
        source = self.repo / 'candidate-source.py'
        source.write_text(source.read_text().replace('value is True', 'value is False'))
        self.assertEqual(self.ids, self.coverage()['rerun_acceptance_ids'])
        self.assertEqual(2, self.count())

    def test_bad_registration_is_corrected_from_same_execution(self):
        self.begin()
        attempt = self.attempt()
        receipt = self.observe(attempt, self.ids)
        invalid = deepcopy(receipt)
        invalid['expensive_acceptance']['point_results'][0]['acceptance_id'] = 'UNKNOWN'
        before = self.state()
        self.register(attempt, invalid, ok=False)
        self.assertEqual(before, self.state())
        self.register(attempt, receipt)
        self.assertTrue(self.coverage()['complete'])
        self.assertEqual(2, self.count())

    def test_omitted_point_is_unexecuted_and_blocked_point_does_not_swallow_pass(self):
        self.begin(3)
        attempt = self.attempt()
        receipt = self.observe(attempt, self.ids, unexecuted={'CHECK-02': 'blocked', 'CHECK-03': 'not_run'})
        receipt['expensive_acceptance']['point_results'].pop()
        self.register(attempt, receipt)
        status = self.coverage()
        self.assertEqual(['pass', 'blocked', 'not_run'], [status['points'][i]['status'] for i in self.ids])
        self.assertEqual(1, self.count())

    def test_partial_first_result_is_registered_without_batch_review(self):
        self.begin()
        attempt = self.attempt()
        receipt = self.observe(attempt, self.ids, unexecuted={'CHECK-02': 'not_run'})
        self.register(attempt, receipt)
        status = self.coverage()
        self.assertEqual('pass', status['points']['CHECK-01']['status'])
        self.assertEqual('not_run', status['points']['CHECK-02']['status'])
        self.assertFalse(status['complete'])
        self.assertEqual(['CHECK-02'], status['rerun_acceptance_ids'])
        self.assertEqual(1, self.count())

    def test_missing_status_is_read_only_and_runs_nothing(self):
        self.begin()
        before = self.state()
        status = self.coverage()
        self.assertEqual({'missing'}, {p['status'] for p in status['points'].values()})
        self.assertEqual(self.ids, status['rerun_acceptance_ids'])
        self.assertEqual(before, self.state())
        self.assertEqual(0, self.count())

    def test_disjoint_pending_scopes_can_be_arranged_independently(self):
        self.begin()
        first = self.attempt(['CHECK-01'], bind=False)
        second = self.attempt(['CHECK-02'], bind=False)
        self.assertNotEqual(first['attempt_id'], second['attempt_id'])
        self.assertEqual(['CHECK-01'], first['scope_acceptance_ids'])
        self.assertEqual(['CHECK-02'], second['scope_acceptance_ids'])
        self.assertEqual(0, self.count())

    def test_unbound_attempt_withdrawal_preserves_history_and_cost(self):
        self.begin()
        first = self.attempt(['CHECK-01'], bind=False)
        self.run_ctl('withdraw-subtask-attempt', subtask_id=first['subtask_id'], result={
            'written_by': 'coordinator-001', 'written_role': 'coordinator', 'reason': 'Wrong arrangement; never dispatched.'})
        second = self.attempt(['CHECK-01'])
        self.assertNotEqual(first['attempt_id'], second['attempt_id'])
        self.assertEqual(2, len(self.state()['acceptance_gate']['attempts']))
        self.assertEqual(0, self.count())
        self.run_ctl('withdraw-subtask-attempt', subtask_id=second['subtask_id'], result={
            'written_by': 'coordinator-001', 'written_role': 'coordinator', 'reason': 'Already bound.'}, ok=False)

    def test_ten_then_two_preserves_eight_and_finalizes_without_third_run(self):
        self.begin(10, failing=True)
        first = self.attempt()
        receipt = self.observe(first, self.ids, failed='POINT-FAIL')
        self.register(first, receipt)
        old = deepcopy(self.state()['acceptance_gate']['attempts'][0])
        status = self.coverage()
        self.assertEqual(9, sum(p['status'] == 'pass' for p in status['points'].values()))
        self.assertEqual('fail', status['points']['CHECK-10']['status'])
        self.assertEqual(10, self.count())
        self.run_ctl('dispatch-finding-fix', finding_id='POINT-FAIL')
        changed = self.repo / 'inputs/shared.json'
        changed.write_text(json.dumps({'CHECK-09': True, 'CHECK-10': True}))
        self.run_ctl('record-finding-fix', finding_id='POINT-FAIL', result={
            'summary': 'Correct the shared input.', 'changed_files': ['inputs/shared.json'],
            'sha256': hashlib.sha256(changed.read_bytes()).hexdigest(),
            'verification': 'Deterministic shared input correction.', 'checks': self.work_result()['checks'],
            'written_by': 'impl-001', 'written_role': 'backend-implementer'})
        self.reintegrate()
        self.run_ctl('freeze-candidate')
        before = self.coverage()
        self.assertEqual(['CHECK-09', 'CHECK-10'], before['rerun_acceptance_ids'])
        second = self.attempt()
        self.assertEqual(['CHECK-09', 'CHECK-10'], second['scope_acceptance_ids'])
        result = self.observe(second, ['CHECK-09', 'CHECK-10'])
        result['expensive_acceptance']['closed_finding_ids'] = ['POINT-FAIL']
        self.register(second, result)
        status = self.coverage()
        self.assertTrue(status['complete'])
        for ident in self.ids[:8]:
            self.assertEqual(first['attempt_id'], status['points'][ident]['source_attempt_id'])
        self.assertEqual(old, self.state()['acceptance_gate']['attempts'][0])
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.assertEqual('completed', self.run_ctl('finalize-task')['status'])
        self.assertEqual(12, self.count())
        self.assertEqual(12, sum(a['real_call_count'] for a in self.state()['acceptance_gate']['attempts']))
        self.assertEqual(1, len([t for t in self.state()['subtasks'] if t['stage'] == 'pre_acceptance_review']))


if __name__ == '__main__':
    unittest.main()
