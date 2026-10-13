"""Pre-switch maintenance must stop legacy publication before any writes."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("native_transition_sync", ROOT / "scripts/sync-codex.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class NativeTransitionGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = ROOT / ".tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=tmp)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "codex"
        (self.home / ".ai-harness").mkdir(parents=True)
        (self.home / ".ai-harness/windows-native-transition.hold").write_text("manual migration pending\n")
        (self.home / "AGENTS.md").write_text("user-owned sentinel\n")
        (self.home / "config.toml").write_text('model = "sentinel"\n')

    def snapshot(self):
        return {str(p.relative_to(self.home)):
                ("file", p.read_bytes(), p.stat().st_mtime_ns) if p.is_file()
                else ("directory",)
                for p in self.home.rglob("*")}

    def test_snapshot_detects_empty_directory_creation(self):
        before = self.snapshot()
        (self.home / "unexpected-empty-directory").mkdir()
        self.assertNotEqual(before, self.snapshot())

    def test_sync_api_stops_before_missing_source_validation_or_writes(self):
        before = self.snapshot()
        result = SYNC.synchronize(Path(self.temp.name) / "missing-harness", self.home)
        self.assertFalse(result["ok"])
        self.assertIn("WINDOWS_NATIVE_TRANSITION_HOLD", str(result["errors"]))
        self.assertEqual(before, self.snapshot())

    def test_bootstrap_cli_stops_before_global_agents_write(self):
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(ROOT / "scripts/bootstrap-local.py"),
            "--harness-root", str(ROOT), "--codex-home", str(self.home),
            "--force-global-agents", "--skip-sync", "--skip-rules", "--skip-doctor", "--json"],
            capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("WINDOWS_NATIVE_TRANSITION_HOLD", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_without_hold_sync_keeps_existing_validation(self):
        (self.home / ".ai-harness/windows-native-transition.hold").unlink()
        result = SYNC.synchronize(Path(self.temp.name) / "missing-harness", self.home)
        self.assertIn("managed skill source missing", str(result["errors"]))
        self.assertNotIn("WINDOWS_NATIVE_TRANSITION_HOLD", str(result))


if __name__ == "__main__":
    unittest.main()
