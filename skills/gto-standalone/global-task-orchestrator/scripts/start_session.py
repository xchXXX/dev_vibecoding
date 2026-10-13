"""Resume an existing GTO task without creating a second control plane."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any



ARTIFACTS = (
    "docs/ai/tasks/{task_id}/state.json",
    "docs/ai/tasks/{task_id}/task.md",
    "docs/ai/tasks/{task_id}/events.jsonl",
    "docs/tasks/{task_id}/plan.md",
    "docs/tasks/{task_id}/execution.md",
    "docs/tasks/{task_id}/acceptance.md",
)


def resume_session(repo_root: Path, task_id: str, controller: Path | None = None) -> dict[str, Any]:
    if not task_id.strip() or any(character in task_id for character in ("/", "\\")) or task_id in {".", ".."}:
        return {"ok": False, "mode": "resume", "task_id": task_id, "errors": ["task_id_invalid"]}
    artifact_paths = [repo_root / template.format(task_id=task_id) for template in ARTIFACTS]
    missing = [path.relative_to(repo_root).as_posix() for path in artifact_paths if not path.is_file()]
    if missing:
        return {
            "ok": False, "mode": "resume", "task_id": task_id,
            "errors": ["task_artifacts_missing"], "missing_artifacts": missing,
        }
    state = json.loads(artifact_paths[0].read_text(encoding="utf-8"))
    candidate = state.get('acceptance_gate', {}).get('current_candidate') or {}
    snapshot = candidate.get('runtime_snapshot')
    controller_path = controller or Path(__file__).resolve().with_name("orchestrator_ctl.py")
    if snapshot and controller is None:
        from runtime_evidence import verify_tree
        root = repo_root / snapshot['path']
        if not root.resolve().is_relative_to(repo_root.resolve()):
            return {'ok': False, 'errors': ['runtime snapshot escapes repository']}
        manifest = json.loads((root / '.snapshot.json').read_text(encoding="utf-8"))
        if manifest.get('sha256') != snapshot['sha256']:
            return {'ok': False, 'errors': ['runtime snapshot binding mismatch']}
        verify_tree(root, manifest)
        controller_path = root / 'scripts/orchestrator_ctl.py' 
    if not controller_path.is_file():
        return {"ok": False, "mode": "resume", "task_id": task_id, "errors": ["gto_controller_missing"]}
    completed = subprocess.run(
        [
            sys.executable, str(controller_path), "--action", "validate",
            "--repo-root", str(repo_root), "--task-id", task_id, "--json",
        ],
        text=True,
        encoding='utf-8',
        capture_output=True,
        check=False,
    )
    try:
        validation = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False, "mode": "resume", "task_id": task_id,
            "errors": ["gto_validation_output_invalid"],
            "controller_exit_code": completed.returncode,
        }
    if completed.returncode or not validation.get("ok"):
        return {
            "ok": False, "mode": "resume", "task_id": task_id,
            "errors": validation.get("errors", ["gto_validation_failed"]),
            "controller_exit_code": completed.returncode,
        }
    return {
        "ok": True, "mode": "resume", "task_id": task_id,
        "repo_root": str(repo_root),
        "artifacts": [path.relative_to(repo_root).as_posix() for path in artifact_paths],
        "status": validation.get("status"),
        "current_phase": validation.get("current_phase"),
        "next_action": validation.get("next_action", {"kind": "none"}),
        "controller": str(controller_path),
        "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume and validate one existing six-artifact GTO task.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = Path(args.repo_root).resolve()
        if not root.is_dir():
            raise ValueError("repo-root must be an existing directory")
        payload = resume_session(root, args.task_id)
    except (OSError, ValueError) as error:
        payload = {"ok": False, "mode": "resume", "task_id": args.task_id, "errors": [str(error)]}
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
