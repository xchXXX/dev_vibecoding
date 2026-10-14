from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
GTO_ROOT = REPO_ROOT / "skills/global-task-orchestrator"
LINUX_TOOL_COMMANDS = (
    "git", "rg", "curl", "wget", "rsync", "file", "lsof", "python3",
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
    temp_root = root / "linux-tmp"
    temp_root.mkdir()
    for command in LINUX_TOOL_COMMANDS:
        executable = bin_root / command
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_root}:{os.environ.get('PATH', '')}",
        "TEMP": str(temp_root),
        "TMP": str(temp_root),
        "TMPDIR": str(temp_root),
    }


def configure_native_plugins(codex_home: Path) -> None:
    codex_home.mkdir(parents=True, exist_ok=True)
    config = codex_home / "config.toml"
    with config.open("a", encoding="utf-8") as handle:
        for name in ("browser@openai-bundled", "unified-computer-use@openai-bundled", "computer-use@openai-bundled"):
            handle.write(f'\n[plugins."{name}"]\nenabled = true\n')


class WslNativeEntrypointTests(unittest.TestCase):
    ENTRYPOINTS = (
        SCRIPTS_ROOT / "bootstrap-local.py",
        SCRIPTS_ROOT / "sync-codex.py",
        SCRIPTS_ROOT / "doctor-core.py",
        GTO_ROOT / "scripts/start_session.py",
    )
    FORBIDDEN_WINDOWS_EXECUTABLES = re.compile(
        r"(?i)(?<![a-z0-9_./-])(cmd(?:\.exe)?|powershell(?:\.exe)?|pwsh(?:\.exe)?|wsl(?:\.exe)?)(?![a-z0-9_./-])"
    )

    def test_formal_codex_operations_have_python_entrypoints(self) -> None:
        missing = [str(path.relative_to(REPO_ROOT)) for path in self.ENTRYPOINTS if not path.is_file()]
        self.assertEqual([], missing, f"missing WSL Python entrypoints: {missing}")
        self.assertFalse((SCRIPTS_ROOT / "start_session.py").exists(), "retired root session bridge must stay absent")

    @staticmethod
    def executable_text(source: str) -> str:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                node.value = ast.Constant(value="")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {
                "ArgumentParser", "add_argument", "add_subparsers", "add_parser"
            }:
                for keyword in node.keywords:
                    if keyword.arg in {"help", "description", "epilog"} and isinstance(keyword.value, ast.Constant):
                        keyword.value = ast.Constant(value="")
        return ast.unparse(tree)

    def test_python_normal_path_does_not_name_windows_executables(self) -> None:
        for executable in ("cmd.exe", "powershell.exe", "pwsh", "wsl"):
            self.assertIsNotNone(self.FORBIDDEN_WINDOWS_EXECUTABLES.search(
                self.executable_text(f'subprocess.run(["{executable}", "argument"])')))
        documentation = '\"\"\"WSL runtime.\"\"\"\n# powershell.exe is retired\nparser.add_argument("--option", help="WSL GUI skill")'
        self.assertIsNone(self.FORBIDDEN_WINDOWS_EXECUTABLES.search(self.executable_text(documentation)))
        self.assertIsNone(self.FORBIDDEN_WINDOWS_EXECUTABLES.search("/home/user/.codex/bin/wsl/deadbeef/rg"))
        violations: dict[str, list[str]] = {}
        for path in self.ENTRYPOINTS:
            self.assertTrue(path.is_file(), f"missing WSL Python entrypoint: {path}")
            source = path.read_text(encoding="utf-8")
            code = self.executable_text(source)
            hits = sorted({match.group(0) for match in self.FORBIDDEN_WINDOWS_EXECUTABLES.finditer(code)})
            if hits:
                violations[path.relative_to(REPO_ROOT).as_posix()] = hits
        self.assertEqual({}, violations, f"formal WSL path names Windows executables: {violations}")


