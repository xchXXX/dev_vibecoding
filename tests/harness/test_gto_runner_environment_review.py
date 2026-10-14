"""RAR-006: real runner namespace and doctor, synthetic installation only.

No host auth/config/history is read. The model-launch boundary is replaced with
a real doctor invocation; all filesystem setup and bwrap mounts are production.
The tiny GTO controller is an explicit fixture isolating environment provenance.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from runtime_common import MANAGED_SKILLS, MANAGED_WSL_RUNTIME_FILES


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load('review_runner_environment', ROOT / 'tests/benchmarks/gto_blackbox.py')
DOCTOR = load('review_environment_doctor', ROOT / 'scripts/doctor-core.py')


class RunnerEnvironmentReviewTest(unittest.TestCase):
    def test_public_plugin_config_preserves_disk_state_without_extra_fields(self):
        base = ROOT / '.tmp'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='t3-plugin-boundary-', dir=base) as raw:
            declaration = Path(raw) / 'capabilities.json'
            declaration.write_text(json.dumps({'schema_version': 3, 'capabilities': [
                {'id': 'browser', 'kind': 'windows_native', 'provider': 'codex',
                 'required_plugins': ['browser@openai-bundled']}]}))
            for settings, expected in (
                ({}, {}),
                ({'plugins': {'browser@openai-bundled': {'enabled': False, 'extra': 'SYNTHETIC-PRIVATE'},
                              'unrelated': {'enabled': True}}},
                 {'plugins': {'browser@openai-bundled': {'enabled': False}}}),
                ({'plugins': {'browser@openai-bundled': {'enabled': True, 'extra': 'SYNTHETIC-PRIVATE'}}},
                 {'plugins': {'browser@openai-bundled': {'enabled': True}}}),
            ):
                with self.subTest(expected=expected):
                    rendered = RUNNER.public_plugin_config(settings, declaration)
                    self.assertEqual(expected, tomllib.loads(rendered))
                    self.assertNotIn('SYNTHETIC-PRIVATE', rendered)
            with self.assertRaisesRegex(RuntimeError, 'enabled state'):
                RUNNER.public_plugin_config({'plugins': {'browser@openai-bundled': {'enabled': 'false'}}}, declaration)

    def test_fresh_environment_publication_is_consumable_by_runner(self):
        base = ROOT / '.tmp'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='t3-runner-publication-', dir=base) as raw:
            root = Path(raw)
            installed, isolated, runtime = [root / name for name in ('installed', 'isolated', 'runtime')]
            installed.mkdir()
            template = ROOT / 'templates/codex/AGENTS.global.md'
            (installed / 'AGENTS.md').write_text(template.read_text().replace('{{HARNESS_ROOT}}', ROOT.as_posix()))
            completed = subprocess.run([sys.executable, str(ROOT / 'scripts/bootstrap-local.py'),
                '--harness-root', str(ROOT), '--codex-home', str(installed), '--environment-only', '--json'],
                capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertTrue(json.loads(completed.stdout)['ok'])
            receipt = json.loads((installed / '.ai-harness/bootstrap.receipt.json').read_text())
            self.assertTrue(receipt['managed_runtime_files'])
            for row in receipt['managed_runtime_files']:
                self.assertEqual(hashlib.sha256(Path(row['source_path']).read_bytes()).hexdigest(), row['source_sha256'])
                self.assertEqual(hashlib.sha256(Path(row['target_path']).read_bytes()).hexdigest(), row['target_sha256'])
            try:
                copied = RUNNER.copy_installed_environment(installed, isolated, runtime)
            except RuntimeError as error:
                self.fail(f'fresh matching publication rejected by runner: {error}')
            self.assertTrue(copied['installed_hashes'])
            self.assertEqual((installed / '.ai-harness/bootstrap.receipt.json').read_bytes(),
                             (isolated / '.ai-harness/bootstrap.receipt.json').read_bytes())

    def test_rar_006_runner_keeps_default_receipt_paths_and_doctor_inputs(self):
        base = ROOT / '.tmp/review-acceptance-routing/review'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as raw:
            scratch = Path(raw)
            source, installed, binaries = [scratch / p for p in ('harness', 'installed', 'bin')]
            for p in (source, installed, binaries):
                p.mkdir()

            def put(path, text):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)

            def sha(path):
                return hashlib.sha256(path.read_bytes()).hexdigest()

            # Only public source dependencies and deliberately synthetic skills.
            for relative in ('rules', 'schemas', 'scripts', 'templates'):
                shutil.copytree(ROOT / relative, source / relative,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            for _, relative in MANAGED_WSL_RUNTIME_FILES:
                path = source / relative
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ROOT / relative, path)
            baseline_path = source / 'config/ai/wsl-tool-baseline.json'
            baseline = json.loads(baseline_path.read_text())
            for profile in baseline['profiles']:
                profile['packages'] = [p for p in profile['packages'] if p['command'] == 'python3']
            put(baseline_path, json.dumps(baseline))
            put(source / 'config/ai/windows-external-capabilities.json', json.dumps({
                'schema_version': 3, 'capabilities': [
                    {'id': 'browser', 'kind': 'windows_native', 'provider': 'codex',
                     'required_plugins': ['browser@openai-bundled']}]}))

            managed = []
            for name in MANAGED_SKILLS:
                put(source / f'skills/{name}/SKILL.md', f'# synthetic {name}\n')
            put(source / 'skills/global-task-orchestrator/scripts/orchestrator_ctl.py',
                'print(\'{"ok":true}\')\n')
            put(source / 'skills/global-task-orchestrator/scripts/start_session.py',
                'print(\'{"ok":true}\')\n')
            schema = 'skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json'
            (source / schema).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / schema, source / schema)
            # The real doctor derives its input from the packaged canonical example.
            contract = 'skills/global-task-orchestrator/references/revision-3-contract.example.json'
            (source / contract).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / contract, source / contract)
            shutil.copytree(source / 'skills', installed / 'skills')
            for path in (installed / 'skills').rglob('*'):
                if path.is_file():
                    relative = path.relative_to(installed / 'skills').as_posix()
                    managed.append({'skill': relative.split('/')[0], 'source': 'skills/' + relative,
                                    'target': relative, 'sha256': sha(path)})
            receipt = {'schema_version': '3.0', 'harness_root': str(source),
                       'codex_home': str(installed), 'managed_skills': list(MANAGED_SKILLS),
                       'managed_files': managed, 'managed_schema_files': []}
            put(installed / '.ai-harness/codex-sync.receipt.json', json.dumps(receipt))
            template = source / 'templates/codex/AGENTS.global.md'
            put(installed / 'AGENTS.md', template.read_text().replace('{{HARNESS_ROOT}}', str(source)))
            runtime_entries = []
            for target_relative, source_relative in MANAGED_WSL_RUNTIME_FILES:
                origin = source / source_relative
                target = installed / '.ai-harness/runtime/wsl-environment' / target_relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, target)
                runtime_entries.append({'source_path': str(origin), 'target_path': str(target),
                                        'source_sha256': sha(origin), 'target_sha256': sha(target)})
            bootstrap = {'schema_version': '2.0', 'harness_root': str(source),
                         'codex_home': str(installed), 'template_path': str(template),
                         'template_sha256': sha(template), 'target_path': str(installed / 'AGENTS.md'),
                         'target_sha256': sha(installed / 'AGENTS.md'),
                         'managed_runtime_files': runtime_entries}
            put(installed / '.ai-harness/bootstrap.receipt.json', json.dumps(bootstrap))
            put(installed / 'config.toml', 'model = "synthetic-no-model"\n[plugins."browser@openai-bundled"]\nenabled=true\n')
            # Synthetic bind placeholder, never a real credential.
            put(installed / 'auth.json', '{}\n')
            put(installed / 'sessions/private.jsonl', 'SYNTHETIC-PRIVATE-HISTORY\n')
            put(installed / 'memories/private.md', 'SYNTHETIC-PRIVATE-MEMORY\n')
            for name in ('codex', 'codex-code-mode-host'):
                put(binaries / name, '#!/bin/sh\nexit 99\n')
                (binaries / name).chmod(0o755)

            self.assertEqual([], DOCTOR._bootstrap_audit(source, installed)['issues'])
            self.assertEqual([], DOCTOR._wsl_runtime_audit(source, installed, bootstrap))
            expected_receipt_sha = sha(installed / '.ai-harness/codex-sync.receipt.json')
            expected_bootstrap_sha = sha(installed / '.ai-harness/bootstrap.receipt.json')
            real_run, real_which = subprocess.run, shutil.which
            observed = {}

            def run(arguments, *args, **kwargs):
                if arguments[0] == 'bwrap' and 'debug' in arguments and 'prompt-input' in arguments:
                    launch = arguments[:arguments.index('codex')]
                    probe = (
                        "import os,json,subprocess,hashlib,tomllib; from pathlib import Path; "
                        "h=Path(os.environ['CODEX_HOME']); "
                        f"r=subprocess.run(['python3',str(h/'.ai-harness/runtime/wsl-environment/bin/doctor-core.py'),"
                        f"'--repo-root',{str(source)!r},'--codex-home',str(h),'--json'],capture_output=True,text=True); "
                        "print(json.dumps({'home':str(h),'doctor_exit':r.returncode,'doctor_stdout':r.stdout,"
                        "'doctor_stderr':r.stderr,'receipt_sha':hashlib.sha256((h/'.ai-harness/codex-sync.receipt.json').read_bytes()).hexdigest(),"
                        "'bootstrap_sha':hashlib.sha256((h/'.ai-harness/bootstrap.receipt.json').read_bytes()).hexdigest() if (h/'.ai-harness/bootstrap.receipt.json').exists() else None,"
                        "'history_hidden':not (h/'sessions/private.jsonl').exists(),"
                        "'memory_hidden':not (h/'memories/private.md').exists(),"
                        "'plugins_feature':tomllib.loads((h/'config.toml').read_text())['features']['plugins']}))"
                    )
                    completed = real_run(launch + ['python3', '-c', probe], capture_output=True, text=True)
                    self.assertEqual(0, completed.returncode, completed.stderr)
                    observed.update(json.loads(completed.stdout))
                    # The real Codex binary is never invoked in this test.
                    return subprocess.CompletedProcess(arguments, 0, '{}', '')
                return real_run(arguments, *args, **kwargs)

            with patch.object(RUNNER, 'ROOT', source), patch.object(RUNNER, 'FIXTURES', ROOT / 'tests/fixtures/gto-workflow'), \
                    patch.dict(os.environ, {'CODEX_HOME': str(installed)}), \
                    patch.object(sys, 'argv', ['gto_blackbox.py', '--mode', 'inspect']), \
                    patch.object(shutil, 'which', side_effect=lambda name: str(binaries / name) if name == 'codex' else real_which(name)), \
                    patch.object(subprocess, 'run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                try:
                    RUNNER.main()
                finally:
                    evidence_root = ROOT / '.artifacts/harness-minimal-convergence'
                    evidence_root.mkdir(parents=True, exist_ok=True)
                    run_root = source / '.artifacts/gto-workflow/blackbox'
                    for run_path in sorted(run_root.glob('*')):
                        for name in ('namespace-doctor.json', 'launcher.json', 'namespace-lifecycle.json',
                                     'cleanup.json', 'boundary.stdout', 'boundary.stderr'):
                            artifact = run_path / name
                            if artifact.is_file():
                                shutil.copy2(artifact, evidence_root / f'T3-rar-006-{run_path.name}-{name}')

            self.assertTrue(observed, 'runner must reach the instrumented real namespace doctor probe')
            report = json.loads(observed['doctor_stdout'])
            observed['doctor'] = report
            evidence = ROOT / '.artifacts/harness-minimal-convergence/T3-rar-006-doctor.json'
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(observed, indent=2) + '\n')
            runs = list((source / '.artifacts/gto-workflow/blackbox').iterdir())
            self.assertEqual(1, len(runs))
            for name in ('launcher.json', 'namespace-lifecycle.json', 'cleanup.json'):
                shutil.copy2(runs[0] / name, evidence.parent / ('T3-rar-006-' + name))
            audit = report['codex_audit']
            with self.subTest(boundary='declared-plugin-disk-state-without-runtime-claim'):
                external = report['windows_external_capabilities']
                self.assertTrue(external['ok'], external)
                self.assertFalse(external['runtime_verified'])
                self.assertEqual({'browser@openai-bundled': 'enabled'}, external['capabilities'][0]['plugin_states'])
                self.assertFalse(external['capabilities'][0]['runtime_verified'])
                self.assertIs(observed['plugins_feature'], False)
            with self.subTest(boundary='private-history-and-receipt-bytes'):
                self.assertTrue(observed['history_hidden'] and observed['memory_hidden'])
                self.assertEqual(expected_receipt_sha, observed['receipt_sha'])
            with self.subTest(boundary='original-logical-codex-home'):
                self.assertEqual(str(installed), observed['home'])
                self.assertFalse(audit['receipt_issues'], audit['receipt_issues'])
            with self.subTest(boundary='bootstrap-receipt'):
                self.assertFalse(audit['bootstrap']['issues'], audit['bootstrap']['issues'])
                self.assertEqual(expected_bootstrap_sha, observed['bootstrap_sha'])
            with self.subTest(boundary='runtime-source-inventory'):
                issues = [i for i in audit['runtime_issues'] if i['type'].startswith('managed_runtime_')]
                self.assertFalse(issues, issues)
                self.assertEqual(0, observed['doctor_exit'], report)


if __name__ == '__main__':
    unittest.main()
