"""Shared standard-library helpers for the WSL control-plane entrypoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import signal
import time
import tempfile
import tomllib
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_probe_deadline = ContextVar("probe_deadline", default=None)


class ProbeBudgetExpired(subprocess.TimeoutExpired):
    def __str__(self):
        return "probe_budget_exhausted: " + super().__str__()


@contextmanager
def probe_budget(seconds):
    """Scope one shared deadline; nested scopes cannot extend their parent."""
    deadline = time.monotonic() + seconds
    previous = _probe_deadline.get()
    token = _probe_deadline.set(min(previous, deadline) if previous is not None else deadline)
    try:
        yield
    finally:
        _probe_deadline.reset(token)


def run_probe(args, *, timeout=30.0, deadline=None, **kwargs):
    """Bound a probe and its descendants by the earlier monotonic deadline."""
    shared_deadline = _probe_deadline.get()
    if shared_deadline is not None:
        deadline = min(deadline, shared_deadline) if deadline is not None else shared_deadline
    remaining = timeout
    if deadline is not None:
        remaining = min(timeout, deadline - time.monotonic()) if timeout is not None else deadline - time.monotonic()
    if remaining is None or remaining <= 0:
        if shared_deadline is not None and time.monotonic() >= shared_deadline:
            raise ProbeBudgetExpired(args, remaining or 0)
        raise subprocess.TimeoutExpired(args, remaining or 0)
    check = kwargs.pop("check", False)
    capture = kwargs.pop("capture_output", False)
    input_data = kwargs.pop("input", None)
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if input_data is not None:
        kwargs["stdin"] = subprocess.PIPE
    kwargs["start_new_session"] = True
    process = subprocess.Popen(args, **kwargs)
    try:
        wait = min(remaining, deadline - time.monotonic()) if deadline is not None else remaining
        if wait <= 0:
            raise subprocess.TimeoutExpired(args, wait)
        stdout, stderr = process.communicate(input_data, timeout=wait)
    except BaseException as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        if isinstance(error, subprocess.TimeoutExpired) and shared_deadline is not None and time.monotonic() >= shared_deadline:
            raise ProbeBudgetExpired(args, remaining, output=error.output, stderr=error.stderr) from error
        raise
    result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    if check:
        result.check_returncode()
    return result


MANAGED_SKILLS = (
    "global-task-orchestrator",
    "command-failure-memory",
    "pre-dev-benchmark",
    "fix-closure-gate",
)

MANAGED_WSL_RUNTIME_FILES = (
    ("config/wsl-tool-baseline.json", "config/ai/wsl-tool-baseline.json"),
    ("config/windows-external-capabilities.json", "config/ai/windows-external-capabilities.json"),
    ("schemas/wsl-tool-baseline.schema.json", "schemas/wsl-tool-baseline.schema.json"),
    ("schemas/windows-external-capabilities.schema.json", "schemas/windows-external-capabilities.schema.json"),
    ("schemas/project-environment.schema.json", "schemas/project-environment.schema.json"),
    ("bin/provision-wsl.py", "scripts/provision-wsl.py"),
    ("bin/project-env-doctor.py", "scripts/project-env-doctor.py"),
    ("bin/resolve-wsl-path.py", "scripts/resolve-wsl-path.py"),
    ("bin/doctor-core.py", "scripts/doctor-core.py"),
    ("bin/runtime_common.py", "scripts/runtime_common.py"),
)
RETIRED_MANAGED_WSL_RUNTIME_FILES = (
    "bin/windows-external-bridge.py",
    "bin/node-repl-wsl-compat.py",
)
PACKAGE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
COMMAND_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._-]*$")
DECLARATION_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9+._-]*$")
PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9+._@-]*$")
WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"^([A-Za-z]):[\\/](.*)$")


def validate_windows_external_capabilities(payload: Any) -> list[str]:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "capabilities"}:
        return ["windows external declaration requires schema_version and capabilities"]
    if payload["schema_version"] != 3 or not isinstance(payload["capabilities"], list) or not payload["capabilities"]:
        return ["windows external declaration requires schema_version 3 and non-empty capabilities"]
    errors: list[str] = []
    identifiers: set[str] = set()
    for i, item in enumerate(payload["capabilities"]):
        if not isinstance(item, dict):
            errors.append(f"capabilities[{i}] must be an object")
            continue
        fields = {"id", "kind", "provider", "required_plugins"}
        if set(item) != fields or item.get("kind") != "windows_native":
            errors.append(f"capabilities[{i}] must declare only Windows native plugin fields")
            continue
        for key in ("id", "provider"):
            if not isinstance(item[key], str) or not DECLARATION_ID_PATTERN.fullmatch(item[key]):
                errors.append(f"capabilities[{i}].{key} is invalid")
        identifier = str(item["id"])
        if identifier in identifiers:
            errors.append(f"capabilities[{i}].id is duplicated")
        identifiers.add(identifier)
        plugins = item["required_plugins"]
        if (not isinstance(plugins, list) or not plugins
                or any(not isinstance(x, str) or not PLUGIN_ID_PATTERN.fullmatch(x) for x in plugins)
                or len(set(map(str, plugins))) != len(plugins)):
            errors.append(f"capabilities[{i}].required_plugins is invalid")
    return errors


def load_windows_external_capabilities(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [str(error)]
    errors = validate_windows_external_capabilities(payload)
    return (payload if isinstance(payload, dict) else None), errors


def _configured_enabled_state(container: Any, key: str) -> str:
    if not isinstance(container, dict):
        return "invalid"
    if key not in container:
        return "missing"
    entry = container[key]
    if not isinstance(entry, dict):
        return "invalid"
    value = entry.get("enabled", True)
    return "enabled" if value is True else "disabled" if value is False else "invalid"


def inspect_windows_external_capabilities(codex_home: Path, declaration_path: Path) -> dict[str, Any]:
    """Read plugin configuration only; Desktop owns transport and GUI verification."""
    result: dict[str, Any] = {"ok": False, "runtime_verified": False,
        "declaration_path": str(declaration_path), "capabilities": [], "issues": []}
    declaration, errors = load_windows_external_capabilities(declaration_path)
    if errors or declaration is None:
        result["issues"] = [{"type": "windows_external_declaration_invalid", "error": e} for e in errors]
        return result
    config_path = codex_home / "config.toml"
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    except (OSError, tomllib.TOMLDecodeError):
        result["issues"].append({"type": "windows_external_config_invalid"})
        return result
    for item in declaration["capabilities"]:
        states = {name: _configured_enabled_state(config.get("plugins", {}), name)
                  for name in item["required_plugins"]}
        configured = all(state == "enabled" for state in states.values())
        result["capabilities"].append({"id": item["id"], "kind": item["kind"],
            "provider": item["provider"], "plugin_states": states,
            "status": "configured_on_disk" if configured else "needs_desktop_attention",
            "action": "use_native_plugin" if configured else "check_desktop_plugin",
            "runtime_verified": False})
        for plugin, state in states.items():
            if state != "enabled":
                result["issues"].append({"type": "windows_external_plugin_" + state,
                    "capability": item["id"], "plugin": plugin})
    result["ok"] = not result["issues"]
    return result


def validate_wsl_baseline(payload: Any) -> list[str]:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "profiles"}:
        return ["baseline must contain only schema_version and profiles"]
    if payload.get("schema_version") != 1 or not isinstance(payload.get("profiles"), list) or not payload["profiles"]:
        return ["baseline schema_version must be 1 with non-empty profiles"]
    errors: list[str] = []
    profile_ids: set[str] = set()
    for index, profile in enumerate(payload["profiles"]):
        prefix = f"profiles[{index}]"
        if not isinstance(profile, dict) or set(profile) != {"id", "packages"}:
            errors.append(f"{prefix} has unknown or missing fields")
            continue
        profile_id = profile.get("id")
        packages = profile.get("packages")
        if not isinstance(profile_id, str) or not COMMAND_PATTERN.fullmatch(profile_id) or profile_id in profile_ids:
            errors.append(f"{prefix}.id is invalid or duplicated")
        profile_ids.add(str(profile_id))
        if not isinstance(packages, list):
            errors.append(f"{prefix}.packages must be a list")
            continue
        package_names: set[str] = set()
        for package_index, package in enumerate(packages):
            item_prefix = f"{prefix}.packages[{package_index}]"
            allowed = {"name", "source", "command", "version", "probe", "doctor", "doctor_commands"}
            if not isinstance(package, dict) or not {"name", "source", "command"} <= set(package) or set(package) - allowed:
                errors.append(f"{item_prefix} has unknown or missing fields")
                continue
            name, source, command = package["name"], package["source"], package["command"]
            if not isinstance(name, str) or not PACKAGE_NAME_PATTERN.fullmatch(name) or name in package_names:
                errors.append(f"{item_prefix}.name is invalid or duplicated")
            package_names.add(str(name))
            if source not in {"apt", "external"}:
                errors.append(f"{item_prefix}.source is unsupported")
            if not isinstance(command, str) or not COMMAND_PATTERN.fullmatch(command):
                errors.append(f"{item_prefix}.command is invalid")
            if "version" in package and (not isinstance(package["version"], str) or not package["version"]):
                errors.append(f"{item_prefix}.version is invalid")
            for key in ("probe",):
                if key in package and (not isinstance(package[key], list) or not package[key] or not all(isinstance(part, str) and part for part in package[key])):
                    errors.append(f"{item_prefix}.{key} is invalid")
            if "doctor" in package and not isinstance(package["doctor"], bool):
                errors.append(f"{item_prefix}.doctor is invalid")
            if "doctor_commands" in package and (not isinstance(package["doctor_commands"], list) or not package["doctor_commands"] or not all(isinstance(part, str) and COMMAND_PATTERN.fullmatch(part) for part in package["doctor_commands"])):
                errors.append(f"{item_prefix}.doctor_commands is invalid")
    return errors


def load_wsl_baseline(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [str(error)]
    errors = validate_wsl_baseline(payload)
    return (payload if isinstance(payload, dict) else None), errors


def select_wsl_profile(baseline: dict[str, Any], profile_id: str) -> dict[str, Any] | None:
    return next((item for item in baseline["profiles"] if item["id"] == profile_id), None)


def command_available(package: dict[str, Any]) -> bool:
    command = package["command"]
    if not shutil.which(command):
        return False
    probe = package.get("probe")
    if probe:
        try:
            result = run_probe(probe, text=True, capture_output=True, check=False)
        except ProbeBudgetExpired:
            raise
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode:
            return False
    expected_version = package.get("version")
    if not expected_version:
        return True
    try:
        result = run_probe([command, "--version"], text=True, capture_output=True, check=False)
    except ProbeBudgetExpired:
        raise
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and expected_version in result.stdout


def add_common_arguments(parser: argparse.ArgumentParser, *, repo_flag: str = "--repo-root") -> None:
    parser.add_argument(repo_flag, dest="repo_root", default="")
    parser.add_argument("--json", action="store_true")


def resolve_repo_root(value: str, script_path: Path) -> Path:
    root = Path(value or os.environ.get("AI_HARNESS_ROOT", "") or script_path.parent.parent)
    root = root.expanduser().resolve()
    if not (root / "rules" / "registry" / "RULES_ENTRY.md").is_file():
        raise ValueError(f"harness_root_invalid: {root}")
    return root


def resolve_codex_home(value: str = "") -> Path:
    configured = value or os.environ.get("CODEX_HOME", "")
    if not configured or not configured.strip():
        raise ValueError("codex_home_required: pass --codex-home or set CODEX_HOME to the verified host directory")
    target = Path(configured).expanduser()
    if not target.is_absolute():
        raise ValueError("codex_home_absolute_required")
    return target.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def write_json(path: Path, payload: Any) -> None:
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def emit(payload: dict[str, Any], *, as_json: bool, success_message: str = "") -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    elif payload.get("ok"):
        print(success_message or "ok")
        for warning in payload.get("warnings", []):
            print(f"WARNING {warning}")
    else:
        for error in payload.get("errors", payload.get("issues", [])):
            print(f"ERROR {error}")
    return 0 if payload.get("ok") else 1
