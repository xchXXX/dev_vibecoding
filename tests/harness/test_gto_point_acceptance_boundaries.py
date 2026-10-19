"""Independent executor and portable release boundaries for point acceptance."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import test_control_plane as legacy
import test_gto_workflow as workflow
from test_gto_point_acceptance import PointHarness


class PointBoundaryTest(PointHarness, unittest.TestCase):
    def test_public_resume_uses_frozen_controller_after_installed_package_update(self):
        installation_temp = tempfile.TemporaryDirectory(dir=self.repo.parent)
        self.addCleanup(installation_temp.cleanup)
        installed = Path(installation_temp.name) / 'global-task-orchestrator'
        shutil.copytree(legacy.REPO_ROOT / 'skills/global-task-orchestrator', installed,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        with patch.object(legacy, 'CONTROLLER', installed / 'scripts/orchestrator_ctl.py'):
            self.begin()  # Public init/review/freeze; no business acceptance run.
        snapshot = self.state()['acceptance_gate']['current_candidate']['runtime_snapshot']
        frozen = self.repo / snapshot['path']
        frozen_controller = frozen / 'scripts/orchestrator_ctl.py'
        original_snapshot = {p.relative_to(frozen).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in frozen.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        original_artifacts = {p.relative_to(self.repo).as_posix(): p.read_bytes()
                              for p in (self.repo / 'docs').rglob('*') if p.is_file()}
        installed_controller = installed / 'scripts/orchestrator_ctl.py'
        installed_controller.write_text('raise SystemExit("new installed controller must not validate the frozen task")\n')
        command = [sys.executable, str(installed / 'scripts/start_session.py'),
                   '--repo-root', str(self.repo), '--task-id', legacy.TASK_ID, '--json']
        resumed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, resumed.returncode, resumed.stdout + resumed.stderr)
        response = json.loads(resumed.stdout)
        self.assertTrue(response['ok'])
        self.assertEqual(frozen_controller.resolve(), Path(response['controller']).resolve())
        self.assertEqual(snapshot, self.state()['acceptance_gate']['current_candidate']['runtime_snapshot'])
        self.assertEqual(original_snapshot,
            {p.relative_to(frozen).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in frozen.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
        self.assertEqual(original_artifacts,
            {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in (self.repo / 'docs').rglob('*') if p.is_file()})
        self.assertEqual(0, self.count())
        # Actual resume must verify the old snapshot, not merely return its path.
        frozen_controller.write_bytes(frozen_controller.read_bytes() + b'\n# corrupt frozen bytes\n')
        rejected = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn('snapshot', rejected.stdout.lower())
        self.assertEqual(original_artifacts,
            {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in (self.repo / 'docs').rglob('*') if p.is_file()})
        self.assertEqual(0, self.count())

    def test_installed_version_refresh_does_not_replace_frozen_execution(self):
        from test_gto_plan_preflight_contract import load_controller
        load_controller()
        from runtime_evidence import freeze_tree, verify_tree
        installed = self.repo / '.tmp/installed'
        frozen = self.repo / '.tmp/frozen'
        installed.mkdir()
        (installed / 'entry.py').write_text('print("frozen-v1")\n')
        snapshot = freeze_tree(installed, frozen)
        (installed / 'entry.py').write_text('print("installed-v2")\n')
        verify_tree(frozen, snapshot)
        actual = subprocess.run([sys.executable, str(frozen / 'entry.py')], cwd=self.repo,
                                capture_output=True, text=True)
        self.assertEqual(0, actual.returncode, actual.stderr)
        self.assertEqual('frozen-v1', actual.stdout.strip())

    def test_other_executors_capability_cannot_authorize_bound_tester(self):
        contract = workflow.workflow_contract()
        dependent = next(t for t in contract['subtasks'] if t['subtask_id'] == 'TEST-001')
        requirement = {'capability_id': 'fixture-cli', 'tool': 'CLI', 'probe': 'execute fixture',
                       'binding_paths': ['candidate-config.json'], 'max_age_seconds': 3600}
        dependent['assignment']['required_capabilities'] = [requirement]
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(contract)
        self.run_ctl('prepare-workspace')
        with patch.dict(os.environ, {'GTO_SESSION_ID': 'point-boundary-session'}):
            capture = self.run_ctl('capture-capability-context', subtask_id='TEST-001',
                platform_agent_id='coordinator-001')['captures']['fixture-cli']
            path = self.repo / '.artifacts/capability.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({**capture, 'tool': requirement['tool'], 'probe': requirement['probe'],
                'session_id': 'point-boundary-session', 'status': 'passed',
                'operation': 'synthetic CLI capability probe', 'observed': 'fixture output'}))
            self.run_ctl('record-capability-probe', subtask_id='TEST-001', result={
                'capability_id': 'fixture-cli', 'evidence': {'path': '.artifacts/capability.json',
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}})
            before = self.state()
            rejection = self.bind('TEST-001', agent='initial-test-001', role='initial-tester', ok=False)
            self.assertRegex(str(rejection).lower(), 'executor|identity|agent')
            self.assertEqual(before, self.state())

    def test_release_contains_current_controller_and_relative_fixture_runs_in_isolation(self):
        release = self.repo / '.tmp/release'
        package = self.repo / '.tmp/package'
        shutil.copytree(legacy.REPO_ROOT / 'skills/gto-standalone/global-task-orchestrator', package,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        process = subprocess.run([sys.executable, str(legacy.REPO_ROOT / 'skills/gto-standalone/build_release.py'),
            '--source', str(package), '--refresh-source', str(legacy.REPO_ROOT / 'skills/global-task-orchestrator'),
            '--output-dir', str(release)], capture_output=True, text=True)
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        archive = release / 'global-task-orchestrator.zip'
        with zipfile.ZipFile(archive) as zipped:
            for directory in ('scripts', 'schemas'):
                for source in (legacy.REPO_ROOT / 'skills/global-task-orchestrator' / directory).rglob('*'):
                    if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
                        relative = source.relative_to(legacy.REPO_ROOT / 'skills/global-task-orchestrator').as_posix()
                        self.assertEqual(source.read_bytes(), zipped.read('global-task-orchestrator/' + relative), relative)
            zipped.extractall(self.repo / 'extracted')
        controller = self.repo / 'extracted/global-task-orchestrator/scripts/orchestrator_ctl.py'
        command = subprocess.run([sys.executable, str(controller), '--help'], cwd=self.repo,
                                 capture_output=True, text=True)
        self.assertEqual(0, command.returncode, command.stderr)
        self.assertIn('acceptance-status', command.stdout)
        self.assertIn('withdraw-subtask-attempt', command.stdout)


class PointScopedCapabilityTest(PointHarness, unittest.TestCase):
    def init_task(self, contract):
        template = next(task for task in contract['subtasks'] if task['subtask_id'] == 'EXPENSIVE-001')
        template['assignment']['required_capabilities'] = [{
            'capability_id': 'browser', 'tool': 'official-browser',
            'probe': 'Read the fixture page through the actual executor browser.',
            'binding_paths': ['candidate-config.json'], 'max_age_seconds': 3600}]
        items = contract['acceptance_gate']['acceptance_items']
        items[0]['capabilities'] = []
        items[1]['capabilities'] = ['browser']
        return legacy.ControlPlaneContractTest.init_task(self, contract)

    def test_missing_page_capability_blocks_only_page_scope_and_preserves_ordinary_pass(self):
        self.begin()
        # CHECK-01 is ordinary CLI work; CHECK-02 represents a page-dependent
        # assignment. This tests dispatch policy, without claiming browser use.
        ordinary = self.attempt(['CHECK-01'])
        self.register(ordinary, self.observe(ordinary, ['CHECK-01']))
        ordinary_history = self.state()['acceptance_gate']['attempts'][0]
        self.assertEqual('pass', self.coverage()['points']['CHECK-01']['status'])
        page = self.attempt(['CHECK-02'], bind=False)
        before = self.state()
        rejection = self.bind(page['subtask_id'], agent='accept-001', role='tester', ok=False)
        self.assertRegex(str(rejection).lower(), 'capability.*browser|browser.*probe')
        self.assertEqual(before, self.state(), 'A missing probe must not mutate earlier results.')
        status = self.coverage()
        self.assertEqual('pass', status['points']['CHECK-01']['status'])
        self.assertEqual(ordinary['attempt_id'], status['points']['CHECK-01']['source_attempt_id'])
        self.assertNotEqual('pass', status['points']['CHECK-02']['status'])
        self.assertFalse(status['complete'])
        self.assertEqual(ordinary_history, self.state()['acceptance_gate']['attempts'][0])
        self.assertEqual(1, self.count())


if __name__ == '__main__':
    unittest.main()
