import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import sys
import shutil

from test_gto_plan_preflight_contract import load_controller
import test_control_plane as base
import test_gto_workflow as workflow

ROOT = Path(__file__).resolve().parents[2]


class CapabilityGateTest(unittest.TestCase):
    def setUp(self):
        self.ctl = load_controller()
        self.folder = tempfile.TemporaryDirectory(dir=ROOT / '.tmp')
        self.addCleanup(self.folder.cleanup)
        self.repo = Path(self.folder.name)
        (self.repo / 'dependency.lock').write_text('v1')
        self.task = {'subtask_id': 'UI-001', 'assignment': {'required_capabilities': [{
            'capability_id': 'browser', 'tool': 'official-browser',
            'probe': 'Open local probe and capture its text',
            'binding_paths': ['dependency.lock'], 'max_age_seconds': 3600}]}}
        self.state = {'subtasks': [self.task], 'capability_receipts': []}
        self.env = patch.dict(os.environ, {'GTO_SESSION_ID': 'actual-test-session'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def api(self, name):
        fn = getattr(self.ctl, name, None)
        self.assertIsNotNone(fn, 'capability gate API is absent: ' + name)
        return fn

    def payload(self, status='passed'):
        path = self.repo / '.artifacts/probe.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {**self.ctl._capture_capability_context(self.repo, self.task['assignment']['required_capabilities'][0]), 'tool': 'official-browser', 'probe': self.task['assignment']['required_capabilities'][0]['probe'],
                'session_id': os.environ['GTO_SESSION_ID'], 'status': status,
                'operation': 'browser snapshot', 'observed': 'probe text visible'}
        path.write_text(json.dumps(data))
        return {'capability_id': 'browser', 'evidence': {'path': '.artifacts/probe.json',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}

    def test_missing_proof_blocks_only_dependent_task(self):
        errors = self.api('_capability_errors')
        self.assertTrue(errors(self.repo, self.state, self.task))
        self.assertEqual([], errors(self.repo, self.state, {'assignment': {}}))

    def test_real_evidence_binding_expires_on_session_dependency_and_tamper(self):
        record = self.api('_capability_receipt')
        errors = self.api('_capability_errors')
        receipt = record(self.repo, self.task, self.payload())
        self.state['capability_receipts'].append(receipt)
        self.assertEqual([], errors(self.repo, self.state, self.task))
        with patch.dict(os.environ, {'GTO_SESSION_ID': 'new-session'}):
            self.assertTrue(errors(self.repo, self.state, self.task))
        (self.repo / 'dependency.lock').write_text('v2')
        self.assertTrue(errors(self.repo, self.state, self.task))
        (self.repo / 'dependency.lock').write_text('v1')
        (self.repo / '.artifacts/probe.json').write_text('{}')
        self.assertTrue(errors(self.repo, self.state, self.task))

    def test_latest_failed_probe_invalidates_previous_success(self):
        record = self.api('_capability_receipt')
        self.state['capability_receipts'].append(record(self.repo, self.task, self.payload()))
        self.state['capability_receipts'].append(record(self.repo, self.task, self.payload('failed')))
        self.assertTrue(self.api('_capability_errors')(self.repo, self.state, self.task))

    def test_old_probe_cannot_be_rebound_or_renewed(self):
        payload = self.payload()
        before = self.api('_capability_receipt')(self.repo, self.task, payload)
        after = self.api('_capability_receipt')(self.repo, self.task, payload)
        self.assertEqual(before['recorded_at'], after['recorded_at'])
        (self.repo / 'dependency.lock').write_text('v2')
        with self.assertRaisesRegex(ValueError, 'capture-time'):
            self.api('_capability_receipt')(self.repo, self.task, payload)

    def test_contract_approval_binds_capability_declarations(self):
        from test_gto_initial_test_routing import initial_contract
        state = initial_contract(1)
        state['approval']['planned_subtask_ids'] = [t['subtask_id'] for t in state['subtasks']]
        before = self.ctl._contract_hash(state)
        state['subtasks'][0]['assignment']['required_capabilities'] = self.task['assignment']['required_capabilities']
        self.assertNotEqual(before, self.ctl._contract_hash(state))


class CapabilityCliTest(unittest.TestCase):
    setUp = workflow.WorkflowTest.setUp
    tearDown = workflow.WorkflowTest.tearDown
    run_ctl = base.ControlPlaneContractTest.run_ctl
    init_task = base.ControlPlaneContractTest.init_task
    state = base.ControlPlaneContractTest.state

    def test_probe_receipt_and_subtask_preflight_are_real_cli_and_read_only(self):
        from test_gto_initial_test_routing import initial_contract
        # Two ready root testers isolate capability checks from dependency gates.
        contract = initial_contract(2)
        dependent = contract['subtasks'][0]
        requirement = {'capability_id': 'browser', 'tool': 'test-browser', 'probe': 'read probe page',
                       'binding_paths': ['dependency.lock'], 'max_age_seconds': 60}
        dependent['assignment']['required_capabilities'] = [requirement]
        (self.repo / 'dependency.lock').write_text('v1')
        self.init_task(contract)
        self.run_ctl('set-phase', phase='doc_sync')
        with patch.dict(os.environ, {'GTO_SESSION_ID': 'cli-test-session'}):
            rejected = self.run_ctl('preflight', subtask_id=dependent['subtask_id'], ok=False)
            self.assertIn('probe evidence missing', str(rejected))
            evidence = self.repo / '.artifacts/capability/probe.json'
            evidence.parent.mkdir(parents=True)
            capture = self.run_ctl('capture-capability-context', subtask_id=dependent['subtask_id'],
                                   platform_agent_id='impl-001')['captures']['browser']
            evidence.write_text(json.dumps({**capture, 'tool': requirement['tool'], 'probe': requirement['probe'],
                'session_id': 'cli-test-session', 'status': 'passed',
                'operation': 'fixture-only operation', 'observed': 'synthetic test data, not live browser proof'}))
            self.run_ctl('record-capability-probe', subtask_id=dependent['subtask_id'], result={
                'capability_id': 'browser', 'evidence': {'path': evidence.relative_to(self.repo).as_posix(),
                'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}})
            before = {str(p): p.read_bytes() for p in (self.repo / 'docs').rglob('*') if p.is_file()}
            self.run_ctl('preflight', subtask_id=dependent['subtask_id'])
            self.assertEqual(before, {str(p): p.read_bytes() for p in (self.repo / 'docs').rglob('*') if p.is_file()})
            with patch.dict(os.environ, {'GTO_SESSION_ID': 'different-session'}):
                self.run_ctl('preflight', subtask_id=dependent['subtask_id'], ok=False)
                independent = contract['subtasks'][1]['subtask_id']
                self.run_ctl('preflight', subtask_id=independent)
            original = json.loads(evidence.read_text())
            fresh = self.run_ctl('capture-capability-context', subtask_id=dependent['subtask_id'],
                                 platform_agent_id='impl-001')['captures']['browser']
            failed = evidence.with_name('failed.json')
            failed.write_text(json.dumps({**original, **fresh, 'status': 'failed', 'observed': 'synthetic later failure'}))
            def register(path, ok=True):
                return self.run_ctl('record-capability-probe', subtask_id=dependent['subtask_id'], ok=ok, result={
                    'capability_id': 'browser', 'evidence': {'path': path.relative_to(self.repo).as_posix(),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}})
            register(failed)
            copied = evidence.with_name('copied-success.json')
            copied.write_bytes(evidence.read_bytes())
            self.assertIn('already registered', str(register(copied, ok=False)))
            copied.write_text(json.dumps({**original, 'observed': 'old success with different description'}))
            self.assertIn('newer', str(register(copied, ok=False)))
            self.run_ctl('preflight', subtask_id=dependent['subtask_id'], ok=False)

    def test_copied_active_state_cannot_advance_from_another_checkout(self):
        self.init_task(workflow.workflow_contract())
        target = self.repo / '.tmp/copied-checkout'
        shutil.copytree(self.repo / 'docs', target / 'docs')
        result = subprocess.run([sys.executable, '-B', str(base.CONTROLLER), '--action', 'set-phase',
            '--repo-root', str(target), '--task-id', base.TASK_ID, '--phase', 'doc_sync', '--json'],
            capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('checkout', result.stdout)


if __name__ == '__main__':
    unittest.main()

