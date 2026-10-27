from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from runtime_common import run_probe, probe_budget, ProbeBudgetExpired
import tomllib
from pathlib import Path
from typing import Any

from runtime_common import emit


def _windows_backed(value: str) -> bool:
    normalized = value.replace("\\", "/").lower()
    return normalized.startswith("/mnt/") or (len(normalized) >= 3 and normalized[1:3] == ":/")


def _windows_temp(value: str) -> bool:
    return _windows_backed(value)


def _windows_executable(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(2) == b"MZ"
    except OSError:
        return False


def _finding(category: str, path: Path | str = "") -> dict[str, str]:
    result = {"category": category}
    if path:
        result["path"] = str(path)
    return result


def _relative_project_path(project_root: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"{field} must be a project-relative path")
    candidate = (project_root / value).resolve()
    if candidate != project_root and project_root not in candidate.parents:
        raise ValueError(f"{field} escapes project root")
    return candidate


def _node_dependencies(package_json: Path) -> list[tuple[str, str]]:
    package = json.loads(package_json.read_text(encoding="utf-8-sig"))
    if not isinstance(package, dict):
        raise ValueError("package.json must be an object")
    dependencies: list[tuple[str, str]] = []
    for key in ("dependencies", "devDependencies"):
        section = package.get(key, {})
        if section is not None and not isinstance(section, dict):
            raise ValueError(f"package.json {key} must be an object")
        if isinstance(section, dict):
            for name, version in section.items():
                if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
                    raise ValueError(f"package.json {key} has an invalid dependency")
                dependencies.append((name, version))
    return list(dict.fromkeys(dependencies))


def _pyproject_dependencies(pyproject_file: Path, extras: list[str]) -> list[str]:
    payload = tomllib.loads(pyproject_file.read_text(encoding="utf-8-sig"))
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError("pyproject.toml must contain a project table")
    dependencies = project.get("dependencies", [])
    optional = project.get("optional-dependencies", {})
    if not isinstance(dependencies, list) or not all(
        isinstance(requirement, str) and requirement.strip()
        for requirement in dependencies
    ):
        raise ValueError("pyproject.toml project.dependencies must be a string array")
    if not isinstance(optional, dict):
        raise ValueError("pyproject.toml project.optional-dependencies must be a table")
    result = list(dependencies)
    for extra in extras:
        extra_requirements = optional.get(extra)
        if not isinstance(extra_requirements, list) or not all(
            isinstance(requirement, str) and requirement.strip()
            for requirement in extra_requirements
        ):
            raise ValueError(
                f"pyproject.toml optional dependency group is missing or invalid: {extra}"
            )
        result.extend(extra_requirements)
    return result


def _valid_node_package(path: Path, name: str) -> bool:
    try:
        package = json.loads(path.read_text(encoding="utf-8-sig"))
    except ProbeBudgetExpired:
        raise
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    return isinstance(package, dict) and package.get("name") == name and isinstance(package.get("version"), str) and bool(package["version"])


def _npm_integrity_ok(project_root: Path) -> tuple[bool, str]:
    npm = shutil.which("npm")
    if not npm:
        return False, "missing"
    try:
        executable = Path(npm).resolve(strict=True)
    except OSError:
        return False, "failed"
    if _windows_backed(str(executable)):
        return False, "windows"
    try:
        checked = run_probe(
            [str(executable), "ls", "--depth=0", "--offline", "--json", "--ignore-scripts", "--include=prod", "--include=dev"],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(checked.stdout)
    except ProbeBudgetExpired:
        raise
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False, "failed"
    return checked.returncode == 0 and isinstance(payload, dict), ""


def _is_isolated_venv(python: Path, venv: Path) -> bool:
    try:
        checked = run_probe(
            [str(python), "-c", "import json,sys; print(json.dumps({'prefix': sys.prefix, 'base_prefix': sys.base_prefix}))"],
            text=True,
            capture_output=True,
            check=False,
        )
        details = json.loads(checked.stdout)
    except ProbeBudgetExpired:
        raise
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    prefix = details.get("prefix") if isinstance(details, dict) else None
    base_prefix = details.get("base_prefix") if isinstance(details, dict) else None
    return (
        checked.returncode == 0
        and isinstance(prefix, str)
        and isinstance(base_prefix, str)
        and Path(prefix).resolve() == venv.resolve()
        and Path(prefix).resolve() != Path(base_prefix).resolve()
    )


def _validate_declaration(declaration: object, project_root: Path) -> dict[str, Any]:
    required_top = {"schema_version", "project_id", "capabilities"}
    allowed_top = required_top | {"python", "node"}
    if not isinstance(declaration, dict) or not required_top <= set(declaration) or set(declaration) - allowed_top or not ({"python", "node"} & set(declaration)):
        raise ValueError("invalid declaration fields")
    if declaration.get("schema_version") != 1 or not isinstance(declaration.get("project_id"), str) or not declaration["project_id"].strip():
        raise ValueError("invalid declaration header")
    for section, keys in (("python", None), ("node", {"package_json", "node_modules"})):
        if section not in declaration:
            continue
        value = declaration[section]
        if not isinstance(value, dict):
            raise ValueError(f"invalid {section} declaration")
        if section == "python":
            has_requirements = "requirements_file" in value
            has_pyproject = "pyproject_file" in value
            allowed = (
                {"requirements_file", "venv"}
                if has_requirements and not has_pyproject
                else {"pyproject_file", "venv", "extras"}
                if has_pyproject and not has_requirements
                else set()
            )
            manifest_key = "requirements_file" if has_requirements else "pyproject_file"
            if (
                not allowed
                or not {"venv", manifest_key} <= set(value)
                or set(value) - allowed
            ):
                raise ValueError("invalid python declaration")
            extras = value.get("extras", [])
            if (
                not isinstance(extras, list)
                or not all(
                    isinstance(extra, str)
                    and extra
                    and extra[0].isalnum()
                    and all(character.isalnum() or character in "._-" for character in extra)
                    for extra in extras
                )
                or len(set(extras)) != len(extras)
            ):
                raise ValueError("invalid python extras")
            for key in ("venv", manifest_key):
                _relative_project_path(project_root, value[key], f"python.{key}")
        else:
            if set(value) != keys:
                raise ValueError(f"invalid {section} declaration")
            for key, path_value in value.items():
                _relative_project_path(project_root, path_value, f"{section}.{key}")
    capabilities = declaration.get("capabilities", [])
    if not isinstance(capabilities, list):
        raise ValueError("invalid capabilities declaration")
    seen: set[str] = set()
    for capability in capabilities:
        if not isinstance(capability, dict) or set(capability) != {"id", "required"} or not isinstance(capability.get("id"), str) or not capability["id"].strip() or not isinstance(capability.get("required"), bool) or capability["id"] in seen:
            raise ValueError("invalid capability declaration")
        seen.add(capability["id"])
    return declaration


@probe_budget(120)
def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only project environment diagnosis for WSL projects.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings: list[dict[str, str]] = []
    try:
        project_root = Path(args.project_root).resolve()
        declaration = _validate_declaration(json.loads(Path(args.environment).read_text(encoding="utf-8-sig")), project_root)
        for variable in ("TEMP", "TMP", "TMPDIR"):
            value = os.environ.get(variable, "")
            if value and _windows_temp(value):
                findings.append(_finding("windows_temp", f"{variable}={value}"))
        modules: Path | None = None
        if "python" in declaration:
            python = declaration["python"]
            venv = _relative_project_path(project_root, python["venv"], "python.venv")
            manifest_key = "requirements_file" if "requirements_file" in python else "pyproject_file"
            manifest = _relative_project_path(project_root, python[manifest_key], f"python.{manifest_key}")
            venv_python = venv / "bin/python"
            resolved_venv = venv.resolve()
            resolved_python = venv_python.resolve()
            if (venv / "Scripts/python.exe").is_file():
                findings.append(_finding("windows_python_environment", venv / "Scripts/python.exe"))
            elif not manifest.is_file():
                findings.append(_finding("missing_python_manifest", manifest))
            elif not venv_python.is_file() or not os.access(venv_python, os.X_OK):
                findings.append(_finding("missing_python_dependency", venv))
            elif _windows_executable(resolved_python):
                findings.append(_finding("windows_python_environment", resolved_python))
            elif not (venv / "pyvenv.cfg").is_file() or not _is_isolated_venv(venv_python, resolved_venv):
                findings.append(_finding("system_python_venv", venv_python))
            else:
                if manifest_key == "requirements_file":
                    has_requirements = any(
                        line.split("#", 1)[0].strip()
                        for line in manifest.read_text(encoding="utf-8-sig").splitlines()
                    )
                    pip_arguments = ["-r", str(manifest)]
                else:
                    declared_requirements = _pyproject_dependencies(
                        manifest, python.get("extras", [])
                    )
                    has_requirements = bool(declared_requirements)
                    pip_arguments = declared_requirements
                if has_requirements:
                    checked = run_probe(
                        [
                            str(venv_python),
                            "-m",
                            "pip",
                            "install",
                            "--dry-run",
                            "--no-index",
                            "--disable-pip-version-check",
                            *pip_arguments,
                        ],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    if checked.returncode:
                        findings.append(_finding("missing_python_requirement", manifest))
        if "node" in declaration:
            node = declaration["node"]
            modules = _relative_project_path(project_root, node["node_modules"], "node.node_modules")
            package_json = _relative_project_path(project_root, node["package_json"], "node.package_json")
            if (modules / "esbuild/bin/esbuild.exe").is_file():
                findings.append(_finding("windows_node_artifact", modules / "esbuild/bin/esbuild.exe"))
            elif not package_json.is_file():
                findings.append(_finding("missing_node_manifest", package_json))
            elif not modules.is_dir():
                findings.append(_finding("missing_node_dependency", modules))
            else:
                dependencies = _node_dependencies(package_json)
                for dependency, _ in dependencies:
                    installed = modules / dependency
                    if not installed.is_dir() or not _valid_node_package(installed / "package.json", dependency):
                        findings.append(_finding("missing_node_dependency", installed))
                if dependencies:
                    npm_ok, npm_problem = _npm_integrity_ok(project_root)
                    if not npm_ok:
                        findings.append(_finding("windows_node_artifact" if npm_problem == "windows" else "missing_node_dependency", npm_problem))
            if modules.is_dir() and any(path.is_dir() and path.name.startswith("win32-") for path in (modules / "@esbuild").glob("*") if (modules / "@esbuild").is_dir()):
                findings.append(_finding("windows_node_artifact", modules / "@esbuild"))
            if modules.is_dir() and any(path.is_file() and path.suffix.casefold() in {".cmd", ".ps1", ".exe"} for path in (modules / ".bin").glob("*") if (modules / ".bin").is_dir()):
                findings.append(_finding("windows_node_artifact", modules / ".bin"))
        capabilities = declaration.get("capabilities") if isinstance(declaration.get("capabilities"), list) else []
        for capability in capabilities:
            if not isinstance(capability, dict) or not capability.get("required"):
                continue
            capability_id = capability.get("id")
            if capability_id not in {"playwright", "docker"}:
                findings.append(_finding("unsupported_capability", str(capability_id)))
                continue
            if capability_id == "playwright":
                if modules is None:
                    findings.append(_finding("missing_playwright"))
                else:
                    entry = modules / ".bin/playwright"
                    browser_root = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]).expanduser() if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") else modules / "playwright/.local-browsers"
                    browser = next(browser_root.glob("**/chrome-linux/chrome"), None) if browser_root.is_dir() else None
                    if not entry.is_file() or not os.access(entry, os.X_OK) or browser is None:
                        findings.append(_finding("missing_playwright"))
                    elif not os.access(browser, os.X_OK):
                        findings.append(_finding("playwright_browser_not_executable", browser))
            if capability_id == "docker":
                docker = shutil.which("docker")
                if not docker:
                    findings.append(_finding("missing_docker"))
                elif _windows_backed(docker):
                    findings.append(_finding("docker_not_linux_client", docker))
                else:
                    version = run_probe([docker, "version"], text=True, capture_output=True, check=False)
                    if version.returncode or "windows" in (version.stdout + version.stderr).casefold():
                        findings.append(_finding("docker_not_linux_client", docker))
                    else:
                        info = run_probe([docker, "info"], text=True, capture_output=True, check=False)
                        if info.returncode:
                            findings.append(_finding("docker_info_failed", docker))
        payload: dict[str, Any] = {"ok": not findings, "project_root": str(project_root), "findings": findings, "errors": []}
    except ProbeBudgetExpired as error:
        payload = {"ok": False, "project_root": args.project_root, "findings": findings,
                   "errors": [str(error)], "error": {"category": "probe_budget_exhausted"}}
    except (OSError, subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as error:
        payload = {"ok": False, "project_root": args.project_root, "findings": findings, "errors": [str(error)], "error": {"category": "invalid_project_environment"}}
    return emit(payload, as_json=args.json, success_message="Project environment is ready")


if __name__ == "__main__":
    raise SystemExit(main())
