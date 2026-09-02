from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_common import atomic_write, emit, resolve_codex_home, resolve_repo_root, sha256_file, write_json


MANAGED_MARKER = "<!-- ai-harness:managed-global-agents:v1 -->"


def _run(script: Path, arguments: list[str]) -> dict[str, Any]:
    process = subprocess.run([sys.executable, str(script), *arguments, "--json"], text=True, capture_output=True, check=False)
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "errors": [process.stderr.strip() or process.stdout.strip() or f"exit {process.returncode}"]}
    if process.returncode or not payload.get("ok"):
        raise RuntimeError(f"bootstrap_step_failed: {script.name}: {payload.get('errors', payload)}")
    return payload


def _write_global_agents(root: Path, codex_home: Path, force: bool) -> tuple[bool, str, Path]:
    template_path = root / "templates" / "codex" / "AGENTS.global.md"
    if not template_path.is_file():
        raise ValueError(f"global_agents_template_missing: {template_path}")
    rendered = template_path.read_text(encoding="utf-8-sig").replace("{{HARNESS_ROOT}}", root.as_posix())
    if not rendered.startswith(MANAGED_MARKER):
        raise ValueError("global_agents_template_missing_managed_marker")
    target = codex_home / "AGENTS.md"
    backup_path = ""
    if target.is_file():
        existing = target.read_text(encoding="utf-8-sig")
        if existing == rendered:
            return False, backup_path, target
        if not existing.startswith(MANAGED_MARKER) and not force:
            raise ValueError("global_agents_unmanaged")
        if not existing.startswith(MANAGED_MARKER):
            digest = sha256_file(target)
            backup = codex_home / ".ai-harness" / "backups" / f"AGENTS.{digest}.md"
            if not backup.exists():
                atomic_write(backup, existing)
            backup_path = str(backup)
    atomic_write(target, rendered)
    return True, backup_path, target


def _clear_hooks(codex_home: Path) -> bool:
    hooks_path = codex_home / "hooks.json"
    if not hooks_path.is_file():
        return False
    try:
        payload = json.loads(hooks_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"hooks_json_invalid: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("hooks_json_root_not_object")
    hooks = payload.get("hooks")
    if hooks in (None, {}):
        return False
    payload["hooks"] = {}
    atomic_write(hooks_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the Linux-native Codex control plane.")
    parser.add_argument("--harness-root", "--repo-root", dest="repo_root", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--force-global-agents", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-rules", action="store_true")
    parser.add_argument("--skip-doctor", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload: dict[str, Any] = {
        "ok": False,
        "completed_steps": [],
        "issues": [],
        "restart_required": False,
        "restart_reasons": [],
    }
    try:
        root_source = "explicit" if args.repo_root else ("environment" if os.environ.get("AI_HARNESS_ROOT") else "script_root")
        root = resolve_repo_root(args.repo_root, Path(__file__))
        codex_home = resolve_codex_home(args.codex_home)
        codex_home.mkdir(parents=True, exist_ok=True)
        updated, backup_path, target = _write_global_agents(root, codex_home, args.force_global_agents)
        payload.update(harness_root={"path": str(root), "source": root_source}, codex_home=str(codex_home), updated=updated, backup_path=backup_path)
        payload["completed_steps"].append("global_agents")
        payload["hooks_cleared"] = _clear_hooks(codex_home)
        payload["completed_steps"].append("hook_cleanup")
        scripts = Path(__file__).parent
        restart_reasons: list[str] = []
        if updated:
            restart_reasons.append("managed_global_agents_changed")
        if not args.skip_sync:
            sync_payload = _run(scripts / "sync-codex.py", ["--harness-root", str(root), "--codex-home", str(codex_home)])
            payload["completed_steps"].append("sync")
            if sync_payload.get("changed_managed_skills"):
                restart_reasons.append("managed_skill_runtime_changed")
            if sync_payload.get("changed_schema_files"):
                restart_reasons.append("managed_schema_runtime_changed")
        if not args.skip_rules:
            _run(scripts / "generate_rules_index.py", ["--repo-root", str(root)])
            payload["completed_steps"].append("rules_generate")
            _run(scripts / "validate_rules.py", ["--repo-root", str(root)])
            payload["completed_steps"].append("rules_validate")
        receipt_path = codex_home / ".ai-harness" / "bootstrap.receipt.json"
        receipt = {
            "schema_version": "2.0", "harness_root": str(root), "harness_root_source": root_source,
            "codex_home": str(codex_home), "template_path": str(root / "templates" / "codex" / "AGENTS.global.md"),
            "template_sha256": sha256_file(root / "templates" / "codex" / "AGENTS.global.md"),
            "target_path": str(target), "target_sha256": sha256_file(target),
            "completed_steps": list(payload["completed_steps"]),
        }
        write_json(receipt_path, receipt)
        payload.update(receipt_path=str(receipt_path))
        payload["completed_steps"].append("receipt")
        if not args.skip_doctor:
            _run(scripts / "doctor-core.py", ["--root", str(root), "--codex-home", str(codex_home), "--strict"])
            payload["completed_steps"].append("doctor")
        payload["restart_reasons"] = restart_reasons
        payload["restart_required"] = bool(restart_reasons)
        payload["ok"] = True
    except (OSError, ValueError, RuntimeError) as error:
        payload["issues"].append(str(error))
    return emit(payload, as_json=args.json, success_message="Linux-native Codex bootstrap completed")


if __name__ == "__main__":
    raise SystemExit(main())
