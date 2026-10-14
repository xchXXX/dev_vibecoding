#!/usr/bin/env python3
"""Prepare or read-only check a Linux Git clone for repository-local Codex skills."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

SKILLS = (
    "global-task-orchestrator",
    "pre-dev-benchmark",
    "fix-closure-gate",
    "command-failure-memory",
)


def prepare(check=False):
    repo = Path(__file__).resolve().parents[1]
    venv = repo / ".venv"
    python = venv / "bin/python"
    errors = []
    report = dict(ok=False, mode="check" if check else "setup", repo_root=str(repo),
                  venv_path=str(venv), python_path=str(python), source_commit=None,
                  skill_paths={}, session_verified=False, errors=errors, command_results=[])

    def run(argv, timeout=120, env=None):
        completed = subprocess.run(argv, cwd=repo, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout, env=env)
        report["command_results"].append(dict(argv=argv, exit_code=completed.returncode,
                                              stdout=completed.stdout, stderr=completed.stderr))
        return completed

    try:
        if sys.version_info < (3, 11):
            errors.append("Python 3.11 or newer is required.")
        git = shutil.which("git")
        if git is None:
            errors.append("Git is required on PATH.")
        else:
            source = run([git, "rev-parse", "HEAD"], timeout=10)
            if source.returncode:
                errors.append("Cannot identify the source commit of this Git clone.")
            else:
                report["source_commit"] = source.stdout.strip()
        for name in SKILLS:
            link = repo / ".agents/skills" / name
            canonical = repo / "skills" / name
            report["skill_paths"][name] = str(link)
            if (any(p.is_symlink() for p in (repo / "skills", canonical, canonical / "SKILL.md"))
                    or not canonical.resolve().is_relative_to(repo)):
                errors.append("Canonical skill symlink escape is not allowed: " + name)
            elif (not link.is_symlink() or str(link.readlink()) != "../../skills/" + name
                    or link.resolve() != canonical.resolve()
                    or not (link / "SKILL.md").is_file()):
                errors.append("Missing or invalid canonical skill discovery link: " + name)
        if venv.is_symlink():
            errors.append(".venv must not be a symlink.")
        elif venv.exists() and (not venv.is_dir() or not (venv / "pyvenv.cfg").is_file()
                                or not python.is_file()):
            errors.append("Existing .venv is not a Python virtual environment; it will not be overwritten.")
        elif not venv.exists() and check:
            errors.append("Repository-local .venv is missing; run setup first.")
        if errors:
            return report
        if not venv.exists():
            created = run([sys.executable, "-B", "-m", "venv", str(venv)])
            if created.returncode:
                errors.append("Failed to create the repository-local virtual environment.")
                return report
        for path in venv.rglob("*"):
            if not path.is_symlink():
                continue
            interpreter_link = (path.parent == venv / "bin"
                                and re.fullmatch(r"python(?:3(?:\.\d+)?)?", path.name)
                                and path.resolve().is_file())
            if not interpreter_link and not path.resolve().is_relative_to(venv):
                errors.append("Virtual environment write paths must stay inside .venv: " + str(path))
                return report
        identity = run([str(python), "-B", "-c",
                        "import json,sys; print(json.dumps({'prefix':sys.prefix,'base_prefix':sys.base_prefix,'version':list(sys.version_info[:2])}))"])
        if identity.returncode:
            errors.append("Repository virtual environment interpreter cannot execute.")
            return report
        observed = json.loads(identity.stdout)
        if (Path(observed["prefix"]).resolve() != venv.resolve()
                or Path(observed["base_prefix"]).resolve() == venv.resolve()
                or tuple(observed["version"]) < (3, 11)):
            errors.append("Interpreter is not the repository-local Python 3.11+ virtual environment.")
            return report
        if not check:
            install_env = {key: value for key, value in os.environ.items()
                           if not key.startswith("PIP_") and key != "PYTHONUSERBASE"}
            # pip reads PIP_CONFIG_FILE even in isolated mode; os.devnull disables
            # global, user and virtual-environment config files without editing them.
            install_env["PIP_CONFIG_FILE"] = os.devnull
            installed = run([str(python), "-B", "-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir",
                             "install", "-r", str(repo / "requirements.txt")], env=install_env)
            if installed.returncode:
                errors.append("Repository virtual environment dependency installation failed.")
                return report
        dependency = run([str(python), "-B", "-c",
                          "from jsonschema import Draft202012Validator, FormatChecker"])
        if dependency.returncode:
            errors.append("jsonschema is unavailable in the repository virtual environment.")
            return report
        doctor = run([str(python), "-B", str(repo / "skills/global-task-orchestrator/scripts/doctor.py"), "--json"])
        report["gto_doctor"] = json.loads(doctor.stdout) if doctor.stdout.strip() else {}
        if doctor.returncode or report["gto_doctor"].get("ok") is not True:
            errors.append("Repository-local GTO doctor failed.")
        report["ok"] = not errors
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as error:
        errors.append(str(error))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Inspect without creating or installing anything.")
    parser.add_argument("--json", action="store_true", help="Emit JSON (also the default).")
    args = parser.parse_args()
    report = prepare(check=args.check)
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
