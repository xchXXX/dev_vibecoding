"""Runtime and retained-evidence behavior; no model calls or fabricated acceptance."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_gto_plan_preflight_contract import load_controller

ROOT = Path(__file__).resolve().parents[2]


def runtime_module():
    path = ROOT / 'skills/global-task-orchestrator/scripts/runtime_evidence.py'
    if not path.exists():
        raise AssertionError('runtime snapshot and retention module is absent')
    spec = importlib.util.spec_from_file_location('runtime_evidence', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeHardeningTest(unittest.TestCase):
    def test_current_contract_does_not_accept_retired_workflow(self):
        from test_gto_workflow import workflow_contract
        ctl = load_controller()
        for revision in (None, 2):
            contract = workflow_contract()
            if revision is None:
                contract.pop('workflow_revision', None)
            else:
                contract['workflow_revision'] = revision
            self.assertTrue(any('workflow_revision' in e for e in ctl._validate_contract(contract)))

    def test_null_candidate_has_no_current_coverage(self):
        ctl = load_controller()
        self.assertIsNone(ctl._current_batch_coverage(Path('.'),
            {'acceptance_gate': {'current_candidate': None, 'coverage_receipts': []}},
            'ordinary', lambda *_: {}))

    def test_snapshot_keeps_exact_bytes_and_detects_tampering(self):
        runtime = runtime_module()
        with tempfile.TemporaryDirectory(dir=ROOT / '.tmp') as folder:
            root = Path(folder)
            source = root / 'skill'
            source.mkdir()
            (source / 'tool.py').write_text('print("one")\n')
            frozen = runtime.freeze_tree(source, root / 'snapshot')
            (source / 'tool.py').write_text('print("two")\n')
            self.assertEqual('print("one")\n', (root / 'snapshot/tool.py').read_text())
            runtime.verify_tree(root / 'snapshot', frozen)
            (root / 'snapshot/tool.py').write_text('tamper')
            with self.assertRaisesRegex(ValueError, 'snapshot'):
                runtime.verify_tree(root / 'snapshot', frozen)

    def test_snapshot_rejects_symlinks_and_does_not_overwrite(self):
        runtime = runtime_module()
        with tempfile.TemporaryDirectory(dir=ROOT / '.tmp') as folder:
            root = Path(folder)
            source = root / 'source'
            source.mkdir()
            (source / 'data').write_text('real')
            (source / 'alias').symlink_to(source / 'data')
            with self.assertRaises(ValueError):
                runtime.freeze_tree(source, root / 'snapshot')
            self.assertFalse((root / 'snapshot').exists())
            (source / 'alias').unlink()
            (root / 'redirected').symlink_to(source, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                runtime.freeze_tree(source, root / 'redirected/nested')
            runtime.freeze_tree(source, root / 'snapshot')
            with self.assertRaises(FileExistsError):
                runtime.freeze_tree(source, root / 'snapshot')

    def test_failed_run_is_retained_and_corruption_prevents_verification(self):
        runtime = runtime_module()
        with tempfile.TemporaryDirectory(dir=ROOT / '.tmp') as folder:
            root = Path(folder)
            retained = root / '.artifacts' / 'task'
            binding = {'candidate_id': 'candidate-test', 'runtime_sha256': 'a' * 64}
            first = runtime.run_command(retained, [sys.executable, '-c',
                'print("observed failure"); raise SystemExit(7)'], cwd=root, binding=binding)
            second = runtime.run_command(retained, [sys.executable, '-c', 'print("ok")'],
                cwd=root, binding=binding)
            self.assertNotEqual(first, second)
            manifest = runtime.verify_run(first, binding)
            self.assertEqual(7, manifest['exit_code'])
            self.assertEqual('failed', manifest['status'])
            self.assertIn('observed failure', (first / 'stdout.log').read_text())
            with self.assertRaisesRegex(ValueError, 'binding'):
                runtime.verify_run(first, dict(binding, candidate_id='another'))
            (first / 'stdout.log').write_text('silently replaced')
            with self.assertRaisesRegex(ValueError, 'hash'):
                runtime.verify_run(first, binding)

    def test_native_failed_stdout_is_valid_bound_evidence(self):
        runtime = runtime_module()
        with tempfile.TemporaryDirectory(dir=ROOT / '.tmp') as folder:
            repo = Path(folder)
            task = {'subtask_id': 'A-1', 'stage': 'expensive_acceptance', 'dispatch': {'platform_agent_id': 'acceptor'}}
            state = {'task_id': 'synthetic-task', 'subtasks': [task], 'acceptance_gate': {
                'current_candidate': {'candidate_id': 'C-1', 'fingerprint': 'f' * 64,
                    'runtime_snapshot': {'sha256': 'a' * 64}},
                'attempts': [{'attempt_id': 'attempt-1', 'subtask_id': 'A-1'}]}}
            run = runtime.run_command(repo / '.artifacts/runs',
                [sys.executable, '-c', 'print("observed failure"); raise SystemExit(7)'],
                cwd=repo, binding=runtime.acceptance_binding(state, 'A-1'))
            reference = {'path': (run / 'manifest.json').relative_to(repo).as_posix(),
                         'sha256': runtime.digest((run / 'manifest.json').read_bytes())}
            result = {'expensive_acceptance': {'outcome': 'environment_failure', 'run_evidence': reference,
                      'evidence_refs': [(run / 'stdout.log').relative_to(repo).as_posix()]}}
            self.assertEqual([], runtime.acceptance_run_errors(repo, state, task, result))
            (repo / '.artifacts/foreign.log').write_text('not captured')
            result['expensive_acceptance']['evidence_refs'] = ['.artifacts/foreign.log']
            self.assertTrue(runtime.acceptance_run_errors(repo, state, task, result))

    def test_timeout_keeps_output_and_is_not_a_pass(self):
        runtime = runtime_module()
        with tempfile.TemporaryDirectory(dir=ROOT / '.tmp') as folder:
            root = Path(folder)
            run = runtime.run_command(root / '.artifacts/task', [sys.executable, '-u', '-c',
                'import time; print("started"); time.sleep(30)'], cwd=root,
                binding={'candidate_id': 'candidate-test'}, timeout=0.5)
            manifest = runtime.verify_run(run, {'candidate_id': 'candidate-test'})
            self.assertEqual('interrupted', manifest['status'])
            self.assertIn('started', (run / 'stdout.log').read_text())


class CurrentGuardTest(unittest.TestCase):
    # Reuse current-contract setup only; no inherited test duplication.
    from test_gto_execution_plan import ResultPreflightTest as _Fixture
    setUp = _Fixture.setUp
    tearDown = _Fixture.tearDown
    git = _Fixture.git
    init_git_checkout = _Fixture.init_git_checkout
    state = _Fixture.state
    item = staticmethod(_Fixture.item)
    bind = _Fixture.bind
    work_result = _Fixture.work_result
    integrate = _Fixture.integrate
    review_payload = _Fixture.review_payload
    review = _Fixture.review
    run_ctl = _Fixture.run_ctl
    start = _Fixture.start

    def test_current_negative_scope_rebind_and_candidate_symlink_guards(self):
        self.start()
        self.bind('WORK-001')
        self.bind('WORK-001', ok=False)
        payload = self.work_result()
        payload['changed_files'] = ['outside-scope.py']
        rejected = self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=payload, ok=False)
        self.assertIn('write_paths', str(rejected))
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=self.work_result())
        self.bind('WORK-001', ok=False)
        target = self.repo / 'candidate-source.py'
        target.unlink()
        target.symlink_to(self.input_dir / 'external.py')
        (self.input_dir / 'external.py').write_text('external')
        with self.assertRaises(self.ctl.ControlError):
            self.ctl._candidate_records(self.repo, self.state())

    def test_parent_symlink_cannot_disguise_disposable_evidence(self):
        self.start()
        temporary = self.repo / '.tmp/raw.log'
        temporary.write_text('disposable')
        alias = self.repo / '.artifacts/alias'
        alias.parent.mkdir(exist_ok=True)
        alias.symlink_to(self.repo / '.tmp', target_is_directory=True)
        self.assertIn('symlink', self.ctl._evidence_file_error(self.repo, '.artifacts/alias/raw.log'))
        import acceptance_batches as batches
        with self.assertRaisesRegex(batches.BatchEvidenceError, 'symlink'):
            batches._file(self.repo, {'path': '.artifacts/alias/raw.log',
                'sha256': batches.digest(temporary.read_bytes())}, pointer=False, json_required=False)

    def test_real_cli_rejects_missing_foreign_and_tampered_run_then_accepts_exact_run(self):
        import subprocess
        import test_control_plane as base
        from test_gto_workflow import usage
        self.start()
        self.integrate()
        self.review()
        self.run_ctl('freeze-candidate')
        ident = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(ident, agent='initial-test-001', role='tester')
        payload = base.result('completed', 'initial-test-001', 'tester', expensive_acceptance={
            'outcome': 'pass', 'real_call_count': 1, 'duration_seconds': 1, 'failed_stage': 'none',
            'evidence_refs': ['.artifacts/accept.log'],
            'evidence_by_acceptance_id': {'REAL-PATH-001': ['.artifacts/accept.log']},
            'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'],
            'usage_evidence': usage('initial-test-001', 'accept'), 'closed_finding_ids': []})
        input_path = self.repo / '.tmp/result.json'
        def submit(expected):
            input_path.write_text(json.dumps(payload))
            result = subprocess.run([sys.executable, '-B', str(base.CONTROLLER), '--action',
                'record-subtask-result', '--repo-root', str(self.repo), '--task-id', base.TASK_ID,
                '--subtask-id', ident, '--result-json-file', str(input_path), '--json'], capture_output=True, text=True)
            self.assertEqual(expected, result.returncode == 0, result.stdout + result.stderr)
            return result.stdout
        self.assertIn('run_evidence', submit(False))
        base.attach_acceptance_run(self.repo, ident, payload, create_fixture_files=True)
        ref = payload['expensive_acceptance']['run_evidence']
        manifest_path = self.repo / ref['path']
        original = manifest_path.read_bytes()
        runtime = runtime_module()
        manifest = json.loads(original)
        manifest['binding']['attempt_id'] = 'foreign-attempt'
        manifest_path.write_text(json.dumps(manifest))
        ref['sha256'] = runtime.digest(manifest_path.read_bytes())
        self.assertIn('binding', submit(False))
        manifest_path.write_bytes(original)
        ref['sha256'] = runtime.digest(original)
        output = manifest_path.parent / 'stdout.log'
        raw = output.read_bytes()
        output.write_text('tampered')
        self.assertIn('hash', submit(False))
        output.write_bytes(raw)
        business = self.repo / '.artifacts/accept.log'
        business_raw = business.read_bytes()
        business.write_text('tampered business verdict')
        self.assertIn('business evidence hash', submit(False))
        business.write_bytes(business_raw)
        submit(True)
        output.write_text('tampered after result')
        self.assertTrue(self.ctl._current_run_errors(self.repo, self.state()))


if __name__ == '__main__':
    unittest.main()
