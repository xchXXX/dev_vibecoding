"""Independent reviewer regressions for revision 3's completion boundary."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import importlib.util

import test_gto_workflow as workflow
import test_control_plane as legacy


class UsagePlatformTest(unittest.TestCase):
    def test_ui_platform_positive_and_negative_receipts(self):
        spec = importlib.util.spec_from_file_location('usage_platform_controller', legacy.CONTROLLER)
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        # Environment labels are declarations, not proof that a GUI tool was used.
        for tool, environment, accepted in [('Browser', 'wsl', True), ('Computer Use', 'windows_native', True),
                ('Computer Use', 'wsl', True), ('Computer Use', 'linux', True),
                ('Computer Use', 'remote-desktop', True), ('Computer Use', '', False),
                ('CLI', 'wsl', False), ('API', 'linux', False)]:
            with self.subTest(tool=tool, environment=environment):
                evidence = workflow.usage('review-001', 'review')
                evidence[0].update(tool=tool, environment=environment, entry='http://localhost/form',
                    ui_applicability='required', ui_not_applicable_reason='')
                errors = controller._usage_errors(evidence, 'review-001')
                self.assertEqual(accepted, not errors, errors)


class ReviewRegressionTest(unittest.TestCase):
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
    accept = workflow.WorkflowTest.accept

    def setUp(self):
        base = legacy.REPO_ROOT / '.tmp/gto-workflow/review'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.input_temp = tempfile.TemporaryDirectory(dir=base)
        self.repo, self.input_dir = Path(self.temp.name), Path(self.input_temp.name)
        self._json_input_index = 0

    def tearDown(self):
        self.input_temp.cleanup()
        self.temp.cleanup()

    def test_integration_waits_for_every_declared_work_subtask(self):
        """R3-001: an unconnected implementation must not disappear at integration."""
        payload = workflow.workflow_contract()
        unfinished = deepcopy(payload['subtasks'][0])
        unfinished.update(subtask_id='WORK-002', title='Second required implementation',
                          write_paths=['candidate-secondary.py'])
        payload['acceptance_gate']['candidate_inputs']['code_paths'].append('candidate-secondary.py')
        payload['subtasks'].insert(1, unfinished)
        self.init_git_checkout('candidate-source.py', 'candidate-secondary.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(payload)
        self.run_ctl('prepare-workspace')
        self.bind('WORK-001')
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=self.work_result())
        # All work must be complete before integration may be dispatched.
        relative = '.tmp/blocked-integration.md'
        path = self.repo / relative
        path.write_text('Wait for WORK-002 before integrating.\n')
        import hashlib
        self.run_ctl('bind-dispatch', subtask_id='INTEGRATE-001',
                     agent_key='backend-implementer', platform_agent_id='impl-001',
                     context_mode='isolated', brief_kind='subtask', brief_path=relative,
                     brief_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ok=False)

    def test_discoverer_test_write_scope_is_in_candidate_inventory(self):
        """R3-002: reviewer-owned regression files are candidate inputs too."""
        payload = workflow.workflow_contract()
        payload['subtasks'][2]['write_paths'] = ['tests/regression']
        self.run_ctl('init-task', contract=payload, title='Missing proof scope',
                     owner='main-coordinator', ok=False)


    def test_explicit_candidate_log_symlink_remains_supported(self):
        """R3-004: declared runtime inputs do not use the log-file exemption."""
        payload = workflow.workflow_contract()
        relative = '.artifacts/acceptance.log'
        payload['subtasks'][3]['write_paths'] = [relative]
        payload['acceptance_gate']['candidate_inputs']['runtime_input_paths'] = [relative]
        target = self.repo / '.artifacts/real-input.txt'
        target.parent.mkdir(parents=True)
        target.write_text('Frozen runtime input\n')
        (self.repo / relative).symlink_to('real-input.txt')
        self.init_task(payload)


    def test_coordinator_block_preserves_inflight_acceptance_failure_receipt(self):
        """R3-005: a running acceptance can preserve failure evidence while blocked."""
        workflow.WorkflowTest.start(self)
        self.integrate()
        self.review()
        self.run_ctl('freeze-candidate')
        ident = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(ident, agent='accept-001', role='tester')
        blocked = workflow.WorkflowTest.published_result(self, 'coordinator_blocked')
        self.run_ctl('set-phase', phase='blocked', result=blocked)
        finding = workflow.WorkflowTest.new_finding(self, 'F-INFLIGHT-ACCEPT', 'accept-001')
        finding['review_owner'] = legacy.REVIEWER
        self.run_ctl('record-acceptance-findings', subtask_id=ident,
                     result={'written_by': 'accept-001', 'findings': [finding]})
        self.run_ctl('record-subtask-result', subtask_id=ident,
                     result=legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance={
                         'outcome': 'product_failure', 'real_call_count': 1, 'duration_seconds': 1,
                         'failed_stage': 'boundary', 'evidence_refs': ['.artifacts/failure.log'],
                         'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'],
                         'usage_evidence': workflow.usage('accept-001', 'acceptance'),
                         'evidence_by_acceptance_id': {}, 'finding_id': 'F-INFLIGHT-ACCEPT'}))
        state = self.state()
        self.assertEqual('product_failure', state['acceptance_gate']['attempts'][-1]['outcome'])
        self.assertEqual('blocked', state['status'])
        self.assertEqual('human_adjudication', state['next_action']['kind'])
        self.assertEqual(blocked, state['coordinator_blocker']['result'])
        self.run_ctl('dispatch-finding-fix', finding_id='F-INFLIGHT-ACCEPT', ok=False)
        self.run_ctl('validate')

    def test_coordinator_block_preserves_dispatched_fix_receipt(self):
        """R3-005: receipt of an already dispatched repair does not resume scheduling."""
        workflow.WorkflowTest.start(self)
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        finding = workflow.WorkflowTest.new_finding(self, 'F-INFLIGHT-FIX')
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001',
                     result=self.review_payload(verdict='fail', findings=[finding]))
        self.run_ctl('dispatch-finding-fix', finding_id='F-INFLIGHT-FIX')
        source = self.repo / 'candidate-source.py'
        source.write_text(source.read_text() + 'fix F-INFLIGHT-FIX\n')
        blocked = workflow.WorkflowTest.published_result(self, 'coordinator_blocked')
        self.run_ctl('set-phase', phase='blocked', result=blocked)
        import hashlib
        self.run_ctl('record-finding-fix', finding_id='F-INFLIGHT-FIX', result={
            'summary': 'Fix root cause F-INFLIGHT-FIX', 'changed_files': ['candidate-source.py'],
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'verification': 'Focused Red/Green and regression.',
            'checks': self.work_result()['checks'],
            'written_by': 'impl-001', 'written_role': 'backend-implementer'})
        state = self.state()
        self.assertEqual('awaiting_re_review', state['findings']['F-INFLIGHT-FIX']['status'])
        self.assertEqual('blocked', state['status'])
        self.assertEqual('human_adjudication', state['next_action']['kind'])
        self.assertEqual(blocked, state['coordinator_blocker']['result'])
        self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001', ok=False)
        self.run_ctl('validate')

if __name__ == '__main__':
    unittest.main()