class PreDevBenchmarkEntrypointTests(unittest.TestCase):
    def test_skill_example_runs_real_repo_root_python3_entrypoint(self) -> None:
        # Keep the fixed doctor's public test ID, but exercise the portable
        # command from a consumer directory with a separately installed skill.
        skill_path = REPO_ROOT / "skills/pre-dev-benchmark/SKILL.md"
        source = skill_path.read_text(encoding="utf-8")
        expected_prefix = 'python "<实际技能目录>/scripts/scaffold_benchmark.py"'
        documentation_violations = []
        if expected_prefix not in source:
            documentation_violations.append(f"missing self-contained skill command: {expected_prefix}")
        if "```powershell" in source.casefold():
            documentation_violations.append("example still uses a PowerShell code fence")
        if re.search(r"(?m)^\s*python\s+scripts/scaffold_benchmark\.py\b", source):
            documentation_violations.append("example still points at scripts/scaffold_benchmark.py")

        scratch = REPO_ROOT / ".tmp/portable-harness"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai-harness-benchmark-", dir=scratch) as raw:
            installed = Path(raw) / "installed-skills/pre-dev-benchmark"
            shutil.copytree(skill_path.parent, installed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            consumer = Path(raw) / "consumer"
            consumer.mkdir()
            output = consumer / ".tmp/sample"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(installed / "scripts/scaffold_benchmark.py"),
                    "--output",
                    str(output),
                    "--slug",
                    "root-command",
                    "--title",
                    "Root command",
                ],
                cwd=consumer,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertEqual(
                {"benchmark-plan.md", "fixture-matrix.md", "runbook.md"},
                {path.name for path in output.iterdir()},
            )
            for path in output.iterdir():
                self.assertIn("Root command", path.read_text(encoding="utf-8"))
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
    def setUp(self) -> None:
        (REPO_ROOT / '.tmp').mkdir(exist_ok=True)

    def test_session_entry_resumes_existing_six_artifact_task_without_second_control_plane(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-session-", dir=REPO_ROOT / ".tmp") as raw:
            fixture = Path(raw)
            task_id = "20300102-030405-example-task"
            contract_path = fixture / '.tmp/contract.json'
            contract_path.parent.mkdir(parents=True)
            shutil.copyfile(GTO_ROOT / 'references/revision-3-contract.example.json', contract_path)
            initialized = subprocess.run([
                sys.executable, str(GTO_ROOT / "scripts/orchestrator_ctl.py"), "--action", "init-task",
                "--repo-root", str(fixture), "--task-id", task_id, "--title", "Session resume fixture",
                "--owner", "coordinator", "--contract-json-file",
                str(contract_path), "--json"],
                text=True, capture_output=True, check=False)
            self.assertEqual(0, initialized.returncode, initialized.stderr or initialized.stdout)
            artifacts = [path for path in (fixture / "docs").rglob("*")
                         if path.is_file() and path.name != ".control.lock"]
            self.assertEqual(6, len(artifacts))
            before = {path.relative_to(fixture).as_posix(): path.read_bytes() for path in artifacts}
            state = json.loads((fixture / f"docs/ai/tasks/{task_id}/state.json").read_text())
            completed = subprocess.run(
                [sys.executable, str(GTO_ROOT / "scripts/start_session.py"), "--repo-root", str(fixture),
                 "--task-id", task_id, "--json"], cwd=fixture, text=True, capture_output=True, check=False)
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertEqual("resume", payload["mode"])
            self.assertEqual(state["next_action"], payload["next_action"])
            self.assertEqual(before, {path.relative_to(fixture).as_posix(): path.read_bytes() for path in artifacts})
            self.assertFalse((fixture / "skills").exists())
            self.assertFalse((fixture / ".ai/session").exists())
            self.assertFalse((fixture / "docs/ai/runs").exists())


class BootstrapDoctorRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        (REPO_ROOT / '.tmp').mkdir(exist_ok=True)

    def test_installed_gto_validation_keeps_contract_in_consumer_tmp_and_runs_installed_controller(self) -> None:
        # Break caught: doctor wrote the init contract beside the temporary
        # consumer project, so the source controller rejected it before the
        # installed controller could perform validate.
        self.maxDiff = None
        spec = importlib.util.spec_from_file_location("a2pt_doctor", SCRIPTS_ROOT / "doctor-core.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        doctor = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(SCRIPTS_ROOT), *sys.path]):
            spec.loader.exec_module(doctor)

        with tempfile.TemporaryDirectory(prefix="a2pt-installed-gto-", dir=REPO_ROOT / ".tmp") as raw:
            runtime_root = Path(raw)
            codex_home = runtime_root / "codex"
            installed_skill = codex_home / "skills/global-task-orchestrator"
            shutil.copytree(GTO_ROOT, installed_skill)
            installed_controller = installed_skill / "scripts/orchestrator_ctl.py"
            installed_real = installed_controller.with_name("orchestrator_ctl.installed.py")
            installed_controller.rename(installed_real)
            marker = runtime_root / "installed-validate.marker"
            installed_controller.write_text(
                "import os\n"
                "import sys\n"
                "from pathlib import Path\n"
                "if '--action' in sys.argv and sys.argv[sys.argv.index('--action') + 1] == 'validate':\n"
                "    Path(os.environ['A2PT_INSTALLED_VALIDATE_MARKER']).write_text('validate\\n', encoding='utf-8')\n"
                f"os.execv(sys.executable, [sys.executable, {str(installed_real)!r}, *sys.argv[1:]])\n",
                encoding="utf-8",
            )
            consumer_root = runtime_root / "consumer"
            consumer_root.mkdir()
            with (
                patch.object(doctor.tempfile, "TemporaryDirectory", return_value=nullcontext(str(consumer_root))),
                patch.dict(os.environ, {"A2PT_INSTALLED_VALIDATE_MARKER": str(marker)}),
            ):
                result = doctor._installed_gto_validation(REPO_ROOT, codex_home)

            task_id = "DOCTOR-001"
            actual = {
                "ok": result["ok"],
                "returncode": result["returncode"],
                "controller_path": result["controller_path"],
                "contract_in_consumer_tmp": len(list((consumer_root / ".tmp").rglob("*.json")))
                if (consumer_root / ".tmp").is_dir()
                else 0,
                "contract_at_consumer_root": (consumer_root / "contract.json").is_file(),
                "source_init_state_created": (
                    consumer_root / f"docs/ai/tasks/{task_id}/state.json"
                ).is_file(),
                "installed_validate_marker": marker.is_file(),
            }
            expected = {
                "ok": True,
                "returncode": 0,
                "controller_path": str(installed_controller),
                "contract_in_consumer_tmp": 1,
                "contract_at_consumer_root": False,
                "source_init_state_created": True,
                "installed_validate_marker": True,
            }
            self.assertEqual(expected, actual, result)
            probe_contract = json.loads((consumer_root / '.tmp/contract.json').read_text())
            packaged_contract = json.loads((GTO_ROOT / 'references/revision-3-contract.example.json').read_text())
            self.assertEqual(packaged_contract, probe_contract)
            self.assertEqual(3, probe_contract['workflow_revision'])

    def test_sync_installs_gto_schema_for_the_installed_read_only_validate_action(self) -> None:
        # Break caught: package schema must be owned by the skill receipt and
        # reachable from the installed controller. Source-tree validation alone
        # is not evidence that the installed runtime can
        # perform the same read-only validation.
        task_id = "20300102-030405-installed-gto"
        with tempfile.TemporaryDirectory(prefix="ai-harness-installed-gto-", dir="/tmp") as raw:
            runtime_root = Path(raw)
            codex_home = runtime_root / "codex"
            fixture_repo = runtime_root / "fixture-repo"
            contract_path = fixture_repo / '.tmp/contract.json'
            contract_path.parent.mkdir(parents=True)
            shutil.copyfile(GTO_ROOT / 'references/revision-3-contract.example.json', contract_path)
            initialized = subprocess.run([
                sys.executable, str(GTO_ROOT / 'scripts/orchestrator_ctl.py'), '--action', 'init-task',
                '--repo-root', str(fixture_repo), '--task-id', task_id, '--title', 'Installed validation',
                '--owner', 'test-fixture', '--contract-json-file', str(contract_path), '--json',
            ], text=True, capture_output=True, check=False)
            self.assertEqual(0, initialized.returncode, initialized.stderr or initialized.stdout)

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
        scratch = REPO_ROOT / ".tmp/portable-harness"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai-harness-restart-required-", dir=scratch) as raw:
            environment = linux_tool_environment(Path(raw))
            codex_home = Path(raw) / "codex"
            source_root = Path(raw) / "source"
            for relative in ("skills", "config/ai", "schemas"):
                shutil.copytree(REPO_ROOT / relative, source_root / relative,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for relative in ("templates/codex/AGENTS.global.md", "rules/registry/RULES_ENTRY.md",
                             "scripts/provision-wsl.py", "scripts/project-env-doctor.py",
                             "scripts/resolve-wsl-path.py", "scripts/doctor-core.py", "scripts/runtime_common.py"):
                target = source_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / relative, target)
            schema_relative = "skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json"
            schema_source = source_root / schema_relative
            current_schema = schema_source.read_bytes()
            previous_schema = json.loads(current_schema)
            previous_schema["$comment"] = "Synthetic previous managed release with the same valid schema."
            schema_source.write_text(json.dumps(previous_schema), encoding="utf-8")
            skill_source = source_root / "skills/global-task-orchestrator/SKILL.md"
            current_skill = skill_source.read_bytes()
            skill_source.write_bytes(current_skill + b"\n<!-- Synthetic previous managed release. -->\n")

            def bootstrap() -> dict[str, object]:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS_ROOT / "bootstrap-local.py"),
                        "--harness-root", str(source_root), "--codex-home", str(codex_home),
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
            self.assertNotIn("managed_schema_runtime_changed", initial["restart_reasons"])

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

            schema_target = codex_home / "skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json"
            self.assertEqual(schema_source.read_bytes(), schema_target.read_bytes())
            schema_source.write_bytes(current_schema)
            schema_changed = bootstrap()
            self.assertTrue(schema_changed["restart_required"], schema_changed)
            self.assertEqual(["managed_skill_runtime_changed"], schema_changed["restart_reasons"])
            self.assertEqual(
                current_schema,
                schema_target.read_bytes(),
            )

            skill_target = codex_home / "skills/global-task-orchestrator/SKILL.md"
            self.assertEqual(skill_source.read_bytes(), skill_target.read_bytes())
            skill_source.write_bytes(current_skill)
            skill_changed = bootstrap()
            self.assertTrue(skill_changed["restart_required"], skill_changed)
            self.assertEqual(["managed_skill_runtime_changed"], skill_changed["restart_reasons"])
            self.assertEqual(current_skill, skill_target.read_bytes())

    def test_bootstrap_rejects_tampered_managed_schema_and_skill_without_overwrite(self) -> None:
        scratch = REPO_ROOT / ".tmp/portable-harness"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai-harness-tamper-", dir=scratch) as raw:
            environment = linux_tool_environment(Path(raw))
            codex_home = Path(raw) / "codex"
            command = [sys.executable, str(SCRIPTS_ROOT / "bootstrap-local.py"),
                       "--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home),
                       "--skip-rules", "--skip-doctor", "--json"]
            initial = subprocess.run(command, capture_output=True, text=True, env=environment)
            self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
            for relative, changed in (("schemas/orchestrator-task-state.schema.json", b"{}\n"),
                                      ("SKILL.md", b"User-modified skill\n")):
                with self.subTest(relative=relative):
                    target = codex_home / "skills/global-task-orchestrator" / relative
                    original = target.read_bytes()
                    target.write_bytes(changed)
                    before = {str(path.relative_to(codex_home)): path.read_bytes()
                              for path in codex_home.rglob("*") if path.is_file()}
                    result = subprocess.run(command, capture_output=True, text=True, env=environment)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("managed drift", result.stdout)
                    self.assertEqual({str(path.relative_to(codex_home)): path.read_bytes()
                                      for path in codex_home.rglob("*") if path.is_file()}, before)
                    target.write_bytes(original)

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

            receipt = json.loads((codex_home / ".ai-harness/codex-sync.receipt.json").read_text())
            package_schema = "global-task-orchestrator/schemas/orchestrator-task-state.schema.json"
            schema_rows = [row for row in receipt["managed_files"]
                           if row.get("skill") == "global-task-orchestrator" and row.get("target") == package_schema]
            self.assertEqual(1, len(schema_rows), "GTO schema must be owned and audited as a skill file")
            self.assertTrue((codex_home / "skills" / package_schema).is_file())
            self.assertFalse((codex_home / "schemas/orchestrator-task-state.schema.json").exists())
            configure_native_plugins(codex_home)
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
        self.assertEqual([], payload["codex_audit"]["schemas"], "no standalone schema is required for package-owned GTO")
        gto_audit = next(row for row in payload["codex_audit"]["skills"]
                         if row["managed_skill_name"] == "global-task-orchestrator")
        self.assertTrue(gto_audit["ok"], gto_audit)
        self.assertEqual(gto_audit["source_file_count"], gto_audit["runtime_file_count"])
        self.assertGreater(gto_audit["runtime_file_count"], 0)
        installed_gto = payload["codex_audit"]["installed_gto_validation"]
        self.assertTrue(installed_gto["ok"], installed_gto)
        self.assertEqual("validate", installed_gto["action"])

    def test_bootstrap_preserves_hooks_and_supported_notify_config(self) -> None:
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
            original_hooks = hooks_path.read_bytes()
            config_path = codex_home / "config.toml"
            config_path.write_text(
                'model = "keep-model"\n'
                'notify = ["/missing/legacy_notify", "turn-ended"]\n'
                '[features]\n'
                'multi_agent = true\n',
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
            self.assertNotIn("hook_cleanup", payload["completed_steps"])
            self.assertIn("hooks_cleared", payload)
            self.assertFalse(payload["hooks_cleared"])
            remaining = json.loads(hooks_path.read_text(encoding="utf-8"))
            self.assertEqual({"preserve": True}, remaining["custom_top_level"])
            self.assertEqual(original_hooks, hooks_path.read_bytes())
            remaining_config = config_path.read_text(encoding="utf-8")
            self.assertIn('notify = ["/missing/legacy_notify", "turn-ended"]', remaining_config)
            self.assertIn('model = "keep-model"', remaining_config)
            self.assertIn("multi_agent = true", remaining_config)

            configure_native_plugins(codex_home)
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

    def test_machine_doctor_does_not_classify_supported_notify_as_a_hook(self) -> None:
        # Break caught: top-level notify is a supported Codex setting, but the
        # broad hook regex previously made every fresh Desktop process unhealthy.
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-notify-", dir="/tmp") as raw:
            root = Path(raw)
            environment = linux_tool_environment(root)
            codex_home = root / "codex"
            bootstrap = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "bootstrap-local.py"), "--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor", "--json"],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(0, bootstrap.returncode, bootstrap.stderr or bootstrap.stdout)
            config_path = codex_home / "config.toml"
            config_path.write_text(
                'notify = ["python3", "/opt/user-notify.py"]\n[features]\nmulti_agent = true\n',
                encoding="utf-8",
            )

            configure_native_plugins(codex_home)
            doctor = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--root", str(REPO_ROOT), "--codex-home", str(codex_home), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            audit = json.loads(doctor.stdout)

        self.assertNotIn("hook_configuration_present", audit["errors"])
        self.assertTrue(audit["codex_audit"]["hooks"]["ok"], audit)

    def test_strict_doctor_preserves_and_observes_hooks_in_user_config(self) -> None:
        scratch = REPO_ROOT / ".tmp/portable-harness"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-", dir=scratch) as raw:
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
            configure_native_plugins(codex_home)
            config_before = (codex_home / "config.toml").read_bytes()
            doctor = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--root", str(REPO_ROOT), "--codex-home", str(codex_home), "--strict", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            audit = json.loads(doctor.stdout)
            self.assertEqual((codex_home / "config.toml").read_bytes(), config_before)
            self.assertNotIn("hook_configuration_present", audit["errors"])
            self.assertTrue(audit["codex_audit"]["hooks"]["ok"], audit)
            self.assertIs(audit["codex_audit"]["hooks"].get("managed"), False)
            self.assertTrue(audit["codex_audit"]["hooks"].get("observations"))

    def test_strict_doctor_preserves_and_observes_user_hooks_json_entries(self) -> None:
        scratch = REPO_ROOT / ".tmp/portable-harness"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-", dir=scratch) as raw:
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

            configure_native_plugins(codex_home)
            hooks_before = (codex_home / "hooks.json").read_bytes()
            doctor = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--root", str(REPO_ROOT), "--codex-home", str(codex_home), "--strict", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual((codex_home / "hooks.json").read_bytes(), hooks_before)

        audit = json.loads(doctor.stdout)
        self.assertNotIn("hook_configuration_present", audit["errors"])
        self.assertTrue(audit["codex_audit"]["hooks"]["ok"], audit)
        self.assertIs(audit["codex_audit"]["hooks"].get("managed"), False)
        self.assertTrue(audit["codex_audit"]["hooks"].get("observations"))


class MachineDoctorExitSemanticsTests(unittest.TestCase):
    def test_ordinary_machine_doctor_exit_code_matches_health(self) -> None:
        # Break caught: callers that run the ordinary startup doctor continue
        # into tests when unhealthy JSON is reported with a successful exit code.
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-exit-", dir="/tmp") as raw:
            root = Path(raw)
            environment = linux_tool_environment(root)
            unhealthy = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--repo-root", str(REPO_ROOT), "--codex-home", str(root / "missing-codex"), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            unhealthy_payload = json.loads(unhealthy.stdout)
            self.assertFalse(unhealthy_payload["ok"], unhealthy_payload)
            self.assertNotEqual(0, unhealthy.returncode, unhealthy_payload)

            codex_home = root / "codex"
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
            configure_native_plugins(codex_home)
            healthy = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "doctor-core.py"), "--repo-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--json"],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            healthy_payload = json.loads(healthy.stdout)

        self.assertTrue(healthy_payload["ok"], healthy_payload)
        self.assertEqual(0, healthy.returncode, healthy_payload)


if __name__ == "__main__":
    unittest.main()
