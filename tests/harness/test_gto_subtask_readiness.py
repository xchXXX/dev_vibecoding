"""Independent QA regression for pending dependency readiness; author /root/qa."""
from copy import deepcopy
import hashlib
import json
import unittest

import test_control_plane as base
import test_gto_workflow as workflow
from test_gto_initial_test_routing import initial_contract, check
import test_gto_execution_plan as execution


class SubtaskReadinessTest(unittest.TestCase):
    setUp = workflow.WorkflowTest.setUp
    tearDown = workflow.WorkflowTest.tearDown
    git = workflow.WorkflowTest.git
    init_git_checkout = workflow.WorkflowTest.init_git_checkout
    state = workflow.WorkflowTest.state
    item = staticmethod(workflow.WorkflowTest.item)
    run_ctl = execution.ResultPreflightTest.run_ctl
    published_result = workflow.WorkflowTest.published_result
    snapshot = execution.ResultPreflightTest.snapshot

    def start(self, first_pending=False):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        contract = initial_contract(1)
        for task in contract['subtasks']:
            task['status'] = 'pending'
        if not first_pending:
            contract['subtasks'][0]['status'] = 'ready'
        self.run_ctl('init-task', contract=contract, title='Readiness regression', owner='coordinator')
        self.run_ctl('prepare-workspace')
        self.run_ctl('set-phase', phase='doc_sync')
        self.run_ctl('set-phase', phase='test_sync')
        return self.state()['approval']['contract_sha256']

    def bind(self, ident, agent='qa-independent', key=None, ok=True):
        task = self.item(self.state(), ident)
        relative = '.tmp/readiness-' + ident + '.md'
        path = self.repo / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text('Execute only this approved assignment.\n')
        return self.run_ctl('bind-dispatch', subtask_id=ident,
            agent_key=key or task['planned_agent_key'], platform_agent_id=agent,
            context_mode='isolated', brief_kind='subtask', brief_path=relative,
            brief_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ok=ok)

    def complete_test(self):
        task = self.item(self.state(), 'TEST-001')
        result = base.result('completed', 'qa-independent', task['planned_agent_key'], checks=[check('red')])
        self.run_ctl('record-subtask-result', subtask_id='TEST-001', result=result)
        return deepcopy(self.item(self.state(), 'TEST-001')['result'])

    def assert_preflight_rejected_readonly(self, ident):
        before = self.snapshot()
        try:
            self.run_ctl('preflight', subtask_id=ident, ok=False)
        finally:
            self.assertEqual(before, self.snapshot(), 'preflight must not write task artifacts')

    def test_initial_pending_root_becomes_ready_via_normal_actions(self):
        self.start(first_pending=True)
        self.assertEqual('ready', self.item(self.state(), 'TEST-001')['status'])
        self.bind('TEST-001')

    def test_completed_dependency_promotes_and_binds_pending_successor(self):
        approval = self.start()
        self.bind('TEST-001')
        result = self.complete_test()
        state = self.state()
        self.assertEqual('ready', self.item(state, 'WORK-001')['status'])
        self.assertEqual(approval, state['approval']['contract_sha256'])
        self.assertEqual(result, self.item(state, 'TEST-001')['result'])
        self.assertEqual('pending', self.item(state, 'INTEGRATE-001')['status'])
        self.run_ctl('set-phase', phase='code_impl')
        self.bind('WORK-001', agent='builder-independent')
        self.assertEqual('in_progress', self.item(self.state(), 'WORK-001')['status'])
        self.bind('WORK-001', agent='builder-independent', ok=False)
        self.bind('TEST-001', ok=False)

    def test_blocked_result_waits_until_public_resume_then_promotes(self):
        approval = self.start()
        self.bind('TEST-001')
        self.run_ctl('set-phase', phase='blocked', result=self.published_result('coordinator_blocked'))
        result = self.complete_test()
        blocked = self.state()
        self.assertEqual('pending', self.item(blocked, 'WORK-001')['status'])
        self.bind('WORK-001', agent='builder-independent', ok=False)
        self.run_ctl('set-phase', phase='test_sync', result=self.published_result('coordinator_resumed'))
        state = self.state()
        self.assertEqual('ready', self.item(state, 'WORK-001')['status'])
        self.assertEqual(approval, state['approval']['contract_sha256'])
        self.assertEqual(result, self.item(state, 'TEST-001')['result'])
        self.run_ctl('set-phase', phase='code_impl')
        self.bind('WORK-001', agent='builder-independent')

    def test_unfinished_dependency_preflight_rejects_and_does_not_mutate(self):
        self.start()
        self.assert_preflight_rejected_readonly('WORK-001')
        self.bind('WORK-001', agent='builder-independent', ok=False)

    def test_terminal_preflight_rejects_and_does_not_mutate(self):
        self.start()
        self.bind('TEST-001')
        self.complete_test()
        self.assert_preflight_rejected_readonly('TEST-001')

    def test_expensive_template_and_final_documentation_stay_pending(self):
        self.start()
        self.bind('TEST-001')
        self.complete_test()
        for ident in ('ACCEPT-001', 'DOC-001'):
            self.assertEqual('pending', self.item(self.state(), ident)['status'])
            self.assert_preflight_rejected_readonly(ident)
            self.bind(ident, ok=False)

    def test_promoted_successor_keeps_planned_identity_constraints(self):
        self.start()
        self.bind('TEST-001')
        self.complete_test()
        self.run_ctl('set-phase', phase='code_impl')
        before = self.snapshot()
        self.bind('WORK-001', agent='qa-independent', ok=False)
        self.bind('WORK-001', agent='builder-independent', key='unapproved', ok=False)
        self.assertEqual(before, self.snapshot())
        self.bind('WORK-001', agent='builder-independent')


if __name__ == '__main__':
    unittest.main()
