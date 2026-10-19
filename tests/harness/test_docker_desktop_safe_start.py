from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "modules/wsl-environment/tooling/docker-desktop-safe-start.ps1"
POWERSHELL = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
DOCTOR_CORE = REPO_ROOT / "scripts/doctor-core.py"


def windows_path(path: Path) -> str:
    completed = subprocess.run(
        ["wslpath", "-w", str(path)],
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def load_doctor_core():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("doctor_core", DOCTOR_CORE)
    if spec is None or spec.loader is None:
        raise AssertionError("doctor-core.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DockerDesktopSafeStartTests(unittest.TestCase):
    maxDiff = None

    def run_repair(self, local_app_data: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        self.assertTrue(POWERSHELL.is_file(), "Windows PowerShell is required for this Windows boundary test")
        self.assertTrue(
            SCRIPT.is_file(),
            "missing modules/wsl-environment/tooling/docker-desktop-safe-start.ps1",
        )
        completed = subprocess.run(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                windows_path(SCRIPT),
                "-Action",
                "RepairOnly",
                "-LocalAppDataRoot",
                windows_path(local_app_data),
                "-Json",
            ],
            text=True,
            errors="replace",
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(
                f"safe-start must emit one JSON object; stdout={completed.stdout!r}; stderr={completed.stderr!r}"
            ) from error
        self.assertIsInstance(payload, dict)
        return completed, payload

    def test_repair_only_rotates_known_zero_byte_socket_directories_and_preserves_backups(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-docker-safe-start-", dir="/mnt/c") as raw:
            root = Path(raw)
            run_dir = root / "Docker/run"
            secrets_dir = root / "docker-secrets-engine"
            run_dir.mkdir(parents=True)
            secrets_dir.mkdir(parents=True)
            for name in ("dockerEthernetVfkit", "dockerInference", "sailor-ingest.sock", "userAnalyticsOtlpHttp.sock"):
                (run_dir / name).touch()
            (secrets_dir / "engine.sock").touch()

            completed, payload = self.run_repair(root)

            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertTrue(payload.get("ok"), payload)
            self.assertTrue(payload.get("repaired"), payload)
            repairs = payload.get("repairs")
            self.assertIsInstance(repairs, list, payload)
            self.assertEqual(2, len(repairs), payload)
            self.assertEqual([], list(run_dir.iterdir()))
            self.assertEqual([], list(secrets_dir.iterdir()))
            backup_paths = [Path(str(item["backup_path"]).replace("\\", "/").replace("C:/", "/mnt/c/")) for item in repairs]
            backup_names = {path.name for path in backup_paths}
            self.assertTrue(any(name.startswith("run.stale-") for name in backup_names), backup_names)
            self.assertTrue(any(name.startswith("docker-secrets-engine.stale-") for name in backup_names), backup_names)
            preserved = {
                path.name
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(
                {"dockerEthernetVfkit", "dockerInference", "sailor-ingest.sock", "userAnalyticsOtlpHttp.sock", "engine.sock"},
                preserved,
            )

    def test_repair_only_fails_closed_on_unknown_or_nonzero_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-docker-safe-start-", dir="/mnt/c") as raw:
            root = Path(raw)
            run_dir = root / "Docker/run"
            run_dir.mkdir(parents=True)
            unknown = run_dir / "do-not-touch.txt"
            unknown.write_text("important", encoding="utf-8")

            completed, payload = self.run_repair(root)

            self.assertNotEqual(0, completed.returncode, payload)
            self.assertFalse(payload.get("ok"), payload)
            self.assertEqual("unsafe_directory_content", payload.get("error", {}).get("category"), payload)
            self.assertEqual("important", unknown.read_text(encoding="utf-8"))
            self.assertTrue(run_dir.is_dir())
            self.assertEqual([], list((root / "Docker").glob("run.stale-*")))

    def test_repair_only_is_a_noop_for_empty_directories(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-docker-safe-start-", dir="/mnt/c") as raw:
            root = Path(raw)
            (root / "Docker/run").mkdir(parents=True)
            (root / "docker-secrets-engine").mkdir(parents=True)

            completed, payload = self.run_repair(root)

            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertTrue(payload.get("ok"), payload)
            self.assertFalse(payload.get("repaired"), payload)
            self.assertEqual([], payload.get("repairs"), payload)
            self.assertEqual([], list(root.rglob("*.stale-*")))

    def test_status_resolves_a_per_user_docker_desktop_install(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-docker-safe-start-", dir="/mnt/c") as raw:
            root = Path(raw)
            cli = root / "Programs/DockerDesktop/resources/bin/docker.exe"
            desktop = root / "Programs/DockerDesktop/Docker Desktop.exe"
            cli.parent.mkdir(parents=True)
            cli.touch()
            desktop.touch()
            completed = subprocess.run(
                [
                    str(POWERSHELL),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    windows_path(SCRIPT),
                    "-Action",
                    "Status",
                    "-LocalAppDataRoot",
                    windows_path(root),
                    "-CodexHome",
                    windows_path(root / "codex"),
                    "-TaskName",
                    "AI Harness Docker Safe Start Fixture Missing",
                    "-Json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(windows_path(cli), payload.get("docker_cli_path"), payload)
            self.assertEqual(windows_path(desktop), payload.get("docker_desktop_path"), payload)
            self.assertTrue(payload.get("docker_cli_exists"), payload)
            self.assertTrue(payload.get("docker_desktop_exists"), payload)

    def test_machine_doctor_treats_missing_safe_start_as_optional_but_detects_installed_drift(self) -> None:
        doctor = load_doctor_core()
        with tempfile.TemporaryDirectory(prefix="ai-harness-docker-doctor-") as raw:
            codex_home = Path(raw) / "codex"
            missing = doctor._docker_safe_start_audit(REPO_ROOT, codex_home)
            self.assertTrue(missing["ok"], missing)
            self.assertFalse(missing["installed"], missing)
            self.assertEqual([], missing["issues"], missing)

            installed = codex_home / ".ai-harness/runtime/windows-external/docker-desktop-safe-start.ps1"
            installed.parent.mkdir(parents=True)
            installed.write_bytes(SCRIPT.read_bytes())
            receipt_path = codex_home / ".ai-harness/docker-safe-start.receipt.json"
            source_hash = doctor.sha256_file(SCRIPT)
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_relative_path": "modules/wsl-environment/tooling/docker-desktop-safe-start.ps1",
                        "installed_relative_path": ".ai-harness/runtime/windows-external/docker-desktop-safe-start.ps1",
                        "source_sha256": source_hash,
                        "installed_sha256": source_hash,
                        "task_name": "AI Harness Docker Safe Start",
                        "task_registered": False,
                        "startup_entry_name": "AI Harness Docker Safe Start",
                        "startup_entry_registered": True,
                        "startup_entry_mode": "hkcu_run",
                    }
                ),
                encoding="utf-8",
            )
            healthy = doctor._docker_safe_start_audit(REPO_ROOT, codex_home)
            self.assertTrue(healthy["ok"], healthy)
            self.assertTrue(healthy["installed"], healthy)

            installed.write_text("tampered", encoding="utf-8")
            drifted = doctor._docker_safe_start_audit(REPO_ROOT, codex_home)
            self.assertFalse(drifted["ok"], drifted)
            self.assertIn("docker_safe_start_hash_mismatch", {item["type"] for item in drifted["issues"]})


if __name__ == "__main__":
    unittest.main()
