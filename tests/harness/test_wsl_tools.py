"""Red contract for the fixed Ubuntu WSL developer-tool baseline.

This suite deliberately inspects the live PATH.  It must make a missing Linux
tool, or a Windows executable leaking into the Node toolchain, obvious before a
bootstrap/doctor change is declared complete.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
DOCTOR_PATH = SCRIPTS_ROOT / "doctor-core.py"
PROVISION_PATH = SCRIPTS_ROOT / "provision-wsl.py"
BASELINE_PATH = REPO_ROOT / "config/ai/wsl-tool-baseline.json"

# Ubuntu's fd-find package exposes ``fdfind``.  A separately installed ``fd``
# is compatible, but is not required when fdfind is available.
REQUIRED_COMMANDS = (
    "bwrap",
    "jq",
    "unzip",
    "zip",
    "tree",
    "strace",
    "shellcheck",
    "shfmt",
    "fzf",
    "sqlite3",
    "dos2unix",
    "gcc",
    "g++",
    "make",
    "pkg-config",
    "cmake",
    "ninja",
    "pip3",
    "pnpm",
)
NODE_TOOLCHAIN_COMMANDS = ("node", "npm", "pnpm")
DOCTOR_AUDIT_KEY = "wsl_tool_audit"


def command_path(command: str) -> str | None:
    located = shutil.which(command)
    if not located:
        return None
    try:
        return str(Path(located).resolve())
    except OSError:
        return located


def is_windows_backed(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith("/mnt/c/") or "/program files/" in normalized


def load_doctor():
    spec = importlib.util.spec_from_file_location("ai_harness_doctor_core", DOCTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load doctor: {DOCTOR_PATH}")
    sys.path.insert(0, str(SCRIPTS_ROOT))
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def parse_json_output(test_case: unittest.TestCase, completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        test_case.fail(f"CLI must return JSON instead of parser/import output: {completed.stderr or completed.stdout!r}; {error}")
    test_case.assertIsInstance(payload, dict, payload)
    return payload


class WslToolBaselineTests(unittest.TestCase):
    def test_current_machine_has_the_fixed_ubuntu_wsl_baseline(self) -> None:
        missing = [command for command in REQUIRED_COMMANDS if command_path(command) is None]
        fd_path = command_path("fd")
        fdfind_path = command_path("fdfind")
        if fd_path is None and fdfind_path is None:
            missing.append("fd/fdfind (Ubuntu fd-find supplies fdfind; fd is compatible)")

        node_paths = {command: command_path(command) for command in NODE_TOOLCHAIN_COMMANDS}
        missing.extend(command for command, path in node_paths.items() if path is None)
        windows_backed = {command: path for command, path in node_paths.items() if path and is_windows_backed(path)}

        # Keep all live-machine evidence in one failure.  In particular, a
        # missing baseline must not hide a Windows-provided pnpm from the
        # implementation task's diagnostic output.
        unique_missing = list(dict.fromkeys(missing))
        problems: list[str] = []
        if unique_missing:
            problems.append("missing fixed Ubuntu WSL tools: " + ", ".join(unique_missing))
        if windows_backed:
            problems.append(
                "Node toolchain must be Linux-native, not /mnt/c or Windows Program Files: " + repr(windows_backed)
            )
        self.assertEqual([], problems, " | ".join(problems))

    def test_doctor_exposes_the_exact_wsl_tool_audit_contract(self) -> None:
        doctor = load_doctor()
        with tempfile.TemporaryDirectory(prefix="ai-harness-wsl-tool-doctor-") as raw:
            payload = doctor.audit(REPO_ROOT, Path(raw) / "codex-home")

        self.assertIn(
            DOCTOR_AUDIT_KEY,
            payload,
            f"doctor must expose {DOCTOR_AUDIT_KEY} so the fixed WSL tool baseline is auditable",
        )
        audit = payload[DOCTOR_AUDIT_KEY]
        for field in ("ok", "tools", "missing_tools", "windows_path_tools", "fd_compatibility"):
            self.assertIn(field, audit, f"WSL tool audit must expose {field}")

        tools = audit["tools"]
        self.assertIsInstance(tools, list, "WSL tool audit tools must be a list")
        by_id = {item.get("id"): item for item in tools if isinstance(item, dict)}
        expected_ids = set(REQUIRED_COMMANDS) | {"fdfind", *NODE_TOOLCHAIN_COMMANDS}
        self.assertEqual(expected_ids, set(by_id), "doctor must audit exactly the fixed Ubuntu WSL baseline")
        for command, item in by_id.items():
            for field in ("available", "path", "linux_native"):
                self.assertIn(field, item, f"doctor tool entry {command} must expose {field}")

    def test_doctor_uses_explicit_baseline_instead_of_hardcoded_tool_list(self) -> None:
        # Break caught: a changed declared baseline is ignored when doctor keeps
        # auditing a stale production tuple instead of the supplied contract.
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-baseline-", dir="/tmp") as raw:
            root = Path(raw)
            bin_root = root / "bin"
            bin_root.mkdir()
            tool = bin_root / "fixture-tool"
            tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": [{"id": "developer", "packages": [{"name": "fixture-tool", "source": "apt", "command": "fixture-tool"}]}],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(DOCTOR_PATH), "--repo-root", str(REPO_ROOT), "--codex-home", str(root / "codex"), "--baseline", str(baseline), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PATH": f"{bin_root}:{os.environ.get('PATH', '')}"},
            )
            payload = parse_json_output(self, completed)

        audit = payload.get(DOCTOR_AUDIT_KEY)
        self.assertIsInstance(audit, dict, payload)
        tools = audit.get("tools")
        self.assertEqual(["fixture-tool"], [item.get("id") for item in tools], payload)

    def test_windows_drive_detection_covers_all_drvfs_drives_and_drive_syntax(self) -> None:
        # Break caught: only treating /mnt/c as Windows lets D:/E: artifacts
        # slip into WSL tool and runtime selection undiagnosed.
        doctor = load_doctor()
        for path in ("/mnt/d/work/node", "/mnt/e/cache/esbuild", r"D:\\Tools\\node.exe", r"E:/Tools/node.exe"):
            with self.subTest(path=path):
                self.assertTrue(doctor._is_windows_backed(path), path)

    def test_doctor_accepts_only_elf_from_the_codex_wsl_bundle_on_drvfs(self) -> None:
        doctor = load_doctor()
        with tempfile.TemporaryDirectory(prefix="ai-harness-codex-wsl-", dir="/mnt/c") as raw:
            root = Path(raw)
            bundled = root / ".codex" / "bin" / "wsl" / "deadbeef" / "rg"
            bundled.parent.mkdir(parents=True)
            bundled.write_bytes(b"\x7fELFfixture")
            bundled.chmod(0o755)
            ordinary = root / "tools" / "rg"
            ordinary.parent.mkdir(parents=True)
            ordinary.write_bytes(b"\x7fELFfixture")
            ordinary.chmod(0o755)

            self.assertTrue(doctor._is_windows_backed(str(bundled)))
            self.assertTrue(doctor._is_linux_native_command_path(str(bundled)))
            self.assertFalse(doctor._is_linux_native_command_path(str(ordinary)))

            bundled.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            self.assertFalse(doctor._is_linux_native_command_path(str(bundled)))

    def test_real_baseline_covers_public_tools_without_claiming_pnpm_is_an_apt_package(self) -> None:
        # Break caught: a baseline that omits AGENTS public tools or models pnpm
        # as an unavailable apt package causes false readiness or unsafe installs.
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        packages = baseline["profiles"][0]["packages"]
        package_names = {item["name"] for item in packages}
        expected_apt_packages = {
            "git", "ripgrep", "curl", "wget", "rsync", "file", "lsof", "python3", "python3-venv", "bubblewrap",
            "nodejs", "npm", "jq", "unzip", "zip", "tree", "strace", "shellcheck", "shfmt", "fzf",
            "fd-find", "sqlite3", "dos2unix", "build-essential", "pkg-config", "cmake", "ninja-build", "python3-pip",
        }
        self.assertTrue(expected_apt_packages <= package_names, package_names)
        self.assertNotIn("pnpm", package_names, packages)
        self.assertIn("pnpm", {item["command"] for item in packages}, packages)
        by_name = {item["name"]: item for item in packages}
        self.assertIsInstance(by_name["python3-venv"].get("probe"), list, by_name["python3-venv"])
        self.assertIsInstance(by_name["build-essential"].get("probe"), list, by_name["build-essential"])
        self.assertEqual([], [item["name"] for item in packages if item.get("doctor") is False], packages)

    def test_node_25_without_corepack_keeps_linux_pnpm_required_and_audited(self) -> None:
        # Break caught: Node 25 may not ship Corepack, but pnpm remains a required
        # Linux-native tool and must not disappear from the machine doctor.
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        packages = baseline["profiles"][0]["packages"]
        baseline_commands = {
            command
            for package in packages
            for command in [package["command"], *package.get("doctor_commands", [])]
        }
        contract_failures: list[str] = []
        if "corepack" in baseline_commands:
            contract_failures.append("baseline still requires corepack")
        if "pnpm" not in baseline_commands:
            contract_failures.append("baseline no longer requires pnpm")

        with tempfile.TemporaryDirectory(prefix="ai-harness-node25-pnpm-", dir="/tmp") as raw:
            root = Path(raw)
            bin_root = root / "bin"
            bin_root.mkdir()
            for command in baseline_commands - {"corepack"}:
                executable = bin_root / command
                if command == "node":
                    executable.write_text("#!/bin/sh\necho v25.0.0\n", encoding="utf-8")
                elif command == "pnpm":
                    executable.write_text("#!/bin/sh\necho 10.0.0\n", encoding="utf-8")
                else:
                    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                executable.chmod(0o755)
            completed = subprocess.run(
                [sys.executable, str(DOCTOR_PATH), "--repo-root", str(REPO_ROOT), "--codex-home", str(root / "codex"), "--baseline", str(BASELINE_PATH), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PATH": str(bin_root), "TEMP": "/tmp", "TMP": "/tmp", "TMPDIR": "/tmp"},
            )
            payload = parse_json_output(self, completed)

        audit = payload[DOCTOR_AUDIT_KEY]
        by_id = {item["id"]: item for item in audit["tools"]}
        if not audit["ok"]:
            contract_failures.append(f"Node 25 audit is unhealthy: {audit}")
        if "corepack" in by_id:
            contract_failures.append(f"doctor still audits corepack: {by_id}")
        pnpm = by_id.get("pnpm")
        if not isinstance(pnpm, dict) or not pnpm.get("available") or not pnpm.get("linux_native"):
            contract_failures.append(f"pnpm is not Linux-native and available: {by_id}")
        self.assertEqual([], contract_failures, payload)

    def test_provision_uses_declared_probe_before_marking_shared_command_available(self) -> None:
        # Break caught: python3 and make may exist while python3 -m venv or the
        # build toolchain is broken; command presence alone is a false green.
        with tempfile.TemporaryDirectory(prefix="ai-harness-baseline-probe-", dir="/tmp") as raw:
            root = Path(raw)
            bin_root = root / "bin"
            bin_root.mkdir()
            for command in ("python3", "make"):
                executable = bin_root / command
                executable.write_text("#!/bin/sh\nexit 29\n", encoding="utf-8")
                executable.chmod(0o755)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": [
                            {
                                "id": "developer",
                                "packages": [
                                    {"name": "python3-venv", "source": "apt", "command": "python3", "probe": ["python3", "-m", "venv", "--help"]},
                                    {"name": "build-essential", "source": "apt", "command": "make", "probe": ["make", "--version"]},
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(PROVISION_PATH), "--baseline", str(baseline), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PATH": f"{bin_root}:{os.environ.get('PATH', '')}"},
            )
            payload = parse_json_output(self, completed)

        self.assertEqual(0, completed.returncode, payload)
        self.assertEqual(["build-essential", "python3-venv"], payload.get("missing_packages"), payload)

    def test_doctor_marks_present_command_unhealthy_when_its_declared_probe_fails(self) -> None:
        # Break caught: doctor cannot call a command healthy solely because it
        # resolves on PATH when the declaration's runtime probe fails.
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-probe-", dir="/tmp") as raw:
            root = Path(raw)
            bin_root = root / "bin"
            bin_root.mkdir()
            tool = bin_root / "fixture-tool"
            tool.write_text("#!/bin/sh\nif test \"$1\" = --probe; then exit 37; fi\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {"schema_version": 1, "profiles": [{"id": "developer", "packages": [{"name": "fixture-tool", "source": "apt", "command": "fixture-tool", "probe": ["fixture-tool", "--probe"]}]}]},
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(DOCTOR_PATH), "--repo-root", str(REPO_ROOT), "--codex-home", str(root / "codex"), "--baseline", str(baseline), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PATH": f"{bin_root}:{os.environ.get('PATH', '')}"},
            )
            payload = parse_json_output(self, completed)

        audit = payload[DOCTOR_AUDIT_KEY]
        self.assertFalse(audit["ok"], payload)
        self.assertIn("fixture-tool", audit["missing_tools"], payload)

    def test_doctor_rejects_windows_package_command_and_missing_doctor_commands(self) -> None:
        # Break caught: package-level checks cannot hide a Windows-backed git
        # command or call build-essential healthy when gcc/g++ are absent.
        with tempfile.TemporaryDirectory(prefix="ai-harness-mixed-baseline-", dir="/tmp") as raw:
            root = Path(raw)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": [
                            {
                                "id": "developer",
                                "packages": [
                                    {"name": "git", "source": "apt", "command": "git"},
                                    {
                                        "name": "build-essential",
                                        "source": "apt",
                                        "command": "make",
                                        "doctor_commands": ["gcc", "g++", "make"],
                                    },
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            linux_bin = root / "linux-bin"
            linux_bin.mkdir()
            for command in ("git", "gcc", "g++", "make"):
                executable = linux_bin / command
                executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                executable.chmod(0o755)
            with tempfile.TemporaryDirectory(prefix="ai-harness-git-link-", dir="/mnt/c") as mount_raw:
                mounted_git = Path(mount_raw) / "git"
                mounted_git.symlink_to(linux_bin / "git")
                completed = subprocess.run(
                    [sys.executable, str(DOCTOR_PATH), "--repo-root", str(REPO_ROOT), "--codex-home", str(root / "windows-git-codex"), "--baseline", str(baseline), "--json"],
                    text=True,
                    capture_output=True,
                    check=False,
                    env={**os.environ, "PATH": f"{mounted_git.parent}:{linux_bin}", "TEMP": "/tmp", "TMP": "/tmp", "TMPDIR": "/tmp"},
                )
                payload = parse_json_output(self, completed)
            windows_git_audit = payload[DOCTOR_AUDIT_KEY]

            missing_bin = root / "missing-build-bin"
            missing_bin.mkdir()
            for command in ("git", "make"):
                executable = missing_bin / command
                executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                executable.chmod(0o755)
            completed = subprocess.run(
                [sys.executable, str(DOCTOR_PATH), "--repo-root", str(REPO_ROOT), "--codex-home", str(root / "missing-build-codex"), "--baseline", str(baseline), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PATH": str(missing_bin), "TEMP": "/tmp", "TMP": "/tmp", "TMPDIR": "/tmp"},
            )
            payload = parse_json_output(self, completed)

        with self.subTest(condition="windows_git"):
            self.assertFalse(windows_git_audit["ok"], windows_git_audit)
            self.assertIn("git", windows_git_audit["windows_path_tools"], windows_git_audit)
        with self.subTest(condition="missing_build_commands"):
            audit = payload[DOCTOR_AUDIT_KEY]
            self.assertFalse(audit["ok"], payload)
            self.assertTrue({"gcc", "g++"} <= set(audit["missing_tools"]), payload)

    def test_external_pnpm_gap_has_actionable_handoff_in_plan_and_dry_run(self) -> None:
        # Break caught: an externally managed pnpm gap must never yield an empty plan that
        # gives users no owner, prerequisite, or next executable action.
        with tempfile.TemporaryDirectory(prefix="ai-harness-external-pnpm-gap-", dir="/tmp") as raw:
            root = Path(raw)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {"schema_version": 1, "profiles": [{"id": "developer", "packages": [{"name": "pnpm-runtime", "source": "external", "command": "pnpm", "probe": ["pnpm", "--version"]}]}]},
                ),
                encoding="utf-8",
            )
            environment = {**os.environ, "PATH": "/usr/bin:/bin"}
            for arguments in ([], ["--apply", "--dry-run"]):
                with self.subTest(arguments=arguments):
                    completed = subprocess.run(
                        [sys.executable, str(PROVISION_PATH), "--baseline", str(baseline), *arguments, "--json"],
                        text=True,
                        capture_output=True,
                        check=False,
                        env=environment,
                    )
                    payload = parse_json_output(self, completed)
                    handoff = payload.get("handoff")
                    self.assertIsInstance(handoff, dict, payload)
                    for key in ("owner", "prerequisite", "next_action"):
                        self.assertIsInstance(handoff.get(key), str, handoff)
                        self.assertTrue(handoff[key], handoff)


if __name__ == "__main__":
    unittest.main()
