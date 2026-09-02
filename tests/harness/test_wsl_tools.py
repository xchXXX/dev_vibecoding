"""Red contract for the fixed Ubuntu WSL developer-tool baseline.

This suite deliberately inspects the live PATH.  It must make a missing Linux
tool, or a Windows executable leaking into the Node toolchain, obvious before a
bootstrap/doctor change is declared complete.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
DOCTOR_PATH = SCRIPTS_ROOT / "doctor-core.py"

# Ubuntu's fd-find package exposes ``fdfind``.  A separately installed ``fd``
# is compatible, but is not required when fdfind is available.
REQUIRED_COMMANDS = (
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
NODE_TOOLCHAIN_COMMANDS = ("node", "npm", "pnpm", "corepack")
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
        # missing baseline must not hide a Windows-provided corepack from the
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


if __name__ == "__main__":
    unittest.main()
