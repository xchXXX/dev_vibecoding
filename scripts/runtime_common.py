"""Shared standard-library helpers for the WSL control-plane entrypoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


MANAGED_SKILLS = (
    "global-task-orchestrator",
    "command-failure-memory",
    "pre-dev-benchmark",
    "fix-closure-gate",
)


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
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".codex").resolve()


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
