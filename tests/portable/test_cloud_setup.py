"""Linux cloud bootstrap boundary: real CLI, local venv, canonical discovery."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
import zipfile

from support import PortableCase, REPO

SKILLS = ('global-task-orchestrator', 'pre-dev-benchmark', 'fix-closure-gate', 'command-failure-memory')


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux cloud recipient contract')
class CloudSetupTests(PortableCase):
    def fixture(self):
        script = REPO / 'scripts/cloud-setup.py'
        self.assertTrue(script.is_file(), 'Missing cloud recipient entrypoint scripts/cloud-setup.py')
        self.write('scripts/cloud-setup.py', script.read_bytes())
        self.write('requirements.txt', '# Offline fixture: dependency already provided by isolated test interpreter.\n')
        for skill in SKILLS:
            self.write('skills/' + skill + '/SKILL.md', 'Fixture canonical ' + skill + '\n')
            link = self.root / '.agents/skills' / skill
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to('../../skills/' + skill, target_is_directory=True)
        self.write('skills/global-task-orchestrator/scripts/doctor.py',
                   'import json\nprint(json.dumps({"ok": True, "fixture_doctor": True}))\n')
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True, capture_output=True)
        subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '--allow-empty', '-qm', 'cloud fixture'], cwd=self.root, check=True, capture_output=True)
        return self.root / 'scripts/cloud-setup.py'

    def cli(self, script, *flags, environment=None):
        completed = subprocess.run([sys.executable, '-B', str(script), *flags], cwd=self.root.parent,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                 **(environment or {})},
            capture_output=True, text=True, encoding='utf-8', timeout=40)
        self.assertEqual('', completed.stderr, completed.stderr)
        return completed, json.loads(completed.stdout)

    def create_venv(self):
        subprocess.run([sys.executable, '-B', '-m', 'venv', '--without-pip', str(self.root / '.venv')],
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                       check=True, capture_output=True, timeout=30)
        # Reuse the already installed test dependency without network or global installation.
        version = f'python{sys.version_info.major}.{sys.version_info.minor}'
        site = self.root / '.venv/lib' / version / 'site-packages'
        (site / 'fixture-dependencies.pth').write_text(sysconfig.get_path('purelib') + '\n')

    def test_repository_entrypoints_link_only_to_canonical_skills(self):
        self.assertTrue((REPO / 'scripts/cloud-setup.py').is_file(),
                        'Missing cloud recipient entrypoint scripts/cloud-setup.py')
        for skill in SKILLS:
            with self.subTest(skill=skill):
                link = REPO / '.agents/skills' / skill
                self.assertTrue(link.is_symlink(), 'Cloud discovery must link canonical skills')
                self.assertEqual('../../skills/' + skill, os.readlink(link))
                self.assertEqual((REPO / 'skills' / skill).resolve(), link.resolve())
                self.assertTrue((link / 'SKILL.md').is_file())

    def test_check_missing_venv_is_read_only_and_reports_unverified_session(self):
        script = self.fixture()
        before = self.snapshot(self.root)
        command, report = self.cli(script, '--check')
        self.assertNotEqual(0, command.returncode)
        self.assertIs(report['ok'], False)
        self.assertIs(report['session_verified'], False)
        self.assertTrue(report['errors'])
        self.assertFalse((self.root / '.venv').exists())
        self.assertEqual(before, self.snapshot(self.root))

    def test_real_venv_check_and_setup_reuse_are_repo_relative(self):
        script = self.fixture()
        self.create_venv()
        before = self.snapshot(self.root)
        command, report = self.cli(script, '--check')
        self.assertEqual(0, command.returncode, report)
        self.assertIs(report['ok'], True)
        self.assertIs(report['session_verified'], False)
        self.assertEqual(str(self.root.resolve()), report['repo_root'])
        self.assertEqual(str(self.root / '.venv'), report['venv_path'])
        self.assertEqual(str(self.root / '.venv/bin/python'), report['python_path'])
        self.assertEqual(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.root, text=True).strip(), report['source_commit'])
        self.assertEqual(set(SKILLS), set(report['skill_paths']))
        self.assertEqual(before, self.snapshot(self.root))
        prefix_before = (self.root / '.venv/pyvenv.cfg').read_bytes()
        command, report = self.cli(script)
        self.assertEqual(0, command.returncode, report)
        self.assertIs(report['ok'], True)
        self.assertEqual(prefix_before, (self.root / '.venv/pyvenv.cfg').read_bytes())

    def test_nonvenv_and_linked_venv_are_rejected_without_overwriting_data(self):
        script = self.fixture()
        sentinel = self.write('.venv/user.txt', b'owned user data\n')
        before = self.snapshot(self.root)
        command, report = self.cli(script)
        self.assertNotEqual(0, command.returncode)
        self.assertIs(report['ok'], False)
        self.assertEqual(before, self.snapshot(self.root))

        self.assertEqual(b'owned user data\n', sentinel.read_bytes())
        shutil.move(str(self.root / '.venv'), str(self.root / 'outside-venv'))
        (self.root / '.venv').symlink_to(self.root / 'outside-venv', target_is_directory=True)
        before = self.snapshot(self.root)
        command, report = self.cli(script)
        self.assertNotEqual(0, command.returncode)
        self.assertIs(report['ok'], False)
        self.assertTrue((self.root / '.venv').is_symlink())
        self.assertEqual(before, self.snapshot(self.root))
        (self.root / '.venv').unlink()
        self.write('.venv/pyvenv.cfg', 'home = /external/interpreter\ninclude-system-site-packages = false\n')
        (self.root / '.venv/bin').mkdir()
        (self.root / '.venv/bin/python').symlink_to(sys.executable)
        before = self.snapshot(self.root)
        command, report = self.cli(script)
        self.assertNotEqual(0, command.returncode)
        self.assertIs(report['ok'], False)
        self.assertEqual(before, self.snapshot(self.root))

    def test_canonical_skills_parent_cannot_escape_repository(self):
        script = self.fixture()
        outside = tempfile.TemporaryDirectory(prefix='cloud-external-', dir=self.root.parent)
        self.addCleanup(outside.cleanup)
        destination = Path(outside.name) / 'skills'
        shutil.move(str(self.root / 'skills'), str(destination))
        (self.root / 'skills').symlink_to(destination, target_is_directory=True)
        before = self.snapshot(self.root)
        external_before = self.snapshot(Path(outside.name))
        command, report = self.cli(script, '--check')
        self.assertNotEqual(0, command.returncode)
        self.assertIs(report['ok'], False)
        self.assertTrue(any('skill' in error.lower() and ('escape' in error.lower() or 'symlink' in error.lower())
                            for error in report['errors']), report)
        self.assertEqual(before, self.snapshot(self.root))
        self.assertEqual(external_before, self.snapshot(Path(outside.name)))
        (self.root / 'skills').unlink()
        shutil.move(str(destination), str(self.root / 'skills'))
        canonical = self.root / 'skills/global-task-orchestrator'
        destination = Path(outside.name) / 'canonical-gto'
        shutil.move(str(canonical), str(destination))
        canonical.symlink_to(destination, target_is_directory=True)
        before, external_before = self.snapshot(self.root), self.snapshot(Path(outside.name))
        command, report = self.cli(script, '--check')
        self.assertNotEqual(0, command.returncode)
        self.assertTrue(any('skill' in error.lower() and ('escape' in error.lower() or 'symlink' in error.lower())
                            for error in report['errors']), report)
        self.assertEqual(before, self.snapshot(self.root))
        self.assertEqual(external_before, self.snapshot(Path(outside.name)))

    def test_venv_site_packages_link_cannot_redirect_installation(self):
        script = self.fixture()
        self.create_venv()
        version = f'python{sys.version_info.major}.{sys.version_info.minor}'
        site = self.root / '.venv/lib' / version / 'site-packages'
        destination = self.root / 'outside-site'
        shutil.move(str(site), str(destination))
        site.symlink_to(destination, target_is_directory=True)
        before = self.snapshot(self.root)
        command, report = self.cli(script)
        self.assertNotEqual(0, command.returncode)
        self.assertIs(report['ok'], False)
        self.assertEqual(before, self.snapshot(self.root))

        site.unlink()
        shutil.move(str(destination), str(site))
        binary = self.root / '.venv/bin'
        destination = self.root / 'outside-bin'
        shutil.move(str(binary), str(destination))
        binary.symlink_to(destination, target_is_directory=True)
        before = self.snapshot(self.root)
        command, report = self.cli(script)
        self.assertNotEqual(0, command.returncode)
        self.assertIs(report['ok'], False)
        self.assertEqual(before, self.snapshot(self.root))

    def test_setup_installs_local_wheel_only_inside_venv_despite_pip_targets(self):
        script = self.fixture()
        self.create_venv()
        wheel = self.root / 'cloud_fixture_pkg-0.0.1-py3-none-any.whl'
        dist = 'cloud_fixture_pkg-0.0.1.dist-info/'
        with zipfile.ZipFile(wheel, 'w') as archive:
            archive.writestr('cloud_fixture_pkg/__init__.py', 'MARKER = "fixture"\n')
            archive.writestr(dist + 'METADATA', 'Metadata-Version: 2.1\nName: cloud-fixture-pkg\nVersion: 0.0.1\n')
            archive.writestr(dist + 'WHEEL', 'Wheel-Version: 1.0\nGenerator: independent-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
            archive.writestr(dist + 'RECORD', '')
        self.write('requirements.txt', str(wheel) + '\n')
        config = self.write('pip-user.conf', '[global]\ntarget = ' + str(self.root / 'config-target') + '\n')
        site_config = self.write('.venv/pip.conf', '[install]\ntarget = ' + str(self.root / 'site-config-target') + '\n')
        config_before, site_config_before = config.read_bytes(), site_config.read_bytes()
        command, report = self.cli(script, environment={
            'PIP_TARGET': str(self.root / 'env-target'), 'PIP_PREFIX': str(self.root / 'env-prefix'),
            'PIP_USER': '1', 'PYTHONUSERBASE': str(self.root / 'user-base'), 'PIP_CONFIG_FILE': str(config),
            'HOME': str(self.root / 'fixture-home')})
        self.assertEqual(0, command.returncode, report)
        self.assertIs(report['ok'], True)
        version = f'python{sys.version_info.major}.{sys.version_info.minor}'
        installed = self.root / '.venv/lib' / version / 'site-packages/cloud_fixture_pkg/__init__.py'
        self.assertEqual(b'MARKER = "fixture"\n', installed.read_bytes())
        for target in ('env-target', 'env-prefix', 'user-base', 'config-target', 'site-config-target'):
            self.assertFalse((self.root / target).exists(), target)
        self.assertEqual(config_before, config.read_bytes())
        self.assertEqual(site_config_before, site_config.read_bytes())
        pip_command = next(item['argv'] for item in report['command_results'] if 'pip' in item['argv'])
        self.assertIn('--isolated', pip_command)
        self.assertIn('--no-cache-dir', pip_command)
        self.assertFalse((self.root / 'fixture-home/.cache/pip').exists())


if __name__ == '__main__':
    unittest.main()
