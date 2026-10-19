"""Independent portability regressions; set GTO_TEST_PACKAGE to the candidate.

Encoding cases use a real CLI with a controlled pipe encoding, not a claim of
Windows-native acceptance. The process-tree case executes real Linux processes.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(os.environ.get('GTO_TEST_REPO', Path.cwd())).resolve()
PACKAGE = Path(os.environ.get('GTO_TEST_PACKAGE', ROOT / 'skills/gto-standalone/global-task-orchestrator')).resolve()


class ReviewPortabilityTest(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.tmp/gto-standalone/review/probes'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'user skills/global-task-orchestrator'
        shutil.copytree(PACKAGE, self.skill, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.repo = self.root / '消费 项目'
        self.repo.mkdir()
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        self.env.pop('PYTHONPATH', None)

    def call(self, script, *args, pipe_encoding='utf-8'):
        env = dict(self.env, PYTHONIOENCODING=pipe_encoding)
        return subprocess.run([sys.executable, '-B', str(self.skill / 'scripts' / script), *map(str, args)],
                              cwd=self.repo, env=env, capture_output=True, timeout=30)

    def test_resume_unicode_project_with_legacy_pipe_encoding(self):
        """JSON CLI must work in non-UTF-8 pipes without an undocumented env fix."""
        task = '20300101-120000-review-portability'
        contract = self.repo / '.tmp/contract.json'
        contract.parent.mkdir()
        shutil.copyfile(self.skill / 'references/revision-3-contract.example.json', contract)
        initialized = self.call('orchestrator_ctl.py', '--action', 'init-task', '--repo-root', self.repo,
                                '--task-id', task, '--contract-json-file', contract, '--owner', 'coordinator',
                                '--title', '独立使用', '--json')
        self.assertEqual(initialized.returncode, 0, initialized.stderr.decode('utf-8', 'replace'))
        doctor = self.call('doctor.py', '--json', pipe_encoding='cp1252')
        self.assertEqual(doctor.returncode, 0, doctor.stderr.decode('utf-8', 'replace'))
        resumed = self.call('start_session.py', '--repo-root', self.repo, '--task-id', task, '--json',
                            pipe_encoding='cp1252')
        self.assertEqual(resumed.returncode, 0, resumed.stderr.decode('utf-8', 'replace'))
        # Machine JSON is either escaped ASCII or UTF-8; preserve the exact Unicode path.
        self.assertEqual(json.loads(resumed.stdout)['repo_root'], str(self.repo))

    def test_workspace_unicode_git_path_with_legacy_locale(self):
        """Exercise real Git bytes with the text-decoding locale used by legacy Windows."""
        for args in [('init',), ('-c', 'user.name=GTO Review', '-c', 'user.email=review@example.invalid',
                                'commit', '--allow-empty', '-m', 'probe baseline')]:
            git = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True)
            self.assertEqual(git.returncode, 0, git.stderr.decode('utf-8', 'replace'))
        task = '20300101-120000-review-git'
        contract = self.repo / '.tmp/contract.json'
        contract.parent.mkdir()
        shutil.copyfile(self.skill / 'references/revision-3-contract.example.json', contract)
        initialized = self.call('orchestrator_ctl.py', '--action', 'init-task', '--repo-root', self.repo,
                                '--task-id', task, '--contract-json-file', contract, '--owner', 'coordinator',
                                '--title', 'git encoding', '--json')
        self.assertEqual(initialized.returncode, 0, initialized.stderr.decode('utf-8', 'replace'))
        # Only the OS locale boundary is simulated. Git, controller, files, and CLI are real.
        bootstrap = ('import locale,runpy,sys; locale.getencoding=lambda: "cp1252"; '
                     'sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")')
        result = subprocess.run([sys.executable, '-B', '-c', bootstrap,
                                 str(self.skill / 'scripts/orchestrator_ctl.py'), '--action', 'prepare-workspace',
                                 '--repo-root', str(self.repo), '--task-id', task, '--json'],
                                cwd=self.repo, env=dict(self.env, PYTHONUTF8='0', PYTHONIOENCODING='utf-8'),
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout.decode('utf-8', 'replace') + result.stderr.decode('utf-8', 'replace'))
        self.assertTrue(json.loads(result.stdout)['ok'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'real Linux process-tree probe')
    def test_timeout_stops_descendant_that_ignores_sigterm(self):
        """A timeout must not leave the child consuming resources after its parent exits."""
        spec = importlib.util.spec_from_file_location('review_runtime', self.skill / 'scripts/runtime_evidence.py')
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        child_pid_file = self.repo / 'child.pid'
        child_code = ('import os,signal,time; from pathlib import Path; '
                      'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                      f'Path({str(child_pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)')
        parent_code = ('import subprocess,sys,time; '
                       f'subprocess.Popen([sys.executable,"-c",{child_code!r}]); time.sleep(30)')
        child_pid = None
        try:
            run = runtime.run_command(self.repo / '.artifacts/probe',
                                      [sys.executable, '-c', parent_code], cwd=self.repo,
                                      binding={'candidate_id': 'review-probe'}, timeout=1.0)
            self.assertTrue(child_pid_file.is_file(), 'probe child must have started before timeout')
            child_pid = int(child_pid_file.read_text())
            manifest = runtime.verify_run(run, {'candidate_id': 'review-probe'})
            self.assertEqual(manifest['status'], 'interrupted')
            # SIGKILL may leave a short-lived zombie; zombies no longer execute work.
            def running():
                status = Path(f'/proc/{child_pid}/stat')
                return status.exists() and status.read_text().split(') ', 1)[1][0] != 'Z'
            deadline = time.monotonic() + 2
            while running() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(running(), f'timed-out descendant {child_pid} is still executing')
        finally:
            if child_pid is None and child_pid_file.exists():
                child_pid = int(child_pid_file.read_text())
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
