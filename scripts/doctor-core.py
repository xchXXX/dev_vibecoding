from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from runtime_common import MANAGED_SKILLS, emit, resolve_codex_home, resolve_repo_root, sha256_file


MANAGED_MARKER = "<!-- ai-harness:managed-global-agents:v1 -->"
HOOK_CONFIG_PATTERN = re.compile(
    r"(?im)(?:^\s*\[[^\]\n]*hook[^\]\n]*\]\s*$|"
    r"^\s*[a-z0-9_.-]*hook[a-z0-9_.-]*\s*=|\bhooks?/)"
)
WSL_REQUIRED_COMMANDS = (
    "jq", "unzip", "zip", "tree", "strace", "shellcheck", "shfmt", "fzf",
    "sqlite3", "dos2unix", "gcc", "g++", "make", "pkg-config", "cmake", "ninja",
    "pip3", "pnpm",
)
WSL_NODE_TOOLCHAIN_COMMANDS = ("node", "npm", "pnpm", "corepack")
STRICT_CONTRACT_TESTS = (
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
MANAGED_SCHEMA_FILES = ("orchestrator-task-state.schema.json",)


def _command_path(command: str) -> str:
    located = shutil.which(command)
    if not located:
        return ""
    try:
        return str(Path(located).resolve())
    except OSError:
        return located


def _is_windows_backed(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith("/mnt/c/") or "/program files/" in normalized


def _wsl_tool_audit() -> dict[str, Any]:
    paths = {command: _command_path(command) for command in WSL_REQUIRED_COMMANDS}
    fd_path = _command_path("fd")
    fdfind_path = _command_path("fdfind")
    fd_command, selected_fd_path = ("fd", fd_path) if fd_path else ("fdfind", fdfind_path)
    paths.update({command: _command_path(command) for command in WSL_NODE_TOOLCHAIN_COMMANDS})
    paths["fdfind"] = selected_fd_path

    ordered_ids = (*WSL_REQUIRED_COMMANDS, "fdfind", *WSL_NODE_TOOLCHAIN_COMMANDS)
    tools = []
    for command in dict.fromkeys(ordered_ids):
        path = paths[command]
        tools.append({
            "id": command,
            "available": bool(path),
            "path": path,
            "linux_native": bool(path) and not _is_windows_backed(path),
        })

    missing_tools = [item["id"] for item in tools if not item["available"]]
    windows_path_tools = [item["id"] for item in tools if item["available"] and not item["linux_native"]]
    return {
        "ok": not missing_tools and not windows_path_tools,
        "tools": tools,
        "missing_tools": missing_tools,
        "windows_path_tools": windows_path_tools,
        "fd_compatibility": {
            "available": bool(selected_fd_path),
            "command": fd_command if selected_fd_path else "",
            "path": selected_fd_path,
            "ubuntu_package": "fd-find",
            "note": "Ubuntu fd-find exposes fdfind; fd is accepted when present.",
        },
    }


def _files(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        return None, str(error)
    if not isinstance(payload, dict):
        return None, "root_not_object"
    return payload, None


def _runtime_validation_contract() -> dict[str, Any]:
    return {
        "six_points": {
            "do": "Validate the installed GTO runtime.",
            "do_not": ["Do not write project files."],
            "change_areas": ["schemas/orchestrator-task-state.schema.json"],
            "implementation": "Run the installed controller validate action.",
            "acceptance": ["Installed validation succeeds."],
            "risks": ["The runtime schema can drift."],
        },
        "objective": "Validate the installed GTO runtime.",
        "scope_in": ["schemas/orchestrator-task-state.schema.json"],
        "scope_out": ["Do not write project files."],
        "acceptance": ["Installed validation succeeds."],
        "stop_conditions": ["The runtime schema can drift."],
        "decisions": ["Run the installed controller validate action."],
        "approval": {"status": "approved", "approved_by": "doctor"},
        "subtasks": [
            {
                "subtask_id": "DOCTOR-001",
                "title": "Validate installed controller",
                "role": "test-verifier",
                "status": "ready",
                "dependencies": [],
                "read_paths": ["schemas/orchestrator-task-state.schema.json"],
                "write_paths": [],
                "assignment": {
                    "goal": "Validate the installed controller.",
                    "must_include": ["Use read-only validate."],
                    "verification": ["Run validate."],
                },
            }
        ],
    }


def _installed_gto_validation(repo_root: Path, codex_home: Path) -> dict[str, Any]:
    controller = codex_home / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
    source_controller = repo_root / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
    payload: dict[str, Any] = {
        "controller_path": str(controller),
        "action": "validate",
        "ok": False,
        "returncode": None,
        "stdout": "",
        "stderr": "",
    }
    if not controller.is_file():
        payload["stderr"] = "installed_gto_controller_missing"
        return payload
    if not source_controller.is_file():
        payload["stderr"] = "source_gto_controller_missing"
        return payload
    with tempfile.TemporaryDirectory(prefix="ai-harness-gto-doctor-", dir="/tmp") as raw:
        fixture_root = Path(raw)
        task_id = "DOCTOR-001"
        contract_path = fixture_root / "contract.json"
        contract_path.write_text(json.dumps(_runtime_validation_contract()), encoding="utf-8")
        initialized = subprocess.run(
            [
                sys.executable, str(source_controller), "--action", "init-task",
                "--repo-root", str(fixture_root), "--task-id", task_id,
                "--title", "Installed controller validation", "--owner", "doctor",
                "--contract-json-file", str(contract_path), "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if initialized.returncode:
            payload.update(returncode=initialized.returncode, stdout=initialized.stdout, stderr=initialized.stderr)
            return payload
        validated = subprocess.run(
            [
                sys.executable, str(controller), "--action", "validate",
                "--repo-root", str(fixture_root), "--task-id", task_id, "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    try:
        result = json.loads(validated.stdout)
    except json.JSONDecodeError:
        result = {}
    payload.update(
        ok=validated.returncode == 0 and bool(result.get("ok")),
        returncode=validated.returncode,
        stdout=validated.stdout,
        stderr=validated.stderr,
    )
    return payload


def _contract_gate(repo_root: Path) -> dict[str, Any]:
    command = [sys.executable, "-m", "unittest", "-q", *STRICT_CONTRACT_TESTS]
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return {
            "ok": False,
            "tests": list(STRICT_CONTRACT_TESTS),
            "test_count": len(STRICT_CONTRACT_TESTS),
            "returncode": None,
            "stdout": "",
            "stderr": str(error),
        }
    return {
        "ok": completed.returncode == 0,
        "tests": list(STRICT_CONTRACT_TESTS),
        "test_count": len(STRICT_CONTRACT_TESTS),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _bootstrap_audit(repo_root: Path, codex_home: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    receipt_path = codex_home / ".ai-harness" / "bootstrap.receipt.json"
    agents_path = codex_home / "AGENTS.md"
    template_path = repo_root / "templates/codex/AGENTS.global.md"
    receipt, receipt_error = _read_json_object(receipt_path)
    if receipt_error:
        issues.append({"type": "bootstrap_receipt_invalid" if receipt_error != "missing" else "bootstrap_receipt_missing", "path": str(receipt_path), "error": receipt_error})
    if not agents_path.is_file():
        issues.append({"type": "global_agents_missing", "path": str(agents_path)})
    if not template_path.is_file():
        issues.append({"type": "global_agents_template_missing", "path": str(template_path)})
    if agents_path.is_file() and template_path.is_file():
        actual = agents_path.read_text(encoding="utf-8-sig")
        expected = template_path.read_text(encoding="utf-8-sig").replace("{{HARNESS_ROOT}}", repo_root.as_posix())
        if not actual.startswith(MANAGED_MARKER):
            issues.append({"type": "global_agents_unmanaged", "path": str(agents_path)})
        if actual != expected:
            issues.append({"type": "global_agents_template_drift", "path": str(agents_path)})
    if receipt is not None:
        checks = (
            ("harness_root", str(repo_root), "bootstrap_harness_root_mismatch"),
            ("codex_home", str(codex_home), "bootstrap_codex_home_mismatch"),
            ("target_path", str(agents_path), "bootstrap_target_path_mismatch"),
            ("template_path", str(template_path), "bootstrap_template_path_mismatch"),
        )
        for field, expected, issue_type in checks:
            if str(receipt.get(field, "")) != expected:
                issues.append({"type": issue_type, "path": str(receipt_path)})
        if agents_path.is_file() and receipt.get("target_sha256") != sha256_file(agents_path):
            issues.append({"type": "bootstrap_target_hash_mismatch", "path": str(agents_path)})
        if template_path.is_file() and receipt.get("template_sha256") != sha256_file(template_path):
            issues.append({"type": "bootstrap_template_hash_mismatch", "path": str(template_path)})
    return {
        "receipt_path": str(receipt_path), "global_agents_path": str(agents_path),
        "issues": issues, "ok": not issues,
    }


def _hook_audit(repo_root: Path, codex_home: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    hooks_path = codex_home / "hooks.json"
    payload, hooks_error = _read_json_object(hooks_path)
    if hooks_error and hooks_error != "missing":
        issues.append({"type": "hooks_json_invalid", "path": str(hooks_path), "error": hooks_error})
    if payload is not None and payload.get("hooks") not in (None, {}):
        issues.append({"type": "hook_configuration_present", "path": str(hooks_path), "location": "root.hooks"})
    for config_path in (codex_home / "config.toml", repo_root / ".codex/config.toml"):
        if not config_path.is_file():
            continue
        source = config_path.read_text(encoding="utf-8-sig").replace("\\", "/")
        if HOOK_CONFIG_PATTERN.search(source):
            issues.append({"type": "hook_configuration_present", "path": str(config_path), "location": "text"})
    return {"hooks_path": str(hooks_path), "issues": issues, "ok": not issues}


def audit(repo_root: Path, codex_home: Path) -> dict[str, Any]:
    source_issues: list[dict[str, str]] = []
    runtime_issues: list[dict[str, str]] = []
    receipt_issues: list[dict[str, str]] = []
    skills: list[dict[str, Any]] = []
    schemas: list[dict[str, Any]] = []
    receipt_path = codex_home / ".ai-harness" / "codex-sync.receipt.json"
    receipt: dict[str, Any] | None = None
    if receipt_path.is_file():
        try:
            parsed = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
            receipt = parsed if isinstance(parsed, dict) else None
        except (OSError, json.JSONDecodeError) as error:
            receipt_issues.append({"type": "receipt_invalid", "path": str(receipt_path), "error": str(error)})
    else:
        receipt_issues.append({"type": "receipt_missing", "path": str(receipt_path)})
    for name in MANAGED_SKILLS:
        source_root = repo_root / "skills" / name
        runtime_root = codex_home / "skills" / name
        source_hashes = _files(source_root)
        runtime_hashes = _files(runtime_root)
        if not source_hashes:
            source_issues.append({"type": "source_skill_missing", "skill": name, "path": str(source_root)})
        for relative, digest in source_hashes.items():
            if relative not in runtime_hashes:
                runtime_issues.append({"type": "runtime_file_missing", "skill": name, "target": relative})
            elif runtime_hashes[relative] != digest:
                runtime_issues.append({"type": "runtime_hash_mismatch", "skill": name, "target": relative})
        for relative in sorted(set(runtime_hashes) - set(source_hashes)):
            runtime_issues.append({"type": "runtime_unexpected_managed_file", "skill": name, "target": relative})
        skill_issues = [issue for issue in source_issues + runtime_issues if issue.get("skill") == name]
        skills.append({"managed_skill_name": name, "source_file_count": len(source_hashes), "runtime_file_count": len(runtime_hashes), "issues": skill_issues, "ok": not skill_issues})
    for name in MANAGED_SCHEMA_FILES:
        source = repo_root / "schemas" / name
        target = codex_home / "schemas" / name
        schema_issues: list[dict[str, str]] = []
        if not source.is_file():
            issue = {"type": "source_schema_missing", "schema": name, "path": str(source)}
            source_issues.append(issue)
            schema_issues.append(issue)
        elif not target.is_file():
            issue = {"type": "runtime_schema_missing", "schema": name, "path": str(target)}
            runtime_issues.append(issue)
            schema_issues.append(issue)
        elif sha256_file(source) != sha256_file(target):
            issue = {"type": "runtime_schema_hash_mismatch", "schema": name, "path": str(target)}
            runtime_issues.append(issue)
            schema_issues.append(issue)
        schemas.append({
            "managed_schema_name": name,
            "source_path": str(source),
            "target_path": str(target),
            "issues": schema_issues,
            "ok": not schema_issues,
        })
    if receipt is not None:
        if receipt.get("managed_skills") != list(MANAGED_SKILLS):
            receipt_issues.append({"type": "receipt_managed_skills_mismatch", "path": str(receipt_path)})
        if Path(str(receipt.get("harness_root", ""))).resolve() != repo_root:
            receipt_issues.append({"type": "receipt_harness_root_mismatch", "path": str(receipt_path)})
        if Path(str(receipt.get("codex_home", ""))).resolve() != codex_home:
            receipt_issues.append({"type": "receipt_codex_home_mismatch", "path": str(receipt_path)})
        expected = {
            (item.get("skill"), item.get("target"), item.get("sha256"))
            for item in receipt.get("managed_files", []) if isinstance(item, dict)
        }
        actual = {
            (name, f"{name}/{relative}", digest)
            for name in MANAGED_SKILLS for relative, digest in _files(repo_root / "skills" / name).items()
        }
        if expected != actual:
            receipt_issues.append({"type": "receipt_managed_files_mismatch", "path": str(receipt_path)})
        expected_schemas = {
            (item.get("source"), item.get("target"), item.get("sha256"))
            for item in receipt.get("managed_schema_files", []) if isinstance(item, dict)
        }
        actual_schemas = {
            (f"schemas/{name}", f"schemas/{name}", sha256_file(repo_root / "schemas" / name))
            for name in MANAGED_SCHEMA_FILES
            if (repo_root / "schemas" / name).is_file()
        }
        if expected_schemas != actual_schemas:
            receipt_issues.append({"type": "receipt_managed_schema_files_mismatch", "path": str(receipt_path)})
    bootstrap = _bootstrap_audit(repo_root, codex_home)
    hooks = _hook_audit(repo_root, codex_home)
    installed_gto_validation = _installed_gto_validation(repo_root, codex_home)
    if not installed_gto_validation["ok"]:
        runtime_issues.append({"type": "installed_gto_validation_failed", "path": installed_gto_validation["controller_path"]})
    wsl_tool_audit = _wsl_tool_audit()
    tool_issues = ([{"type": "wsl_tool_missing", "tool": tool} for tool in wsl_tool_audit["missing_tools"]] +
                   [{"type": "wsl_tool_windows_path", "tool": tool} for tool in wsl_tool_audit["windows_path_tools"]])
    issues = source_issues + runtime_issues + receipt_issues + bootstrap["issues"] + hooks["issues"] + tool_issues
    codex_audit = {
        "managed_skills": list(MANAGED_SKILLS), "skills": skills, "schemas": schemas,
        "source_issues": source_issues, "runtime_issues": runtime_issues,
        "receipt_issues": receipt_issues, "bootstrap": bootstrap,
        "hooks": hooks, "installed_gto_validation": installed_gto_validation, "ok": not issues,
    }
    return {
        "ok": not issues,
        "repo_root": str(repo_root),
        "codex_home": str(codex_home),
        "codex_audit": codex_audit,
        "wsl_tool_audit": wsl_tool_audit,
        "errors": sorted({issue["type"] for issue in issues}),
        "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the Linux-native Codex managed-skill runtime.")
    parser.add_argument("--root", "--repo-root", dest="repo_root", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--audit-target", choices=("codex_minimal",), default="codex_minimal")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_repo_root(args.repo_root, Path(__file__))
        payload = audit(root, resolve_codex_home(args.codex_home))
        if args.strict:
            contract_gate = _contract_gate(root)
            payload["contract_gate"] = contract_gate
            if not contract_gate["ok"]:
                payload["ok"] = False
                payload["errors"] = sorted({*payload.get("errors", []), "contract_gate_failed"})
    except (OSError, ValueError) as error:
        payload = {"ok": False, "errors": [str(error)]}
    code = emit(payload, as_json=args.json, success_message="Codex managed runtime audit passed")
    return code if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
