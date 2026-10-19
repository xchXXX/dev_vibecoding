"""Approved agent allocation and read-only result preflight behavior."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from test_gto_plan_preflight_contract import load_controller
from test_gto_initial_test_routing import initial_contract
import test_control_plane as base
import test_gto_workflow as workflow
from test_gto_workflow import workflow_contract, usage
import hashlib
import subprocess
import sys


class ExecutionPlanTest(unittest.TestCase):
    def setUp(self):
        self.ctl = load_controller()
        self.state = initial_contract(1)
        keys = ['A', 'C', 'C', 'D', 'A', 'E']
        for task, key in zip(self.state['subtasks'], keys):
            task['planned_agent_key'] = key
        self.state['approval']['planned_subtask_ids'] = [t['subtask_id'] for t in self.state['subtasks']]

    def test_execution_plan_is_part_of_approval(self):
        before = self.ctl._contract_hash(self.state)
        for field, value in [('planned_agent_key', 'Z'), ('dependencies', ['REVIEW-001']), ('write_paths', ['other'])]:
            candidate = deepcopy(self.state)
            candidate['subtasks'][0][field] = value
            self.assertNotEqual(before, self.ctl._contract_hash(candidate), field)
        candidate = deepcopy(self.state)
        candidate['subtasks'][0]['status'] = 'in_progress'
        self.assertEqual(before, self.ctl._contract_hash(candidate))

    def test_planned_test_to_acceptance_reuse_and_wrong_identity(self):
        first, *_, acceptor, doc = self.state['subtasks']
        first['dispatch'] = {'agent_key': 'A', 'platform_agent_id': 'real-A'}
        validator = getattr(self.ctl, '_planned_dispatch_errors', None)
        self.assertIsNotNone(validator, 'missing planned allocation gate')
        self.assertEqual([], validator(self.state, acceptor, 'A', 'real-A'))
        self.assertTrue(validator(self.state, acceptor, 'A', 'real-B'))
        self.assertTrue(validator(self.state, acceptor, 'B', 'real-A'))
        self.assertTrue(validator(self.state, doc, 'E', 'real-A'))

    def test_readable_table_shows_agent_not_only_role(self):
        rendered = self.ctl._render_artifacts('example', 'Example', self.state)
        self.assertIn('A（测试）', rendered['execution.md'])
        self.assertIn('复用', rendered['execution.md'])
        self.assertIn('A（验收）', rendered['plan.md'])
        self.assertIn('N0 --> N1', rendered['plan.md'])
        self.assertIn('分支全部完成后才能汇合', rendered['plan.md'])

    def test_task_graph_escapes_mermaid_labels(self):
        self.state['subtasks'][0]['title'] = '检查 "空值" #1\n<后续>'
        plan = self.ctl._render_artifacts('example', 'Example', self.state)['plan.md']
        diagram = plan.split('```mermaid', 1)[1].split('```', 1)[0]
        self.assertIn('检查 #quot;空值#quot; #35;1 #60;后续#62;', diagram)
        self.assertEqual(1, diagram.count('N0['))

    def test_result_shape_errors_are_aggregated(self):
        validator = getattr(self.ctl, '_result_input_errors', None)
        self.assertIsNotNone(validator, 'missing shared result preflight')
        errors = validator('record-subtask-result', {'status': 'bogus', 'summary': 42})
        self.assertGreater(len(errors), 2)
        self.assertTrue(any('status' in e for e in errors))
        self.assertTrue(any('summary' in e for e in errors))

    def test_derived_task_inherits_allocation_without_changing_approval(self):
        original = self.state['subtasks'][2]
        original['status'] = 'completed'
        before = self.ctl._contract_hash(self.state)
        created = deepcopy(original)
        self.ctl._inherit_plan(created, original)
        created.update(subtask_id='integration-again', dependencies=[original['subtask_id']])
        self.state['subtasks'].append(created)
        self.assertEqual(before, self.ctl._contract_hash(self.state))
        self.assertEqual([], self.ctl._execution_plan_errors(self.state))
        created['planned_agent_key'] = 'Z'
        self.assertTrue(self.ctl._execution_plan_errors(self.state))

    def test_derived_task_cannot_expand_work_or_change_assignment_and_dependencies(self):
        source = self.state['subtasks'][1]
        extra = deepcopy(source)
        self.ctl._inherit_plan(extra, source)
        extra['subtask_id'] = 'UNAPPROVED-WORK'
        self.state['subtasks'].append(extra)
        self.assertTrue(self.ctl._execution_plan_errors(self.state))
        self.state['subtasks'].pop()
        source = self.state['subtasks'][2]
        source['status'] = 'completed'
        extra = deepcopy(source)
        self.ctl._inherit_plan(extra, source)
        extra.update(subtask_id='integration-again', dependencies=[source['subtask_id']])
        self.state['subtasks'].append(extra)
        self.assertEqual([], self.ctl._execution_plan_errors(self.state))
        for field, value in [('dependencies', []), ('assignment', dict(source['assignment'], goal='Unapproved work'))]:
            original = extra[field]
            extra[field] = value
            self.assertTrue(self.ctl._execution_plan_errors(self.state), field)
            extra[field] = original


class ResultPreflightTest(unittest.TestCase):
    setUp = workflow.WorkflowTest.setUp
    tearDown = workflow.WorkflowTest.tearDown
    git = workflow.WorkflowTest.git
    init_git_checkout = workflow.WorkflowTest.init_git_checkout
    state = workflow.WorkflowTest.state
    item = staticmethod(workflow.WorkflowTest.item)
    bind = workflow.WorkflowTest.bind
    work_result = workflow.WorkflowTest.work_result
    published_result = workflow.WorkflowTest.published_result
    integrate = workflow.WorkflowTest.integrate
    review_payload = workflow.WorkflowTest.review_payload
    review = workflow.WorkflowTest.review
    new_finding = workflow.WorkflowTest.new_finding
    reintegrate = workflow.WorkflowTest.reintegrate
    rereview = workflow.WorkflowTest.rereview

    def run_ctl(self, action, *, ok=True, **kwargs):
        if not hasattr(self, 'ctl'):
            self.ctl = load_controller()
        if action in {'record-subtask-result', 'validate-result'} and 'result' in kwargs:
            base.attach_acceptance_run(self.repo, kwargs.get('subtask_id'), kwargs['result'], create_fixture_files=ok)
        argv = ['--action', action, '--repo-root', str(self.repo), '--task-id', base.TASK_ID]
        for name, value in kwargs.items():
            if name in {'contract', 'result'}:
                self._json_input_index += 1
                path = self.repo / '.tmp' / f'input-{self._json_input_index}.json'
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps(value))
                argv += [f'--{name}-json-file', str(path)]
            else:
                argv += ['--' + name.replace('_', '-'), str(value)]
        try:
            result = self.ctl._run(self.ctl._parser().parse_args(argv))
        except self.ctl.ControlError as exc:
            if ok:
                self.fail(str(exc.errors))
            return {'ok': False, 'errors': exc.errors}
        self.assertTrue(ok, result)
        return result

    def start(self):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        contract = workflow_contract()
        for t in contract['subtasks']:
            t['planned_agent_key'] = t['role']
        self.run_ctl('init-task', contract=contract, title='Allocation', owner='main-coordinator')
        self.run_ctl('prepare-workspace')

    def test_new_contract_and_persisted_state_require_all_allocations(self):
        contract = workflow_contract()
        for missing in (range(len(contract['subtasks'])), [0]):
            candidate = deepcopy(contract)
            for index in missing:
                candidate['subtasks'][index].pop('planned_agent_key')
            rejected = self.run_ctl('init-task', contract=candidate, title='Missing allocation', owner='main-coordinator', ok=False)
            self.assertIn('planned_agent_key', str(rejected))
            self.assertFalse((self.repo / 'docs/ai/tasks' / base.TASK_ID / 'state.json').exists())
        self.start()
        state = self.state()
        state['approval'].pop('planned_subtask_ids')
        for task in state['subtasks']:
            task.pop('planned_agent_key')
        state['approval']['contract_sha256'] = self.ctl._contract_hash(state)
        paths = self.ctl._task_paths(self.repo, base.TASK_ID)
        paths['state.json'].write_text(json.dumps(state))
        rejected = self.run_ctl('validate', ok=False)
        self.assertIn('planned_subtask_ids', str(rejected))

    def snapshot(self):
        return {str(p.relative_to(self.repo)): p.read_bytes() for p in (self.repo / 'docs').rglob('*') if p.is_file()}

    def preflight(self, action, **kwargs):
        before = self.snapshot()
        result = self.run_ctl('validate-result', result_action=action, **kwargs)
        self.assertEqual(before, self.snapshot(), 'preflight changed files or lock')
        return result

    def test_preflight_then_record_work_review_and_acceptance_with_planned_reuse(self):
        self.start()
        self.bind('WORK-001')
        self.preflight('record-subtask-result', subtask_id='WORK-001', result=self.work_result())
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=self.work_result())
        self.bind('INTEGRATE-001')
        self.preflight('record-subtask-result', subtask_id='INTEGRATE-001', result=self.work_result('integration'))
        self.run_ctl('record-subtask-result', subtask_id='INTEGRATE-001', result=self.work_result('integration'))
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        review = self.review_payload()
        self.preflight('record-review-result', subtask_id='REVIEW-SEC-001', result=review)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=review)
        self.run_ctl('freeze-candidate')
        attempt = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')
        ident = attempt['subtask_id']
        tester = self.item(self.state(), 'TEST-001')['dispatch']['platform_agent_id']
        self.bind(ident, agent=tester, role='tester')
        result = base.result('completed', tester, 'tester', expensive_acceptance={
            'outcome': 'pass', 'real_call_count': 1, 'duration_seconds': 1, 'failed_stage': 'none',
            'evidence_refs': ['.artifacts/accept.log'],
            'evidence_by_acceptance_id': {'REAL-PATH-001': ['.artifacts/accept.log']},
            'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'],
            'usage_evidence': usage(tester, 'accept'), 'closed_finding_ids': []})
        self.preflight('record-subtask-result', subtask_id=ident, result=result)
        self.run_ctl('record-subtask-result', subtask_id=ident, result=result)
        self.assertEqual('completed', self.item(self.state(), ident)['status'])

    def test_rejected_preflight_aggregates_and_preserves_files(self):
        self.start()
        self.bind('WORK-001')
        result = self.preflight('record-subtask-result', subtask_id='WORK-001',
                                result={'summary': 3, 'status': 'invalid'}, ok=False)
        self.assertGreater(len(result['errors']), 2)

    def test_formal_record_rechecks_changed_result(self):
        self.start()
        self.bind('WORK-001')
        result = self.work_result()
        self.preflight('record-subtask-result', subtask_id='WORK-001', result=result)
        result['written_by'] = 'other-person'
        before = self.snapshot()
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=result, ok=False)
        self.assertEqual(before, self.snapshot())
    def test_frozen_plan_rejects_tampering_without_updating_files(self):
        self.start()
        paths = self.ctl._task_paths(self.repo, base.TASK_ID)
        state = self.state()
        state['subtasks'][0]['planned_agent_key'] = 'wrong'
        paths['state.json'].write_text(json.dumps(state))
        before = self.snapshot()
        result = self.run_ctl('validate', ok=False)
        self.assertIn('approval', str(result))
        self.assertEqual(before, self.snapshot())

    def test_bind_rejects_wrong_allocation_and_unfinished_dependencies(self):
        self.start()
        path = self.repo / '.tmp/bind.md'
        path.write_text('Only this assignment.')
        args = dict(subtask_id='TEST-001', agent_key='other', platform_agent_id='new-id',
                    context_mode='isolated', brief_kind='subtask', brief_path='.tmp/bind.md',
                    brief_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        before = self.snapshot()
        rejected = self.run_ctl('bind-dispatch', **args, ok=False)
        self.assertIn('planned_agent_key', str(rejected))
        self.assertEqual(before, self.snapshot())
        args.update(subtask_id='INTEGRATE-001', agent_key='backend-implementer')
        rejected = self.run_ctl('bind-dispatch', **args, ok=False)
        self.assertTrue(any(word in str(rejected) for word in ('dependencies', 'stage', 'work')))
        self.assertEqual(before, self.snapshot())

    def test_preflight_repair_then_reintegration_and_rereview(self):
        self.start()
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=self.review_payload(
            verdict='fail', findings=[self.new_finding('F-1')]))
        self.run_ctl('dispatch-finding-fix', finding_id='F-1')
        payload = self.published_result('finding_fix')
        payload['sha256'] = hashlib.sha256((self.repo / 'candidate-source.py').read_bytes()).hexdigest()
        self.preflight('record-finding-fix', finding_id='F-1', result=payload)
        self.run_ctl('record-finding-fix', finding_id='F-1', result=payload)
        self.reintegrate()
        self.rereview('REVIEW-SEC-001', ['F-1'])
        self.run_ctl('validate')

    def test_cli_preflight_does_not_create_files(self):
        self.start()
        self.bind('WORK-001')
        payload = self.repo / '.tmp/result.json'
        payload.write_text(json.dumps(self.work_result()))
        before = self.snapshot()
        run = subprocess.run([sys.executable, str(base.CONTROLLER), '--action', 'validate-result',
                              '--result-action', 'record-subtask-result', '--repo-root', str(self.repo),
                              '--task-id', base.TASK_ID, '--subtask-id', 'WORK-001',
                              '--result-json-file', str(payload)], capture_output=True, text=True)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        self.assertTrue(json.loads(run.stdout)['read_only'])
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
