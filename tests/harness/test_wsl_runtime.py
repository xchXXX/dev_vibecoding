from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
LINUX_TOOL_COMMANDS = (
    "jq", "unzip", "zip", "tree", "strace", "shellcheck", "shfmt", "fzf",
    "sqlite3", "dos2unix", "gcc", "g++", "make", "pkg-config", "cmake", "ninja",
    "pip3", "pnpm", "node", "npm", "corepack", "fdfind",
)
STRICT_DOCTOR_CONTRACT_TESTS = (
    "tests.harness.test_pure_codex_cleanup.PureCodexRepositoryCleanupTests.test_active_truth_has_no_affirmative_retired_contracts",
    "tests.harness.test_pure_codex_cleanup.PureCodexRepositoryCleanupTests.test_active_truth_scan_does_not_exempt_mixed_affirmative_contracts",
    "tests.harness.test_control_plane.ControlPlaneContractTest.test_cli_rejects_single_dash_pascal_case_aliases",
    "tests.harness.test_control_plane.ControlPlaneContractTest.test_documented_gto_actions_and_flags_exist_in_the_real_cli",
    "tests.harness.test_control_plane.ControlPlaneContractTest.test_documented_gto_flags_are_exposed_by_the_real_parser",
    "tests.harness.test_control_plane.ControlPlaneContractTest.test_orchestrator_schema_accepts_v3_and_rejects_v2",
    "tests.harness.test_control_plane.ControlPlaneContractTest.test_current_task_templates_validate_and_use_only_active_commands",
    "tests.harness.test_command_failure_memory.CommandFailureMemoryContractTests.test_parser_rejects_single_dash_pascal_case_aliases",
    "tests.harness.test_wsl_runtime.PreDevBenchmarkEntrypointTests.test_skill_example_runs_real_repo_root_python3_entrypoint",
)


def linux_tool_environment(root: Path) -> dict[str, str]:
    bin_root = root / "linux-bin"
    bin_root.mkdir()
    for command in LINUX_TOOL_COMMANDS:
        executable = bin_root / command
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_root}:{os.environ.get('PATH', '')}"}


class WslNativeEntrypointTests(unittest.TestCase):
    ENTRYPOINTS = (
        "bootstrap-local.py",
        "sync-codex.py",
        "doctor-core.py",
        "start_session.py",
    )
    FORBIDDEN_WINDOWS_EXECUTABLES = re.compile(
        r"(?i)(?<![a-z0-9_.-])(cmd(?:\.exe)?|powershell(?:\.exe)?|pwsh(?:\.exe)?|wsl(?:\.exe)?)(?![a-z0-9_.-])"
    )

    def test_formal_codex_operations_have_python_entrypoints(self) -> None:
        missing = [name for name in self.ENTRYPOINTS if not (SCRIPTS_ROOT / name).is_file()]
        self.assertEqual([], missing, f"missing WSL Python entrypoints: {missing}")

    def test_python_normal_path_does_not_name_windows_executables(self) -> None:
        violations: dict[str, list[str]] = {}
        for name in self.ENTRYPOINTS:
            path = SCRIPTS_ROOT / name
            self.assertTrue(path.is_file(), f"missing WSL Python entrypoint: {path}")
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path))
            hits = sorted({match.group(0) for match in self.FORBIDDEN_WINDOWS_EXECUTABLES.finditer(source)})
            if hits:
                violations[name] = hits
        self.assertEqual({}, violations, f"formal WSL path names Windows executables: {violations}")


