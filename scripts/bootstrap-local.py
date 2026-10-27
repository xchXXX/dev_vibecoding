from __future__ import annotations

import argparse
import importlib.util
import fcntl
import json
import os
import shutil
import subprocess
from runtime_common import run_probe
import sys
import tempfile
import tomllib
import re
from contextlib import contextmanager, ExitStack
from pathlib import Path
from typing import Any

from runtime_common import MANAGED_SKILLS, MANAGED_WSL_RUNTIME_FILES, RETIRED_MANAGED_WSL_RUNTIME_FILES, atomic_write, emit, inspect_windows_external_capabilities, resolve_codex_home, resolve_repo_root, sha256_file, write_json


MANAGED_MARKER = "<!-- ai-harness:managed-global-agents:v1 -->"


def _source_generation(root):
    files = {path.relative_to(root).as_posix(): sha256_file(path)
            for directory in ("scripts", "skills", "schemas", "rules", "templates", "config", "tests", "docs")
            for path in sorted((root / directory).rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            and not path.is_relative_to(root / "docs/tasks") and not path.is_relative_to(root / "docs/ai/tasks")}
    files.update({path.name: sha256_file(path) for path in root.glob("*.md") if path.is_file()})
    return files


def _doctor_module(root):
    spec = importlib.util.spec_from_file_location("bootstrap_doctor", root / "scripts/doctor-core.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def _run(script: Path, arguments: list[str]) -> dict[str, Any]:
    process = run_probe([sys.executable, str(script), *arguments, "--json"], timeout=300, text=True, capture_output=True, check=False)
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
    changed = False
    hooks_path = codex_home / "hooks.json"
    if hooks_path.is_file():
        try:
            payload = json.loads(hooks_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as error:
            raise ValueError(f"hooks_json_invalid: {error}") from error
        if not isinstance(payload, dict):
            raise ValueError("hooks_json_root_not_object")
        hooks = payload.get("hooks")
        if hooks not in (None, {}):
            payload["hooks"] = {}
            atomic_write(hooks_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            changed = True

    return changed


def _environment_preflight(root: Path, codex_home: Path) -> tuple[dict[str, Any], list[Path]]:
    runtime = codex_home / '.ai-harness/runtime/wsl-environment'
    receipt = codex_home / '.ai-harness/bootstrap.receipt.json'
    previous = json.loads(receipt.read_text(encoding='utf-8-sig')) if receipt.is_file() else {}
    if (not isinstance(previous, dict) or (receipt.is_file() and previous.get('harness_root') != str(root))
            or (receipt.is_file() and previous.get('codex_home') != str(codex_home))
            or not isinstance(previous.get('managed_runtime_files', []), list)):
        raise ValueError('bootstrap_receipt_invalid')
    rows = previous.get('managed_runtime_files', [])
    if any(not isinstance(x, dict) or not isinstance(x.get('target_path'), str)
           or not isinstance(x.get('target_sha256'), str) for x in rows):
        raise ValueError('bootstrap_receipt_invalid')
    records = {x['target_path']: x['target_sha256'] for x in rows}
    if len(records) != len(rows):
        raise ValueError('bootstrap_receipt_duplicate_target')
    sources = {str(runtime / rel): str(root / source) for rel, source in MANAGED_WSL_RUNTIME_FILES}
    sources.update({str(runtime / rel): str(root / 'modules/wsl-environment/tooling' / Path(rel).name) for rel in RETIRED_MANAGED_WSL_RUNTIME_FILES})
    for row in rows:
        if row['target_path'] in sources and (row.get('source_path') != sources[row['target_path']]
                or not isinstance(row.get('source_sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', row['source_sha256'])
                or row['source_sha256'] != row['target_sha256']):
            raise ValueError('environment_receipt_source_invalid: ' + row['target_path'])
    targets = [runtime / rel for rel, _ in MANAGED_WSL_RUNTIME_FILES]
    retired = [runtime / rel for rel in RETIRED_MANAGED_WSL_RUNTIME_FILES]
    for _, source in MANAGED_WSL_RUNTIME_FILES:
        if not (root / source).is_file():
            raise ValueError('managed_wsl_runtime_source_missing: ' + source)
    for target in [*targets, *retired, receipt]:
        if target.is_symlink() or any(x.is_symlink() for x in target.parents if x != codex_home.parent):
            raise ValueError('environment_target_symlink: ' + str(target))
        if target.exists() and not target.is_file():
            raise ValueError('environment_target_not_file: ' + str(target))
        if target != receipt and target.exists() and records.get(str(target)) != sha256_file(target):
            raise ValueError('environment_installed_drift: ' + str(target))
    if any(x.exists() for x in retired):
        config = codex_home / 'config.toml'
        data = tomllib.loads(config.read_text(encoding='utf-8-sig')) if config.is_file() else {}
        servers = data.get('mcp_servers', {})
        if not isinstance(servers, dict):
            raise ValueError('legacy_mcp_config_invalid')
        for name in ('computer_use_wsl', 'browser_use_wsl'):
            item = servers.get(name)
            if item is not None and (not isinstance(item, dict) or item.get('enabled') is not False):
                raise ValueError('legacy GUI must already be explicitly disabled')
    return previous, [*targets, *retired, receipt]


@contextmanager
def _environment_transaction(root: Path, codex_home: Path):
    """Save installed preimages before writes; roll back files and receipt on failure."""
    previous, targets = _environment_preflight(root, codex_home)
    backup_root = codex_home / '.ai-harness/backups/environment-publication'
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='before-', dir=backup_root))
    manifest = []
    for i, target in enumerate(targets):
        item = {'target': str(target), 'existed': target.is_file()}
        if item['existed']:
            saved = backup / str(i)
            shutil.copy2(target, saved)
            item.update(copy=str(saved), sha256=sha256_file(saved))
        manifest.append(item)
    write_json(backup / 'manifest.json', {'files': manifest})
    try:
        yield previous
    except BaseException as original:
        failures = []
        for item in reversed(manifest):
            target = Path(item['target'])
            try:
                if item['existed']:
                    saved = Path(item['copy'])
                    if sha256_file(saved) != item['sha256']:
                        raise RuntimeError('backup hash mismatch')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(saved, target)
                    shutil.copystat(saved, target)
                else:
                    target.unlink(missing_ok=True)
            except Exception as error:
                failures.append({'target': str(target), 'error': str(error)})
        if failures:
            raise RuntimeError(json.dumps({'type': 'environment_restore_failed',
                'original_error': type(original).__name__ + ': ' + str(original),
                'backup_path': str(backup), 'unrestored': failures})) from original
        raise


def _sync_wsl_environment_runtime(root: Path, codex_home: Path, *, previous=None, prepared=None) -> tuple[bool, list[dict[str, str]], list[str]]:
    if previous is None:
        previous, _ = _environment_preflight(root, codex_home)
    verified_targets = {row['target_path']: row['target_sha256'] for row in previous.get('managed_runtime_files', [])}
    runtime_root = codex_home / '.ai-harness/runtime/wsl-environment'
    owned = {str(runtime_root / rel) for rel, _ in MANAGED_WSL_RUNTIME_FILES}
    owned.update(str(runtime_root / rel) for rel in RETIRED_MANAGED_WSL_RUNTIME_FILES)
    managed_files = [x for x in previous.get('managed_runtime_files', []) if x['target_path'] not in owned]
    changed = False
    retired_files_removed = []
    for relative in RETIRED_MANAGED_WSL_RUNTIME_FILES:
        target = runtime_root / relative
        if target.is_file():
            target.unlink()
            changed = True
            retired_files_removed.append(str(target))
    for relative, source_relative in MANAGED_WSL_RUNTIME_FILES:
        source, target = root / source_relative, runtime_root / relative
        digest = prepared[source_relative] if prepared is not None else sha256_file(source)
        target_digest = verified_targets.get(str(target)) if target.is_file() else None
        if target_digest != digest:
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, name = tempfile.mkstemp(prefix='.' + target.name + '.', dir=target.parent)
            os.close(descriptor)
            temporary = Path(name)
            try:
                shutil.copy2(source, temporary)
                if sha256_file(temporary) != digest:
                    raise ValueError('publication_source_changed')
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            changed = True
        managed_files.append({'source_path': str(source), 'target_path': str(target),
                              'source_sha256': digest, 'target_sha256': digest})
    return changed, managed_files, retired_files_removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the Linux-native Codex control plane.")
    parser.add_argument("--harness-root", "--repo-root", dest="repo_root", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--force-global-agents", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--environment-only", action="store_true", help="Publish only environment runtime and its receipt; preserve skills, config and AGENTS.")
    parser.add_argument("--git-workflow-only", action="store_true", help="Publish managed AGENTS, Git checker and task workspace entry; preserve other runtime state.")
    parser.add_argument("--skill", choices=MANAGED_SKILLS, help="Synchronize only one managed skill before the shared environment runtime.")
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
        "retired_runtime_files_removed": [],
    }
    try:
        with ExitStack() as publication:
            root_source = "explicit" if args.repo_root else ("environment" if os.environ.get("AI_HARNESS_ROOT") else "script_root")
            root = resolve_repo_root(args.repo_root, Path(__file__))
            codex_home = resolve_codex_home(args.codex_home)
            # A staged host migration must not republish the previous environment.
            if (codex_home / ".ai-harness/windows-native-transition.hold").exists():
                raise ValueError("WINDOWS_NATIVE_TRANSITION_HOLD: complete the native migration before publishing")
            if args.git_workflow_only:
                if args.environment_only or args.skill or args.force_global_agents or args.skip_sync or args.skip_rules or args.skip_doctor:
                    raise ValueError("--git-workflow-only cannot be combined with other publication modes")
                from publish_git_workflow import publish
                return emit(publish(root, codex_home), as_json=args.json)
            if args.environment_only:
                if args.skill or args.skip_sync or args.force_global_agents:
                    raise ValueError("--environment-only cannot be combined with skill, skip-sync or force-global-agents")
                lock_path = codex_home / ".ai-harness/codex-sync.lock"
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                with lock_path.open("a+", encoding="utf-8") as lock:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                    if (codex_home / ".ai-harness/windows-native-transition.hold").exists():
                        raise ValueError("WINDOWS_NATIVE_TRANSITION_HOLD")
                    receipt_path = codex_home / ".ai-harness/bootstrap.receipt.json"
                    with _environment_transaction(root, codex_home) as previous:
                        changed, files, retired = _sync_wsl_environment_runtime(root, codex_home, previous=previous)
                        template = root / "templates/codex/AGENTS.global.md"
                        agents = codex_home / "AGENTS.md"
                        # Adopt only a proven, already-rendered managed entry; never rewrite active instructions.
                        if template.is_file() and agents.is_file():
                            rendered = template.read_text(encoding="utf-8-sig").replace("{{HARNESS_ROOT}}", root.as_posix())
                            if rendered.startswith(MANAGED_MARKER) and agents.read_text(encoding="utf-8-sig") == rendered:
                                previous.update(harness_root=str(root), codex_home=str(codex_home),
                                    template_path=str(template), template_sha256=sha256_file(template),
                                    target_path=str(agents), target_sha256=sha256_file(agents))
                        write_json(receipt_path, {**previous, "harness_root": str(root), "codex_home": str(codex_home), "managed_runtime_files": files,
                            "environment_publication": {"harness_root": str(root), "codex_home": str(codex_home), "scope": "environment-only"}})
                        return emit({"ok": True, "scope": "environment-only", "runtime_changed": changed,
                            "managed_runtime_files": files, "retired_runtime_files_removed": retired,
                            "receipt_path": str(receipt_path)}, as_json=args.json)
            scripts = Path(__file__).parent
            if not args.skip_rules:
                _run(scripts / "generate_rules_index.py", ["--repo-root", str(root)])
                payload["completed_steps"].append("rules_generate")
                _run(scripts / "validate_rules.py", ["--repo-root", str(root)])
                payload["completed_steps"].append("rules_validate")
            generation = _source_generation(root)
            doctor = _doctor_module(root) if not args.skip_doctor else None
            contract_gate = None
            if doctor is not None and args.skill in {None, 'global-task-orchestrator'}:
                contract_gate = doctor._contract_gate(root)
                if not contract_gate['ok']:
                    raise RuntimeError(contract_gate.get('category', 'contract_gate_failed'))
            if generation != _source_generation(root):
                raise ValueError('publication_source_changed')
            codex_home.mkdir(parents=True, exist_ok=True)
            lock_path = codex_home / '.ai-harness/codex-sync.lock'
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock = publication.enter_context(lock_path.open('a+', encoding='utf-8'))
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if (codex_home / '.ai-harness/windows-native-transition.hold').exists():
                raise ValueError('WINDOWS_NATIVE_TRANSITION_HOLD')
            if generation != _source_generation(root):
                raise ValueError('publication_source_changed')
            spec = importlib.util.spec_from_file_location('bootstrap_sync', scripts / 'sync-codex.py')
            sync = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sync)
            selected = [args.skill] if args.skill else list(MANAGED_SKILLS)
            prepared = {name: {relative[len('skills/' + name + '/'):]: digest
                        for relative, digest in generation.items() if relative.startswith('skills/' + name + '/')}
                        for name in selected}
            rollback = [codex_home / 'AGENTS.md', codex_home / 'hooks.json',
                        codex_home / '.ai-harness/bootstrap.receipt.json']
            if not args.skip_sync:
                rollback += [codex_home / 'skills' / name for name in selected]
                rollback += [codex_home / '.ai-harness/codex-sync.receipt.json',
                             codex_home / 'schemas/orchestrator-task-state.schema.json']
            publication.enter_context(sync._publication_backup(rollback, lock_path.parent))
            updated, backup_path, target = _write_global_agents(root, codex_home, args.force_global_agents)
            payload.update(harness_root={"path": str(root), "source": root_source}, codex_home=str(codex_home), updated=updated, backup_path=backup_path)
            payload["completed_steps"].append("global_agents")
            restart_reasons: list[str] = []
            if updated:
                restart_reasons.append("managed_global_agents_changed")
            payload["restart_reasons"] = restart_reasons
            payload["restart_required"] = bool(restart_reasons)
            payload["hooks_cleared"] = _clear_hooks(codex_home)
            payload["completed_steps"].append("hook_cleanup")
            scripts = Path(__file__).parent
            if args.skip_sync and args.skill:
                raise ValueError("--skill cannot be combined with --skip-sync")
            if not args.skip_sync:
                sync_payload = sync.synchronize(root, codex_home, skills=[args.skill] if args.skill else None, _locked=True, _prepared=prepared)
                if not sync_payload.get('ok'):
                    raise RuntimeError('sync_failed: ' + json.dumps(sync_payload))
                payload["sync"] = sync_payload
                payload["completed_steps"].append("sync")
                if sync_payload.get("changed_managed_skills"):
                    restart_reasons.append("managed_skill_runtime_changed")
                if sync_payload.get("changed_schema_files"):
                    restart_reasons.append("managed_schema_runtime_changed")
            if not args.skip_sync:
                runtime_previous = publication.enter_context(_environment_transaction(root, codex_home))
            managed_runtime_files: list[dict[str, str]] = []
            previous_receipt_path = codex_home / ".ai-harness" / "bootstrap.receipt.json"
            if args.skip_sync and previous_receipt_path.is_file():
                previous_receipt = json.loads(previous_receipt_path.read_text(encoding="utf-8-sig"))
                if isinstance(previous_receipt, dict) and isinstance(previous_receipt.get("managed_runtime_files"), list):
                    managed_runtime_files = previous_receipt["managed_runtime_files"]
            if not args.skip_sync:
                wsl_runtime_changed, managed_runtime_files, retired_runtime_files_removed = _sync_wsl_environment_runtime(root, codex_home, previous=runtime_previous, prepared=generation)
                payload["retired_runtime_files_removed"] = retired_runtime_files_removed
                payload["managed_runtime_files"] = managed_runtime_files
                payload["completed_steps"].append("wsl_environment_runtime")
                if wsl_runtime_changed:
                    restart_reasons.append("managed_wsl_environment_runtime_changed")
                payload["restart_reasons"] = restart_reasons
                payload["restart_required"] = bool(restart_reasons)

            payload["windows_external_capabilities"] = inspect_windows_external_capabilities(
                codex_home, root / "config/ai/windows-external-capabilities.json")
            payload["completed_steps"].append("windows_external_readonly_check")
            receipt_path = codex_home / ".ai-harness" / "bootstrap.receipt.json"
            receipt = {
                "schema_version": "2.0", "harness_root": str(root), "harness_root_source": root_source,
                "codex_home": str(codex_home), "template_path": str(root / "templates" / "codex" / "AGENTS.global.md"),
                "template_sha256": sha256_file(root / "templates" / "codex" / "AGENTS.global.md"),
                "target_path": str(target), "target_sha256": sha256_file(target),
                "managed_runtime_files": managed_runtime_files,
                "completed_steps": list(payload["completed_steps"]),
            }
            write_json(receipt_path, receipt)
            payload.update(receipt_path=str(receipt_path))
            payload["completed_steps"].append("receipt")
            if not args.skip_doctor:
                audited = doctor.audit(root, codex_home, managed_skill=args.skill)
                audited['contract_gate'] = contract_gate
                if not audited['ok']:
                    raise RuntimeError('bootstrap_doctor_failed: ' + json.dumps(audited.get('errors', [])))
                payload['doctor'] = audited
                payload["completed_steps"].append("doctor")
            payload["restart_reasons"] = restart_reasons
            payload["restart_required"] = bool(restart_reasons)
            if generation != _source_generation(root):
                raise ValueError('publication_source_changed')
            payload["ok"] = True
    except (Exception, KeyboardInterrupt, SystemExit) as error:
        payload["issues"].append(type(error).__name__ + ": " + str(error))
    return emit(payload, as_json=args.json, success_message="Linux-native Codex bootstrap completed")


if __name__ == "__main__":
    raise SystemExit(main())
