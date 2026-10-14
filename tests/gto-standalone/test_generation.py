"""The distribution is reproducibly generated and drift is detected before use."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / 'scripts/generate-gto-standalone.py'


class GenerationTest(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.tmp/gto-standalone/generation'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        for name, data in {
            'SKILL.md': '# Portable skill\n', 'README.md': 'Read me\n',
            'requirements.txt': 'jsonschema>=4.10.3,<5\n',
            'scripts/tool.py': 'print("中文 exact bytes")\r\n',
            'references/guide.md': '# Guide\n',
        }.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data.encode('utf-8'))

    def call(self, destination, *args):
        self.assertTrue(GENERATOR.is_file(), 'missing standalone generation entrypoint')
        return subprocess.run([sys.executable, '-B', str(GENERATOR), '--source',
            str(self.source), '--output', str(destination), *args],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30)

    @staticmethod
    def contents(root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def test_generation_is_exact_and_deterministic_and_detects_drift(self):
        first, second = self.root / 'one', self.root / 'two'
        for output in (first, second):
            result = self.call(output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        one = self.contents(first)
        self.assertEqual(one, self.contents(second))
        for name, content in self.contents(self.source).items():
            self.assertEqual(one[name], content, name)
        manifest = json.loads(one['SOURCE.json'])
        self.assertEqual(manifest['source'], 'skills/global-task-orchestrator')
        self.assertEqual({row['path']: row['sha256'] for row in manifest['files']},
                         {name: hashlib.sha256(data).hexdigest()
                          for name, data in self.contents(self.source).items()})
        self.assertEqual(self.call(first, '--check').returncode, 0)
        for kind in ('changed', 'missing', 'extra'):
            with self.subTest(kind=kind):
                probe = self.root / kind
                shutil.copytree(first, probe)
                if kind == 'changed':
                    (probe / 'scripts/tool.py').write_bytes(b'edited')
                elif kind == 'missing':
                    (probe / 'README.md').unlink()
                else:
                    (probe / 'extra.txt').write_bytes(b'private')
                before = self.contents(probe)
                checked = self.call(probe, '--check')
                self.assertNotEqual(checked.returncode, 0, checked.stdout)
                self.assertEqual(self.contents(probe), before, 'check must be read-only')

    def test_unknown_source_content_is_rejected_before_output(self):
        (self.source / 'private.txt').write_bytes(b'not package content')
        output = self.root / 'output'
        result = self.call(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
