"""Behavior-first Red contract for the WSL environment governance tools.

The suite exercises scripts as a caller does: via their public CLI and JSON
output.  It deliberately avoids a real package install, Docker change, or
Windows/Codex configuration mutation.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
FIXTURES_ROOT = REPO_ROOT / "tests/fixtures/wsl-environment"
PROVISION = SCRIPTS_ROOT / "provision-wsl.py"
MACHINE_DOCTOR = SCRIPTS_ROOT / "doctor-core.py"
PROJECT_DOCTOR = SCRIPTS_ROOT / "project-env-doctor.py"
PATH_RESOLVER = SCRIPTS_ROOT / "resolve-wsl-path.py"
BOOTSTRAP = SCRIPTS_ROOT / "bootstrap-local.py"
MANAGED_WSL_RUNTIME_FILES = {
    "config/wsl-tool-baseline.json": REPO_ROOT / "config/ai/wsl-tool-baseline.json",
    "config/windows-external-capabilities.json": REPO_ROOT / "config/ai/windows-external-capabilities.json",
    "schemas/wsl-tool-baseline.schema.json": REPO_ROOT / "schemas/wsl-tool-baseline.schema.json",
    "schemas/windows-external-capabilities.schema.json": REPO_ROOT / "schemas/windows-external-capabilities.schema.json",
    "schemas/project-environment.schema.json": REPO_ROOT / "schemas/project-environment.schema.json",
    "bin/provision-wsl.py": SCRIPTS_ROOT / "provision-wsl.py",
    "bin/project-env-doctor.py": SCRIPTS_ROOT / "project-env-doctor.py",
    "bin/resolve-wsl-path.py": SCRIPTS_ROOT / "resolve-wsl-path.py",
    "bin/doctor-core.py": SCRIPTS_ROOT / "doctor-core.py",
    "bin/runtime_common.py": SCRIPTS_ROOT / "runtime_common.py",
}
LINUX_BASELINE_COMMANDS = (
    "git", "rg", "curl", "wget", "rsync", "file", "lsof", "python3", "bwrap", "node", "npm", "jq", "unzip", "zip",
    "tree", "strace", "shellcheck", "shfmt", "fzf", "fdfind", "sqlite3", "dos2unix", "make", "gcc", "g++", "pkg-config",
    "cmake", "ninja", "pip3", "pnpm",
)


def json_payload(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            "CLI must emit one JSON object in --json mode; "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        ) from error
    if not isinstance(payload, dict):
        raise AssertionError(f"CLI JSON root must be an object, got {type(payload).__name__}")
    return payload


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linux_baseline_environment(root: Path) -> dict[str, str]:
    bin_root = root / "linux-bin"
    bin_root.mkdir()
    for command in LINUX_BASELINE_COMMANDS:
        executable = bin_root / command
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
    temp_root = root / "linux-tmp"
    temp_root.mkdir()
    return {
        "PATH": f"{bin_root}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(root / "linux-home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TEMP": str(temp_root),
        "TMP": str(temp_root),
        "TMPDIR": str(temp_root),
    }


def linux_project_environment(path: str, **overrides: str) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": path,
        "TEMP": "/tmp",
        "TMP": "/tmp",
        "TMPDIR": "/tmp",
        **overrides,
    }


def write_linux_venv_config(venv: Path) -> None:
    (venv / "pyvenv.cfg").write_text(
        "home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.12.0\n",
        encoding="utf-8",
    )


def write_healthy_fake_venv(venv: Path, *, pip_install_exit: int = 0) -> None:
    python = venv / "bin/python"
    python.parent.mkdir(parents=True, exist_ok=True)
    identity = json.dumps({"prefix": str(venv), "base_prefix": "/usr/bin/python3"})
    python.write_text(
        "#!/bin/sh\n"
        "if test \"$1\" = -c; then\n"
        f"  printf '%s\\n' '{identity}'\n"
        "  exit 0\n"
        "fi\n"
        "if test \"$1\" = -m && test \"$2\" = pip && test \"$3\" = install; then\n"
        f"  exit {pip_install_exit}\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    write_linux_venv_config(venv)


def finding_categories(payload: dict[str, object]) -> set[str]:
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise AssertionError(f"diagnostic JSON must expose findings[]: {payload}")
    categories: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("category"), str):
            raise AssertionError(f"every finding must expose a string category: {finding!r}")
        categories.add(finding["category"])
    return categories


class WslEnvironmentContractTests(unittest.TestCase):
    maxDiff = None

    def test_harness_declares_its_real_jsonschema_import_dependency(self) -> None:
        import ast
        controller = REPO_ROOT / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
        tree = ast.parse(controller.read_text(encoding="utf-8-sig"))
        self.assertTrue(any(isinstance(node, ast.ImportFrom) and node.module == "jsonschema"
                            for node in ast.walk(tree)), "fixture must match a real production import")
        declaration = json.loads((REPO_ROOT / "config/ai/environment.json").read_text())
        manifest = REPO_ROOT / declaration["python"]["requirements_file"]
        requirements = [line.split("#", 1)[0].strip() for line in manifest.read_text().splitlines()]
        self.assertTrue(any(line.lower().startswith("jsonschema") for line in requirements), requirements)

    def test_harness_manifest_doctor_rejects_real_venv_without_jsonschema(self) -> None:
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec("jsonschema"), "system interpreter prerequisite")
        base = REPO_ROOT / ".tmp"
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="t3-project-dependency-", dir=base) as raw:
            project = Path(raw)
            declaration = json.loads((REPO_ROOT / "config/ai/environment.json").read_text())
            environment_file = project / "environment.json"
            environment_file.write_text(json.dumps(declaration))
            manifest_relative = declaration["python"]["requirements_file"]
            shutil.copy2(REPO_ROOT / manifest_relative, project / manifest_relative)
            venv = project / declaration["python"]["venv"]
            # venv uses the bundled ensurepip wheels; no network or host install.
            created = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True)
            self.assertEqual(0, created.returncode, created.stderr)
            python = venv / "bin/python"
            pip = subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True, text=True)
            self.assertEqual(0, pip.returncode, pip.stderr)
            self.assertIn(str(venv), pip.stdout)
            probe = subprocess.run([str(python), "-c",
                "import importlib.util,json,sys; print(json.dumps({'prefix':sys.prefix,'base':sys.base_prefix,'jsonschema':importlib.util.find_spec('jsonschema') is not None}))"],
                capture_output=True, text=True)
            self.assertEqual(0, probe.returncode, probe.stderr)
            identity = json.loads(probe.stdout)
            self.assertEqual(str(venv), identity["prefix"])
            self.assertNotEqual(identity["base"], identity["prefix"])
            self.assertFalse(identity["jsonschema"])
            missing = subprocess.run([str(python), "-m", "pip", "install", "--dry-run", "--no-index",
                "--disable-pip-version-check", "jsonschema"], capture_output=True, text=True)
            self.assertNotEqual(0, missing.returncode)
            self.assertIn("No matching distribution found for jsonschema", missing.stderr)
            completed, payload = self.run_json(PROJECT_DOCTOR,
                ["--project-root", str(project), "--environment", str(environment_file)],
                environment=linux_project_environment("/usr/bin:/bin"))
            self.assertNotEqual(0, completed.returncode, payload)
            self.assertFalse(payload["ok"], payload)
            self.assertIn("missing_python_requirement", finding_categories(payload), payload)

    def test_global_agents_gives_fresh_sessions_host_and_dependency_contract(self) -> None:
        template = (REPO_ROOT / "templates/codex/AGENTS.global.md").read_text(encoding="utf-8")
        self.assertIn("Windows 原生、Linux 或 WSL", template)
        self.assertIn("不混用跨系统 venv 或 node_modules", template)
        self.assertIn("基础安装与 doctor 使用 Python 3.11+", template)
        self.assertIn("项目首次运行时按项目已有环境声明核验所需依赖", template)
        self.assertIn("没有选择 WSL 的项目不承担 WSL 工具清单", template)
        self.assertIn("当前宿主实际暴露的能力", template)
        self.assertIn("先核实发行版、同一项目路径和 Codex home 映射", template)
        self.assertIn("指令更新须在新会话核验", template)

    def run_json(
        self,
        script: Path,
        arguments: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        self.assertTrue(
            script.is_file(),
            f"missing contract entrypoint {script.relative_to(REPO_ROOT)}; "
            "this is a production behavior failure, not a fixture/import failure",
        )
        completed = subprocess.run(
            [sys.executable, str(script), *arguments, "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        return completed, json_payload(completed)

    def copy_project_fixture(self, destination: Path) -> Path:
        shutil.copytree(FIXTURES_ROOT / "project-valid", destination)
        return destination / "config/ai/environment.json"

    def test_provision_accepts_valid_manifest_and_selects_named_profile(self) -> None:
        # Break caught: a malformed or ignored baseline can make a task install
        # the wrong machine tooling instead of the explicit selected profile.
        completed, payload = self.run_json(
            PROVISION,
            ["--baseline", str(FIXTURES_ROOT / "baseline.valid.json"), "--profile", "developer"],
        )

        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual("plan", payload.get("mode"), payload)
        self.assertEqual("developer", payload.get("profile"), payload)
        self.assertFalse(payload.get("mutated"), payload)
        self.assertEqual(["fixture-wsl-tool", "jq"], sorted(payload.get("missing_packages", [])), payload)

    def test_provision_rejects_invalid_manifest_before_any_plan_or_apply(self) -> None:
        # Break caught: an unknown package source could turn a declarative
        # baseline into an arbitrary-download installation channel.
        completed, payload = self.run_json(
            PROVISION,
            ["--baseline", str(FIXTURES_ROOT / "baseline.invalid.json"), "--profile", "developer"],
        )

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual("invalid_baseline", payload.get("error", {}).get("category"), payload)
        self.assertTrue(payload.get("validation_errors"), payload)
        self.assertFalse(payload.get("mutated"), payload)

    def test_provision_defaults_to_plan_and_dry_run_apply_never_requests_broad_upgrade(self) -> None:
        # Break caught: a harmless doctor/bootstrap invocation must not perform
        # an OS upgrade, and explicit apply must remain a minimal package action.
        baseline = str(FIXTURES_ROOT / "baseline.valid.json")
        planned, planned_payload = self.run_json(PROVISION, ["--baseline", baseline, "--profile", "developer"])
        self.assertEqual(0, planned.returncode, planned.stderr or planned.stdout)
        self.assertEqual("plan", planned_payload.get("mode"), planned_payload)
        self.assertFalse(planned_payload.get("mutated"), planned_payload)
        self.assertEqual([], planned_payload.get("executed_commands"), planned_payload)

        applied, applied_payload = self.run_json(
            PROVISION,
            ["--baseline", baseline, "--profile", "developer", "--apply", "--dry-run"],
        )
        self.assertEqual(0, applied.returncode, applied.stderr or applied.stdout)
        self.assertEqual("apply", applied_payload.get("mode"), applied_payload)
        self.assertTrue(applied_payload.get("dry_run"), applied_payload)
        self.assertFalse(applied_payload.get("mutated"), applied_payload)
        commands = applied_payload.get("planned_commands")
        self.assertIsInstance(commands, list, applied_payload)
        command_text = "\n".join(" ".join(command) for command in commands)
        self.assertIn("apt", command_text, applied_payload)
        self.assertIn("install", command_text, applied_payload)
        self.assertNotRegex(command_text, r"(?i)\b(full-|dist-)?upgrade\b", applied_payload)
        self.assertNotIn("remove", command_text.casefold(), applied_payload)

    def test_machine_doctor_reports_windows_backed_command_and_temp_before_runtime_work(self) -> None:
        # Break caught: a Windows node/npm chosen through PATH or a Windows TEMP
        # can corrupt WSL builds while a superficial tool-exists check is green.
        with tempfile.TemporaryDirectory(prefix="ai-harness-windows-bin-", dir="/mnt/c") as raw:
            windows_bin = Path(raw)
            node = windows_bin / "node"
            node.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            node.chmod(0o755)
            for label, windows_temp in (
                ("drive_path", r"C:\\Users\\fixture\\AppData\\Local\\Temp"),
                ("mounted_path", str(windows_bin / "Temp")),
            ):
                with self.subTest(temp_source=label):
                    environment = {
                        **os.environ,
                        "PATH": f"{windows_bin}:{os.environ.get('PATH', '')}",
                        "TEMP": windows_temp,
                        "TMP": windows_temp,
                        "TMPDIR": windows_temp,
                    }
                    with tempfile.TemporaryDirectory(prefix="ai-harness-machine-doctor-") as codex_raw:
                        completed, payload = self.run_json(
                            MACHINE_DOCTOR,
                            ["--repo-root", str(REPO_ROOT), "--codex-home", str(Path(codex_raw) / "codex")],
                            environment=environment,
                        )

                    self.assertFalse(payload.get("ok"), payload)
                    categories = finding_categories(payload)
                    self.assertTrue({"windows_command_path", "windows_temp"} <= categories, payload)

    def test_project_doctor_classifies_windows_venv_and_windows_esbuild_artifact(self) -> None:
        # Break caught: Windows-created Python and esbuild artifacts must be
        # stopped before a WSL project test mistakes an ABI failure for a defect.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-doctor-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            scripts = project_root / ".venv/Scripts"
            scripts.mkdir(parents=True)
            (scripts / "python.exe").write_bytes(b"MZ fixture Windows executable")
            esbuild = project_root / "node_modules/esbuild/bin"
            esbuild.mkdir(parents=True)
            (esbuild / "esbuild.exe").write_bytes(b"MZ fixture Windows executable")
            environment = {
                **os.environ,
                "TEMP": r"C:\\Users\\fixture\\AppData\\Local\\Temp",
                "TMP": r"C:\\Users\\fixture\\AppData\\Local\\Temp",
            }
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
                environment=environment,
            )

        self.assertNotEqual(0, completed.returncode, payload)
        categories = finding_categories(payload)
        self.assertTrue(
            {"windows_temp", "windows_python_environment", "windows_node_artifact"} <= categories,
            payload,
        )

    def test_project_doctor_classifies_missing_dependencies_and_declared_optional_capabilities(self) -> None:
        # Break caught: a clean checkout must report missing project/runtime
        # layers distinctly rather than treating them as machine package failures.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-missing-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            empty_bin = project_root / "empty-bin"
            empty_bin.mkdir()
            environment = {**os.environ, "PATH": str(empty_bin)}
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
                environment=environment,
            )

        self.assertNotEqual(0, completed.returncode, payload)
        categories = finding_categories(payload)
        self.assertTrue(
            {"missing_python_dependency", "missing_node_dependency", "missing_playwright", "missing_docker"}
            <= categories,
            payload,
        )

    def test_project_doctor_rejects_unknown_and_escaping_declaration_paths(self) -> None:
        # Break caught: permissive project declarations can read arbitrary files
        # outside the project root or silently accept undeclared behavior.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-declaration-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            original = json.loads(environment_file.read_text(encoding="utf-8"))
            cases = (
                ("unknown", {**original, "unknown_field": True}),
                ("absolute", {**original, "python": {**original["python"], "venv": "/tmp/outside"}}),
                ("traversal", {**original, "node": {**original["node"], "node_modules": "../outside"}}),
                (
                    "invalid-pyproject-extras",
                    {
                        **original,
                        "python": {
                            "pyproject_file": "pyproject.toml",
                            "venv": ".venv",
                            "extras": [{"not": "an-extra-name"}],
                        },
                    },
                ),
            )
            for label, declaration in cases:
                with self.subTest(declaration=label):
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertEqual("invalid_project_environment", payload.get("error", {}).get("category"), payload)

    def test_project_doctor_does_not_accept_empty_runtime_shells(self) -> None:
        # Break caught: empty .venv or node_modules directories are stale shells,
        # not proof that manifest dependencies are available to this WSL project.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-shells-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration["capabilities"] = []
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            (project_root / ".venv").mkdir()
            (project_root / "node_modules").mkdir()
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
            )

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertTrue({"missing_python_dependency", "missing_node_dependency"} <= finding_categories(payload), payload)

    def test_project_environment_allows_exactly_one_language_runtime(self) -> None:
        # Break caught: Python-only and Node-only repositories must not invent
        # the other ecosystem, while a declaration with neither is unusable.
        schema = json.loads((REPO_ROOT / "schemas/project-environment.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        schema_failures: dict[str, list[str]] = {}
        parser_failures: dict[str, dict[str, object]] = {}
        with tempfile.TemporaryDirectory(prefix="ai-harness-single-runtime-", dir="/tmp") as raw:
            root = Path(raw)
            for mode in ("python-only", "node-only", "neither"):
                project_root = root / mode / "project"
                environment_file = self.copy_project_fixture(project_root)
                declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                declaration["capabilities"] = []
                if mode == "python-only":
                    declaration.pop("node")
                    write_healthy_fake_venv(project_root / ".venv")
                elif mode == "node-only":
                    declaration.pop("python")
                    installed = project_root / "node_modules/fixture-node-package"
                    installed.mkdir(parents=True)
                    installed.joinpath("package.json").write_text(
                        json.dumps({"name": "fixture-node-package", "version": "1.0.0"}),
                        encoding="utf-8",
                    )
                    npm_bin = root / "node-only-npm-bin"
                    npm_bin.mkdir(exist_ok=True)
                    fake_npm = npm_bin / "npm"
                    fake_npm.write_text(
                        "#!" + sys.executable + "\n"
                        "import json, sys\n"
                        "expected = ['ls', '--depth=0', '--offline', '--json', '--ignore-scripts', '--include=prod', '--include=dev']\n"
                        "print(json.dumps({'dependencies': {}}))\n"
                        "raise SystemExit(0 if sys.argv[1:] == expected else 23)\n",
                        encoding="utf-8",
                    )
                    fake_npm.chmod(0o755)
                else:
                    declaration.pop("python")
                    declaration.pop("node")
                environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                schema_errors = [error.message for error in validator.iter_errors(declaration)]
                completed, payload = self.run_json(
                    PROJECT_DOCTOR,
                    ["--project-root", str(project_root), "--environment", str(environment_file)],
                    environment=linux_project_environment(
                        f"{npm_bin}:/usr/bin:/bin" if mode == "node-only" else "/usr/bin:/bin"
                    ),
                )
                if mode == "neither":
                    if not schema_errors:
                        schema_failures[mode] = schema_errors
                    if completed.returncode == 0 or payload.get("error", {}).get("category") != "invalid_project_environment":
                        parser_failures[mode] = payload
                else:
                    if schema_errors:
                        schema_failures[mode] = schema_errors
                    if completed.returncode != 0 or not payload.get("ok"):
                        parser_failures[mode] = payload

        self.assertEqual(
            {"schema": {}, "parser": {}},
            {"schema": schema_failures, "parser": parser_failures},
        )

    def test_project_doctor_accepts_real_linux_venv_symlink(self) -> None:
        # Break caught: a standard Linux venv commonly links bin/python outside
        # the venv directory; that alone must not be mistaken for system Python.
        with tempfile.TemporaryDirectory(prefix="ai-harness-real-linux-venv-", dir="/tmp") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration.pop("node")
            declaration["capabilities"] = []
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            (project_root / "requirements.txt").write_text("", encoding="utf-8")
            created = subprocess.run(
                [sys.executable, "-m", "venv", "--without-pip", str(project_root / ".venv")],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, created.returncode, created.stderr or created.stdout)
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
                environment=linux_project_environment("/usr/bin:/bin"),
            )

        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(payload.get("ok"), payload)

    def test_project_doctor_accepts_linux_venv_stored_in_a_mounted_project(self) -> None:
        # Break caught: a Linux ELF venv inside a repository on /mnt/d is still
        # a Linux project environment; mount location alone must not relabel it
        # as a Windows interpreter.
        mount_root = Path("/mnt/d")
        if not mount_root.is_dir():
            self.skipTest("WSL mounted-drive boundary is unavailable")
        with tempfile.TemporaryDirectory(
            prefix="ai-harness-mounted-linux-venv-", dir=mount_root
        ) as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration.pop("node")
            declaration["capabilities"] = []
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            (project_root / "requirements.txt").write_text("", encoding="utf-8")
            write_healthy_fake_venv(project_root / ".venv")
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
                environment=linux_project_environment("/usr/bin:/bin"),
            )

        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(payload.get("ok"), payload)

    def test_project_doctor_verifies_declared_python_requirements_and_isolated_venv(self) -> None:
        # Break caught: a present Python executable is insufficient when declared
        # requirements are absent or .venv merely points at the system Python.
        with tempfile.TemporaryDirectory(prefix="ai-harness-python-requirements-", dir="/tmp") as raw:
            root = Path(raw)
            cases = (
                ("missing-requirement", "missing_python_requirement"),
                ("system-python-link", "system_python_venv"),
            )
            for mode, expected_category in cases:
                with self.subTest(mode=mode):
                    project_root = root / mode / "project"
                    environment_file = self.copy_project_fixture(project_root)
                    declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                    declaration.pop("node")
                    declaration["capabilities"] = []
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    python = project_root / ".venv/bin/python"
                    if mode == "missing-requirement":
                        (project_root / "requirements.txt").write_text("fixture-not-installed==1.0\n", encoding="utf-8")
                        write_healthy_fake_venv(project_root / ".venv", pip_install_exit=1)
                    else:
                        python.parent.mkdir(parents=True)
                        python.symlink_to(Path(sys.executable).resolve())
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                        environment=linux_project_environment("/usr/bin:/bin"),
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertIn(expected_category, finding_categories(payload), payload)

    def test_project_doctor_checks_pyproject_dependencies_without_building_the_project(self) -> None:
        # Break caught: projects whose dependency truth is pyproject.toml must
        # not duplicate requirements.txt or invoke a local package build merely
        # to prove that their declared runtime/test dependencies are installed.
        with tempfile.TemporaryDirectory(prefix="ai-harness-pyproject-dependencies-", dir="/tmp") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration.pop("node")
            declaration["python"] = {
                "pyproject_file": "pyproject.toml",
                "venv": ".venv-wsl",
                "extras": ["test"],
            }
            declaration["capabilities"] = []
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            (project_root / "pyproject.toml").write_text(
                "[project]\n"
                "name = \"fixture-project\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"fastapi>=0.116,<1\"]\n"
                "[project.optional-dependencies]\n"
                "test = [\"pytest>=8.4,<9\"]\n",
                encoding="utf-8",
            )
            invocation = project_root / "pip-invocation.json"
            venv = project_root / ".venv-wsl"
            python = venv / "bin/python"
            python.parent.mkdir(parents=True)
            identity = json.dumps({"prefix": str(venv), "base_prefix": "/usr/bin/python3"})
            python.write_text(
                "#!" + sys.executable + "\n"
                "import json, sys\n"
                "from pathlib import Path\n"
                f"identity = {identity!r}\n"
                f"invocation = Path({str(invocation)!r})\n"
                "if sys.argv[1:2] == ['-c']:\n"
                "    print(identity)\n"
                "    raise SystemExit(0)\n"
                "if sys.argv[1:4] == ['-m', 'pip', 'install']:\n"
                "    invocation.write_text(json.dumps(sys.argv[4:]), encoding='utf-8')\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(31)\n",
                encoding="utf-8",
            )
            python.chmod(0o755)
            write_linux_venv_config(venv)

            schema = json.loads((REPO_ROOT / "schemas/project-environment.schema.json").read_text(encoding="utf-8"))
            self.assertEqual([], list(Draft202012Validator(schema).iter_errors(declaration)))
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
                environment=linux_project_environment("/usr/bin:/bin"),
            )
            self.assertEqual(0, completed.returncode, payload)
            self.assertTrue(payload.get("ok"), payload)
            pip_arguments = json.loads(invocation.read_text(encoding="utf-8"))
            self.assertEqual(
                [
                    "--dry-run",
                    "--no-index",
                    "--disable-pip-version-check",
                    "fastapi>=0.116,<1",
                    "pytest>=8.4,<9",
                ],
                pip_arguments,
            )

    def test_project_doctor_requires_declared_node_packages_and_rejects_windows_shims(self) -> None:
        # Break caught: a nonempty node_modules cannot stand in for declared
        # dependencies, and generic Windows command shims are unusable in WSL.
        with tempfile.TemporaryDirectory(prefix="ai-harness-node-dependencies-", dir="/tmp") as raw:
            root = Path(raw)
            for mode, expected_category in (
                ("missing-dependencies", "missing_node_dependency"),
                ("windows-shims", "windows_node_artifact"),
            ):
                with self.subTest(mode=mode):
                    project_root = root / mode / "project"
                    environment_file = self.copy_project_fixture(project_root)
                    declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                    declaration["capabilities"] = []
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    write_healthy_fake_venv(project_root / ".venv")
                    package = {
                        "name": "fixture",
                        "private": True,
                        "dependencies": {"runtime-package": "1.0.0"},
                        "devDependencies": {"dev-package": "1.0.0"},
                    }
                    (project_root / "package.json").write_text(json.dumps(package), encoding="utf-8")
                    modules = project_root / "node_modules"
                    modules.mkdir()
                    if mode == "windows-shims":
                        for suffix in (".cmd", ".ps1", ".exe"):
                            shim = modules / ".bin" / f"tool{suffix}"
                            shim.parent.mkdir(exist_ok=True)
                            shim.write_text("fixture", encoding="utf-8")
                        (modules / "runtime-package").mkdir()
                        (modules / "dev-package").mkdir()
                    else:
                        (modules / "placeholder").mkdir()
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                        environment=linux_project_environment("/usr/bin:/bin"),
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertIn(expected_category, finding_categories(payload), payload)

    def test_project_doctor_uses_offline_npm_to_verify_declared_node_package_versions(self) -> None:
        # Break caught: an empty or stale package directory can satisfy a
        # directory-only check even though npm cannot resolve the declared
        # runtime-package version from this project's installed dependency tree.
        npm = shutil.which("npm")
        self.assertIsNotNone(npm, "the WSL baseline contract requires a Linux-native npm")
        assert npm is not None
        expected_command = [
            "ls", "--depth=0", "--offline", "--json", "--ignore-scripts", "--include=prod", "--include=dev",
        ]
        with tempfile.TemporaryDirectory(prefix="ai-harness-node-version-audit-", dir="/tmp") as raw:
            root = Path(raw)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            npm_log = root / "npm-invocation.json"
            fake_npm = fake_bin / "npm"
            fake_npm.write_text(
                "#!" + sys.executable + "\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['NPM_AUDIT_LOG']).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
                "expected = ['ls', '--depth=0', '--offline', '--json', '--ignore-scripts', '--include=prod', '--include=dev']\n"
                "if sys.argv[1:] != expected:\n"
                "    print(json.dumps({'error': 'unexpected npm audit arguments'}))\n"
                "    raise SystemExit(19)\n"
                "installed = Path.cwd() / 'node_modules/runtime-package/package.json'\n"
                "try:\n"
                "    package = json.loads(installed.read_text(encoding='utf-8'))\n"
                "except (OSError, json.JSONDecodeError):\n"
                "    package = {}\n"
                "healthy = package.get('name') == 'runtime-package' and package.get('version') == '9.9.9'\n"
                "print(json.dumps({'dependencies': {'runtime-package': {'version': package.get('version')}}}))\n"
                "raise SystemExit(0 if healthy else 1)\n",
                encoding="utf-8",
            )
            fake_npm.chmod(0o755)
            for mode, expected_returncode in (("empty-directory", 1), ("wrong-version", 1), ("healthy", 0)):
                with self.subTest(mode=mode):
                    project_root = root / mode / "project"
                    environment_file = self.copy_project_fixture(project_root)
                    declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                    declaration.pop("python")
                    declaration["capabilities"] = []
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    (project_root / "package.json").write_text(
                        json.dumps(
                            {
                                "name": "fixture-node-only",
                                "private": True,
                                "dependencies": {"runtime-package": "9.9.9"},
                            }
                        ),
                        encoding="utf-8",
                    )
                    installed = project_root / "node_modules/runtime-package"
                    installed.mkdir(parents=True)
                    if mode != "empty-directory":
                        installed.joinpath("package.json").write_text(
                            json.dumps({"name": "runtime-package", "version": "9.9.9" if mode == "healthy" else "1.0.0"}),
                            encoding="utf-8",
                        )
                    npm_environment = linux_project_environment(
                        f"{Path(npm).parent}:/usr/bin:/bin",
                        HOME=str(root / "npm-home"),
                        NPM_CONFIG_CACHE=str(root / "npm-cache"),
                    )
                    observed_npm = subprocess.run(
                        [npm, *expected_command],
                        cwd=project_root,
                        text=True,
                        capture_output=True,
                        check=False,
                        env=npm_environment,
                    )
                    self.assertEqual(
                        expected_returncode,
                        observed_npm.returncode,
                        f"real npm offline integrity semantics changed: {observed_npm.stderr or observed_npm.stdout}",
                    )
                    npm_log.unlink(missing_ok=True)
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                        environment=linux_project_environment(
                            f"{fake_bin}:/usr/bin:/bin",
                            NPM_AUDIT_LOG=str(npm_log),
                        ),
                    )
                    self.assertEqual(expected_returncode, completed.returncode, payload)
                    if expected_returncode:
                        self.assertIn("missing_node_dependency", finding_categories(payload), payload)
                    else:
                        self.assertTrue(payload.get("ok"), payload)
                    self.assertTrue(npm_log.is_file(), "project doctor must invoke npm integrity verification")
                    self.assertEqual(expected_command, json.loads(npm_log.read_text(encoding="utf-8")))

    def test_project_doctor_rejects_windows_targeted_npm_symlink_but_allows_linux_target(self) -> None:
        # Break caught: PATH can expose a Linux-looking /tmp/bin/npm symlink
        # whose executable target is actually Windows-backed.  Resolving that
        # boundary must reject it without rejecting ordinary Linux symlinks.
        expected_command = [
            "ls", "--depth=0", "--offline", "--json", "--ignore-scripts", "--include=prod", "--include=dev",
        ]
        with tempfile.TemporaryDirectory(prefix="ai-harness-npm-symlink-", dir="/tmp") as raw:
            root = Path(raw)
            with tempfile.TemporaryDirectory(prefix="ai-harness-npm-windows-target-", dir="/mnt/c") as windows_raw:
                for mode, target, expected_returncode in (
                    ("windows-target", Path(windows_raw) / "npm", 1),
                    ("linux-target", root / "linux-target/npm", 0),
                ):
                    with self.subTest(target=mode):
                        project_root = root / mode / "project"
                        environment_file = self.copy_project_fixture(project_root)
                        declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                        declaration.pop("python")
                        declaration["capabilities"] = []
                        environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                        installed = project_root / "node_modules/fixture-node-package"
                        installed.mkdir(parents=True)
                        installed.joinpath("package.json").write_text(
                            json.dumps({"name": "fixture-node-package", "version": "1.0.0"}),
                            encoding="utf-8",
                        )
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(
                            "#!" + sys.executable + "\n"
                            "import json, sys\n"
                            f"expected = {expected_command!r}\n"
                            "print(json.dumps({'dependencies': {}}))\n"
                            "raise SystemExit(0 if sys.argv[1:] == expected else 23)\n",
                            encoding="utf-8",
                        )
                        target.chmod(0o755)
                        bin_root = root / mode / "bin"
                        bin_root.mkdir(parents=True)
                        (bin_root / "npm").symlink_to(target)
                        completed, payload = self.run_json(
                            PROJECT_DOCTOR,
                            ["--project-root", str(project_root), "--environment", str(environment_file)],
                            environment=linux_project_environment(f"{bin_root}:/usr/bin:/bin"),
                        )
                        self.assertEqual(expected_returncode, completed.returncode, payload)
                        if mode == "windows-target":
                            self.assertIn("windows_node_artifact", finding_categories(payload), payload)
                        else:
                            self.assertTrue(payload.get("ok"), payload)

    def test_project_doctor_rejects_non_executable_or_windows_linked_python(self) -> None:
        # Break caught: a file at .venv/bin/python can be a non-executable
        # placeholder or a symlink to a Windows interpreter, neither of which
        # proves this project has a usable Linux Python dependency.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-python-boundary-", dir="/tmp") as raw:
            root = Path(raw)
            for mode, expected_category in (
                ("not-executable", "missing_python_dependency"),
                ("windows-symlink", "windows_python_environment"),
            ):
                with self.subTest(mode=mode):
                    project_root = root / mode / "project"
                    environment_file = self.copy_project_fixture(project_root)
                    declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                    declaration["capabilities"] = []
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    python = project_root / ".venv/bin/python"
                    python.parent.mkdir(parents=True)
                    if mode == "not-executable":
                        python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                        python.chmod(0o644)
                    else:
                        with tempfile.TemporaryDirectory(prefix="ai-harness-python-link-", dir="/mnt/c") as mount_raw:
                            windows_python = Path(mount_raw) / "python.exe"
                            windows_python.write_bytes(b"MZ fixture Windows executable")
                            python.symlink_to(windows_python)
                            (project_root / "node_modules/placeholder").mkdir(parents=True)
                            completed, payload = self.run_json(
                                PROJECT_DOCTOR,
                                ["--project-root", str(project_root), "--environment", str(environment_file)],
                                environment=linux_project_environment("/usr/bin:/bin"),
                            )
                        self.assertNotEqual(0, completed.returncode, payload)
                        self.assertIn(expected_category, finding_categories(payload), payload)
                        continue
                    (project_root / "node_modules/placeholder").mkdir(parents=True)
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                        environment=linux_project_environment("/usr/bin:/bin"),
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertIn(expected_category, finding_categories(payload), payload)

    def test_project_doctor_detects_real_esbuild_windows_platform_package(self) -> None:
        # Break caught: modern esbuild installs can be Windows-only through the
        # @esbuild/win32-* package even when no legacy esbuild.exe exists.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-esbuild-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration["capabilities"] = []
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            write_healthy_fake_venv(project_root / ".venv")
            package_json = project_root / "package.json"
            package_json.write_text(json.dumps({"name": "fixture", "private": True, "dependencies": {}}), encoding="utf-8")
            windows_package = project_root / "node_modules/@esbuild/win32-x64/package.json"
            windows_package.parent.mkdir(parents=True)
            windows_package.write_text(json.dumps({"name": "@esbuild/win32-x64"}), encoding="utf-8")
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
            )

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertIn("windows_node_artifact", finding_categories(payload), payload)

    def test_project_doctor_requires_local_playwright_entry_and_browser(self) -> None:
        # Break caught: a globally installed Playwright is not this project's
        # browser runtime; the local entry and Chromium capability must both exist.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-playwright-", dir="/tmp") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration["capabilities"] = [{"id": "playwright", "required": True}]
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            write_healthy_fake_venv(project_root / ".venv")
            (project_root / "package.json").write_text(json.dumps({"name": "fixture", "private": True, "dependencies": {}}), encoding="utf-8")
            local_playwright = project_root / "node_modules/.bin/playwright"
            local_playwright.parent.mkdir(parents=True)
            local_playwright.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            local_playwright.chmod(0o755)
            browser = project_root / "node_modules/playwright/.local-browsers/chromium-fixture/chrome-linux/chrome"
            browser.parent.mkdir(parents=True)
            browser.write_text("fixture browser", encoding="utf-8")
            browser.chmod(0o755)
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
                environment=linux_project_environment("/usr/bin:/bin"),
            )

        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(payload.get("ok"), payload)
        self.assertNotIn("missing_playwright", finding_categories(payload), payload)

    def test_project_doctor_reports_non_linux_or_unhealthy_docker_stably(self) -> None:
        # Break caught: Docker's pathname alone does not prove a Linux client or
        # a usable daemon; both must be checked before Docker-dependent tests run.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-docker-", dir="/tmp") as raw:
            root = Path(raw)
            for mode, category in (("windows", "docker_not_linux_client"), ("info-fails", "docker_info_failed")):
                with self.subTest(mode=mode):
                    project_root = root / mode
                    environment_file = self.copy_project_fixture(project_root)
                    declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                    declaration["capabilities"] = [{"id": "docker", "required": True}]
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    write_healthy_fake_venv(project_root / ".venv")
                    (project_root / "package.json").write_text(json.dumps({"name": "fixture", "private": True, "dependencies": {}}), encoding="utf-8")
                    (project_root / "node_modules").mkdir()
                    bin_root = root / f"bin-{mode}"
                    bin_root.mkdir()
                    docker = bin_root / "docker"
                    if mode == "windows":
                        docker.write_text("#!/bin/sh\nif test \"$1\" = version; then echo windows; exit 0; fi\nexit 0\n", encoding="utf-8")
                    else:
                        docker.write_text("#!/bin/sh\nif test \"$1\" = info; then exit 19; fi\necho linux\n", encoding="utf-8")
                    docker.chmod(0o755)
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                        environment=linux_project_environment(f"{bin_root}:/usr/bin:/bin"),
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertIn(category, finding_categories(payload), payload)

    def test_project_doctor_marks_mnt_c_and_mnt_d_temp(self) -> None:
        # Break caught: both C: and D: DrvFS temporary directories can leak
        # Windows artifacts into WSL project work, not only C: drive values.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-capability-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            completed, payload = self.run_json(
                PROJECT_DOCTOR,
                ["--project-root", str(project_root), "--environment", str(environment_file)],
                environment={**os.environ, "TEMP": "/mnt/c/Temp", "TMP": "/mnt/d/Temp", "TMPDIR": "/tmp"},
            )

        self.assertNotEqual(0, completed.returncode, payload)
        temp_variables = {finding.get("path", "").split("=", 1)[0] for finding in payload.get("findings", []) if finding.get("category") == "windows_temp"}
        self.assertTrue({"TEMP", "TMP"} <= temp_variables, payload)

    def test_project_doctor_rejects_empty_and_unknown_capabilities(self) -> None:
        # Break caught: typoed or empty capability declarations otherwise bypass
        # the project doctor before a real run requests unsupported resources.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-capability-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            for label, capabilities, expected in (
                ("empty-id", [{"id": "", "required": True}], "invalid_project_environment"),
                ("unknown", [{"id": "gpu-hypervisor", "required": True}], "unsupported_capability"),
            ):
                with self.subTest(capability=label):
                    declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                    declaration["capabilities"] = capabilities
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    if expected == "invalid_project_environment":
                        self.assertEqual(expected, payload.get("error", {}).get("category"), payload)
                    else:
                        self.assertIn(expected, finding_categories(payload), payload)

    def test_project_doctor_requires_executable_playwright_browser_and_accepts_declared_external_cache(self) -> None:
        # Break caught: an existing but non-executable browser is unusable, while
        # a declared Linux browser cache outside node_modules is a valid runtime.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-browser-", dir="/tmp") as raw:
            root = Path(raw)
            for mode, expected_returncode, expected_category in (
                ("non-executable", 1, "playwright_browser_not_executable"),
                ("external-cache", 0, ""),
            ):
                with self.subTest(mode=mode):
                    project_root = root / mode / "project"
                    environment_file = self.copy_project_fixture(project_root)
                    declaration = json.loads(environment_file.read_text(encoding="utf-8"))
                    declaration["capabilities"] = [{"id": "playwright", "required": True}]
                    environment_file.write_text(json.dumps(declaration), encoding="utf-8")
                    write_healthy_fake_venv(project_root / ".venv")
                    (project_root / "package.json").write_text(json.dumps({"name": "fixture", "private": True, "dependencies": {}}), encoding="utf-8")
                    entry = project_root / "node_modules/.bin/playwright"
                    entry.parent.mkdir(parents=True)
                    entry.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                    entry.chmod(0o755)
                    browser_root = project_root / "node_modules/playwright/.local-browsers"
                    if mode == "non-executable":
                        browser = browser_root / "chromium/chrome-linux/chrome"
                        browser.parent.mkdir(parents=True)
                        browser.write_text("browser", encoding="utf-8")
                        environment = linux_project_environment("/usr/bin:/bin")
                    else:
                        external = root / "external-playwright-cache"
                        browser = external / "chromium/chrome-linux/chrome"
                        browser.parent.mkdir(parents=True)
                        browser.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                        browser.chmod(0o755)
                        environment = linux_project_environment(
                            "/usr/bin:/bin",
                            PLAYWRIGHT_BROWSERS_PATH=str(external),
                        )
                    completed, payload = self.run_json(
                        PROJECT_DOCTOR,
                        ["--project-root", str(project_root), "--environment", str(environment_file)],
                        environment=environment,
                    )
                    self.assertEqual(expected_returncode, completed.returncode, payload)
                    if expected_category:
                        self.assertIn(expected_category, finding_categories(payload), payload)
                    else:
                        self.assertTrue(payload.get("ok"), payload)

    def test_project_doctor_rejects_mnt_c_docker_even_when_it_claims_linux(self) -> None:
        # Break caught: a Docker binary surfaced from a Windows mount cannot be
        # accepted merely because its version output contains the word Linux.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-drvfs-docker-", dir="/tmp") as raw:
            root = Path(raw)
            project_root = root / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration["capabilities"] = [{"id": "docker", "required": True}]
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            write_healthy_fake_venv(project_root / ".venv")
            (project_root / "package.json").write_text(json.dumps({"name": "fixture", "private": True, "dependencies": {}}), encoding="utf-8")
            (project_root / "node_modules/placeholder").mkdir(parents=True)
            fake_docker = root / "docker"
            fake_docker.write_text("#!/bin/sh\necho linux\n", encoding="utf-8")
            fake_docker.chmod(0o755)
            with tempfile.TemporaryDirectory(prefix="ai-harness-docker-link-", dir="/mnt/c") as mount_raw:
                mounted_link = Path(mount_raw) / "docker"
                mounted_link.symlink_to(fake_docker)
                completed, payload = self.run_json(
                    PROJECT_DOCTOR,
                    ["--project-root", str(project_root), "--environment", str(environment_file)],
                    environment={**os.environ, "PATH": f"{mounted_link.parent}:/usr/bin:/bin"},
                )

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertIn("docker_not_linux_client", finding_categories(payload), payload)

    def test_project_doctor_classifies_missing_declared_manifests_independently(self) -> None:
        # Break caught: missing requirements/package manifests must not be hidden
        # by otherwise present runtime directories or reported as generic failure.
        with tempfile.TemporaryDirectory(prefix="ai-harness-project-manifest-") as raw:
            project_root = Path(raw) / "project"
            environment_file = self.copy_project_fixture(project_root)
            declaration = json.loads(environment_file.read_text(encoding="utf-8"))
            declaration["capabilities"] = []
            environment_file.write_text(json.dumps(declaration), encoding="utf-8")
            (project_root / "requirements.txt").unlink()
            (project_root / "package.json").unlink()
            write_healthy_fake_venv(project_root / ".venv")
            (project_root / "node_modules/placeholder").mkdir(parents=True)
            completed, payload = self.run_json(PROJECT_DOCTOR, ["--project-root", str(project_root), "--environment", str(environment_file)])

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertTrue({"missing_python_manifest", "missing_node_manifest"} <= finding_categories(payload), payload)

    def test_resolver_converts_existing_windows_drive_path_with_spaces_and_unicode(self) -> None:
        # Break caught: attachment paths with normal Windows spaces or Chinese
        # names must not be rejected or silently converted to a different file.
        with tempfile.TemporaryDirectory(prefix="ai harness 路径 ", dir="/mnt/c") as raw:
            source = Path(raw) / "病例 文档.txt"
            source.write_text("fixture", encoding="utf-8")
            relative = source.relative_to("/mnt/c")
            windows_path = "C:\\" + str(relative).replace("/", "\\\\")
            completed, payload = self.run_json(PATH_RESOLVER, ["--path", windows_path])

        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assertTrue(payload.get("ok"), payload)
        self.assertTrue(payload.get("exists"), payload)
        self.assertEqual(str(source), payload.get("wsl_path"), payload)

    def test_resolver_rejects_malformed_windows_path_without_guessing(self) -> None:
        # Break caught: treating arbitrary text as a path can rewrite commands,
        # regular expressions, or error messages supplied to the attachment flow.
        completed, payload = self.run_json(PATH_RESOLVER, ["--path", "C:relative\\not-a-rooted-path"])

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual("malformed_windows_path", payload.get("error", {}).get("category"), payload)
        self.assertFalse(payload.get("exists"), payload)

    def test_resolver_reports_missing_windows_file_deterministically(self) -> None:
        # Break caught: a missing attachment must surface its real category and
        # never trigger a disk scan that guesses a similarly named file.
        completed, payload = self.run_json(PATH_RESOLVER, ["--path", r"C:\\definitely-missing\\病例.txt"])

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual("path_not_found", payload.get("error", {}).get("category"), payload)
        self.assertFalse(payload.get("exists"), payload)

    def test_resolver_rejects_windows_traversal_device_and_unc_paths(self) -> None:
        # Break caught: a resolver that normalizes traversal or device/UNC input
        # can escape the selected drive or accidentally target a special device.
        cases = (
            (r"C:\\..\\..\\secret.txt", "path_traversal"),
            (r"C:\\safe\\nested\\..\\..\\..\\secret.txt", "path_traversal"),
            (r"\\\\.\\NUL", "unsupported_windows_path"),
            (r"\\\\server\\share\\病例.txt", "unsupported_windows_path"),
        )
        for candidate, category in cases:
            with self.subTest(path=candidate):
                completed, payload = self.run_json(PATH_RESOLVER, ["--path", candidate])
                self.assertNotEqual(0, completed.returncode, payload)
                self.assertFalse(payload.get("ok"), payload)
                self.assertFalse(payload.get("exists"), payload)
                self.assertEqual(category, payload.get("error", {}).get("category"), payload)

    def test_resolver_uses_wslpath_output_outside_mnt(self) -> None:
        # Break caught: hardcoding /mnt/<drive> ignores the active WSL path
        # bridge and rejects explicit paths resolved by an alternate mount setup.
        with tempfile.TemporaryDirectory(prefix="ai-harness-wslpath-success-", dir="/tmp") as raw:
            root = Path(raw)
            target = root / "bridge/病例 文档.txt"
            target.parent.mkdir()
            target.write_text("fixture", encoding="utf-8")
            wslpath = root / "wslpath"
            wslpath.write_text("#!/bin/sh\nprintf '%s\\n' \"$BRIDGED_PATH\"\n", encoding="utf-8")
            wslpath.chmod(0o755)
            completed, payload = self.run_json(
                PATH_RESOLVER,
                ["--path", r"C:\\Windows\\病例 文档.txt"],
                environment={**os.environ, "PATH": str(root), "BRIDGED_PATH": str(target)},
            )

        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(str(target), payload.get("wsl_path"), payload)

    def test_resolver_uses_wslpath_for_windows_drive_roots(self) -> None:
        # Break caught: C:\\ and C:/ are valid absolute Windows roots, so the
        # converter must receive them instead of rejecting their empty suffix.
        with tempfile.TemporaryDirectory(prefix="ai-harness-wslpath-drive-root-", dir="/tmp") as raw:
            root = Path(raw)
            target = root / "converted-root"
            target.mkdir()
            wslpath = root / "wslpath"
            wslpath.write_text("#!/bin/sh\nprintf '%s\\n' \"$BRIDGED_PATH\"\n", encoding="utf-8")
            wslpath.chmod(0o755)
            for windows_path in ("C:\\", "C:/"):
                with self.subTest(path=windows_path):
                    completed, payload = self.run_json(
                        PATH_RESOLVER,
                        ["--path", windows_path],
                        environment={**os.environ, "PATH": str(root), "BRIDGED_PATH": str(target)},
                    )
                    self.assertEqual(0, completed.returncode, payload)
                    self.assertTrue(payload.get("ok"), payload)
                    self.assertTrue(payload.get("exists"), payload)
                    self.assertEqual(str(target), payload.get("wsl_path"), payload)

    def test_resolver_reports_wslpath_unavailable_failed_and_invalid_output(self) -> None:
        # Break caught: unavailable, failed, or relative converter output must
        # retain stable JSON categories instead of falling back to guessed paths.
        with tempfile.TemporaryDirectory(prefix="ai-harness-wslpath-errors-", dir="/tmp") as raw:
            root = Path(raw)
            cases = (("unavailable", "wslpath_unavailable"), ("failed", "wslpath_failed"), ("relative", "wslpath_invalid_output"))
            for mode, category in cases:
                with self.subTest(mode=mode):
                    bin_root = root / mode
                    bin_root.mkdir()
                    if mode != "unavailable":
                        wslpath = bin_root / "wslpath"
                        command = "exit 41" if mode == "failed" else "printf 'relative/path\\n'"
                        wslpath.write_text(f"#!/bin/sh\n{command}\n", encoding="utf-8")
                        wslpath.chmod(0o755)
                    completed, payload = self.run_json(
                        PATH_RESOLVER,
                        ["--path", r"C:\\Windows\\fixture.txt"],
                        environment={**os.environ, "PATH": str(bin_root)},
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertFalse(payload.get("ok"), payload)
                    self.assertEqual(category, payload.get("error", {}).get("category"), payload)

    def test_provision_rejects_unknown_option_local_and_duplicate_baseline_entries(self) -> None:
        # Break caught: permissive package metadata can pass apt options, local
        # paths, or duplicate entries through a supposedly declarative baseline.
        invalid_packages = (
            {"name": "jq", "source": "apt", "command": "jq", "unexpected": True},
            {"name": "--allow-unauthenticated", "source": "apt", "command": "jq"},
            {"name": "./local-package.deb", "source": "apt", "command": "jq"},
            {"name": "/tmp/local-package.deb", "source": "apt", "command": "jq"},
        )
        with tempfile.TemporaryDirectory(prefix="ai-harness-invalid-baseline-") as raw:
            for index, package in enumerate(invalid_packages):
                with self.subTest(package=package["name"]):
                    baseline_path = Path(raw) / f"invalid-{index}.json"
                    baseline_path.write_text(
                        json.dumps({"schema_version": 1, "profiles": [{"id": "developer", "packages": [package]}]}),
                        encoding="utf-8",
                    )
                    completed, payload = self.run_json(PROVISION, ["--baseline", str(baseline_path)])
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertEqual("invalid_baseline", payload.get("error", {}).get("category"), payload)

            duplicate_path = Path(raw) / "duplicate.json"
            duplicate_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": [
                            {
                                "id": "developer",
                                "packages": [
                                    {"name": "jq", "source": "apt", "command": "jq"},
                                    {"name": "jq", "source": "apt", "command": "jq"},
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed, payload = self.run_json(PROVISION, ["--baseline", str(duplicate_path)])
            self.assertNotEqual(0, completed.returncode, payload)
            self.assertEqual("invalid_baseline", payload.get("error", {}).get("category"), payload)

    def test_provision_returns_json_when_fake_apt_get_fails(self) -> None:
        # Break caught: a failed explicit apply must retain machine-readable
        # diagnostics instead of leaking a traceback or silently retrying apt.
        with tempfile.TemporaryDirectory(prefix="ai-harness-fake-apt-", dir="/tmp") as raw:
            bin_root = Path(raw) / "bin"
            bin_root.mkdir()
            apt_get = bin_root / "apt-get"
            apt_get.write_text("#!/bin/sh\nexit 23\n", encoding="utf-8")
            apt_get.chmod(0o755)
            baseline_path = Path(raw) / "baseline.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": [{"id": "developer", "packages": [{"name": "fixture-tool", "source": "apt", "command": "fixture-tool"}]}],
                    }
                ),
                encoding="utf-8",
            )
            completed, payload = self.run_json(
                PROVISION,
                ["--baseline", str(baseline_path), "--apply"],
                environment={**os.environ, "PATH": f"{bin_root}:{os.environ.get('PATH', '')}"},
            )

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual("provision_failed", payload.get("error", {}).get("category"), payload)
        self.assertEqual([], payload.get("executed_commands"), payload)

    def test_bootstrap_syncs_managed_wsl_runtime_and_hashes_into_isolated_codex_home(self) -> None:
        # Break caught: a new Codex session can receive the old global AGENTS.md
        # but lack the baseline, schemas, and executable WSL tooling it needs.
        with tempfile.TemporaryDirectory(prefix="ai-harness-isolated-codex-") as raw:
            codex_home = Path(raw) / "codex"
            completed, payload = self.run_json(
                BOOTSTRAP,
                [
                    "--harness-root",
                    str(REPO_ROOT),
                    "--codex-home",
                    str(codex_home),
                    "--skip-rules",
                    "--skip-doctor",
                ],
            )
            runtime_root = codex_home / ".ai-harness/runtime/wsl-environment"
            receipt = codex_home / ".ai-harness/bootstrap.receipt.json"
            receipt_payload = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else {}

            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertTrue(payload.get("ok"), payload)
            for relative_target in MANAGED_WSL_RUNTIME_FILES:
                self.assertTrue(
                    (runtime_root / relative_target).is_file(),
                    f"bootstrap must install managed WSL runtime file: {relative_target}",
                )

            for relative_target, source_path in MANAGED_WSL_RUNTIME_FILES.items():
                target_path = runtime_root / relative_target
                self.assertTrue(source_path.is_file(), f"managed WSL runtime source missing: {source_path}")
                self.assertEqual(sha256_file(source_path), sha256_file(target_path), relative_target)

            runtime_entries = receipt_payload.get("managed_runtime_files")
            self.assertIsInstance(runtime_entries, list, receipt_payload)
            entries_by_target = {
                item.get("target_path"): item
                for item in runtime_entries
                if isinstance(item, dict) and isinstance(item.get("target_path"), str)
            }
            self.assertEqual(
                {str(runtime_root / relative_target) for relative_target in MANAGED_WSL_RUNTIME_FILES},
                set(entries_by_target),
                receipt_payload,
            )
            for relative_target, source_path in MANAGED_WSL_RUNTIME_FILES.items():
                target_path = runtime_root / relative_target
                entry = entries_by_target[str(target_path)]
                self.assertEqual(sha256_file(source_path), entry.get("source_sha256"), entry)
                self.assertEqual(sha256_file(target_path), entry.get("target_sha256"), entry)

    def test_installed_wsl_runtime_scripts_reach_their_json_contract(self) -> None:
        # Break caught: copied scripts without their shared runtime module fail
        # at import time, leaving a fresh Codex session unable to run its tools.
        with tempfile.TemporaryDirectory(prefix="ai-harness-installed-wsl-runtime-") as raw:
            codex_home = Path(raw) / "codex"
            bootstrapped, bootstrap_payload = self.run_json(
                BOOTSTRAP,
                ["--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor"],
            )
            self.assertEqual(0, bootstrapped.returncode, bootstrap_payload)
            runtime_bin = codex_home / ".ai-harness/runtime/wsl-environment/bin"
            commands = (
                ("provision-wsl.py", ["--profile", "developer"]),
                (
                    "project-env-doctor.py",
                    [
                        "--project-root", str(FIXTURES_ROOT / "project-valid"),
                        "--environment", str(FIXTURES_ROOT / "project-valid/config/ai/environment.json"),
                    ],
                ),
                ("resolve-wsl-path.py", ["--path", r"C:\\definitely-missing\\病例.txt"]),
                ("doctor-core.py", ["--repo-root", str(REPO_ROOT), "--codex-home", str(codex_home)]),
            )
            for script_name, arguments in commands:
                with self.subTest(script=script_name):
                    completed = subprocess.run(
                        [sys.executable, str(runtime_bin / script_name), *arguments, "--json"],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertNotIn("ModuleNotFoundError", completed.stderr, completed.stderr)
                    payload = json_payload(completed)
                    self.assertIn("ok", payload, payload)

    def test_machine_doctor_reports_runtime_tamper_or_deletion_stably(self) -> None:
        # Break caught: a stale or removed installed runtime must be visible to
        # machine doctor before a new session executes unverified tooling.
        for mode, expected_error in (("tamper", "managed_runtime_hash_mismatch"), ("delete", "managed_runtime_missing")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="ai-harness-runtime-integrity-") as raw:
                codex_home = Path(raw) / "codex"
                bootstrapped, bootstrap_payload = self.run_json(
                    BOOTSTRAP,
                    ["--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor"],
                )
                self.assertEqual(0, bootstrapped.returncode, bootstrap_payload)
                target = codex_home / ".ai-harness/runtime/wsl-environment/bin/provision-wsl.py"
                if mode == "tamper":
                    target.write_text("tampered\n", encoding="utf-8")
                else:
                    target.unlink()
                completed, payload = self.run_json(
                    MACHINE_DOCTOR,
                    ["--repo-root", str(REPO_ROOT), "--codex-home", str(codex_home)],
                )
                self.assertNotEqual(0, completed.returncode, payload)
                self.assertIn(expected_error, payload.get("errors", []), payload)

    def test_bootstrap_skip_sync_does_not_create_managed_wsl_runtime(self) -> None:
        # Break caught: --skip-sync must not leave partially refreshed tools
        # behind, because callers use it to guarantee a no-runtime-sync run.
        with tempfile.TemporaryDirectory(prefix="ai-harness-skip-wsl-runtime-") as raw:
            codex_home = Path(raw) / "codex"
            completed, payload = self.run_json(
                BOOTSTRAP,
                ["--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-sync", "--skip-rules", "--skip-doctor"],
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertTrue(payload.get("ok"), payload)
            self.assertFalse((codex_home / ".ai-harness/runtime/wsl-environment").exists(), payload)

    def test_machine_doctor_rejects_unregistered_runtime_files_and_receipt_path_drift(self) -> None:
        # Break caught: a newly copied runtime file or receipt redirected to a
        # different source/target can evade hash checks while changing execution.
        for mode in ("unexpected-file", "source-path", "target-path"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="ai-harness-runtime-drift-", dir="/tmp") as raw:
                codex_home = Path(raw) / "codex"
                bootstrapped, bootstrap_payload = self.run_json(
                    BOOTSTRAP,
                    ["--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor"],
                )
                self.assertEqual(0, bootstrapped.returncode, bootstrap_payload)
                receipt_path = codex_home / ".ai-harness/bootstrap.receipt.json"
                if mode == "unexpected-file":
                    extra = codex_home / ".ai-harness/runtime/wsl-environment/bin/unregistered.py"
                    extra.write_text("print('unregistered')\n", encoding="utf-8")
                    expected = "managed_runtime_unexpected"
                else:
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    key = "source_path" if mode == "source-path" else "target_path"
                    receipt["managed_runtime_files"][0][key] = str(Path("/tmp") / f"drifted-{key}")
                    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                    expected = "managed_runtime_receipt_path_mismatch"
                completed, payload = self.run_json(
                    MACHINE_DOCTOR,
                    ["--repo-root", str(REPO_ROOT), "--codex-home", str(codex_home)],
                    environment=linux_baseline_environment(Path(raw)),
                )
                self.assertNotEqual(0, completed.returncode, payload)
                self.assertIn(expected, payload.get("errors", []), payload)

    def test_machine_doctor_rejects_ambiguous_runtime_receipt_entries(self) -> None:
        # Break caught: receipt parsing must not silently collapse duplicate,
        # malformed, or conflicting target entries before integrity validation.
        with tempfile.TemporaryDirectory(prefix="ai-harness-runtime-receipt-shape-", dir="/tmp") as raw:
            root = Path(raw)
            environment = linux_baseline_environment(root)
            for mode in ("duplicate", "non-object", "conflicting-hash"):
                with self.subTest(mode=mode):
                    codex_home = root / mode / "codex"
                    bootstrapped, bootstrap_payload = self.run_json(
                        BOOTSTRAP,
                        ["--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor"],
                        environment=environment,
                    )
                    self.assertEqual(0, bootstrapped.returncode, bootstrap_payload)
                    receipt_path = codex_home / ".ai-harness/bootstrap.receipt.json"
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    entries = receipt["managed_runtime_files"]
                    self.assertTrue(entries, receipt)
                    if mode == "duplicate":
                        entries.append(dict(entries[0]))
                    elif mode == "non-object":
                        entries.append("not-a-runtime-receipt-object")
                    else:
                        conflict = dict(entries[0])
                        conflict["target_sha256"] = "0" * 64
                        entries[:] = [conflict, dict(entries[0])]
                    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                    completed, payload = self.run_json(
                        MACHINE_DOCTOR,
                        ["--repo-root", str(REPO_ROOT), "--codex-home", str(codex_home)],
                        environment=environment,
                    )
                    self.assertNotEqual(0, completed.returncode, payload)
                    self.assertIn("managed_runtime_receipt_mismatch", payload.get("errors", []), payload)

    def test_bootstrap_skip_sync_preserves_healthy_runtime_and_receipt(self) -> None:
        # Break caught: a no-sync bootstrap must retain an already verified
        # runtime and still pass doctor, rather than deleting or rehashing it.
        with tempfile.TemporaryDirectory(prefix="ai-harness-runtime-preserve-", dir="/tmp") as raw:
            root = Path(raw)
            environment = linux_baseline_environment(root)
            codex_home = root / "codex"
            initial, initial_payload = self.run_json(
                BOOTSTRAP,
                ["--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-rules", "--skip-doctor"],
                environment=environment,
            )
            self.assertEqual(0, initial.returncode, initial_payload)
            (codex_home / 'config.toml').write_text(''.join('[plugins."'+name+'"]'+chr(10)+'enabled=true'+chr(10) for name in ['browser@openai-bundled','unified-computer-use@openai-bundled','computer-use@openai-bundled']))
            receipt_path = codex_home / ".ai-harness/bootstrap.receipt.json"
            before_entries = json.loads(receipt_path.read_text(encoding="utf-8"))["managed_runtime_files"]
            runtime_hashes = {path.relative_to(codex_home).as_posix(): sha256_file(path) for path in (codex_home / ".ai-harness/runtime/wsl-environment").rglob("*") if path.is_file()}
            completed, payload = self.run_json(
                BOOTSTRAP,
                ["--harness-root", str(REPO_ROOT), "--codex-home", str(codex_home), "--skip-sync", "--skip-rules"],
                environment=environment,
            )
            after_entries = json.loads(receipt_path.read_text(encoding="utf-8"))["managed_runtime_files"]
            after_hashes = {path.relative_to(codex_home).as_posix(): sha256_file(path) for path in (codex_home / ".ai-harness/runtime/wsl-environment").rglob("*") if path.is_file()}

        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(before_entries, after_entries)
        self.assertEqual(runtime_hashes, after_hashes)


if __name__ == "__main__":
    unittest.main()
