from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from typing import Any

from runtime_common import MANAGED_SKILLS, MANAGED_WSL_RUNTIME_FILES, command_available, emit, inspect_windows_external_capabilities, load_wsl_baseline, resolve_codex_home, resolve_repo_root, select_wsl_profile, sha256_file


MANAGED_MARKER = "<!-- ai-harness:managed-global-agents:v1 -->"
HOOK_CONFIG_PATTERN = re.compile(
    r"(?im)(?:^\s*\[[^\]\n]*hook[^\]\n]*\]\s*$|"
    r"^\s*[a-z0-9_.-]*hook[a-z0-9_.-]*\s*=|\bhooks?/)"
)
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


def _command_path(command: str) -> str:
    located = shutil.which(command)
    return located or ""


def _is_windows_backed(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return bool(re.match(r"^/mnt/[a-z](?:/|$)", normalized) or re.match(r"^[a-z]:/", normalized) or "/program files/" in normalized)


def _is_linux_native_command_path(path: str) -> bool:
    if not path:
        return False
    if not _is_windows_backed(path):
        return True
    normalized = path.replace("\\", "/").lower()
    if not re.search(r"(?:^|/)\.codex/bin/wsl/[0-9a-f]+/[^/]+$", normalized):
        return False
    try:
        with Path(path).open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def _is_windows_environment_value(value: str) -> bool:
    normalized = value.replace("\\", "/").lower()
    return normalized.startswith("/mnt/") or (len(normalized) >= 3 and normalized[1:3] == ":/")


def _machine_environment_findings(tool_audit: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for tool in tool_audit["tools"]:
        if tool["available"] and not tool["linux_native"]:
            findings.append({"category": "windows_command_path", "command": tool["id"], "path": tool["path"]})
    for variable in ("TEMP", "TMP", "TMPDIR"):
        value = os.environ.get(variable, "")
        if value and _is_windows_environment_value(value):
            findings.append({"category": "windows_temp", "variable": variable, "value": value})
    return findings


def _wsl_tool_audit(baseline_path: Path, profile_id: str = "developer") -> dict[str, Any]:
    baseline, validation_errors = load_wsl_baseline(baseline_path)
    profile = select_wsl_profile(baseline, profile_id) if baseline else None
    if validation_errors or profile is None:
        return {"ok": False, "tools": [], "missing_tools": [], "windows_path_tools": [], "fd_compatibility": {"available": False, "command": "", "path": "", "ubuntu_package": "fd-find", "note": ""}, "errors": validation_errors or ["baseline_profile_missing"]}
    package_audit: list[dict[str, Any]] = []
    audit_commands: list[str] = []
    unhealthy_commands: set[str] = set()
    for package in profile["packages"]:
        command = package["command"]
        path = _command_path(command)
        available = bool(path) and command_available(package)
        audit_commands.append(command)
        audit_commands.extend(package.get("doctor_commands", []))
        if not available:
            unhealthy_commands.add(command)
        entry = {
            "id": package["name"],
            "command": command,
            "available": available,
            "path": path,
            "linux_native": _is_linux_native_command_path(path),
        }
        package_audit.append(entry)
    ordered_ids: list[str] = []
    for package in profile["packages"]:
        ordered_ids.extend(package.get("doctor_commands", []))
    if not ordered_ids:
        ordered_ids = [package["command"] for package in profile["packages"]]
    ordered_ids = list(dict.fromkeys(ordered_ids))
    audit_commands = list(dict.fromkeys(audit_commands))
    paths = {command: _command_path(command) for command in ordered_ids}
    selected_fd_path = paths.get("fd") or paths.get("fdfind", "")
    fd_command = "fd" if paths.get("fd") else "fdfind"
    tools = []
    for command in ordered_ids:
        path = paths[command]
        tools.append({
            "id": command,
            "available": bool(path),
            "path": path,
            "linux_native": _is_linux_native_command_path(path),
        })

    missing_tools = sorted({*unhealthy_commands, *(command for command in audit_commands if not _command_path(command))})
    windows_path_tools = sorted({command for command in audit_commands if (path := _command_path(command)) and not _is_linux_native_command_path(path)})
    return {
        "ok": not missing_tools and not windows_path_tools,
        "tools": tools,
        "package_audit": package_audit,
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


def _runtime_validation_contract(skill_root: Path) -> dict[str, Any]:
    """Exercise the current packaged contract without maintaining a second schema fixture."""
    return json.loads((skill_root / "references/revision-3-contract.example.json").read_text(encoding="utf-8"))


def _installed_gto_validation(repo_root: Path, codex_home: Path, *, compare_source: bool = True) -> dict[str, Any]:
    controller = codex_home / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
    source_controller = (
        repo_root / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
        if compare_source else controller
    )
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
        contract_path = fixture_root / ".tmp" / "contract.json"
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(json.dumps(_runtime_validation_contract(source_controller.parents[1])), encoding="utf-8")
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
        environment = dict(os.environ)
        environment["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        completed = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
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


def _wsl_runtime_audit(repo_root: Path, codex_home: Path, receipt: dict[str, Any] | None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    runtime_root = codex_home / ".ai-harness" / "runtime" / "wsl-environment"
    expected_receipt = {str(runtime_root / target): source for target, source in MANAGED_WSL_RUNTIME_FILES}
    raw_entries = (receipt or {}).get("managed_runtime_files", [])
    if not isinstance(raw_entries, list) or any(not isinstance(item, dict) for item in raw_entries):
        issues.append({"type": "managed_runtime_receipt_mismatch", "path": str(runtime_root)})
        raw_entries = []
    receipt_entries = {
        item.get("target_path"): item
        for item in raw_entries
        if isinstance(item, dict) and isinstance(item.get("target_path"), str)
    }
    if len(receipt_entries) != len(raw_entries) or not set(expected_receipt).issubset(receipt_entries):
        issues.append({"type": "managed_runtime_receipt_mismatch", "path": str(runtime_root)})
    for target_relative, source_relative in MANAGED_WSL_RUNTIME_FILES:
        source = repo_root / source_relative
        target = runtime_root / target_relative
        if not source.is_file():
            issues.append({"type": "managed_runtime_source_missing", "path": str(source)})
        elif not target.is_file():
            issues.append({"type": "managed_runtime_missing", "path": str(target)})
        elif sha256_file(source) != sha256_file(target):
            issues.append({"type": "managed_runtime_hash_mismatch", "path": str(target)})
        entry = receipt_entries.get(str(target))
        if entry is None:
            issues.append({"type": "managed_runtime_receipt_mismatch", "path": str(target)})
        else:
            if entry.get("source_path") != str(source) or entry.get("target_path") != str(target):
                issues.append({"type": "managed_runtime_receipt_path_mismatch", "path": str(target)})
            if source.is_file() and target.is_file() and (entry.get("source_sha256") != sha256_file(source) or entry.get("target_sha256") != sha256_file(target)):
                issues.append({"type": "managed_runtime_receipt_mismatch", "path": str(target)})
        if any(
            isinstance(item, dict) and item.get("source_path") == str(source) and item.get("target_path") != str(target)
            for item in raw_entries
        ):
            issues.append({"type": "managed_runtime_receipt_path_mismatch", "path": str(target)})
    for target_path in receipt_entries:
        if target_path not in expected_receipt and Path(target_path).is_relative_to(runtime_root):
            issues.append({"type": "managed_runtime_unexpected", "path": target_path})
    expected_files = {target for target, _ in MANAGED_WSL_RUNTIME_FILES}
    if runtime_root.is_dir():
        for path in runtime_root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                relative = path.relative_to(runtime_root).as_posix()
                if relative not in expected_files:
                    issues.append({"type": "managed_runtime_unexpected", "path": str(path)})
    return issues


def _docker_safe_start_audit(repo_root: Path, codex_home: Path) -> dict[str, Any]:
    source_relative = Path("modules/wsl-environment/tooling/docker-desktop-safe-start.ps1")
    installed_relative = Path(".ai-harness/runtime/windows-external/docker-desktop-safe-start.ps1")
    receipt_path = codex_home / ".ai-harness" / "docker-safe-start.receipt.json"
    source_path = repo_root / source_relative
    installed_path = codex_home / installed_relative
    if not receipt_path.is_file():
        return {
            "installed": False,
            "receipt_path": str(receipt_path),
            "source_path": str(source_path),
            "installed_path": str(installed_path),
            "issues": [],
            "ok": True,
        }

    issues: list[dict[str, str]] = []
    receipt, receipt_error = _read_json_object(receipt_path)
    if receipt_error:
        issues.append({"type": "docker_safe_start_receipt_invalid", "path": str(receipt_path), "error": receipt_error})
        receipt = None
    if receipt is not None:
        expected_fields = {
            "schema_version": 1,
            "source_relative_path": source_relative.as_posix(),
            "installed_relative_path": installed_relative.as_posix(),
            "task_name": "AI Harness Docker Safe Start",
            "task_registered": False,
            "startup_entry_name": "AI Harness Docker Safe Start",
            "startup_entry_registered": True,
            "startup_entry_mode": "hkcu_run",
        }
        for field, expected in expected_fields.items():
            if receipt.get(field) != expected:
                issues.append({"type": "docker_safe_start_receipt_mismatch", "path": str(receipt_path), "field": field})
    if not source_path.is_file():
        issues.append({"type": "docker_safe_start_source_missing", "path": str(source_path)})
    if not installed_path.is_file():
        issues.append({"type": "docker_safe_start_installed_missing", "path": str(installed_path)})
    if receipt is not None and source_path.is_file() and installed_path.is_file():
        source_hash = sha256_file(source_path)
        installed_hash = sha256_file(installed_path)
        if source_hash != installed_hash:
            issues.append({"type": "docker_safe_start_hash_mismatch", "path": str(installed_path)})
        if receipt.get("source_sha256") != source_hash or receipt.get("installed_sha256") != installed_hash:
            issues.append({"type": "docker_safe_start_receipt_hash_mismatch", "path": str(receipt_path)})
    return {
        "installed": True,
        "receipt_path": str(receipt_path),
        "source_path": str(source_path),
        "installed_path": str(installed_path),
        "issues": issues,
        "ok": not issues,
    }


def audit(
    repo_root: Path,
    codex_home: Path,
    baseline_path: Path | None = None,
    managed_skill: str | None = None,
) -> dict[str, Any]:
    if managed_skill is not None and managed_skill not in MANAGED_SKILLS:
        raise ValueError(f"unsupported managed skill audit scope: {managed_skill}")
    selected_skills = set(MANAGED_SKILLS if managed_skill is None else (managed_skill,))
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
        if name in selected_skills:
            expected_hashes = source_hashes
            if not source_hashes:
                source_issues.append({"type": "source_skill_missing", "skill": name, "path": str(source_root)})
        else:
            expected_hashes = {
                str(item.get("target", ""))[len(name) + 1:]: str(item.get("sha256", ""))
                for item in (receipt or {}).get("managed_files", [])
                if isinstance(item, dict) and item.get("skill") == name
                and str(item.get("target", "")).startswith(name + "/")
            }
        for relative, digest in expected_hashes.items():
            if relative not in runtime_hashes:
                runtime_issues.append({"type": "runtime_file_missing", "skill": name, "target": relative})
            elif runtime_hashes[relative] != digest:
                issue_type = "runtime_hash_mismatch" if name in selected_skills else "runtime_receipt_hash_mismatch"
                runtime_issues.append({"type": issue_type, "skill": name, "target": relative})
        for relative in sorted(set(runtime_hashes) - set(expected_hashes)):
            runtime_issues.append({"type": "runtime_unexpected_managed_file", "skill": name, "target": relative})
        skill_issues = [issue for issue in source_issues + runtime_issues if issue.get("skill") == name]
        skills.append({"managed_skill_name": name, "source_file_count": len(source_hashes), "runtime_file_count": len(runtime_hashes), "issues": skill_issues, "ok": not skill_issues})
    # GTO has only its package schema; unrelated schema ownership remains auditable.
    legacy_relative = 'schemas/orchestrator-task-state.schema.json'
    legacy = codex_home / legacy_relative
    if legacy.exists() or legacy.is_symlink():
        runtime_issues.append({"type": "legacy_gto_schema_present", "path": str(legacy)})
    for row in (receipt or {}).get("managed_schema_files", []):
        relative = row.get("target", "") if isinstance(row, dict) else ""
        target = codex_home / relative
        issues = []
        if relative == legacy_relative or (isinstance(row, dict) and row.get('source') == legacy_relative):
            issues.append({"type": "legacy_gto_schema_inventory", "path": relative})
        elif (not relative.startswith("schemas/") or ".." in Path(relative).parts
                or target.is_symlink() or not target.resolve().is_relative_to(codex_home.resolve())):
            issues.append({"type": "receipt_schema_target_invalid", "path": relative})
        elif not target.is_file() or sha256_file(target) != row.get("sha256"):
            issues.append({"type": "runtime_schema_receipt_hash_mismatch", "path": str(target)})
        runtime_issues.extend(issues)
        schemas.append({"target_path": str(target), "issues": issues, "ok": not issues})
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
            for name in MANAGED_SKILLS
            for relative, digest in _files(
                (repo_root / "skills" / name) if name in selected_skills else (codex_home / "skills" / name)
            ).items()
        }
        if expected != actual:
            receipt_issues.append({"type": "receipt_managed_files_mismatch", "path": str(receipt_path)})
    bootstrap = _bootstrap_audit(repo_root, codex_home)
    runtime_issues.extend(_wsl_runtime_audit(repo_root, codex_home, _read_json_object(codex_home / ".ai-harness" / "bootstrap.receipt.json")[0]))
    hooks = _hook_audit(repo_root, codex_home)
    docker_safe_start = _docker_safe_start_audit(repo_root, codex_home)
    windows_external_capabilities = inspect_windows_external_capabilities(
        codex_home,
        codex_home / ".ai-harness/runtime/wsl-environment/config/windows-external-capabilities.json",
    )
    installed_gto_validation = _installed_gto_validation(
        repo_root,
        codex_home,
        compare_source=managed_skill in {None, "global-task-orchestrator"},
    )
    if not installed_gto_validation["ok"]:
        runtime_issues.append({"type": "installed_gto_validation_failed", "path": installed_gto_validation["controller_path"]})
    wsl_tool_audit = _wsl_tool_audit(baseline_path or (repo_root / "config" / "ai" / "wsl-tool-baseline.json"))
    environment_findings = _machine_environment_findings(wsl_tool_audit)
    tool_issues = ([{"type": "wsl_tool_missing", "tool": tool} for tool in wsl_tool_audit["missing_tools"]] +
                   [{"type": "wsl_tool_windows_path", "tool": tool} for tool in wsl_tool_audit["windows_path_tools"]] +
                   [{"type": finding["category"], "path": finding.get("path", "")} for finding in environment_findings])
    if wsl_tool_audit.get("errors"):
        tool_issues.extend({"type": "invalid_wsl_baseline", "error": error} for error in wsl_tool_audit["errors"])
    issues = source_issues + runtime_issues + receipt_issues + bootstrap["issues"] + hooks["issues"] + docker_safe_start["issues"] + windows_external_capabilities["issues"] + tool_issues
    codex_audit = {
        "managed_skills": list(MANAGED_SKILLS), "audit_scope": managed_skill or "all", "skills": skills, "schemas": schemas,
        "source_issues": source_issues, "runtime_issues": runtime_issues,
        "receipt_issues": receipt_issues, "bootstrap": bootstrap,
        "hooks": hooks, "docker_safe_start": docker_safe_start,
        "windows_external_capabilities": windows_external_capabilities,
        "installed_gto_validation": installed_gto_validation, "ok": not issues,
    }
    return {
        "ok": not issues,
        "repo_root": str(repo_root),
        "codex_home": str(codex_home),
        "codex_audit": codex_audit,
        "windows_external_capabilities": windows_external_capabilities,
        "wsl_tool_audit": wsl_tool_audit,
        "findings": environment_findings,
        "errors": sorted({issue["type"] for issue in issues}),
        "warnings": [],
    }


def audit_environment(repo_root: Path, codex_home: Path, baseline_path: Path | None = None) -> dict[str, Any]:
    """Environment-only audit never executes managed skills or their schemas."""
    receipt, error = _read_json_object(codex_home / ".ai-harness/bootstrap.receipt.json")
    issues = _wsl_runtime_audit(repo_root, codex_home, receipt)
    if error:
        issues.append({"type": "bootstrap_receipt_invalid", "error": error})
    plugins = inspect_windows_external_capabilities(codex_home,
        codex_home / ".ai-harness/runtime/wsl-environment/config/windows-external-capabilities.json")
    issues.extend(plugins["issues"])
    tools = _wsl_tool_audit(baseline_path or repo_root / "config/ai/wsl-tool-baseline.json")
    findings = _machine_environment_findings(tools)
    issues.extend({"type": "wsl_tool_missing", "tool": x} for x in tools["missing_tools"])
    issues.extend({"type": "wsl_tool_windows_path", "tool": x} for x in tools["windows_path_tools"])
    issues.extend({"type": "invalid_wsl_baseline", "error": x} for x in tools.get("errors", []))
    issues.extend({"type": x["category"]} for x in findings)
    return {"ok": not issues, "scope": "environment-only", "issues": issues,
        "runtime_verified": False, "windows_external_capabilities": plugins,
        "wsl_tool_audit": tools, "findings": findings,
        "errors": sorted({x["type"] for x in issues})}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the Linux-native Codex managed-skill runtime.")
    parser.add_argument("--root", "--repo-root", dest="repo_root", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--baseline", default="")
    parser.add_argument("--audit-target", choices=("codex_minimal",), default="codex_minimal")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--environment-only", action="store_true", help="Audit environment files and plugins without managed skills or their schemas.")
    parser.add_argument("--skill", choices=MANAGED_SKILLS, help="Compare only this managed skill to the current source; verify others against the installed receipt.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_repo_root(args.repo_root, Path(__file__))
        if args.environment_only:
            if args.skill or args.strict:
                raise ValueError("--environment-only cannot be combined with --skill or --strict")
            payload = audit_environment(root, resolve_codex_home(args.codex_home),
                Path(args.baseline).resolve() if args.baseline else None)
            return emit(payload, as_json=args.json)
        payload = audit(
            root,
            resolve_codex_home(args.codex_home),
            Path(args.baseline).resolve() if args.baseline else None,
            managed_skill=args.skill,
        )
        if args.strict and args.skill in {None, "global-task-orchestrator"}:
            contract_gate = _contract_gate(root)
            payload["contract_gate"] = contract_gate
            if not contract_gate["ok"]:
                payload["ok"] = False
                payload["errors"] = sorted({*payload.get("errors", []), "contract_gate_failed"})
    except (OSError, ValueError) as error:
        payload = {"ok": False, "errors": [str(error)]}
    return emit(payload, as_json=args.json, success_message="Codex managed runtime audit passed")


if __name__ == "__main__":
    raise SystemExit(main())
