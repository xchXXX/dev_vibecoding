"""Independent fixtures: no expected values come from production helpers."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class PortableCase(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".tmp" / "portable-harness"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="test-", dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def api(self, module, name):
        try:
            loaded = importlib.import_module("modules.harness." + module)
        except ModuleNotFoundError as error:
            if error.name in {"modules", "modules.harness", "modules.harness." + module}:
                self.fail("Missing frozen production interface: " + module + "." + name)
            raise
        self.assertTrue(callable(getattr(loaded, name, None)),
                        "Missing frozen production interface: " + module + "." + name)
        return getattr(loaded, name)

    def assertRejected(self, callback):
        error_type = self.api("errors", "HarnessError")
        with self.assertRaises(error_type) as caught:
            callback()
        self.assertIsInstance(caught.exception.code, str)
        self.assertTrue(caught.exception.code)
        self.assertTrue(str(caught.exception))
        return caught.exception

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def bundle(self, name="bundle", version="1.0.0", entries=None):
        """Hand-authored bundle; manifest is intentionally not built by product code."""
        directory = self.root / name
        directory.mkdir()
        if entries is None:
            entries = [("base", "home", ".ai-harness/portable/runtime/rules/example.md", b"base-v1\n"),
                       ("fix", "skills", "fix-closure-gate/SKILL.md", b"fix-v1\n")]
        records = []
        for index, (module, root, target, content) in enumerate(entries):
            source = "payload/" + str(index) + ".txt"
            self.write(name + "/" + source, content)
            records.append({"source": source, "root": root, "target": target,
                            "module": module, "sha256": hashlib.sha256(content).hexdigest()})
        manifest = {"schema_version": 1, "version": version, "source_commit": "a" * 40,
                    "modules": sorted({entry[0] for entry in entries}), "files": records,
                    "payload_files": [],
                    "dependencies": {"python": ">=3.11", "git": {"required_for": ["build", "git_workflow", "gto"]},
                                     "jsonschema": {"specifier": ">=4.10.3,<5", "required_for": ["gto"]}},
                    "build_entrypoint": "scripts/harness.py build",
                    "support_matrix": {"windows": {"status": "candidate", "session_verified": False},
                                       "linux": {"status": "candidate", "session_verified": False},
                                       "wsl": {"status": "candidate", "session_verified": False}}}
        self.save_manifest(directory, manifest)
        return directory, manifest

    @staticmethod
    def save_manifest(directory, manifest):
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def config(self):
        return {"codex_home": self.root / "用户 home", "skills_dir": self.root / "独立 skills",
                "environment": "auto"}

    @staticmethod
    def snapshot(root):
        if not root.exists():
            return {}
        return {str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob("*") if path.is_file() and not path.is_symlink()}
