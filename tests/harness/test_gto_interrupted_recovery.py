"""Interrupted identity transfer: real CLI, isolated consumer, immutable refusal."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import subprocess
import unittest

import test_gto_coordinator_blocking as base

spec = importlib.util.spec_from_file_location('interruption_controller', base.CONTROLLER)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class InterruptedRecoveryTest(unittest.TestCase):
    ctl = base.CoordinatorBlockingTest.ctl
    state = base.CoordinatorBlockingTest.state
    events = base.CoordinatorBlockingTest.events
    receipt = base.CoordinatorBlockingTest.receipt
    block = base.CoordinatorBlockingTest.block

    def setUp(self):
        base.CoordinatorBlockingTest.setUp(self)
        for args in (['init', '-q'], ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                                         'commit', '--allow-empty', '-qm', 'fixture']):
            subprocess.run(['git', *args], cwd=self.repo, check=True, capture_output=True)
        self.ctl('prepare-workspace')
        self.ctl('set-phase', phase='doc_sync')
        self.original_phase = 'doc_sync'
        self.bind('old-tester')
        self.blocked_receipt = self.block()
        evidence = self.repo / '.artifacts/gto' / base.TASK_ID / 'resume-identity-audit.json'
        evidence.parent.mkdir(parents=True)
        evidence.write_text('User authorizes audited recovery of interrupted agents without delivery results.\n')
        self.audit = dict(approval=dict(approved_by='user', authorization_source='explicit user message',
            reason='Session interrupted before delivery', evidence=dict(path=evidence.relative_to(self.repo).as_posix(),
            sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())),
            previous_coordinator_id='coordinator-001', new_coordinator_id='new-coordinator',
            subtask_id='TEST-001', previous_platform_agent_id='old-tester', new_platform_agent_id='new-tester')

    def bind(self, identity, ok=True):
        brief = self.repo / '.tmp/test-brief.md'
        brief.write_text('Independent initial tests.\n')
        return self.ctl('bind-dispatch', subtask_id='TEST-001', agent_key='tester', platform_agent_id=identity,
            context_mode='isolated', brief_kind='subtask', brief_path='.tmp/test-brief.md',
            brief_sha256=hashlib.sha256(brief.read_bytes()).hexdigest(), ok=ok)

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for directory in (self.artifacts, self.repo / 'docs/tasks' / base.TASK_ID)
                for p in directory.rglob('*') if p.is_file()}

    def recover(self, audit=None, ok=True):
        return self.ctl('recover-interrupted-dispatch', result=self.audit if audit is None else audit, ok=ok)

    def test_audited_recovery_preserves_history_and_allows_normal_new_binding(self):
        before = deepcopy(self.state())
        old_events = self.events()
        self.recover()
        recovered = self.state()
        self.assertEqual(before['acceptance_gate'], recovered['acceptance_gate'])
        self.assertEqual(before['initial_test_owners'], recovered['initial_test_owners'])
        self.assertEqual(before['coordinator_blocker']['result'], recovered['coordinator_blocker']['result'])
        self.assertEqual(old_events, self.events()[:len(old_events)])
        self.assertTrue(recovered['interruption_recoveries'])
        audit_record = recovered['interruption_recoveries'][-1]
        self.assertEqual(before['coordinator_blocker'], audit_record['previous_blocker'])
        self.assertEqual(before['subtasks'][0]['dispatch'], audit_record['previous_dispatch'])
        self.assertEqual(self.audit, audit_record['request'])
        self.assertTrue(audit_record['recorded_at'])
        self.assertRegex(audit_record['runtime_sha256'], r'^[0-9a-f]{64}$')
        for old, new in zip(before['subtasks'], recovered['subtasks']):
            for key in ('dependencies', 'read_paths', 'write_paths', 'assignment', 'planned_agent_key'):
                self.assertEqual(old.get(key), new.get(key))
        resumed = self.receipt(recovered=True)
        rejected_before = self.snapshot()
        self.ctl('set-phase', phase=self.original_phase, result=resumed, ok=False)
        self.assertEqual(rejected_before, self.snapshot())
        resumed['written_by'] = 'new-coordinator'
        self.ctl('set-phase', phase=self.original_phase, result=resumed)
        rejected_before = self.snapshot()
        self.bind('old-tester', ok=False)
        self.assertEqual(rejected_before, self.snapshot())
        self.bind('new-tester')
        self.ctl('validate')
        self.ctl('preflight', subtask_id='TEST-001')
        tester = next(t for t in self.state()['subtasks'] if t['subtask_id'] == 'TEST-001')
        self.assertEqual('new-tester', tester['dispatch']['platform_agent_id'])
        state = self.state()
        acceptance = next(t for t in state['subtasks'] if t['subtask_id'] == 'ACCEPT-001')
        self.assertEqual([], controller._planned_dispatch_errors(state, acceptance, 'tester', 'new-tester'))
        self.assertTrue(controller._planned_dispatch_errors(state, acceptance, 'tester', 'old-tester'))

    def test_missing_or_invalid_authorization_and_old_identity_are_read_only(self):
        variants = []
        for key, value in [('approval', {}), ('previous_coordinator_id', 'wrong'),
                           ('previous_platform_agent_id', 'wrong'), ('new_platform_agent_id', 'old-tester'),
                           ('new_platform_agent_id', 'new-coordinator')]:
            audit = deepcopy(self.audit)
            audit[key] = value
            variants.append(audit)
        audit = deepcopy(self.audit)
        audit['approval']['evidence']['sha256'] = '0' * 64
        variants.append(audit)
        audit = deepcopy(self.audit)
        audit['approval']['authorization_source'] = '  '
        variants.append(audit)
        audit = deepcopy(self.audit)
        audit['approval']['evidence']['path'] = '../outside.json'
        variants.append(audit)
        audit = deepcopy(self.audit)
        original = self.repo / audit['approval']['evidence']['path']
        link = original.with_name('linked-audit.json')
        link.symlink_to(original)
        audit['approval']['evidence']['path'] = link.relative_to(self.repo).as_posix()
        variants.append(audit)
        for audit in variants:
            with self.subTest(audit=audit):
                before = self.snapshot()
                self.recover(audit, ok=False)
                self.assertEqual(before, self.snapshot())

    def test_delivery_changes_are_rejected_without_state_or_event_write(self):
        delivery = self.repo / 'tests/fixtures/example/test_delivery.py'
        delivery.parent.mkdir(parents=True)
        delivery.write_text('delivered = True\n')
        before = self.snapshot()
        self.recover(ok=False)
        self.assertEqual(before, self.snapshot())
        delivery.unlink()
        delivery.symlink_to(self.repo / '.tmp/test-brief.md')
        before = self.snapshot()
        self.recover(ok=False)
        self.assertEqual(before, self.snapshot())

    def test_result_candidate_attempt_and_finding_are_rejected_without_write(self):
        pristine = self.state()
        variants = []
        result_state = deepcopy(pristine)
        result_state['subtasks'][0]['result'] = self.receipt(recovered=True)
        variants.append(result_state)
        for key, value in [('current_candidate', {'candidate_id': 'already-frozen'}),
                           ('attempts', [{'attempt_id': 'used-attempt'}])]:
            state = deepcopy(pristine)
            state['acceptance_gate'][key] = value
            variants.append(state)
        state = deepcopy(pristine)
        state['findings'] = {'already-found': {'finding_id': 'already-found'}}
        variants.append(state)
        for state in variants:
            with self.subTest(state=state):
                (self.artifacts / 'state.json').write_text(json.dumps(state))
                before = self.snapshot()
                self.recover(ok=False)
                self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
