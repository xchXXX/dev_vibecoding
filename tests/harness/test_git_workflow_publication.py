"""Scoped publication preserves unrelated runtime state and refuses drift."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        folder = ROOT / '.tmp/git-workflow/publication-tests'
        folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / '.ai-harness').mkdir()
        self.old = '<!-- ai-harness:managed-global-agents:v1 -->\nPrevious managed instructions\n'
        (self.home / 'AGENTS.md').write_text(self.old)
        self.receipt = {'schema_version': '2.0', 'target_sha256': hashlib.sha256(self.old.encode()).hexdigest(),
                        'managed_runtime_files': [{'sentinel': 'keep'}], 'unrelated': {'keep': True}}
        (self.home / '.ai-harness/bootstrap.receipt.json').write_text(json.dumps(self.receipt))
        for name in ['config.toml', 'skills/other/SKILL.md', '.ai-harness/codex-sync.receipt.json']:
            p = self.home / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('leave this byte-for-byte')

    def run_publish(self, code=0):
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/bootstrap-local.py'),
                              '--codex-home', str(self.home), '--git-workflow-only', '--json'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, code, run.stdout + run.stderr)
        return json.loads(run.stdout)

    def test_scoped_publication_preserves_other_runtime_and_is_idempotent(self):
        self.assertTrue(self.run_publish()['runtime_changed'])
        self.assertFalse(self.run_publish()['runtime_changed'])
        for name in ['config.toml', 'skills/other/SKILL.md', '.ai-harness/codex-sync.receipt.json']:
            self.assertEqual((self.home / name).read_text(), 'leave this byte-for-byte')
        receipt = json.loads((self.home / '.ai-harness/bootstrap.receipt.json').read_text())
        self.assertEqual(receipt['managed_runtime_files'], self.receipt['managed_runtime_files'])
        self.assertEqual(receipt['unrelated'], {'keep': True})
        checker = self.home / '.ai-harness/runtime/git-workflow/check_git_workflow.py'
        self.assertEqual(checker.read_bytes(), (ROOT / 'scripts/check_git_workflow.py').read_bytes())

    def test_hold_blocks_before_runtime_writes(self):
        (self.home / '.ai-harness/windows-native-transition.hold').write_text('hold')
        self.run_publish(code=1)
        self.assertEqual((self.home / 'AGENTS.md').read_text(), self.old)
        self.assertFalse((self.home / '.ai-harness/runtime').exists())

    def test_installed_instructions_drift_is_not_overwritten(self):
        (self.home / 'AGENTS.md').write_text(self.old + 'concurrent change')
        result = self.run_publish(code=1)
        self.assertIn('AGENTS_RECEIPT_DRIFT', str(result))
        self.assertEqual((self.home / 'AGENTS.md').read_text(), self.old + 'concurrent change')

    def test_installed_checker_drift_is_not_overwritten(self):
        self.run_publish()
        checker = self.home / '.ai-harness/runtime/git-workflow/check_git_workflow.py'
        checker.write_text('other task change')
        result = self.run_publish(code=1)
        self.assertIn('GIT_RUNTIME_DRIFT', str(result))
        self.assertEqual(checker.read_text(), 'other task change')


if __name__ == '__main__':
    unittest.main()
