from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import tempfile
import tomllib
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from runtime_common import MANAGED_SKILLS, emit, resolve_codex_home, resolve_repo_root, sha256_file, write_json


@contextmanager
def _publication_backup(paths, directory):
    raw = tempfile.mkdtemp(prefix="sync-rollback-", dir=directory)
    keep = False
    try:
        saved = []
        for index, path in enumerate(paths):
            backup = Path(raw) / str(index)
            existed = path.exists()
            if existed:
                if path.is_dir():
                    shutil.copytree(path, backup, symlinks=True)
                else:
                    shutil.copy2(path, backup)
            saved.append((path, backup, existed))
        try:
            yield
        except BaseException:
            failures = []
            for path, backup, existed in reversed(saved):
                try:
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        path.unlink(missing_ok=True)
                    if existed:
                        backup.replace(path)
                except OSError as error:
                    failures.append(str(error))
            if failures:
                keep = True
                raise RuntimeError("publication_restore_failed: " + raw + ": " + "; ".join(failures))
            raise
    finally:
        if not keep:
            shutil.rmtree(raw)


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


def synchronize(harness_root: Path, codex_home: Path, skills: list[str] | None = None, *, _locked=False, _prepared=None) -> dict[str, Any]:
    if (codex_home / ".ai-harness/windows-native-transition.hold").exists():
        return {"ok": False, "errors": ["WINDOWS_NATIVE_TRANSITION_HOLD: complete the native migration before publishing"]}
    if skills is not None and (
        not skills
        or len(set(skills)) != len(skills)
        or any(name not in MANAGED_SKILLS for name in skills)
    ):
        return {"ok": False, "errors": ["partial sync contains an unsupported managed skill"]}
    selected = tuple(skills) if skills is not None else MANAGED_SKILLS
    missing = [name for name in selected if not (harness_root / "skills" / name / "SKILL.md").is_file()]
    if missing:
        return {"ok": False, "errors": [f"managed skill source missing: {name}" for name in missing]}
    codex_home.mkdir(parents=True, exist_ok=True)
    lock_path = codex_home / ".ai-harness" / "codex-sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    managed_files: list[dict[str, str]] = []
    managed_schema_files: list[dict[str, str]] = []
    changed_managed_skills: list[str] = []
    changed_schema_files: list[str] = []
    prepared = _prepared if _prepared is not None else {name: _tree_hashes(harness_root / "skills" / name) for name in selected}
    receipt_path = codex_home / ".ai-harness" / "codex-sync.receipt.json"
    receipt_before = receipt_path.read_bytes() if receipt_path.exists() else None
    with lock_path.open("a+", encoding="utf-8") as lock:
        if not _locked:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if (codex_home / ".ai-harness/windows-native-transition.hold").exists():
            raise ValueError("WINDOWS_NATIVE_TRANSITION_HOLD")
        receipt_path = codex_home / ".ai-harness" / "codex-sync.receipt.json"
        if (receipt_path.read_bytes() if receipt_path.exists() else None) != receipt_before:
            raise ValueError("publication_generation_changed")
        for name in selected:
            if _tree_hashes(harness_root / "skills" / name) != prepared[name]:
                raise ValueError("publication_source_changed")
        previous: dict[str, Any] = {}
        if skills is not None and not receipt_path.is_file():
            return {"ok": False, "errors": ["partial sync requires an existing installation receipt; use full sync for initial installation"]}
        if receipt_path.exists():
            if receipt_path.is_symlink():
                return {"ok": False, "errors": ["sync receipt must not be a symlink"]}
            previous = json.loads(receipt_path.read_text(encoding='utf-8'))
            if (not isinstance(previous, dict) or previous.get('harness_root') != str(harness_root)
                    or previous.get('codex_home') != str(codex_home)
                    or any(not isinstance(previous.get(key), list) for key in ('managed_skills', 'managed_files', 'managed_schema_files'))):
                return {"ok": False, "errors": ["sync requires a matching existing receipt and managed inventory"]}
            if skills is None and (
                    any(name not in MANAGED_SKILLS for name in previous['managed_skills'])
                    or any(not isinstance(row, dict) or row.get('skill') not in MANAGED_SKILLS
                           for row in previous['managed_files'])):
                return {"ok": False, "errors": ["receipt owns a retired or invalid managed skill; use its reviewed retirement before full sync"]}
            if skills is not None:
                managed_files = [row for row in previous['managed_files'] if row['skill'] not in selected]
            managed_schema_files = list(previous['managed_schema_files'])
        legacy_relative = 'schemas/orchestrator-task-state.schema.json'
        legacy = codex_home / legacy_relative
        retiring_legacy = False
        if 'global-task-orchestrator' in selected:
            rows = [row for row in managed_schema_files if isinstance(row, dict)
                    and (row.get('source') == legacy_relative or row.get('target') == legacy_relative)]
            if rows or legacy.exists() or legacy.is_symlink():
                if (len(rows) != 1 or rows[0].get('source') != legacy_relative
                        or rows[0].get('target') != legacy_relative
                        or legacy.is_symlink() or not legacy.is_file()
                        or not legacy.resolve().is_relative_to(codex_home.resolve())
                        or sha256_file(legacy) != rows[0].get('sha256')):
                    return {"ok": False, "errors": ["legacy GTO schema ownership or hash drift; retain files and receipt"]}
                packaged = harness_root / 'skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json'
                if not packaged.is_file():
                    return {"ok": False, "errors": ["packaged GTO schema missing; retain legacy schema"]}
                managed_schema_files = [row for row in managed_schema_files if row is not rows[0]]
                retiring_legacy = True
        changes = [name for name in selected if prepared[name] != _tree_hashes(codex_home / 'skills' / name)]
        backups = [codex_home / 'skills' / name for name in changes]
        if changes or retiring_legacy:
            backups.append(receipt_path)
        if retiring_legacy:
            backups.append(legacy)
        with _publication_backup(backups, lock_path.parent):
            for name in selected:
                source = harness_root / "skills" / name
                target = codex_home / "skills" / name
                if name in changes:
                    changed_managed_skills.append(name)
                    _replace_tree(source, target)
                    if _tree_hashes(target) != prepared[name]:
                        raise ValueError("publication_source_changed")
                for relative, digest in prepared[name].items():
                    managed_files.append({
                        "skill": name,
                        "source": f"skills/{name}/{relative}",
                        "target": f"{name}/{relative}",
                        "sha256": digest,
                    })
            receipt = {
                **(previous if skills is not None else {}),
                "schema_version": "3.0",
                "harness_root": str(harness_root),
                "codex_home": str(codex_home),
                "managed_skills": (list(dict.fromkeys([*previous.get('managed_skills', []), *selected]))
                                   if skills is not None else list(MANAGED_SKILLS)),
                "managed_files": managed_files,
                "managed_schema_files": managed_schema_files,
            }
            if retiring_legacy:
                # Keep the original file until the atomic receipt commit succeeds.
                # Both paths are protected by the sync lock; failed commits restore it.
                temporary = Path(tempfile.mkdtemp(prefix='retired-gto-schema-', dir=lock_path.parent))
                backup = temporary / legacy.name
                try:
                    legacy.replace(backup)
                    try:
                        write_json(receipt_path, receipt)
                    except BaseException:
                        backup.replace(legacy)
                        raise
                    backup.unlink()
                finally:
                    # If restoration fails, retain the only original bytes for recovery.
                    if not backup.exists():
                        temporary.rmdir()
                changed_schema_files.append(legacy_relative)
            else:
                if previous != receipt:
                    write_json(receipt_path, receipt)
        if not _locked:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return {
        "ok": True, "harness_root": str(harness_root), "codex_home": str(codex_home),
        "managed_skills": receipt['managed_skills'], "synchronized_skills": list(selected),
        "managed_file_count": len(managed_files),
        "managed_schema_file_count": len(managed_schema_files),
        "changed_managed_skills": changed_managed_skills,
        "changed_schema_files": changed_schema_files,
        "runtime_changed": bool(changed_managed_skills or changed_schema_files),
        "receipt_path": str(receipt_path), "warnings": [],
    }


