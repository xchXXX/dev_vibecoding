from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from runtime_common import MANAGED_SKILLS, emit, resolve_codex_home, resolve_repo_root, sha256_file, write_json


MANAGED_SCHEMA_FILES = ("orchestrator-task-state.schema.json",)


def _source_files(source: Path) -> list[Path]:
    return sorted(
        path for path in source.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in _source_files(root)
    }


def _replace_tree(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    backup = target.parent / f".{target.name}.previous-{os.getpid()}"
    try:
        for source_file in _source_files(source):
            destination = staging / source_file.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
        if target.exists():
            target.replace(backup)
        staging.replace(target)
        if backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if target.exists() and backup.exists():
            shutil.rmtree(target)
        if backup.exists():
            backup.replace(target)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists():
            shutil.rmtree(backup)


def _replace_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.staging-", dir=target.parent)
    os.close(descriptor)
    staging = Path(temporary_name)
    try:
        shutil.copy2(source, staging)
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)


def synchronize(harness_root: Path, codex_home: Path) -> dict[str, Any]:
    missing = [name for name in MANAGED_SKILLS if not (harness_root / "skills" / name / "SKILL.md").is_file()]
    missing.extend(
        f"schema:{name}"
        for name in MANAGED_SCHEMA_FILES
        if not (harness_root / "schemas" / name).is_file()
    )
    if missing:
        return {"ok": False, "errors": [f"managed skill source missing: {name}" for name in missing]}
    codex_home.mkdir(parents=True, exist_ok=True)
    lock_path = codex_home / ".ai-harness" / "codex-sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    managed_files: list[dict[str, str]] = []
    managed_schema_files: list[dict[str, str]] = []
    changed_managed_skills: list[str] = []
    changed_schema_files: list[str] = []
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        for name in MANAGED_SKILLS:
            source = harness_root / "skills" / name
            target = codex_home / "skills" / name
            if _tree_hashes(source) != _tree_hashes(target):
                changed_managed_skills.append(name)
            _replace_tree(source, target)
            for path in _source_files(source):
                relative = path.relative_to(source).as_posix()
                managed_files.append({
                    "skill": name,
                    "source": f"skills/{name}/{relative}",
                    "target": f"{name}/{relative}",
                    "sha256": sha256_file(path),
                })
        for name in MANAGED_SCHEMA_FILES:
            source = harness_root / "schemas" / name
            target = codex_home / "schemas" / name
            digest = sha256_file(source)
            if not target.is_file() or sha256_file(target) != digest:
                changed_schema_files.append(name)
                _replace_file(source, target)
            managed_schema_files.append({
                "source": f"schemas/{name}",
                "target": f"schemas/{name}",
                "sha256": digest,
            })
        receipt_path = codex_home / ".ai-harness" / "codex-sync.receipt.json"
        receipt = {
            "schema_version": "3.0",
            "harness_root": str(harness_root),
            "codex_home": str(codex_home),
            "managed_skills": list(MANAGED_SKILLS),
            "managed_files": managed_files,
            "managed_schema_files": managed_schema_files,
        }
        write_json(receipt_path, receipt)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return {
        "ok": True, "harness_root": str(harness_root), "codex_home": str(codex_home),
        "managed_skills": list(MANAGED_SKILLS), "managed_file_count": len(managed_files),
        "managed_schema_file_count": len(managed_schema_files),
        "changed_managed_skills": changed_managed_skills,
        "changed_schema_files": changed_schema_files,
        "runtime_changed": bool(changed_managed_skills or changed_schema_files),
        "receipt_path": str(receipt_path), "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize the frozen Codex skill allow-list on Linux.")
    parser.add_argument("--harness-root", "--repo-root", dest="repo_root", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_repo_root(args.repo_root, Path(__file__))
        payload = synchronize(root, resolve_codex_home(args.codex_home))
    except (OSError, ValueError) as error:
        payload = {"ok": False, "errors": [str(error)]}
    return emit(payload, as_json=args.json, success_message=f"Synchronized {payload.get('managed_file_count', 0)} managed files")


if __name__ == "__main__":
    raise SystemExit(main())
