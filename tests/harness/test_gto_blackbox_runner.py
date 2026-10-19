"""Process lifecycle regressions found during independent blackbox setup inspection."""
from __future__ import annotations

import importlib.util
import ast
import hashlib
import inspect
import json
from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gto_blackbox_runner", ROOT / "tests/benchmarks/gto_blackbox.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class OwnedProcessCleanupTest(unittest.TestCase):
    def cleanup_function(self):
        self.assertTrue(hasattr(RUNNER, "stop_owned_process"),
                        "runner must reap its owned session even after TERM timeout")
        return RUNNER.stop_owned_process

    def test_term_ignoring_owned_process_is_killed_and_reaped(self):
        stop = self.cleanup_function()
        child = subprocess.Popen(
            [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); time.sleep(120)"],
            start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual("ready", child.stdout.readline().strip())
            result = stop(child, grace_seconds=0.05)
            self.assertTrue(result["reaped"])
            self.assertTrue(result["escalated"])
            self.assertIsNotNone(child.poll())
            self.assertEqual(-signal.SIGKILL, child.returncode)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
            child.stdout.close()
            child.stderr.close()

    def test_refuses_to_signal_a_process_in_the_callers_shared_group(self):
        stop = self.cleanup_function()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        try:
            with self.assertRaisesRegex(RuntimeError, "own session group"):
                stop(child, grace_seconds=0.05)
            self.assertIsNone(child.poll(), "refusal must not terminate the foreign process")
        finally:
            child.kill()
            child.wait(timeout=5)

    def test_naturally_completed_process_is_reaped_without_signal_escalation(self):
        stop = self.cleanup_function()
        child = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        child.wait(timeout=5)
        result = stop(child, grace_seconds=0.05)
        self.assertTrue(result["reaped"])
        self.assertFalse(result["escalated"])
        self.assertEqual(0, child.returncode)


class InstalledRuntimeBoundaryTest(unittest.TestCase):
    """默认安装来源与无流程提示合同；不调用模型、namespace或真实认证。"""

    def setUp(self):
        root = ROOT / '.tmp/review-acceptance-routing/test-a'
        root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temporary.cleanup)
        self.host = Path(self.temporary.name) / 'installed'
        self.isolated = Path(self.temporary.name) / 'isolated'
        self.host.mkdir()
        self.isolated.mkdir()
        self.installed_files = {
            'skills/global-task-orchestrator/SKILL.md': '# Installed GTO fixture\n',
            'skills/global-task-orchestrator/scripts/orchestrator_ctl.py': '# installed controller fixture\n',
            'skills/global-task-orchestrator/scripts/start_session.py': '# installed recovery fixture\n',
            'skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json': '{"fixture": "installed-schema"}\n',
        }
        for relative, content in self.installed_files.items():
            self.put(relative, content)
        receipt = {
            'schema_version': '3.0', 'harness_root': '/unavailable-original-source',
            'codex_home': str(self.host), 'managed_skills': ['global-task-orchestrator'],
            'managed_files': [dict(skill='global-task-orchestrator', source=relative,
                target=relative.removeprefix('skills/'), sha256=self.digest(content))
                for relative, content in self.installed_files.items()],
        }
        self.receipt_path = '.ai-harness/codex-sync.receipt.json'
        self.put(self.receipt_path, json.dumps(receipt))
        # 纯哨兵文本，不读取宿主认证或历史。不得进入隔离输出或来源hash。
        for relative in ('auth.json', 'config.toml', 'sessions/old.jsonl', 'history.jsonl',
                         'memories/private.md'):
            self.put(relative, 'DO-NOT-COPY synthetic sentinel\n')

    @staticmethod
    def digest(content):
        return hashlib.sha256(content.encode()).hexdigest()

    def put(self, relative, content):
        path = self.host / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def loader(self):
        self.assertTrue(callable(getattr(RUNNER, 'copy_installed_gto', None)),
                        'runner needs a real installed-runtime loader, not ROOT source bootstrap')
        return RUNNER.copy_installed_gto

    def test_loader_copies_installed_bytes_and_receipt_with_source_hashes(self):
        result = self.loader()(self.host, self.isolated)
        expected = {relative: self.digest(content) for relative, content in self.installed_files.items()}
        expected[self.receipt_path] = hashlib.sha256((self.host / self.receipt_path).read_bytes()).hexdigest()
        for relative, digest in expected.items():
            with self.subTest(relative=relative):
                self.assertEqual((self.host / relative).read_bytes(), (self.isolated / relative).read_bytes())
                self.assertEqual(digest, result['source_hashes'][relative])
        for relative in ('auth.json', 'config.toml', 'sessions', 'history.jsonl', 'memories'):
            self.assertFalse((self.isolated / relative).exists(), relative)
        self.assertFalse((self.isolated / 'schemas').exists())
        self.assertFalse(any('DO-NOT-COPY' in p.read_text() for p in self.isolated.rglob('*') if p.is_file()))

    def test_loader_rejects_installation_that_disagrees_with_receipt(self):
        loader = self.loader()
        for relative, original in self.installed_files.items():
            with self.subTest(relative=relative):
                self.put(relative, '# drift after install\n')
                with self.assertRaisesRegex((RuntimeError, ValueError), 'hash|receipt|sha256|drift'):
                    loader(self.host, self.isolated)
                self.assertEqual([], list(self.isolated.rglob('*')))
                self.put(relative, original)

    def test_loader_rejects_legacy_root_gto_schema_before_copying(self):
        relative = 'schemas/orchestrator-task-state.schema.json'
        self.put(relative, 'legacy schema\n')
        original = json.loads((self.host / self.receipt_path).read_text())
        for inventoried in (True, False):
            with self.subTest(inventoried=inventoried):
                receipt = dict(original)
                receipt['managed_schema_files'] = ([{'source': relative, 'target': relative,
                    'sha256': self.digest('legacy schema\n')}] if inventoried else [])
                self.put(self.receipt_path, json.dumps(receipt))
                with self.assertRaisesRegex(RuntimeError, 'legacy.*schema'):
                    self.loader()(self.host, self.isolated)
                self.assertEqual([], list(self.isolated.rglob('*')))

    def test_public_environment_rejects_legacy_root_source_before_publication(self):
        self.put('schemas/orchestrator-task-state.schema.json', 'legacy source\n')
        with patch.object(RUNNER, 'ROOT', self.host), patch.object(
                Path, 'read_bytes', side_effect=AssertionError('source read before legacy schema preflight')):
            with self.assertRaisesRegex(RuntimeError, 'legacy.*schema'):
                RUNNER.copy_installed_environment(self.host, self.isolated, self.isolated / 'runtime')
        self.assertEqual([], list(self.isolated.rglob('*')))

    def test_loader_requires_receipt_owned_package_schema_and_recovery_entry(self):
        original = (self.host / self.receipt_path).read_text()
        for relative in ('global-task-orchestrator/schemas/orchestrator-task-state.schema.json',
                         'global-task-orchestrator/scripts/start_session.py'):
            with self.subTest(relative=relative):
                receipt = json.loads(original)
                receipt['managed_files'] = [row for row in receipt['managed_files'] if row['target'] != relative]
                self.put(self.receipt_path, json.dumps(receipt))
                with self.assertRaisesRegex((RuntimeError, ValueError), 'incomplete|required|missing'):
                    self.loader()(self.host, self.isolated)
                self.assertEqual([], list(self.isolated.rglob('*')))
        self.put(self.receipt_path, original)

    def test_preparation_drift_can_be_repaired_and_rechecked_before_observation(self):
        loader = self.loader()
        relative = 'skills/global-task-orchestrator/SKILL.md'
        self.put(relative, '# preparation drift\n')
        with self.assertRaisesRegex((RuntimeError, ValueError), 'hash|receipt|sha256|drift'):
            loader(self.host, self.isolated)
        self.assertEqual([], list(self.isolated.rglob('*')), 'rejected preparation must not publish partial content')
        self.put(relative, self.installed_files[relative])
        copied = loader(self.host, self.isolated)
        self.assertEqual(self.digest(self.installed_files[relative]), copied['source_hashes'][relative])
        self.assertEqual(self.installed_files[relative], (self.isolated / relative).read_text())
        self.assertFalse((self.isolated / 'sessions').exists())
        self.assertFalse((self.isolated / 'memories').exists())

    def test_loader_rejects_symlink_outside_installed_skill(self):
        loader = self.loader()
        link = self.host / 'skills/global-task-orchestrator/secret-link.json'
        link.symlink_to(self.host / 'auth.json')
        with self.assertRaisesRegex((RuntimeError, ValueError), 'symlink|scope|outside|receipt|unlisted'):
            loader(self.host, self.isolated)
        self.assertFalse((self.isolated / 'skills/global-task-orchestrator/secret-link.json').exists())

    def test_main_consumes_installed_loader_and_never_bootstraps_source(self):
        tree = ast.parse(inspect.getsource(RUNNER.main))
        calls = [node.func.id for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertIn('copy_installed_gto', calls,
                      'an unused loader cannot prove the actual runner consumes the default installation')
        constants = [node.value for node in ast.walk(tree)
                     if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertFalse(any('bootstrap-local.py' in value for value in constants),
                         'blackbox must not silently rebuild the default installation from ROOT source')

    def test_business_prompts_do_not_supply_orchestration_or_failure_workflow(self):
        forbidden = (r'(?i)global-task-orchestrator|\bGTO\b|workflow_revision|initial_test_owners|'
                     r'\bCFM\b|Command Failure Memory|子代理|整合者|验收者|reviewer|'
                     r'先.{0,20}测试.{0,20}再.{0,20}实现')
        for scenario in ('normal', 'review-boundaries', 'entry-precision', 'project-config'):
            with self.subTest(scenario=scenario):
                prompt = (RUNNER.FIXTURES / scenario / 'prompt.txt').read_text()
                self.assertIn('退款', prompt)
                self.assertNotRegex(prompt, forbidden)


if __name__ == "__main__":
    unittest.main()