def retire_legacy_gui(harness_root: Path, codex_home: Path) -> dict[str, Any]:
    """Retire only the known legacy skill using its receipt; preserve other records."""
    hold = codex_home / ".ai-harness/windows-native-transition.hold"
    if hold.exists():
        return {"ok": False, "errors": ["WINDOWS_NATIVE_TRANSITION_HOLD"]}
    name = "windows-computer-use-wsl"
    receipt_path = codex_home / ".ai-harness/codex-sync.receipt.json"
    if not receipt_path.is_file():
        return {"ok": False, "errors": ["legacy retirement requires an existing receipt"]}
    lock_path = codex_home / ".ai-harness/codex-sync.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if hold.exists():
            return {"ok": False, "errors": ["WINDOWS_NATIVE_TRANSITION_HOLD"]}
        previous = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        if (not isinstance(previous, dict) or previous.get("harness_root") != str(harness_root)
                or previous.get("codex_home") != str(codex_home)
                or not isinstance(previous.get("managed_files"), list)
                or not isinstance(previous.get("managed_skills"), list)
                or any(not isinstance(x, dict) or not isinstance(x.get("target"), str) or not isinstance(x.get("sha256"), str) for x in previous.get("managed_files", []))):
            return {"ok": False, "errors": ["legacy retirement receipt mismatch"]}
        config_path = codex_home / "config.toml"
        config = tomllib.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
        if not isinstance(config.get("mcp_servers", {}), dict):
            raise ValueError("legacy_mcp_config_invalid")
        for server in ("computer_use_wsl", "browser_use_wsl"):
            entry = config.get("mcp_servers", {}).get(server)
            if entry is not None and (not isinstance(entry, dict) or entry.get("enabled") is not False):
                return {"ok": False, "errors": ["legacy GUI must already be explicitly disabled"]}
        target = codex_home / "skills" / name
        rows = [x for x in previous["managed_files"] if x.get("skill") == name]
        if not rows and not target.exists() and name not in previous["managed_skills"]:
            return {"ok": True, "changed": False, "retired_skill": name}
        if target.is_symlink() or any(x.is_symlink() for x in target.rglob("*")):
            return {"ok": False, "errors": ["legacy skill contains symlinks"]}
        expected = {x.get("target"): x.get("sha256") for x in rows}
        actual = {f"{name}/{rel}": digest for rel, digest in _tree_hashes(target).items()}
        if not rows or expected != actual or len(expected) != len(rows):
            return {"ok": False, "errors": ["legacy skill drift; retain files and receipt"]}
        fingerprint = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
        backup = codex_home / ".ai-harness/backups/retired-windows-gui" / fingerprint
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists():
            return {"ok": False, "errors": ["legacy backup already exists; inspect before retry"]}
        target.replace(backup)
        try:
            write_json(receipt_path, {**previous,
                "managed_skills": [x for x in previous["managed_skills"] if x != name],
                "managed_files": [x for x in previous["managed_files"] if x.get("skill") != name]})
        except BaseException:
            backup.replace(target)
            raise
        return {"ok": True, "changed": True, "retired_skill": name, "backup_path": str(backup)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize the frozen Codex skill allow-list on Linux.")
    parser.add_argument("--harness-root", "--repo-root", dest="repo_root", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument(
        "--skill",
        choices=MANAGED_SKILLS,
        help="Update only one managed skill tree, including its packaged scripts and schemas; retain all unselected receipt entries.",
    )
    parser.add_argument("--retire-legacy-gui", action="store_true", help="Retire only the receipt-owned disabled WSL GUI skill; do not synchronize other skills or schemas.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_repo_root(args.repo_root, Path(__file__))
        if args.retire_legacy_gui:
            if args.skill:
                raise ValueError("--retire-legacy-gui cannot be combined with --skill")
            payload = retire_legacy_gui(root, resolve_codex_home(args.codex_home))
        else:
            payload = synchronize(root, resolve_codex_home(args.codex_home), skills=[args.skill] if args.skill else None)
    except (OSError, ValueError) as error:
        payload = {"ok": False, "errors": [str(error)]}
    return emit(payload, as_json=args.json, success_message=f"Synchronized {payload.get('managed_file_count', 0)} managed files")


if __name__ == "__main__":
    raise SystemExit(main())