class PreDevBenchmarkEntrypointTests(unittest.TestCase):
    def test_skill_example_runs_real_repo_root_python3_entrypoint(self) -> None:
        # Break caught: the copied example points at a nonexistent short path or
        # uses PowerShell syntax that cannot be pasted from the repository root.
        skill_path = REPO_ROOT / "skills/pre-dev-benchmark/SKILL.md"
        source = skill_path.read_text(encoding="utf-8")
        expected_prefix = "python3 skills/pre-dev-benchmark/scripts/scaffold_benchmark.py"
        documentation_violations = []
        if expected_prefix not in source:
            documentation_violations.append(f"missing repository-root command: {expected_prefix}")
        if "```powershell" in source.casefold():
            documentation_violations.append("example still uses a PowerShell code fence")
        if re.search(r"(?m)^\s*python\s+scripts/scaffold_benchmark\.py\b", source):
            documentation_violations.append("example still points at scripts/scaffold_benchmark.py")

        with tempfile.TemporaryDirectory(prefix="ai-harness-benchmark-") as raw:
            output = Path(raw) / "sample"
            completed = subprocess.run(
                [
                    "python3",
                    "skills/pre-dev-benchmark/scripts/scaffold_benchmark.py",
                    "--output",
                    str(output),
                    "--slug",
                    "root-command",
                    "--title",
                    "Root command",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertEqual(
                {"benchmark-plan.md", "fixture-matrix.md", "runbook.md"},
                {path.name for path in output.iterdir()},
            )
        self.assertEqual([], documentation_violations, documentation_violations)


class CodexHookRemovalTests(unittest.TestCase):
    def test_codex_command_safety_runtime_and_installer_are_not_managed(self) -> None:
        retired_paths = (
            REPO_ROOT / "hooks/codex/command-safety",
            REPO_ROOT / "hooks/codex/scripts/PreToolUse.ps1",
            REPO_ROOT / "scripts/install-command-safety-gateway.ps1",
            REPO_ROOT / "tests/harness/command-safety-gateway.integration.ps1",
        )
        remaining = [str(path.relative_to(REPO_ROOT)) for path in retired_paths if path.exists()]
        self.assertEqual([], remaining, f"retired Codex hook surface still exists: {remaining}")

class SessionSingleControlPlaneTests(unittest.TestCase):
    def test_session_entry_resumes_existing_six_artifact_task_without_second_control_plane(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-session-") as raw:
            fixture = Path(raw)
            (fixture / "rules/registry").mkdir(parents=True)
            (fixture / "rules/registry/RULES_ENTRY.md").write_text("# fixture\n", encoding="utf-8")
            controller = fixture / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
            controller.parent.mkdir(parents=True)
            controller.write_text(
                "import json\nprint(json.dumps({'ok': True, 'task_id': 'TASK-001', "
                "'status': 'active', 'next_action': {'kind': 'dispatch_subtask'}}))\n",
                encoding="utf-8",
            )
            for root, names in (
                (fixture / "docs/ai/tasks/TASK-001", ("state.json", "task.md", "events.jsonl")),
                (fixture / "docs/tasks/TASK-001", ("plan.md", "execution.md", "acceptance.md")),
            ):
                root.mkdir(parents=True)
                for name in names:
                    (root / name).write_text("{}\n" if name.endswith((".json", ".jsonl")) else "# TASK-001\n", encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "start_session.py"), "--repo-root", str(fixture), "--task-id", "TASK-001", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertEqual("resume", payload["mode"])
            self.assertEqual("dispatch_subtask", payload["next_action"]["kind"])
            self.assertFalse((fixture / ".ai/session").exists())
            self.assertFalse((fixture / "docs/ai/runs").exists())


class BootstrapDoctorRuntimeTests(unittest.TestCase):
    def test_sync_installs_gto_schema_for_the_installed_read_only_validate_action(self) -> None:
        # Break caught: the installed controller resolves its canonical schema
        # from CODEX_HOME/schemas, but the old sync copied only skills.  A
        # source-tree validation is not evidence that the installed runtime can
        # perform the same read-only validation.
        task_id = "20260902-103736-970530-wsl-gto-tooling-hardening"
        with tempfile.TemporaryDirectory(prefix="ai-harness-installed-gto-", dir="/tmp") as raw:
            runtime_root = Path(raw)
            codex_home = runtime_root / "codex"
            fixture_repo = runtime_root / "fixture-repo"
            for relative in (
                f"docs/ai/tasks/{task_id}/state.json",
                f"docs/ai/tasks/{task_id}/task.md",
                f"docs/ai/tasks/{task_id}/events.jsonl",
                f"docs/tasks/{task_id}/plan.md",
                f"docs/tasks/{task_id}/execution.md",
                f"docs/tasks/{task_id}/acceptance.md",
            ):
                source = REPO_ROOT / relative
                target = fixture_repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            source_validate = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"),
                    "--action", "validate", "--repo-root", str(fixture_repo), "--task-id", task_id, "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, source_validate.returncode, source_validate.stderr or source_validate.stdout)

            synced = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "sync-codex.py"), "--repo-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, synced.returncode, synced.stderr or synced.stdout)

            installed_validate = subprocess.run(
                [
                    sys.executable,
                    str(codex_home / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"),
                    "--action", "validate", "--repo-root", str(fixture_repo), "--task-id", task_id, "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, installed_validate.returncode, installed_validate.stderr or installed_validate.stdout)
        installed_payload = json.loads(installed_validate.stdout)
        self.assertTrue(installed_payload["ok"], installed_payload)

    def test_bootstrap_reports_restart_when_managed_runtime_content_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-restart-required-", dir="/tmp") as raw:
            environment = linux_tool_environment(Path(raw))
            codex_home = Path(raw) / "codex"

            def bootstrap() -> dict[str, object]:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS_ROOT / "bootstrap-local.py"),
                        "--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home),
                        "--skip-rules", "--skip-doctor", "--json",
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=environment,
                )
                self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
                return json.loads(completed.stdout)

            initial = bootstrap()
            self.assertTrue(initial["restart_required"], initial)
            self.assertIn("managed_global_agents_changed", initial["restart_reasons"])
            self.assertIn("managed_skill_runtime_changed", initial["restart_reasons"])
            self.assertIn("managed_schema_runtime_changed", initial["restart_reasons"])

            unchanged = bootstrap()
            self.assertFalse(unchanged["restart_required"], unchanged)
            self.assertEqual([], unchanged["restart_reasons"])

            (codex_home / "AGENTS.md").write_text(
                "<!-- ai-harness:managed-global-agents:v1 -->\nstale managed entry\n",
                encoding="utf-8",
            )
            agents_changed = bootstrap()
            self.assertTrue(agents_changed["restart_required"], agents_changed)
            self.assertEqual(["managed_global_agents_changed"], agents_changed["restart_reasons"])

            schema_target = codex_home / "schemas/orchestrator-task-state.schema.json"
            schema_target.write_text("{}\n", encoding="utf-8")
            schema_changed = bootstrap()
            self.assertTrue(schema_changed["restart_required"], schema_changed)
            self.assertEqual(["managed_schema_runtime_changed"], schema_changed["restart_reasons"])

            skill_target = codex_home / "skills/global-task-orchestrator/SKILL.md"
            skill_target.write_text("stale skill\n", encoding="utf-8")
            skill_changed = bootstrap()
            self.assertTrue(skill_changed["restart_required"], skill_changed)
            self.assertEqual(["managed_skill_runtime_changed"], skill_changed["restart_reasons"])

    def test_strict_doctor_runs_the_fixed_non_recursive_contract_gate(self) -> None:
        # Break caught: strict doctor reports only runtime/tool health and lets
        # the active-truth, GTO, CFM, schema, template, or benchmark contracts
        # drift because the focused repository gates were not actually run.
        with tempfile.TemporaryDirectory(prefix="ai-harness-contract-gate-", dir="/tmp") as raw:
            environment = linux_tool_environment(Path(raw))
            codex_home = Path(raw) / "codex"
            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_ROOT / "bootstrap-local.py"),
                    "--harness-root",
                    str(REPO_ROOT),
                    "--codex-home",
                    str(codex_home),
                    "--skip-rules",
                    "--skip-doctor",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(0, bootstrap.returncode, bootstrap.stderr or bootstrap.stdout)

            doctor = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_ROOT / "doctor-core.py"),
                    "--repo-root",
                    str(REPO_ROOT),
                    "--codex-home",
                    str(codex_home),
                    "--strict",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )

        self.assertEqual(0, doctor.returncode, doctor.stderr or doctor.stdout)
        payload = json.loads(doctor.stdout)
        self.assertIn("contract_gate", payload, payload)
        contract_gate = payload["contract_gate"]
        self.assertEqual(list(STRICT_DOCTOR_CONTRACT_TESTS), contract_gate["tests"])
        self.assertEqual(len(STRICT_DOCTOR_CONTRACT_TESTS), contract_gate["test_count"])
        self.assertEqual(0, contract_gate["returncode"])
        self.assertTrue(contract_gate["ok"], contract_gate)
        self.assertTrue(payload["codex_audit"]["schemas"][0]["ok"], payload)
        installed_gto = payload["codex_audit"]["installed_gto_validation"]
        self.assertTrue(installed_gto["ok"], installed_gto)
        self.assertEqual("validate", installed_gto["action"])

    def test_bootstrap_clears_all_hooks_and_preserves_non_hook_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-bootstrap-", dir="/tmp") as raw:
            environment = linux_tool_environment(Path(raw))
            codex_home = Path(raw) / "codex"
            codex_home.mkdir()
            hooks_path = codex_home / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "custom_top_level": {"preserve": True},
                        "hooks": {
                            "PreToolUse": [{"id": "user.custom", "command": "keep"}],
                            "PostToolUse": [{"id": "user.post", "command": "keep-post"}],
                        },
                    }
                ) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_ROOT / "bootstrap-local.py"),
                    "--harness-root",
                    str(REPO_ROOT),
                    "--codex-home",
                    str(codex_home),
                    "--skip-rules",
                    "--skip-doctor",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertIn("hook_cleanup", payload["completed_steps"])
            self.assertIn("hooks_cleared", payload)
            self.assertTrue(payload["hooks_cleared"])
            remaining = json.loads(hooks_path.read_text(encoding="utf-8"))
            self.assertEqual({"preserve": True}, remaining["custom_top_level"])
            self.assertEqual({}, remaining["hooks"])

            doctor = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--root", str(REPO_ROOT), "--codex-home", str(codex_home), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(0, doctor.returncode, doctor.stderr or doctor.stdout)
            audit = json.loads(doctor.stdout)
            self.assertTrue(audit["codex_audit"]["bootstrap"]["ok"], audit)
            self.assertTrue(audit["codex_audit"]["hooks"]["ok"], audit)

    def test_strict_doctor_rejects_any_hook_in_user_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-") as raw:
            codex_home = Path(raw) / "codex"
            bootstrap = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "bootstrap-local.py"), "--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, bootstrap.returncode, bootstrap.stderr or bootstrap.stdout)
            (codex_home / "config.toml").write_text(
                'post_completion_hook = "/usr/local/bin/user-callback"\n', encoding="utf-8"
            )
            doctor = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--root", str(REPO_ROOT), "--codex-home", str(codex_home), "--strict", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, doctor.returncode, doctor.stdout)
            audit = json.loads(doctor.stdout)
            self.assertIn("hook_configuration_present", audit["errors"])

    def test_strict_doctor_rejects_any_residual_hooks_json_entry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-") as raw:
            codex_home = Path(raw) / "codex"
            bootstrap = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "bootstrap-local.py"), "--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, bootstrap.returncode, bootstrap.stderr or bootstrap.stdout)
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"PostToolUse": [{"id": "user.callback", "command": "notify"}]}}) + "\n",
                encoding="utf-8",
            )

            doctor = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--root", str(REPO_ROOT), "--codex-home", str(codex_home), "--strict", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(0, doctor.returncode, doctor.stdout)
        audit = json.loads(doctor.stdout)
        self.assertIn("hook_configuration_present", audit["errors"])


if __name__ == "__main__":
    unittest.main()
