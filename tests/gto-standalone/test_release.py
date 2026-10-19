import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class ReleaseTest(unittest.TestCase):
    def test_zip_contains_exact_verified_package_and_is_reproducible(self):
        builder = ROOT / 'skills/gto-standalone/build_release.py'
        self.assertTrue(builder.is_file(), 'distribution requires a reproducible export entrypoint')
        spec = importlib.util.spec_from_file_location('release_builder', builder)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base = ROOT / '.tmp/gto-standalone'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            package = ROOT / 'skills/gto-standalone/global-task-orchestrator'
            first = module.build(package, Path(folder) / 'one')
            second = module.build(package, Path(folder) / 'two')
            archive = Path(first['archive'])
            self.assertEqual(archive.read_bytes(), Path(second['archive']).read_bytes())
            manifest = json.loads(Path(first['manifest']).read_text(encoding='utf-8'))
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(set(zipped.namelist()), {'global-task-orchestrator/' + p for p in manifest['files']})
                self.assertIn('global-task-orchestrator/scripts/doctor.py', zipped.namelist())
                import hashlib
                for path, digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(zipped.read('global-task-orchestrator/' + path)).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
