"""Exercise the shipped folder in an unrelated consumer directory."""
import json
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(os.environ.get('GTO_TEST_PACKAGE', ROOT / 'skills/gto-standalone/global-task-orchestrator')).resolve()


class PortableTest(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.tmp/gto-standalone/tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / '别人 用户/skills/global-task-orchestrator'
        shutil.copytree(PACKAGE, self.skill, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.repo = self.root / '消费 项目'
        self.repo.mkdir()
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        self.env.pop('PYTHONPATH', None)

    def call(self, script, *args, isolated=False):
        return subprocess.run([sys.executable, *(['-S'] if isolated else []), '-B',
            str(self.skill / 'scripts' / script), *map(str, args)],
            cwd=self.repo, env=self.env, capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_doctor_is_read_only_and_checks_runtime(self):
        doctor = self.skill / 'scripts/doctor.py'
        self.assertTrue(doctor.is_file(), 'portable package needs a stdlib-only preflight')
        before = sorted(p.relative_to(self.skill).as_posix() for p in self.skill.rglob('*'))
        result = self.call('doctor.py', '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
        self.assertEqual(before, sorted(p.relative_to(self.skill).as_posix() for p in self.skill.rglob('*')))
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_missing_dependency_returns_actionable_json_without_traceback(self):
        self.assertTrue((self.skill / 'scripts/doctor.py').is_file(), 'missing portable doctor')
        result = self.call('doctor.py', '--json', isolated=True)
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload['ok'])
        self.assertIn('jsonschema', json.dumps(payload))
        self.assertIn('requirements.txt', json.dumps(payload))
        self.assertNotIn('Traceback', result.stderr)

    def test_all_local_document_links_resolve_inside_package(self):
        broken = []
        for doc in self.skill.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
                if '://' in link or link.startswith('#'):
                    continue
                target = (doc.parent / link.split('#')[0]).resolve()
                if not target.is_relative_to(self.skill.resolve()) or not target.exists():
                    broken.append((str(doc.relative_to(self.skill)), link))
        self.assertEqual(broken, [], 'distribution must not rely on harness or adjacent skills')

    def test_init_validate_resume_from_relocated_folder(self):
        task = '20300101-120000-portable'
        contract = self.repo / '.tmp/contract.json'
        contract.parent.mkdir()
        shutil.copyfile(self.skill / 'references/revision-3-contract.example.json', contract)
        result = self.call('orchestrator_ctl.py', '--action', 'init-task', '--repo-root', self.repo,
            '--task-id', task, '--contract-json-file', contract, '--owner', 'coordinator', '--title', '独立消费', '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for folder, names in [('docs/ai/tasks', ['state.json', 'task.md', 'events.jsonl']),
                              ('docs/tasks', ['plan.md', 'execution.md', 'acceptance.md'])]:
            for name in names:
                self.assertTrue((self.repo / folder / task / name).is_file())
        validation = self.call('orchestrator_ctl.py', '--action', 'validate', '--repo-root', self.repo,
                               '--task-id', task, '--json')
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        resumed = self.call('start_session.py', '--repo-root', self.repo, '--task-id', task, '--json')
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertEqual(Path(json.loads(resumed.stdout)['controller']), self.skill / 'scripts/orchestrator_ctl.py')

    def test_windows_timeout_requests_tree_termination_and_reports_failure(self):
        spec = importlib.util.spec_from_file_location('portable_runtime', self.skill / 'scripts/runtime_evidence.py')
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        self.assertTrue(hasattr(runtime, '_terminate_process_tree'), 'timeout must support Windows process trees')
        process = Mock(pid=9876)
        process.poll.return_value = None
        with patch.object(runtime, 'os', SimpleNamespace(name='nt')):
            with patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as command:
                runtime._terminate_process_tree(process)
                argv = command.call_args.args[0]
                self.assertEqual(argv, ['taskkill', '/PID', '9876', '/T', '/F'])
            with patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
                with self.assertRaises(OSError):
                    runtime._terminate_process_tree(process)


if __name__ == '__main__':
    unittest.main()
