"""Public CLI usability contract: display facts without relaxing existing gates."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

import test_harness_streamlining as previous

ROOT = previous.legacy.REPO_ROOT
SKILL = ROOT / 'skills/global-task-orchestrator'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def package_identity(path):
    spec = importlib.util.spec_from_file_location('usability_runtime_evidence', SKILL / 'scripts/runtime_evidence.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tree_manifest(path)['sha256']


class UsabilityEvidence:
    def setUp(self):
        root = ROOT / '.tmp/harness-usability/testing'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.repo = Path(self.temp.name)
        self.input_dir = self.repo / '.tmp/receipts'
        self.input_dir.mkdir(parents=True)
        self._json_input_index = 0
        self.addCleanup(self.preserve_and_cleanup)

    def preserve_and_cleanup(self):
        dest = ROOT / '.artifacts/harness-usability/testing/consumers' / (self.id() + '-' + uuid.uuid4().hex)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.repo, dest)
        print('Consumer evidence: ' + str(dest), file=sys.stderr)
        self.temp.cleanup()

    def invoke(self, command, *, success=True):
        result = subprocess.run(command, cwd=self.repo, text=True, capture_output=True)
        evidence = self.repo / '.artifacts/cli'
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / (uuid.uuid4().hex + '.json')).write_text(json.dumps({
            'command': command, 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}, indent=2))
        if success:
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        else:
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def assert_diagnostics(self, result):
        self.assertIsInstance(result['diagnostics'], list)
        for row in result['diagnostics']:
            for key in ('code', 'owner', 'affected_scope', 'next_step'):
                self.assertIn(key, row)
                self.assertTrue(row[key], (key, row))


class ToolVersionCliTest(UsabilityEvidence, unittest.TestCase):
    def tools(self, *args, package=SKILL):
        return self.invoke([sys.executable, str(package / 'scripts/tool_paths.py'), *args, '--json'])

    def install_fixture(self):
        home = self.repo / 'home'
        installed = home / 'skills/global-task-orchestrator'
        shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        receipt = home / '.ai-harness/codex-sync.receipt.json'
        receipt.parent.mkdir(parents=True)
        rows = [{'skill': 'global-task-orchestrator',
                 'source': 'skills/global-task-orchestrator/' + p,
                 'target': 'global-task-orchestrator/' + p, 'sha256': digest}
                for p, digest in sorted(tree(installed).items())]
        value = {'schema_version': '3.0', 'harness_root': str(ROOT), 'codex_home': str(home),
                 'managed_skills': ['global-task-orchestrator'], 'managed_files': rows}
        receipt.write_text(json.dumps(value))
        return home, installed, receipt, value

    def test_explicit_relative_source_and_installed_versions_are_observable(self):
        home, installed, receipt, _ = self.install_fixture()
        source = self.repo / 'source'
        shutil.copytree(SKILL, source / 'skills/global-task-orchestrator',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        before = tree(home)
        result = self.tools('--harness-root', 'source', '--codex-home', 'home')
        self.assertTrue(result['ok'])
        versions = result['version_summary']
        self.assertEqual('unknown', versions['session_load'])
        for name, path in [('source', source / 'skills/global-task-orchestrator'),
                           ('loaded', SKILL), ('installed', installed)]:
            self.assertEqual(path.resolve(), Path(versions[name]['path']).resolve())
            self.assertRegex(versions[name]['content_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(package_identity(path), versions[name]['content_sha256'])
        self.assertEqual(versions['source']['content_sha256'], versions['loaded']['content_sha256'])
        self.assertEqual(versions['loaded']['content_sha256'], versions['installed']['content_sha256'])
        self.assertEqual('matched', versions['installed']['receipt_status'])
        self.assertEqual(before, tree(home))
        self.assert_diagnostics(result)

    def test_independent_package_without_home_reports_unknown_and_scoped_diagnostic(self):
        package = self.repo / 'portable'
        shutil.copytree(SKILL, package, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        result = self.tools(package=package)
        self.assertTrue(result['ok'])
        versions = result['version_summary']
        self.assertEqual('unknown', versions['session_load'])
        self.assertIsNone(versions['source']['path'])
        self.assertIsNone(versions['source']['content_sha256'])
        self.assertIsNone(versions['installed']['path'])
        self.assertIsNone(versions['installed']['content_sha256'])
        self.assertEqual('unknown', versions['installed']['receipt_status'])
        self.assertEqual(package, Path(versions['loaded']['path']))
        self.assertFalse(result['tools']['project_env_doctor']['available'])
        self.assert_diagnostics(result)
        self.assertTrue(any('project_env_doctor' in str(d['affected_scope']) for d in result['diagnostics']))

    def test_receipt_missing_invalid_tampered_and_incomplete_never_claim_matched(self):
        home, installed, receipt, good = self.install_fixture()
        original = receipt.read_bytes()
        for case in ('missing', 'invalid_json', 'wrong_owner', 'missing_row', 'duplicate_row',
                     'external_path', 'wrong_hash', 'changed_file'):
            with self.subTest(case=case):
                receipt.write_bytes(original)
                value = json.loads(original)
                target = installed / 'scripts/tool_paths.py'
                old = target.read_bytes()
                if case == 'missing': receipt.unlink()
                elif case == 'invalid_json': receipt.write_text('{broken')
                elif case == 'wrong_owner':
                    value['codex_home'] = str(self.repo / 'another-home')
                    receipt.write_text(json.dumps(value))
                elif case == 'missing_row':
                    value['managed_files'].pop()
                    receipt.write_text(json.dumps(value))
                elif case == 'duplicate_row':
                    value['managed_files'].append(value['managed_files'][0].copy())
                    receipt.write_text(json.dumps(value))
                elif case == 'external_path':
                    value['managed_files'][0]['target'] = '../outside/entry.py'
                    receipt.write_text(json.dumps(value))
                elif case == 'wrong_hash':
                    value['managed_files'][0]['sha256'] = '0' * 64
                    receipt.write_text(json.dumps(value))
                else: target.write_bytes(old + b'\n# installed delta\n')
                before = tree(home)
                result = self.tools('--codex-home', str(home))
                self.assertTrue(result['ok'], 'Display failures must not become execution authorization.')
                status = result['version_summary']['installed']['receipt_status']
                self.assertIn(status, ('missing', 'invalid', 'mismatch'))
                if case == 'missing': self.assertEqual('missing', status)
                self.assert_diagnostics(result)
                self.assertTrue(result['diagnostics'])
                self.assertEqual(before, tree(home))
                target.write_bytes(old)

    def test_content_identity_ignores_cache_metadata_but_detects_dirty_bytes(self):
        home, installed, receipt, _ = self.install_fixture()
        original = self.tools('--codex-home', str(home))['version_summary']['installed']['content_sha256']
        cache = installed / '__pycache__'
        cache.mkdir(exist_ok=True)
        (cache / 'noise.pyc').write_bytes(b'not package content')
        (installed / '.snapshot.json').write_text('{"metadata_only": true}')
        unchanged = self.tools('--codex-home', str(home))['version_summary']['installed']['content_sha256']
        self.assertEqual(original, unchanged)
        file = installed / 'references/observation.example.json'
        file.write_bytes(file.read_bytes() + b'\n')
        changed = self.tools('--codex-home', str(home))['version_summary']['installed']
        self.assertNotEqual(original, changed['content_sha256'])
        self.assertNotEqual('matched', changed['receipt_status'])

    def test_receipt_managed_skills_requires_list_not_membership_compatible_type(self):
        home, installed, receipt, good = self.install_fixture()
        self.assertEqual('matched', self.tools('--codex-home', str(home))['version_summary']['installed']['receipt_status'])
        for invalid in ('global-task-orchestrator', {'global-task-orchestrator': True}):
            with self.subTest(managed_skills=invalid):
                value = dict(good, managed_skills=invalid)
                receipt.write_text(json.dumps(value))
                before = tree(home)
                result = self.tools('--codex-home', str(home))
                self.assertTrue(result['ok'])
                self.assertNotEqual('matched', result['version_summary']['installed']['receipt_status'],
                                    'A string/dict membership match is not a valid managed_skills list.')
                self.assert_diagnostics(result)
                self.assertTrue(result['diagnostics'])
                self.assertEqual(before, tree(home))


class ResumeVersionCliTest(UsabilityEvidence, previous.StreamliningHarness, unittest.TestCase):
    def test_frozen_resume_distinguishes_launcher_without_replacing_snapshot(self):
        self.begin(1)
        snapshot = self.state()['acceptance_gate']['current_candidate']['runtime_snapshot']
        frozen = self.repo / snapshot['path']
        frozen_before = tree(frozen)
        controls = self.controls()
        launcher = self.repo / '.tmp/new-installed'
        shutil.copytree(SKILL, launcher, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (launcher / 'scripts/orchestrator_ctl.py').write_text('raise SystemExit("must use frozen controller")\n')
        command = [sys.executable, str(launcher / 'scripts/start_session.py'),
                   '--repo-root', '.', '--task-id', previous.legacy.TASK_ID, '--json']
        result = self.invoke(command)
        version = result['version_summary']
        self.assertEqual('frozen', version['selection'])
        self.assertEqual('unknown', version['session_load'])
        self.assertEqual(snapshot['sha256'], version['snapshot_sha256'])
        self.assertEqual(launcher, Path(version['launcher']['path']))
        self.assertEqual(frozen.resolve(), Path(version['task_runtime']['path']).resolve())
        self.assertEqual(package_identity(launcher), version['launcher']['content_sha256'])
        self.assertEqual(package_identity(frozen), version['task_runtime']['content_sha256'])
        self.assertNotEqual(version['launcher']['content_sha256'], version['task_runtime']['content_sha256'])
        self.assert_diagnostics(result)
        self.assertEqual(controls, self.controls())
        self.assertEqual(frozen_before, tree(frozen))
        self.assertEqual(0, self.count())
        controller = frozen / 'scripts/orchestrator_ctl.py'
        controller.write_bytes(controller.read_bytes() + b'\n# corruption\n')
        rejected = self.invoke(command, success=False)
        self.assertFalse(rejected['ok'])
        self.assert_diagnostics(rejected)
        self.assertTrue(rejected['diagnostics'])
        self.assertEqual(controls, self.controls())
        self.assertEqual(0, self.count())

    def test_consumed_evidence_damage_is_still_rejected_with_diagnostic(self):
        self.begin(1)
        attempt = self.attempt()
        receipt = self.observe(attempt, self.ids)
        self.register(attempt, receipt)
        before = self.controls()
        ref = receipt['expensive_acceptance']['point_results'][0]['evidence_refs'][0]
        (self.repo / ref).write_text('tampered raw observation')
        rejected = self.resume(ok=False)
        self.assertFalse(rejected['ok'])
        self.assert_diagnostics(rejected)
        self.assertTrue(rejected['diagnostics'])
        self.assertEqual(before, self.controls())
        self.assertEqual(1, self.count())

    def test_documented_hash_then_bind_sequence_keeps_identity_and_stale_hash_gate(self):
        self.begin(1)
        attempt = self.attempt(bind=False)
        brief = self.repo / '.tmp/final-brief.md'
        brief.write_text('Synthetic fixture assignment for ' + attempt['subtask_id'] + '\n')
        old_hash = sha(brief)
        brief.write_text(brief.read_text() + 'Required observation references clarified.\n')
        before = self.controls()
        rejected = self.action('bind-dispatch', '--subtask-id', attempt['subtask_id'],
            '--agent-key', 'tester', '--platform-agent-id', 'accept-001', '--context-mode', 'isolated',
            '--brief-kind', 'subtask', '--brief-path', '.tmp/final-brief.md', '--brief-sha256', old_hash, ok=False)
        self.assertFalse(rejected['ok'])
        self.assertEqual(before, self.controls())
        # Execute the published shell snippet, not an independently retyped
        # implementation; explicit fixture identity is not a real review claim.
        document = (SKILL / 'references/streamlined-execution.md').read_text()
        snippet = next(part.split('```', 1)[0] for part in document.split('```bash\n')[1:]
                       if part.startswith('brief_sha256='))
        env = dict(os.environ, brief_path=brief.relative_to(self.repo).as_posix(), GTO_CONTROLLER=str(SKILL / 'scripts/orchestrator_ctl.py'),
                   repo_root=str(self.repo), task_id=previous.legacy.TASK_ID,
                   subtask_id=attempt['subtask_id'], agent_key='tester', platform_agent_id='accept-001')
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        result = subprocess.run(['bash', '-c', snippet], cwd=self.repo, env=env, text=True, capture_output=True)
        evidence = self.repo / '.artifacts/cli/binding-sequence.json'
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps({'snippet': snippet, 'exit_code': result.returncode,
                                       'stdout': result.stdout, 'stderr': result.stderr}, indent=2))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
        self.assertEqual(0, self.count())


class ScopedDiagnosticCliTest(UsabilityEvidence, previous.ScopedCapabilityStreamliningTest):
    def test_missing_page_probe_does_not_block_ordinary_pass_or_resume(self):
        # Same real public fixture; adding diagnostic projection cannot expand
        # a missing page capability into a global stop.
        super().test_missing_page_probe_does_not_block_ordinary_pass_or_resume()
        result = self.resume()
        self.assert_diagnostics(result)
        scopes = set(result['capability_checks'])
        self.assertTrue(scopes)
        relevant = [d for d in result['diagnostics'] if any(s in str(d['affected_scope']) for s in scopes)]
        self.assertTrue(relevant, 'Capability diagnostics must identify affected subtask IDs.')
        self.assertEqual('pass', result['acceptance']['points']['CHECK-01']['status'])


class GitConfigurationCliTest(UsabilityEvidence, unittest.TestCase):
    def test_missing_and_invalid_policy_remain_rejected_for_ordinary_task(self):
        initialized = subprocess.run(['git', 'init', '-b', 'main'], cwd=self.repo,
                                     text=True, capture_output=True)
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        policy = self.repo / 'config/ai/git-policy.json'
        policy.parent.mkdir(parents=True)
        (self.repo / 'README.md').write_text('Ordinary task; no GTO control plane.\n')
        for content in (None, '{invalid', '{}'):
            with self.subTest(content=content):
                if content is not None: policy.write_text(content)
                before = tree(self.repo / 'config')
                result = self.invoke([sys.executable, str(ROOT / 'scripts/check_git_workflow.py'),
                    '--repo-root', '.', '--phase', 'start', '--json'], success=False)
                self.assertFalse(result['ok'])
                self.assertIn('CONFIG_INVALID', str(result))
                self.assertEqual(before, tree(self.repo / 'config'))
                self.assertFalse((self.repo / 'docs/ai/tasks').exists())
