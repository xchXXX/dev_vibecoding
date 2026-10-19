#!/usr/bin/env python3
"""Minimal WSL-native control plane for long-running orchestrated tasks.

Codex owns semantic decisions.  This module only persists and validates an
already structured contract and advances deterministic review state.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import hashlib
from functools import lru_cache
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator, FormatChecker

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from runtime_evidence import freeze_tree, tree_manifest, verify_tree, acceptance_run_errors
import acceptance_points as point_acceptance
from capability_gate import capability_errors as _capability_errors, capability_receipt as _capability_receipt, capture_context as _capture_capability_context, scoped_declarations as _scoped_capabilities

from acceptance_batches import (
    BatchEvidenceError,
    add_batch as _add_acceptance_batch,
    add_coverage as _add_acceptance_coverage,
    coverage_evidence_sources as _batch_coverage_evidence_sources,
    current_coverage as _current_batch_coverage,
    validate_all_batches as _batch_errors,
    validate_coverages as _coverage_errors,
    validate_partial as _validate_partial_acceptance,
)


SIX_POINT_KEYS = ("do", "do_not", "change_areas", "implementation", "acceptance", "risks")
ARTIFACTS = (
    ("ai", "state.json"),
    ("ai", "task.md"),
    ("ai", "events.jsonl"),
    ("task", "plan.md"),
    ("task", "execution.md"),
    ("task", "acceptance.md"),
)
DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)
FORMAT_CHECKER = FormatChecker()
USER_COMPLETION_WAIVER_DECISION = (
    "user_completion_waiver: acceptance passed and documentation synced without final review"
)


@FORMAT_CHECKER.checks("date-time", raises=ValueError)
def _is_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if not DATE_TIME.fullmatch(value):
        return False
    normalized = value[:-1] + "+00:00" if value[-1:].casefold() == "z" else value
    return dt.datetime.fromisoformat(normalized).tzinfo is not None


class ControlError(Exception):
    def __init__(self, *errors: str) -> None:
        super().__init__(errors[0] if errors else "control-plane error")
        self.errors = list(errors) or ["control-plane error"]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    data = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(data).hexdigest()


def _completion_conclusion(state: dict[str, Any]) -> str:
    return "最新候选已通过完整独立审查覆盖及真实验收，事实已同步，任务完成。" if state.get("status") == "completed" else "任务尚未完成；需最新候选审查、验收和事实回执。"


def _json_file_arg(raw: str | None, label: str) -> Any:
    if raw is None:
        raise ControlError(f"{label} is required")
    try:
        text = Path(raw).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ControlError(f"{label} cannot be read: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ControlError(f"{label} is not valid JSON: {exc.msg}") from exc


def _task_paths(repo: Path, task_id: str) -> dict[str, Path]:
    ai = repo / "docs" / "ai" / "tasks" / task_id
    task = repo / "docs" / "tasks" / task_id
    return {
        "state.json": ai / "state.json",
        "task.md": ai / "task.md",
        "events.jsonl": ai / "events.jsonl",
        "plan.md": task / "plan.md",
        "execution.md": task / "execution.md",
        "acceptance.md": task / "acceptance.md",
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def _upsert_markdown_section(path: Path, heading: str, body: str, fallback: str) -> str:
    if not path.is_file():
        return fallback
    text = path.read_text(encoding="utf-8")
    section = f"{heading}\n\n{body.rstrip()}\n"
    pattern = re.compile(rf"(?ms)^{re.escape(heading)}\n.*?(?=^## |\Z)")
    if pattern.search(text):
        return pattern.sub(section + "\n", text, count=1).rstrip() + "\n"
    return text.rstrip() + "\n\n" + section


@contextlib.contextmanager
def _task_lock(repo: Path, task_id: str) -> Iterator[None]:
    lock_path = repo / "docs" / "ai" / "tasks" / task_id / ".control.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            if stream.tell() == stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _write_state(paths: dict[str, Path], state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    repo = paths["state.json"].parents[4]
    errors = _state_model_errors(repo, state)
    if errors:
        raise ControlError(*errors)
    rendered = _render_artifacts(state["task_id"], state["title"], state)
    action = state.get("next_action", {}).get("kind", "not_initialized")
    task_body = (
        f"- status: `{state.get('status', 'draft')}`\n"
        f"- current_phase: `{state.get('current_phase', 'planning')}`\n"
        f"- next_action: `{action}`"
    )
    if blocker := state.get("coordinator_blocker"):
        task_body += f"\n- blocked_from_phase: `{blocker['previous_phase']}`\n- blocked_by: " + "; ".join(blocker["result"]["blocked_by"])
    conclusion = _completion_conclusion(state)
    synchronized = {
        "task.md": _upsert_markdown_section(paths["task.md"], "## 当前状态", task_body, rendered["task.md"]),
        "acceptance.md": _upsert_markdown_section(
            paths["acceptance.md"], "## 最终结论", conclusion, rendered["acceptance.md"]
        ),
    }
    for name, text in synchronized.items():
        _atomic_write(paths[name], text)
        state.setdefault("artifact_sha256", {})[name] = _sha(text.encode("utf-8"))
    _atomic_write(paths["state.json"], json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def _append_event(path: Path, task_id: str, event: str, **data: Any) -> None:
    record = {"timestamp": _now(), "task_id": task_id, "event": event, **data}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


@contextlib.contextmanager
def _preserve_artifacts_on_io_failure(paths: dict[str, Path]) -> Iterator[None]:
    """Keep one command's six artifacts together if a write or event append fails.

    The caller holds the task lock. Deliberate ControlError outcomes (for example
    a recorded workspace conflict) retain their documented persisted evidence.
    """
    before = {path: path.read_bytes() if path.is_file() else None for path in paths.values()}
    try:
        yield
    except OSError as failure:
        unrecovered = []
        for path, content in before.items():
            try:
                if content is None:
                    path.unlink(missing_ok=True)
                elif not path.is_file() or path.read_bytes() != content:
                    _atomic_write(path, content.decode('utf-8'))
            except (OSError, UnicodeError) as restore_error:
                unrecovered.append(f'{path.name}: {restore_error}')
        detail = 'previous six-artifact contents restored' if not unrecovered else 'restoration incomplete: ' + '; '.join(unrecovered)
        raise ControlError(f'persistent artifact write failed: {failure}; {detail}') from failure


def _load_state(paths: dict[str, Path]) -> dict[str, Any]:
    try:
        value = json.loads(paths["state.json"].read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlError("state.json does not exist") from exc
    except json.JSONDecodeError as exc:
        raise ControlError(f"state.json is invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ControlError("state.json root must be an object")
    if value.get('checkout_binding') != _sha(str(paths['state.json'].parents[4].resolve())):
        raise ControlError('task checkout binding mismatch; do not advance a copied active state')
    return value


def _require_text(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")


def _require_text_list(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{name} must be a non-empty string list")


def validate_plan_output_contract(value: Any) -> list[str]:
    """Validate the semantic Plan payload shown before control-plane creation."""

    if not isinstance(value, dict):
        return ["plan_output: contract must be an object"]

    errors: list[str] = []
    points = value.get("six_points")
    if not isinstance(points, dict):
        errors.append("six_points: must be an object")
    else:
        for key in SIX_POINT_KEYS:
            if key in ("do", "implementation"):
                _require_text(points.get(key), f"six_points.{key}", errors)
            else:
                _require_text_list(points.get(key), f"six_points.{key}", errors)

    requirements = value.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("requirements: must contain the complete numbered requirements list")
    else:
        requirement_ids: set[str] = set()
        for index, item in enumerate(requirements):
            prefix = f"requirements[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix}: must be an object")
                continue
            ident = item.get("id")
            if not isinstance(ident, str) or not re.fullmatch(r"REQ-\d+", ident):
                errors.append(f"{prefix}.id: must be a numbered REQ id")
            elif ident in requirement_ids:
                errors.append(f"{prefix}.id: duplicate requirement id {ident}")
            else:
                requirement_ids.add(ident)
            _require_text(item.get("requirement"), f"{prefix}.requirement", errors)
            _require_text(item.get("owner"), f"{prefix}.owner", errors)
            _require_text_list(item.get("acceptance_ids"), f"{prefix}.acceptance_ids", errors)

    workflow = value.get("workflow")
    if not isinstance(workflow, dict) or workflow.get("source") != "skills/global-task-orchestrator/references/workflow.md":
        errors.append("workflow_source")
        routes: Any = None
    else:
        routes = workflow.get("rework_routes")
    expected_routes = {
        "review": {
            "discoverer": "original_reviewer",
            "fixer": "original_integrator",
            "verifier": "original_reviewer",
        },
        "acceptance": {
            "discoverer": "original_acceptance_owner",
            "fixer": "original_integrator",
            "verifier": "original_acceptance_owner",
        },
    }
    for route, expected in expected_routes.items():
        error_code = f"{route}_rework_route"
        candidate = routes.get(route) if isinstance(routes, dict) else None
        if not isinstance(candidate, dict) or any(candidate.get(key) != expected_value for key, expected_value in expected.items()):
            errors.append(error_code)

    tasks = value.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks: must contain the task table")
    else:
        task_ids: set[str] = set()
        for index, item in enumerate(tasks):
            prefix = f"tasks[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix}: must be an object")
                continue
            for field in ("id", "phase", "owner", "goal", "planned_agent_key"):
                _require_text(item.get(field), f"{prefix}.{field}", errors)
            task_id = item.get("id")
            if isinstance(task_id, str) and task_id.strip():
                if task_id in task_ids:
                    errors.append(f"{prefix}.id: duplicate task id {task_id}")
                task_ids.add(task_id)
            for field in ("dependencies", "inputs", "write_paths", "done_when"):
                candidate = item.get(field)
                if field in {"dependencies", "write_paths"}:
                    if not isinstance(candidate, list) or any(not isinstance(entry, str) or not entry.strip() for entry in candidate):
                        errors.append(f"{prefix}.{field}: must be a string list")
                else:
                    _require_text_list(candidate, f"{prefix}.{field}", errors)
    return errors


def _validate_contract(contract: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["contract must be an object"]
    if contract.get("workflow_revision") != 3:
        return ["workflow_revision must be 3; retired contracts are not supported"]
    points = contract.get("six_points")
    if not isinstance(points, dict):
        return ["six_points must be an object"]
    for key in SIX_POINT_KEYS:
        if key in ("do", "implementation"):
            _require_text(points.get(key), f"six_points.{key}", errors)
        else:
            _require_text_list(points.get(key), f"six_points.{key}", errors)
    mirrors = {
        "objective": "do",
        "scope_in": "change_areas",
        "scope_out": "do_not",
        "acceptance": "acceptance",
        "stop_conditions": "risks",
    }
    for field, point in mirrors.items():
        if contract.get(field) != points.get(point):
            errors.append(f"{field} must equal six_points.{point}")
    decisions = contract.get("decisions")
    _require_text_list(decisions, "decisions", errors)
    if isinstance(decisions, list) and points.get("implementation") not in decisions:
        errors.append("decisions must include six_points.implementation")
    approval = contract.get("approval")
    if not isinstance(approval, dict) or approval.get("status") != "approved":
        errors.append("approval.status must be approved")
    elif not approval.get("approved_by"):
        errors.append("approval.approved_by is required")
    subtasks = contract.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        errors.append("subtasks must contain at least one real subtask")
    else:
        ids: set[str] = set()
        for index, item in enumerate(subtasks):
            prefix = f"subtasks[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in ("subtask_id", "title", "role", "status"):
                _require_text(item.get(field), f"{prefix}.{field}", errors)
            subtask_id = item.get("subtask_id")
            if subtask_id in ids:
                errors.append(f"duplicate subtask_id: {subtask_id}")
            if isinstance(subtask_id, str):
                ids.add(subtask_id)
            if not isinstance(item.get("dependencies"), list):
                errors.append(f"{prefix}.dependencies must be a list")
            for field in ("read_paths", "write_paths"):
                if not isinstance(item.get(field), list):
                    errors.append(f"{prefix}.{field} must be a list")
            assignment = item.get("assignment")
            if not isinstance(assignment, dict):
                errors.append(f"{prefix}.assignment must be an object")
            else:
                _require_text(assignment.get("goal"), f"{prefix}.assignment.goal", errors)
                _require_text_list(assignment.get("must_include"), f"{prefix}.assignment.must_include", errors)
                _require_text_list(assignment.get("verification"), f"{prefix}.assignment.verification", errors)
    verification = contract.get("verification_contract")
    if verification is not None:
        if not isinstance(verification, dict):
            errors.append("verification_contract must be an object")
        else:
            for field in ("minimal_repro", "hit_proof"):
                _require_text(verification.get(field), f"verification_contract.{field}", errors)
            for field in ("diagnostic_checks", "acceptance_checks", "non_goals", "review_evidence"):
                _require_text_list(verification.get(field), f"verification_contract.{field}", errors)
    if isinstance(subtasks, list) and isinstance(verification, dict):
        allowed_keys = set(verification.get("review_evidence", []))
        attempt_subtasks = {
            attempt.get("subtask_id")
            for attempt in contract.get("acceptance_gate", {}).get("attempts", [])
            if isinstance(attempt, dict)
        }
        owners: dict[str, str] = {}
        for index, item in enumerate(subtasks):
            if not isinstance(item, dict) or item.get("stage") != "expensive_acceptance" or item.get("subtask_id") in attempt_subtasks:
                continue
            required = item.get("assignment", {}).get("required_verification_evidence", {})
            if not isinstance(required, dict):
                continue
            for kind, keys in required.items():
                if kind not in {"ordinary", "blackbox"}:
                    errors.append(f"subtasks[{index}].assignment.required_verification_evidence has unsupported kind: {kind}")
                    continue
                if not isinstance(keys, list):
                    continue
                for key in keys:
                    if key not in allowed_keys:
                        errors.append(f"verification evidence key is not declared by verification_contract.review_evidence: {key}")
                    owner = owners.get(key)
                    label = f"{item.get('subtask_id')}:{kind}"
                    if owner and owner != label:
                        errors.append(f"verification evidence key has multiple acceptance owners: {key}")
                    owners[key] = label
    return errors


def _requirements(state: dict[str, Any]) -> list[str]:
    return [value for value in state.get("decisions", []) if isinstance(value, str) and value.startswith("REQ-")]


def _requirement_errors(state: dict[str, Any], *, required: bool = False) -> list[str]:
    rows = _requirements(state)
    errors = []
    if required and not rows:
        errors.append("new revision 3 contract requires a complete REQ checklist")
    ids = set()
    owners = {item.get("subtask_id") for item in state.get("subtasks", [])}
    acceptance = {item.get("acceptance_id") for item in state.get("acceptance_gate", {}).get("acceptance_items", [])}
    for row in rows:
        match = re.fullmatch(r"(REQ-\d+)｜(.+?)｜落实：(.+?)｜验收：(.+)", row)
        if not match:
            errors.append("requirement must include REQ id, body, owners and acceptance ids")
            continue
        ident, body, assigned, checks = match.groups()
        if ident in ids:
            errors.append("duplicate requirement id: " + ident)
        ids.add(ident)
        for values, known, label in ((assigned, owners, "owner"), (checks, acceptance, "acceptance")):
            refs = [value.strip() for value in re.split(r"[、,，;；]", values)]
            if not set(refs).issubset(known):
                errors.append(f"requirement {ident} has unknown {label} references")
    return errors


def _contract_hash(state: dict[str, Any]) -> str:
    rows = _requirements(state)
    planned_ids = state.get('approval', {}).get('planned_subtask_ids')
    if planned_ids is not None:
        by_id = {t['subtask_id']: t for t in state.get('subtasks', [])}
        fields = ('subtask_id', 'title', 'role', 'stage', 'planned_agent_key',
                  'dependencies', 'read_paths', 'write_paths', 'assignment')
        return _sha({'six_points': state.get('six_points'), 'requirements': rows,
                     'checkout_binding': state.get('checkout_binding'),
                     'execution_plan': [{k: by_id.get(ident, {}).get(k) for k in fields}
                                        for ident in planned_ids]})
    return _sha({'six_points': state.get('six_points'), 'requirements': rows,
                 'checkout_binding': state.get('checkout_binding'),
                 'execution_plan': state.get('subtasks', [])})


def _planned_dispatch_errors(state: dict[str, Any], task: dict[str, Any], key: str, agent_id: str) -> list[str]:
    planned = task.get('planned_agent_key')
    if planned is None:
        return ['planned_agent_key is required by the current contract']
    errors = []
    if key != planned:
        errors.append(f"{task['subtask_id']}: agent_key must equal planned_agent_key {planned}")
    for other in state.get('subtasks', []):
        dispatch = other.get('dispatch') or {}
        if not dispatch or other is task:
            continue
        same_key = other.get('planned_agent_key') == planned
        same_id = dispatch.get('platform_agent_id') == agent_id
        if same_key and not same_id:
            errors.append(f"planned agent {planned} must retain platform identity {dispatch.get('platform_agent_id')}")
        if same_id and not same_key:
            errors.append(f"platform identity {agent_id} is already assigned to another planned agent")
    return list(dict.fromkeys(errors))


def _execution_plan_errors(state: dict[str, Any]) -> list[str]:
    ids = state.get('approval', {}).get('planned_subtask_ids')
    if ids is None:
        return ['approved planned_subtask_ids is required; old allocation contracts are not supported']
    tasks = state.get('subtasks', [])
    by_id = {t.get('subtask_id'): t for t in tasks}
    errors = []
    for ident in ids:
        if ident not in by_id:
            errors.append(f"approved subtask is missing: {ident}")
    for task in tasks:
        ident = task.get('subtask_id')
        if not task.get('planned_agent_key'):
            errors.append(f"{ident}: planned_agent_key is required")
        if ident not in ids:
            source = by_id.get(task.get('plan_source_subtask_id'))
            if not source or source.get('subtask_id') not in ids:
                errors.append(f"{ident}: unapproved task requires an approved plan source")
            else:
                errors.extend(_derived_plan_errors(state, task, source, by_id))
        if dispatch := task.get('dispatch'):
            errors.extend(_planned_dispatch_errors(state, task, dispatch.get('agent_key'), dispatch.get('platform_agent_id')))
    return list(dict.fromkeys(errors))


def _derived_plan_errors(state, task, source, by_id):
    """Only the controller's existing repair/review/attempt contracts may extend a plan."""
    ident = task['subtask_id']
    if any(task.get(k) != source.get(k) for k in ('planned_agent_key', 'role', 'stage', 'read_paths', 'write_paths')):
        return [f'{ident}: derived task must retain approved agent, role, stage and scope']
    deps = [by_id.get(d, {}) for d in task.get('dependencies', [])]
    same_source = lambda t: t.get('plan_source_subtask_id', t.get('subtask_id')) == source['subtask_id']
    preceding = state['subtasks'][:state['subtasks'].index(task)]
    prior_integrations = [t for t in preceding if t.get('stage') == 'integration']
    prior_same_source = [t for t in preceding if same_source(t)]
    assignment = task.get('assignment', {})
    stage = task.get('stage')
    valid = False
    if stage == 'integration':
        valid = (len(deps) == 1 and prior_same_source and deps[0] == prior_same_source[-1]
                 and same_source(deps[0]) and deps[0].get('status') == 'completed'
                 and deps[0].get('stage') == stage and assignment == source.get('assignment'))
    elif stage == 'pre_acceptance_review':
        valid = (len(deps) == 2 and prior_same_source and deps[0] == prior_same_source[-1]
                 and prior_integrations and deps[1] == prior_integrations[-1]
                 and same_source(deps[0]) and deps[0].get('stage') == stage
                 and all(d.get('status') == 'completed' and d.get('dispatch') for d in deps))
        if valid:
            lineage = {'original_implementer': _identity(deps[1].get('dispatch', {})),
                       'original_reviewer': _identity(deps[0].get('dispatch', {}))}
            expected = copy.deepcopy(source['assignment'])
            expected['goal'] = 'Review latest changed scope and fixed findings; report new findings with proof.'
            included = assignment.get('must_include', [])
            finding_ids = [line.removeprefix('Re-review finding ').removesuffix('.') for line in included[1:]]
            expected['must_include'] = ['Cover current candidate changes and affected formal documents.',
                                        *[f'Re-review finding {fid}.' for fid in finding_ids]]
            valid = (task.get('lineage') == lineage and assignment == expected
                     and all(state.get('findings', {}).get(fid, {}).get('lineage', {}).get('original_reviewer')
                             == lineage['original_reviewer'] for fid in finding_ids))
    elif stage == 'expensive_acceptance':
        attempts = state.get('acceptance_gate', {}).get('attempts', [])
        matches = [(i, a) for i, a in enumerate(attempts) if a.get('subtask_id') == ident]
        if len(matches) == 1:
            index, attempt = matches[0]
            template = by_id.get(attempt.get('template_subtask_id'), {})
            original = next((by_id[a['subtask_id']] for a in attempts[:index]
                             if a.get('template_subtask_id') == attempt.get('template_subtask_id')
                             and by_id[a['subtask_id']].get('dispatch')), None)
            owner = _identity(original['dispatch']) if original else None
            valid = (same_source(template) and assignment == source.get('assignment')
                     and (not task.get('acceptance_owner') or task['acceptance_owner'] == owner)
                     and (task.get('dependencies') == template.get('dependencies') if not task.get('acceptance_owner')
                          else len(deps) == 1 and prior_integrations and deps[0] == prior_integrations[-1]
                          and deps[0].get('status') == 'completed'))
    return [] if valid else [f'{ident}: derived task does not match an approved repair, review or acceptance contract']


def _inherit_plan(created: dict[str, Any], source: dict[str, Any]) -> None:
    if source.get('planned_agent_key'):
        created['planned_agent_key'] = source['planned_agent_key']
        created['plan_source_subtask_id'] = source.get('plan_source_subtask_id', source['subtask_id'])


def _render_artifacts(task_id: str, title: str, contract: dict[str, Any]) -> dict[str, str]:
    points = contract["six_points"]

    def bullets(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values)

    def cell(value: Any) -> str:
        if isinstance(value, list):
            value = "<br>".join(str(item) for item in value)
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    def owner(item: dict[str, Any]) -> str:
        roles = {'tester': '测试', 'backend-implementer': '后端实施', 'frontend-implementer': '前端实施',
                 'reviewer': '审查', 'doc-curator': '文档'}
        stages = {'integration': '整合', 'pre_acceptance_review': '审查',
                  'expensive_acceptance': '验收', 'final_documentation': '文档收尾'}
        label = stages.get(item.get('stage'), roles.get(item.get('role'), item.get('role', '')))
        return f"{item['planned_agent_key']}（{label}）" if item.get('planned_agent_key') else label

    def task_graph(tasks: list[dict[str, Any]]) -> str:
        nodes = {item['subtask_id']: f'N{i}' for i, item in enumerate(tasks)}
        lines = ['```mermaid', 'flowchart TD']
        for item in tasks:
            label = f"{item['subtask_id']} {owner(item)}：{item['title']}"
            entities = {'#': '#35;', '"': '#quot;', '&': '#38;', '<': '#60;', '>': '#62;', '\\': '#92;'}
            label = ''.join(entities.get(char, ' ' if char in '\r\n' else char) for char in label)
            lines.append(f'    {nodes[item["subtask_id"]]}["{label}"]')
        for item in tasks:
            for dependency in item.get('dependencies', []):
                if dependency in nodes:
                    lines.append(f"    {nodes[dependency]} --> {nodes[item['subtask_id']]}")
        return '\n'.join([*lines, '```'])

    def requirement_table(rows: list[str]) -> str:
        rendered = ["| 编号 | 改造结果 | 责任 | 验收 |", "| --- | --- | --- | --- |"]
        for row in rows:
            parts = [part.strip() for part in row.split("｜")]
            rendered.append("| " + " | ".join(cell(part) for part in parts[:4]) + " |")
        return "\n".join(rendered)

    def task_table(items: list[dict[str, Any]]) -> str:
        rendered = ["| 步骤 | 责任 | 交付 | 前置条件 |", "| --- | --- | --- | --- |"]
        remaining = list(items)
        known_ids = {item.get("subtask_id") for item in remaining}
        completed_ids: set[str] = set()
        ordered: list[dict[str, Any]] = []
        while remaining:
            ready = [
                item
                for item in remaining
                if all(dep not in known_ids or dep in completed_ids for dep in (item.get("dependencies") or []))
            ]
            if not ready:
                ordered.extend(remaining)
                break
            for item in ready:
                ordered.append(item)
                completed_ids.add(item.get("subtask_id"))
                remaining.remove(item)
        for item in ordered:
            assignment = item.get("assignment") if isinstance(item.get("assignment"), dict) else {}
            deliverable = assignment.get("goal") or item.get("title", "")
            dependencies = item.get("dependencies") or []
            rendered.append(
                "| "
                + " | ".join(
                    (
                        cell(item.get("subtask_id", "")),
                        cell(owner(item)),
                        cell(deliverable),
                        cell(dependencies or ["无"]),
                    )
                )
                + " |"
            )
        return "\n".join(rendered)

    header = f"# {title}\n\nTask ID: `{task_id}`\n"
    action = contract.get("next_action", {}).get("kind", "not_initialized")
    status_block = (
        "\n## 当前状态\n\n"
        f"- status: `{contract.get('status', 'draft')}`\n"
        f"- current_phase: `{contract.get('current_phase', 'planning')}`\n"
        f"- next_action: `{action}`\n"
    )
    task_md = (
        header
        + f"\n## 要做什么\n\n{points['do']}\n"
        + f"\n## 不做什么\n\n{bullets(points['do_not'])}\n"
        + f"\n## 改哪些地方\n\n{bullets(points['change_areas'])}\n"
        + f"\n## 怎么实现落地\n\n{points['implementation']}\n"
        + f"\n## 怎么验收\n\n{bullets(points['acceptance'])}\n"
        + f"\n## 有什么风险\n\n{bullets(points['risks'])}\n"
        + status_block
    )
    rows = _requirements(contract)
    plan = (
        header
        + "\n## 施工摘要\n\n"
        + f"{points['do']}\n\n{points['implementation']}\n\n"
        + "| 项目 | 内容 |\n| --- | --- |\n"
        + f"| 改造范围 | {cell(points['change_areas'])} |\n"
        + f"| 不做 | {cell(points['do_not'])} |\n"
        + f"| 验收 | {cell(points['acceptance'])} |\n"
        + f"| 主要风险 | {cell(points['risks'])} |\n"
        + "\n## 改造要点\n\n"
        + requirement_table(rows)
        + "\n\n## 施工流程\n\n"
        + (task_graph(contract.get('subtasks', []))
           + '\n\n箭头表示必须先完成；分支全部完成后才能汇合。无相互依赖且写入不冲突可并行，同一代理的任务排队执行。返工路径见已加载 GTO 包 references/workflow.md。\n'
           if any(t.get('planned_agent_key') for t in contract.get('subtasks', [])) else
        "```mermaid\n"
        + "flowchart LR\n"
        + "    P[\"确定方案\"] --> C[\"建立控制面\"]\n"
        + "    C --> T[\"文档与测试\"]\n"
        + "    T --> I[\"实施与整合\"]\n"
        + "    I --> R{\"独立 Review\"}\n"
        + "    R -->|通过| A{\"分层验收\"}\n"
        + "    R -->|问题| F[\"定位与 TDD 修复\"]\n"
        + "    F --> R\n"
        + "    A -->|通过| D[\"事实同步并关闭\"]\n"
        + "    A -->|普通问题| F\n"
        + "    A -->|黑盒效果失败| H[\"报告用户\"]\n"
        + "```\n")
        + "\n## 任务表\n\n"
        + task_table(contract.get("subtasks", []))
        + "\n"
    )
    execution = (
        header
        + f"\n## 施工目标\n\n{points['do']}\n"
        + "\n## 前置条件\n\n- 用户已确认施工摘要、完整要求、流程和任务表。\n- 写入前已冻结范围、验收和风险。\n"
        + f"\n## 执行顺序\n\n{points['implementation']}\n"
        + "\n## 文档先行清单\n\n- 先同步长期真源和任务施工文档。\n"
        + "\n## 测试同步清单\n\n- 先建立最小 Red，再实施 Green 和相关回归。\n"
        + f"\n## 实施批次\n\n{bullets(points['change_areas'])}\n"
        + f"\n## 每批写入范围\n\n{bullets(points['change_areas'])}\n"
        + f"\n## 验证命令\n\n{bullets(points['acceptance'])}\n"
        + f"\n## 回退方案\n\n{bullets(points['risks'])}\n"
        + "\n## 审查与返工路径\n\n遵循已加载 GTO 包的 references/workflow.md 唯一流程真源。\n"
    )
    conclusion = _completion_conclusion(contract)
    if contract.get('approval', {}).get('planned_subtask_ids') is not None:
        execution += '\n## 任务分工与依赖\n\n' + task_table(contract.get('subtasks', [])) + '\n'
        execution += '\n相同代理代号表示复用同一真实身份；不同代号使用不同身份。前置全部完成才可开始；无依赖且写入不冲突的任务可并行，资源不足可排队。\n'
    acceptance = (
        header
        + f"\n## 验收目标\n\n{points['do']}\n"
        + f"\n## 验收标准\n\n{bullets(points['acceptance'])}\n"
        + "\n## 必备证据\n\n- 最小复现、命中证明、相关回归和独立审查证据齐全。\n"
        + "\n## 未决项\n\n- 按当前任务状态持续更新，未完成项不得提前宣称通过。\n"
        + "\n## 最终结论\n\n"
        + conclusion
        + "\n"
    )
    if rows:
        references = [row.split("｜", 1)[0] for row in rows]
        task_md += f"\n## 要求导航\n\n见 docs/tasks/{task_id}/plan.md 的完整要求清单。\n"
        execution += "\n## 要求分工\n\n" + bullets([row.split("｜")[0] + "｜" + "｜".join(row.split("｜")[2:]) for row in rows]) + "\n"
        acceptance += "\n## 要求验证索引\n\n" + bullets(references) + "\n"
    return {"task.md": task_md, "plan.md": plan, "execution.md": execution, "acceptance.md": acceptance}


def _artifact_errors(paths: dict[str, Path], state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for _, name in ARTIFACTS:
        if not paths[name].is_file():
            errors.append(f"{name} is missing")
    hashes = state.get("artifact_sha256", {})
    for name in ("task.md", "plan.md", "execution.md", "acceptance.md"):
        path = paths[name]
        if path.is_file() and _sha(path.read_bytes()) != hashes.get(name):
            errors.append(f"{name} does not match the approved contract")
    errors.extend(_artifact_projection_errors(paths, state))
    events = paths["events.jsonl"]
    if events.is_file():
        for number, line in enumerate(events.read_text(encoding="utf-8").splitlines(), 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"events.jsonl line {number} is invalid JSON")
                continue
            if event.get("task_id") != state.get("task_id"):
                errors.append(f"events.jsonl line {number} has a different task_id")
    return errors


def _artifact_projection_errors(paths: dict[str, Path], state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    action = state.get("next_action", {}).get("kind", "not_initialized")
    task_text = paths["task.md"].read_text(encoding="utf-8") if paths["task.md"].is_file() else ""
    for projection in (
        f"- status: `{state.get('status')}`",
        f"- current_phase: `{state.get('current_phase')}`",
        f"- next_action: `{action}`",
    ):
        if projection not in task_text:
            errors.append(f"task.md current projection is stale: {projection}")
    conclusion = _completion_conclusion(state)
    acceptance_text = paths["acceptance.md"].read_text(encoding="utf-8") if paths["acceptance.md"].is_file() else ""
    if conclusion not in acceptance_text:
        errors.append("acceptance.md current conclusion is stale; preserve the controller-managed exact marker: " + conclusion)
    return errors


def _resolve_schema_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ControlError(f"schema uses unsupported external ref: {ref}")
    current: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise ControlError(f"schema ref cannot be resolved: {ref}")
        current = current[token]
    if not isinstance(current, dict):
        raise ControlError(f"schema ref does not resolve to an object: {ref}")
    return current


def _schema_allowlist_errors(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str = "$",
    seen: set[tuple[int, int]] | None = None,
) -> list[str]:
    """Enforce every additionalProperties allowlist from the canonical schema.

    Structural and cross-object rules remain in `_validate_state`; property
    ownership is never duplicated there and is read directly from the schema.
    """

    if seen is None:
        seen = set()
    marker = (id(value), id(schema))
    if marker in seen:
        return []
    seen.add(marker)
    errors: list[str] = []
    if "$ref" in schema:
        errors.extend(_schema_allowlist_errors(value, _resolve_schema_ref(root, schema["$ref"]), root, path, seen))
    for branch in schema.get("allOf", []):
        if isinstance(branch, dict):
            errors.extend(_schema_allowlist_errors(value, branch, root, path, seen))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        if isinstance(properties, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                child_schema = properties.get(key)
                if isinstance(child_schema, dict):
                    errors.extend(_schema_allowlist_errors(child, child_schema, root, child_path, seen))
                elif additional is False:
                    errors.append(f"schema allowlist rejects unknown field {child_path}")
                elif isinstance(additional, dict):
                    errors.extend(_schema_allowlist_errors(child, additional, root, child_path, seen))
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, child in enumerate(value):
                errors.extend(_schema_allowlist_errors(child, item_schema, root, f"{path}[{index}]", seen))
    return errors


@lru_cache(maxsize=4)
def _schema_document(raw: bytes) -> dict[str, Any]:
    try:
        schema = json.loads(raw)
        if not isinstance(schema, dict):
            raise ValueError('root must be an object')
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ControlError(f'canonical state schema is invalid: {exc}') from exc
    return schema


@lru_cache(maxsize=16)
def _schema_validator(raw: bytes, definition: str | None):
    schema = _schema_document(raw)
    selected = {"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]} if definition else schema
    return Draft202012Validator(selected, format_checker=FORMAT_CHECKER)


def _canonical_schema_errors(state: dict[str, Any], *, definition: str | None = None) -> list[str]:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "orchestrator-task-state.schema.json"
    try:
        raw = schema_path.read_bytes()
    except OSError as exc:
        raise ControlError(f"canonical state schema is unavailable: {exc}") from exc
    # Key by current schema bytes: cache compiled metadata, never task/evidence facts.
    validator = _schema_validator(raw, definition)
    errors = sorted(
        validator.iter_errors(state),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return [
        f"schema {'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in errors
    ]


def _validate_state(paths: dict[str, Path], state: dict[str, Any]) -> list[str]:
    errors = _state_model_errors(paths["state.json"].parents[4], state, include_legacy_dependency_errors=True)
    # Historical receipts remain valid records. Public validation/preflight must
    # additionally reject a frozen candidate that no longer describes live inputs.
    # Repair mutations use _state_model_errors and can still create a new candidate.
    if state.get("workflow_revision") == 3 and state.get("status") != "completed":
        errors.extend(_candidate_staleness_errors(paths["state.json"].parents[4], state))
    errors.extend(_current_run_errors(paths["state.json"].parents[4], state, integrity_only=True))
    errors.extend(_artifact_errors(paths, state))
    return errors


def _state_model_errors(
    repo: Path,
    state: dict[str, Any],
    *,
    include_legacy_dependency_errors: bool = False,
    include_candidate_staleness: bool = True,
) -> list[str]:
    errors = _canonical_schema_errors(state)
    errors.extend(_validate_contract(state))
    errors.extend(_semantic_errors(state))
    errors.extend(_subtask_state_errors(state, include_legacy_dependency_errors=include_legacy_dependency_errors))
    if state.get("workflow_revision") == 3:
        inputs = state.get("acceptance_gate", {}).get("candidate_inputs", {})
        writer_targets = []
        for task in state.get('subtasks', []):
            if task.get('subtask_id') not in state.get('initial_test_owners', []):
                continue
            targets = []
            for raw in task.get('write_paths', []):
                relative = _safe_relative_path(raw)
                if relative is None:
                    continue
                try:
                    targets.append((repo / relative).resolve().relative_to(repo.resolve()).as_posix())
                except (ValueError, OSError, RuntimeError):
                    errors.append('initial tester write target is outside repository or unresolved: ' + raw)
            if any(_paths_overlap(a, b) for previous in writer_targets for a in previous for b in targets):
                errors.append('initial tester writer scopes overlap through physical path aliases')
            writer_targets.append(targets)
        declared = [p for field in ("code_paths", "config_paths", "runtime_input_paths", "document_paths") for p in inputs.get(field, [])]
        for task in state.get("subtasks", []):
            for relative in task.get("write_paths", []):
                path = repo / relative
                in_candidate = any(relative == scope or relative.startswith(scope.rstrip("/") + "/") for scope in declared)
                if _is_log_file_scope(relative) and not in_candidate and (path.is_dir() or path.is_symlink()):
                    errors.append("evidence log write scope must be a regular file, not a directory or symlink: " + relative)
        for index, receipt in enumerate(state.get("verification_evidence_receipts", []), 1):
            errors.extend(
                f"verification evidence receipt {index}: {error}"
                for error in _verification_receipt_errors(
                    repo, state, receipt, require_current_candidate=False
                )
            )
        errors.extend(_batch_errors(repo, state, _candidate_records, metadata_only=True))
        errors.extend(_coverage_errors(repo, state, _candidate_records, metadata_only=True))
    if include_candidate_staleness and (state.get("workflow_revision") != 3 or state.get("status") == "completed"):
        errors.extend(_candidate_staleness_errors(repo, state))
    return errors


def _subtask_state_errors(
    state: dict[str, Any], *, include_legacy_dependency_errors: bool = False
) -> list[str]:
    errors: list[str] = []
    ids = {item.get("subtask_id") for item in state.get("subtasks", []) if isinstance(item, dict)}
    statuses: dict[str, Any] = {
        item.get("subtask_id"): item.get("status")
        for item in state.get("subtasks", [])
        if isinstance(item, dict)
    }
    for item in state.get("subtasks", []):
        if not isinstance(item, dict):
            continue
        subtask_id = item.get("subtask_id", "<unknown>")
        dependencies = item.get("dependencies", [])
        if any(dep not in ids for dep in dependencies):
            errors.append(f"subtask {subtask_id} has an unknown dependency")
        if subtask_id in dependencies:
            errors.append(f"subtask {subtask_id} depends on itself")
        if (
            item.get("status") == "completed"
            and (state.get("workflow_revision") == 3 or include_legacy_dependency_errors)
            and any(statuses.get(dep) != "completed"
                    and not (state.get("workflow_revision") == 3 and item.get("stage") == "final_documentation"
                             and next((t for t in state["subtasks"] if t.get("subtask_id") == dep), {}).get("stage") == "expensive_acceptance")
                    for dep in dependencies)
        ):
            errors.append(f"subtask {subtask_id} completed before its dependencies")
        dispatch = item.get("dispatch")
        if dispatch is not None:
            if item.get("status") not in {"in_progress", "completed", "blocked"}:
                errors.append(f"subtask {subtask_id} dispatch contradicts status")
            if dispatch.get("context_mode") != "isolated" or not re.fullmatch(r"[0-9a-f]{64}", str(dispatch.get("brief_sha256", ""))):
                errors.append(f"subtask {subtask_id} dispatch binding is invalid")
        if item.get("status") in {"completed", "blocked"} and not isinstance(item.get("result"), dict):
            errors.append(f"subtask {subtask_id} {item.get('status')} requires result")
        if "result" in item and item.get("status") not in {"completed", "blocked"}:
            errors.append(f"subtask {subtask_id} result contradicts status")
        result = item.get("result")
        if isinstance(result, dict) and result.get("status") != item.get("status"):
            errors.append(f"subtask {subtask_id} result status must equal subtask status")
        if state.get("workflow_revision") == 3 and item.get("stage") in {"work", "integration"} and item.get("status") == "completed":
            errors.extend(_checks_errors(result.get("checks") if isinstance(result, dict) else None, _required_checks(state, item)))
            if item.get("stage") == "integration":
                errors.extend(_required_work_errors(state))
        if state.get('workflow_revision') == 3 and item.get('stage') == 'expensive_acceptance' and dispatch:
            errors.extend(_acceptor_errors(state, dispatch.get('platform_agent_id')))
    errors.extend(_execution_plan_errors(state))
    if state.get("approval", {}).get("contract_sha256") != _contract_hash(state):
        errors.append("approval is stale because the six-point contract changed")
    return errors


def _semantic_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    phases = {"planning", "doc_sync", "test_sync", "code_impl", "review", "blocked"}
    if state.get("current_phase") not in phases:
        errors.append("current_phase is not a valid v3 phase")
    if state.get("status") not in {"active", "blocked", "completed"}:
        errors.append("status is not valid for v3")
    blocker = state.get("coordinator_blocker")
    if blocker is not None and (
        state.get("workflow_revision") != 3 or state.get("status") != "blocked"
        or state.get("current_phase") != "blocked" or state.get("next_action", {}).get("kind") != "human_adjudication"
    ):
        errors.append("coordinator_blocker requires revision 3 blocked status/phase and human_adjudication")
    if state.get("version") != 3:
        errors.append("state.json version must be 3")
    for field in ("six_points", "approval", "artifact_sha256", "workspace", "review_policy", "findings", "next_action"):
        if field not in state:
            errors.append(f"v3 state requires {field}")
    phase = state.get("current_phase")
    verification = state.get("verification_contract")
    if phase in {"code_impl", "review"} and not isinstance(verification, dict):
        errors.append("verification_contract is required before code_impl/review")
    workspace = state.get("workspace")
    if not isinstance(workspace, dict):
        errors.append("workspace must be an object")
    elif phase in {"code_impl", "review"}:
        decision = workspace.get("overlap_decision", {}).get("status")
        if decision not in {"not_required", "resolved"}:
            errors.append("workspace overlap must be resolved before code_impl/review")
    if phase == "review" and isinstance(verification, dict):
        required = set(verification.get("review_evidence", []))
        observed = _observed_pre_final_evidence(None, state, required)
        missing = sorted(required - observed)
        if missing:
            errors.append("verification evidence is missing before review: " + ", ".join(missing))
    if state.get("workflow_revision") == 3:
        errors.extend(_workflow_errors(state))
    return errors


def _workflow_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = _requirement_errors(state)
    gate = state.get("acceptance_gate")
    if not isinstance(gate, dict):
        return ["workflow_revision=3 requires one acceptance_gate"]
    blackbox_ids = gate.get("blackbox_acceptance_ids", [])
    acceptance_ids = {item.get("acceptance_id") for item in gate.get("acceptance_items", [])}
    try:
        point_acceptance.definitions(gate)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    if len(blackbox_ids) != len(set(blackbox_ids)) or not set(blackbox_ids).issubset(acceptance_ids):
        errors.append("blackbox_acceptance_ids must be a unique subset of acceptance_items")
    subtasks = [item for item in state.get("subtasks", []) if isinstance(item, dict)]
    by_id = {item.get("subtask_id"): item for item in subtasks}
    if state.get("workflow_revision") == 3:
        ranks = {"work": 0, "integration": 1, "pre_acceptance_review": 2, "expensive_acceptance": 3, "final_documentation": 4}
        owners = state.get("initial_test_owners", [])
        if not owners or len(set(owners)) != len(owners) or any(
                by_id.get(ident, {}).get("stage") != "work" or by_id.get(ident, {}).get("role") != "tester"
                for ident in owners):
            errors.append("initial_test_owners must identify independent work/tester subtasks")
        testers = [by_id[ident] for ident in owners if ident in by_id]
        for index, tester in enumerate(testers):
            for other in testers[index + 1:]:
                if any(_paths_overlap(a, b) for a in tester.get("write_paths", []) for b in other.get("write_paths", [])):
                    errors.append("initial test writer scopes overlap; shared fixtures require one writer")
        for task in subtasks:
            if task.get("stage") == "work" and _is_product_task(task) and not set(owners).issubset(_dependency_ids(task, by_id)):
                errors.append("implementation dependencies must include every initial test owner")
        if len([t for t in subtasks if t.get("stage") == "final_documentation"]) != 1:
            errors.append("final_documentation requires exactly one document subtask")
        inputs = gate.get("candidate_inputs", {})
        declared = [p for field in ("code_paths", "config_paths", "runtime_input_paths", "document_paths") for p in inputs.get(field, [])]
        for task in subtasks:
            if task.get("stage") != "final_documentation":
                for path in task.get("write_paths", []):
                    log_file = _is_log_file_scope(path)
                    if path not in _workspace_control_paths(state) and not log_file and not any((path == scope or path.startswith(scope.rstrip("/") + "/")) for scope in declared):
                        errors.append("subtask write_paths must be covered by candidate_inputs, including discoverer tests: " + path)
    if any(item.get("stage") not in ranks for item in subtasks):
        errors.append("workflow_revision=3 requires stage on every subtask")
    missing_stages = sorted(set(ranks) - {item.get("stage") for item in subtasks})
    if missing_stages:
        errors.append("workflow_revision=3 requires every stage: " + ", ".join(missing_stages))
    for item in subtasks:
        stage = item.get("stage")
        dependencies = [by_id.get(value) for value in item.get("dependencies", [])]
        retry = state.get('workflow_revision') == 3 and stage == 'expensive_acceptance' and item.get('acceptance_owner')
        if stage in ranks and ranks[stage] > 0 and not retry and not (state.get("workflow_revision") == 3 and stage == "integration" and any(dep and dep.get("stage") == "integration" for dep in dependencies)) and not any(
            dependency and ranks.get(dependency.get("stage")) == ranks[stage] - 1
            for dependency in dependencies
        ):
            errors.append(f"{stage} requires a direct dependency on the preceding stage")
        for dependency_id in item.get("dependencies", []):
            dependency = by_id.get(dependency_id)
            if dependency and stage in ranks and dependency.get("stage") in ranks:
                if ranks[dependency["stage"]] > ranks[stage]:
                    errors.append("pre_acceptance stage order is reversed")
    for item in subtasks:
        if item.get("stage") != "expensive_acceptance":
            continue
        dependencies = [by_id.get(value) for value in item.get("dependencies", [])]
        if not item.get('acceptance_owner') and not any(dep and dep.get("stage") == "pre_acceptance_review" for dep in dependencies):
            errors.append("expensive_acceptance requires a direct pre_acceptance_review dependency")
    attempts = gate.get("attempts", [])
    policy = gate.get("attempt_policy", {})
    extensions = gate.get("budget_extensions", [])
    expected_maximum = 4
    if isinstance(extensions, list):
        required = {
            "written_by", "written_role", "approved_by", "reason", "approval_evidence_refs",
            "previous_max_expensive_attempts", "max_expensive_attempts",
        }
        for number, extension in enumerate(extensions, 1):
            if not isinstance(extension, dict):
                errors.append(f"acceptance budget extension {number} must be an object")
                continue
            if set(extension) != required:
                errors.append(f"acceptance budget extension {number} fields are invalid")
            if extension.get("written_role") != "coordinator":
                errors.append(f"acceptance budget extension {number} requires coordinator authorship")
            if extension.get("approved_by") != "user":
                errors.append(f"acceptance budget extension {number} requires explicit user approval")
            if not isinstance(extension.get("written_by"), str) or not extension["written_by"].strip():
                errors.append(f"acceptance budget extension {number} requires written_by")
            if not isinstance(extension.get("reason"), str) or not extension["reason"].strip():
                errors.append(f"acceptance budget extension {number} requires a reason")
            evidence = extension.get("approval_evidence_refs")
            if not isinstance(evidence, list) or not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence):
                errors.append(f"acceptance budget extension {number} requires approval evidence")
            previous = extension.get("previous_max_expensive_attempts")
            maximum = extension.get("max_expensive_attempts")
            if type(previous) is not int or previous != expected_maximum:
                errors.append(f"acceptance budget extension {number} previous maximum does not match")
            if type(maximum) is not int or maximum <= expected_maximum:
                errors.append(f"acceptance budget extension {number} must strictly increase the maximum")
            else:
                expected_maximum = maximum
    maximum = policy.get("max_expensive_attempts") if isinstance(policy, dict) else None
    if maximum != expected_maximum:
        errors.append("max_expensive_attempts requires an append-only user authorization chain")
    if isinstance(attempts, list):
        attempt_ids = [item.get("attempt_id") for item in attempts if isinstance(item, dict)]
        subtask_ids = [item.get("subtask_id") for item in attempts if isinstance(item, dict)]
        if len(attempt_ids) != len(set(attempt_ids)) or len(subtask_ids) != len(set(subtask_ids)):
            errors.append("expensive attempt identity must be unique")
        if isinstance(maximum, int) and sum(not a.get('withdrawal') for a in attempts) > maximum:
            errors.append("max_expensive_attempts exceeded")
        candidates = {item.get("candidate_id") for item in attempts if isinstance(item, dict)}
        approval_from = policy.get("approval_required_from_attempt", 3) if isinstance(policy, dict) else 3
        for number, attempt in enumerate(attempts, 1):
            if attempt.get('withdrawal'):
                source = by_id.get(attempt.get('subtask_id'), {})
                if source.get('status') != 'cancelled' or source.get('dispatch') or source.get('result') or 'outcome' in attempt:
                    errors.append('withdrawn acceptance must have no dispatch, outcome or result')
                continue
            number = sum(not a.get('withdrawal') for a in attempts[:number])
            if number >= approval_from:
                approval = attempt.get("approval") if isinstance(attempt, dict) else None
                if not isinstance(approval, dict) or not approval.get("approved_by") or not approval.get("reason"):
                    errors.append(f"expensive attempt {number} requires approval")
            if not isinstance(attempt, dict):
                continue
            subtask = by_id.get(attempt.get("subtask_id"))
            if not subtask or subtask.get("stage") != "expensive_acceptance":
                errors.append(f"expensive attempt {number} must reference an expensive_acceptance subtask")
                continue
            if "outcome" not in attempt:
                current = gate.get("current_candidate")
                if (
                    subtask.get("status") not in {"ready", "in_progress"}
                    or not isinstance(current, dict)
                    or attempt.get("candidate_id") != current.get("candidate_id")
                ):
                    errors.append(f"pending expensive attempt {number} candidate or subtask is inconsistent")
                continue
            result = subtask.get("result")
            evidence = result.get("expensive_acceptance") if isinstance(result, dict) else None
            evidence_fields = {
                "outcome", "real_call_count", "duration_seconds", "failed_stage",
                "evidence_refs", "evidence_by_acceptance_id", "finding_id",
            }
            if state.get('workflow_revision') == 3:
                evidence_fields.update({'mode', 'scope_acceptance_ids', 'passed_acceptance_ids', 'closed_finding_ids',
                    'usage_evidence', 'impact', 'retained_evidence_by_acceptance_id',
                    'preparation', 'blackbox', 'invalid_observation', 'executed_unit_ids',
                    'evidence_batch_ids', 'point_results', 'run_evidence', 'source_preparation_attempt_id'})
            if (
                subtask.get("status") not in {"completed", "blocked"}
                or not isinstance(evidence, dict)
                or any(attempt.get(key) != evidence.get(key) for key in evidence_fields if key in attempt or key in evidence)
            ):
                errors.append(f"completed expensive attempt {number} lacks matching subtask result evidence")
        for candidate_id in candidates:
            full = [
                item for item in attempts
                if isinstance(item, dict)
                and item.get("candidate_id") == candidate_id
                and item.get("kind", "ordinary") == "ordinary"
                and item.get("outcome") in {"pass", "product_failure"}
                and not item.get('point_results')
            ]
            if len(full) > 1:
                errors.append(f"full expensive acceptance repeated for candidate {candidate_id}")
            retry_limit = policy.get("max_environment_retries_per_candidate", 1) if isinstance(policy, dict) else 1
            failures_by_scope = {}
            for item in attempts:
                if item.get('candidate_id') != candidate_id or item.get('withdrawal'):
                    continue
                scopes = ['preparation'] if item.get('kind') == 'preparation' else item.get('scope_acceptance_ids', [])
                approval = item.get('approval', {})
                for scope in scopes:
                    failures = failures_by_scope.get(scope, 0)
                    if (failures >= 1 + retry_limit and not (
                            approval.get('approved_by') == 'user'
                            and isinstance(approval.get('reason'), str) and approval['reason'].strip())):
                        errors.append(f"environment retry requires user authorization for candidate {candidate_id} scope {scope}")
                    if item.get('outcome') == 'environment_failure':
                        failures_by_scope[scope] = failures + 1
    return errors


def _evidence_file_error(repo: Path, raw: Any) -> str | None:
    relative = _safe_relative_path(raw)
    if relative is None:
        return "evidence path must be a safe repository-relative path"
    if relative.startswith(".tmp/"):
        return "acceptance evidence must be retained outside .tmp"
    path = repo / relative
    if any(p.is_symlink() for p in (path, *path.parents) if p != repo.parent):
        return "evidence path must not contain symlinks"
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(repo.resolve())
    except FileNotFoundError:
        return f"evidence file does not exist: {relative}"
    except (OSError, RuntimeError, ValueError):
        return f"evidence path is outside repository or invalid: {relative}"
    if not resolved.is_file():
        return f"evidence path is not a file: {relative}"
    return None


def _acceptance_source(state: dict[str, Any], subtask_id: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    source = next(
        (item for item in state.get("subtasks", []) if item.get("subtask_id") == subtask_id),
        {},
    )
    attempt = next(
        (
            item
            for item in state.get("acceptance_gate", {}).get("attempts", [])
            if isinstance(item, dict) and item.get("subtask_id") == subtask_id
        ),
        {},
    )
    return source, attempt


def _verification_evidence_owner(
    state: dict[str, Any], evidence_key: Any
) -> tuple[str, str] | None:
    attempt_subtasks = {
        attempt.get("subtask_id")
        for attempt in state.get("acceptance_gate", {}).get("attempts", [])
        if isinstance(attempt, dict)
    }
    for template in state.get("subtasks", []):
        if (
            not isinstance(template, dict)
            or template.get("stage") != "expensive_acceptance"
            or template.get("subtask_id") in attempt_subtasks
        ):
            continue
        required = template.get("assignment", {}).get(
            "required_verification_evidence", {}
        )
        if not isinstance(required, dict):
            continue
        for kind, keys in required.items():
            if isinstance(keys, list) and evidence_key in keys:
                return template["subtask_id"], kind
    return None


def _attempt_template_id(state: dict[str, Any], attempt: dict[str, Any]) -> str | None:
    return attempt.get('template_subtask_id')


def _verification_evidence_owner_errors(
    state: dict[str, Any], source_subtask_id: Any, evidence_key: Any
) -> list[str]:
    owner = _verification_evidence_owner(state, evidence_key)
    if owner is None:
        return []
    _, attempt = _acceptance_source(state, source_subtask_id)
    actual = (_attempt_template_id(state, attempt), attempt.get("kind", "ordinary"))
    if actual != owner:
        return [
            "verification evidence key belongs to another acceptance template or attempt kind: "
            + str(evidence_key)
        ]
    return []


def _registered_acceptance_refs(source: dict[str, Any]) -> set[str]:
    evidence = source.get("result", {}).get("expensive_acceptance", {})
    registered = {
        item for item in evidence.get("evidence_refs", []) if isinstance(item, str)
    }
    mapping = evidence.get("evidence_by_acceptance_id", {})
    if isinstance(mapping, dict):
        registered.update(
            item
            for values in mapping.values()
            if isinstance(values, list)
            for item in values
            if isinstance(item, str)
        )
    return registered


def _verification_receipt_errors(
    repo: Path,
    state: dict[str, Any],
    receipt: Any,
    *,
    require_current_candidate: bool = True,
) -> list[str]:
    if not isinstance(receipt, dict):
        return ["verification evidence receipt must be an object"]
    source, attempt = _acceptance_source(state, receipt.get("source_subtask_id"))
    errors: list[str] = []
    dispatch = source.get("dispatch", {})
    result = source.get("result", {})
    evidence = result.get("expensive_acceptance", {})
    if (
        source.get("stage") != "expensive_acceptance"
        or source.get("status") != "completed"
        or result.get("status") != "completed"
        or evidence.get("outcome") != "pass"
        or attempt.get("kind", "ordinary") == "preparation"
    ):
        errors.append("verification evidence source must be a completed non-preparation passing acceptance")
    if (
        receipt.get("written_by") != dispatch.get("platform_agent_id")
        or receipt.get("written_role") != dispatch.get("agent_key")
        or receipt.get("written_by") != result.get("written_by")
        or receipt.get("written_role") != result.get("written_role")
    ):
        errors.append("verification evidence identity must match the dispatch and source result writer")
    if receipt.get("source_result_sha256") != _sha(result):
        errors.append("verification evidence source result hash does not match")
    expected_fingerprint = _sha(
        {
            "records": attempt.get("coverage_snapshot"),
            "inputs": attempt.get("coverage_inputs_sha256"),
            "runtime_sha256": attempt.get("runtime_sha256"),
        }
    )
    if (
        attempt.get("candidate_id") != receipt.get("candidate_id")
        or receipt.get("candidate_fingerprint") != expected_fingerprint
    ):
        errors.append("verification evidence candidate does not match its acceptance attempt")
    if require_current_candidate:
        current = state.get("acceptance_gate", {}).get("current_candidate", {})
        if (
            receipt.get("candidate_id") != current.get("candidate_id")
            or receipt.get("candidate_fingerprint") != current.get("fingerprint")
        ):
            errors.append("verification evidence candidate does not match the current approved candidate")
        errors.extend(
            "verification evidence candidate is stale: " + error
            for error in _current_candidate_errors(repo, state)
        )
    allowed_keys = set(state.get("verification_contract", {}).get("review_evidence", []))
    if receipt.get("evidence_key") not in allowed_keys:
        errors.append("verification evidence key is not declared by the contract")
    errors.extend(
        _verification_evidence_owner_errors(
            state, receipt.get("source_subtask_id"), receipt.get("evidence_key")
        )
    )
    refs = receipt.get("evidence_refs")
    registered = _registered_acceptance_refs(source)
    if isinstance(refs, list):
        for raw in refs:
            if raw not in registered:
                errors.append(f"verification evidence reference is not registered by the source result: {raw}")
            path_error = _evidence_file_error(repo, raw)
            if path_error:
                errors.append(path_error)
    return errors


def _acceptance_review_evidence_errors(
    repo: Path,
    state: dict[str, Any],
    subtask: dict[str, Any],
    result: dict[str, Any],
) -> list[str]:
    _, attempt = _acceptance_source(state, subtask.get("subtask_id"))
    kind = attempt.get("kind", "ordinary")
    if kind == "preparation":
        return []
    required = subtask.get("assignment", {}).get("required_verification_evidence", {})
    keys = required.get(kind, []) if isinstance(required, dict) else []
    observed = result.get("review_evidence", {})
    registered = _registered_acceptance_refs({"result": result})
    errors: list[str] = []
    allowed = set(state.get("verification_contract", {}).get("review_evidence", []))
    if isinstance(observed, dict):
        for key, raw in observed.items():
            if key not in allowed:
                errors.append(f"acceptance review evidence key is not declared by the contract: {key}")
                continue
            if not isinstance(raw, str) or raw not in registered:
                errors.append(f"acceptance review evidence is not a registered file reference: {key}")
                continue
            path_error = _evidence_file_error(repo, raw)
            if path_error:
                errors.append(f"acceptance review evidence {key}: {path_error}")
            errors.extend(
                _verification_evidence_owner_errors(
                    state, subtask.get("subtask_id"), key
                )
            )
    for key in keys:
        raw = observed.get(key) if isinstance(observed, dict) else None
        if not isinstance(raw, str) or not raw.strip():
            errors.append(f"required verification evidence is missing for {kind}: {key}")
            continue
        if raw not in registered:
            errors.append(f"required verification evidence is not registered by this acceptance: {key}")
            continue
        path_error = _evidence_file_error(repo, raw)
        if path_error:
            errors.append(f"required verification evidence {key}: {path_error}")
    return errors


def _observed_pre_final_evidence(repo: Path | None, state: dict[str, Any], required: set[str]) -> set[str]:
    observed: set[str] = set()
    valid_points = (point_acceptance.coverage(repo, state, _candidate_records(repo, state))['points']
                    if repo is not None and state.get('acceptance_gate') else None)
    for subtask in state.get("subtasks", []):
        if not isinstance(subtask, dict) or subtask.get("status") not in {"completed", "blocked"} or subtask.get("role") == "reviewer":
            continue
        evidence = subtask.get("result", {}).get("review_evidence", {})
        if isinstance(evidence, dict):
            if subtask.get("stage") == "expensive_acceptance":
                _, attempt = _acceptance_source(state, subtask.get("subtask_id"))
                current = state.get("acceptance_gate", {}).get("current_candidate", {})
                terminal = subtask.get("result", {}).get("expensive_acceptance", {})
                if attempt.get('point_results'):
                    refs = {ref for row in attempt['point_results'] if row['status'] == 'pass'
                            and (valid_points is None or (valid_points[row['acceptance_id']]['status'] == 'pass'
                                and valid_points[row['acceptance_id']].get('source_attempt_id') == attempt['attempt_id']))
                            for ref in row['evidence_refs']}
                    observed.update(key for key, value in evidence.items() if key in required and value in refs
                                    and not _verification_evidence_owner_errors(state, subtask['subtask_id'], key))
                    continue
                if (
                    attempt.get("kind", "ordinary") == "preparation"
                    or attempt.get("candidate_id") != current.get("candidate_id")
                    or terminal.get("outcome") != "pass"
                ):
                    continue
                registered = _registered_acceptance_refs(subtask)
                observed.update(
                    key
                    for key, value in evidence.items()
                    if key in required
                    and not _verification_evidence_owner_errors(
                        state, subtask.get("subtask_id"), key
                    )
                    and isinstance(value, str)
                    and value in registered
                    and (repo is None or _evidence_file_error(repo, value) is None)
                )
            elif subtask.get('status') == 'completed':
                observed.update(key for key, value in evidence.items() if key in required and value)
    for receipt in state.get("verification_evidence_receipts", []):
        if repo is not None and not _verification_receipt_errors(repo, state, receipt):
            observed.add(receipt["evidence_key"])
    if repo is not None:
        for source_id, key, value in _batch_coverage_evidence_sources(
            repo, state, required, _candidate_records
        ):
            source, _ = _acceptance_source(state, source_id)
            if (
                not _verification_evidence_owner_errors(state, source_id, key)
                and value in _registered_acceptance_refs(source)
                and _evidence_file_error(repo, value) is None
            ):
                observed.add(key)
    return observed


def _required_verification_evidence_errors(repo: Path, state: dict[str, Any]) -> list[str]:
    verification = state.get("verification_contract", {})
    required = set(verification.get("review_evidence", []))
    missing = sorted(required - _observed_pre_final_evidence(repo, state, required))
    return ["verification evidence is missing: " + ", ".join(missing)] if missing else []


def _find_subtask(state: dict[str, Any], subtask_id: str | None) -> dict[str, Any]:
    for subtask in state.get("subtasks", []):
        if subtask.get("subtask_id") == subtask_id:
            return subtask
    raise ControlError(f"unknown subtask_id: {subtask_id}")


def _identity(dispatch: dict[str, Any]) -> dict[str, str]:
    return {"agent_key": dispatch["agent_key"], "platform_agent_id": dispatch["platform_agent_id"]}




def _source_manifest(repo: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    declared: set[str] = set()
    for subtask in state.get("subtasks", []):
        result = subtask.get("result", {})
        if isinstance(result, dict):
            declared.update(result.get("changed_files", []))
    for finding in state.get("findings", {}).values():
        declared.update(finding.get("paths", []))
        fix_delta = finding.get("fix_delta")
        if isinstance(fix_delta, dict):
            changed_files = fix_delta.get("changed_files")
            if isinstance(changed_files, list):
                declared.update(
                    path for path in changed_files if isinstance(path, str) and path.strip()
                )
    if not declared:
        for subtask in state.get("subtasks", []):
            declared.update(subtask.get("write_paths", []))
        declared.update(state.get("scope_in", []))
    task_id = state["task_id"]
    control_artifacts = {
        f"docs/ai/tasks/{task_id}/state.json",
        f"docs/ai/tasks/{task_id}/task.md",
        f"docs/ai/tasks/{task_id}/events.jsonl",
        f"docs/ai/tasks/{task_id}/.control.lock",
        f"docs/tasks/{task_id}/plan.md",
        f"docs/tasks/{task_id}/execution.md",
        f"docs/tasks/{task_id}/acceptance.md",
    }
    write_scopes = {
        relative.rstrip("/")
        for subtask in state.get("subtasks", [])
        if isinstance(subtask, dict) and subtask.get("role") != "reviewer"
        for relative in (_safe_relative_path(raw) for raw in subtask.get("write_paths", []))
        if relative and relative not in control_artifacts
    }
    declared.update(
        dirty
        for dirty in _git_dirty_paths(repo, control_artifacts)
        if any(dirty == scope or dirty.startswith(scope + "/") for scope in write_scopes)
    )
    files: set[Path] = set()
    missing: list[str] = []
    for raw in sorted(declared):
        normalized_raw = Path(raw).as_posix()
        if normalized_raw in control_artifacts:
            continue
        candidate = (repo / raw).resolve()
        try:
            candidate.relative_to(repo)
        except ValueError:
            missing.append(f"unsafe:{raw}")
            continue
        if candidate.is_file():
            files.add(candidate)
        elif candidate.is_dir():
            for path in candidate.rglob("*"):
                if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                    continue
                resolved = path.resolve()
                try:
                    relative = resolved.relative_to(repo).as_posix()
                except ValueError:
                    missing.append(f"unsafe:{path.relative_to(repo).as_posix()}")
                    continue
                if relative in control_artifacts:
                    continue
                files.add(resolved)
        else:
            missing.append(raw)
    manifest = [
        {"path": path.relative_to(repo).as_posix(), "sha256": _sha(path.read_bytes())}
        for path in sorted(files)
    ]
    manifest.extend({"path": raw, "sha256": "missing"} for raw in missing)
    return manifest


def _review_target(repo: Path, state: dict[str, Any]) -> str:
    return _sha(
        {
            "task_id": state.get("task_id"),
            "contract_sha256": state.get("approval", {}).get("contract_sha256"),
            "source_manifest": _source_manifest(repo, state),
        }
    )


def _effect_failures(state: dict[str, Any], scope=None) -> list[dict[str, Any]]:
    gate = state.get('acceptance_gate', {})
    attempts = gate.get('attempts', [])
    _, dependencies = point_acceptance.definitions(gate)
    requested = set().union(*(dependencies[ident] for ident in scope)) if scope is not None else set(dependencies)
    active = []
    for index, failure in enumerate(attempts):
        if failure.get('kind') != 'blackbox' or failure.get('outcome') != 'effect_failure':
            continue
        failed = {r['acceptance_id'] for r in failure.get('point_results', []) if r['status'] == 'fail'}
        failed = failed or set(failure.get('scope_acceptance_ids', gate.get('blackbox_acceptance_ids', [])))
        resolved = set()
        for later in attempts[index + 1:]:
            if (not later.get('authorization_attempt_id') or later.get('source_preparation_attempt_id')
                    or not any('next_round' in decision.get('allow', []) for decision in failure.get('decisions', []))):
                continue
            resolved.update(r['acceptance_id'] for r in later.get('point_results', []) if r['status'] == 'pass')
            if later.get('outcome') == 'pass' and 'point_results' not in later:
                resolved.update(later.get('scope_acceptance_ids', []))
        if (failed - resolved) & requested:
            active.append(failure)
    return active


def _latest_effect_failure(state: dict[str, Any]) -> dict[str, Any] | None:
    failures = _effect_failures(state)
    return failures[-1] if failures else None


def _effect_permission(state: dict[str, Any], permission: str, scope=None) -> bool:
    return all(any(permission in decision.get('allow', []) for decision in failure.get('decisions', []))
               for failure in _effect_failures(state, scope))


def _set_next(state: dict[str, Any], kind: str, target: dict[str, str] | None = None, **extra: Any) -> dict[str, Any]:
    stopped = state.get("coordinator_blocker") or (not _effect_permission(state, 'next_round') and not _effect_permission(state, 'repair'))
    action = {"kind": "human_adjudication"} if stopped else {"kind": kind, **extra}
    if target is not None and not stopped:
        action["target"] = target
    state["next_action"] = action
    return action


def _new_task(args: argparse.Namespace) -> dict[str, Any]:
    slug = args.Slug or ""
    if len(slug) > 80 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ControlError("Slug must be 1..80 characters of lowercase kebab-case")
    local_now = dt.datetime.now().astimezone()
    task_id = f"{local_now.strftime('%Y%m%d-%H%M%S-%f')}-{slug}"
    return {"ok": True, "task_id": task_id, "local_time": local_now.isoformat()}


def _require_contract_in_repo_tmp(repo: Path, raw: str | None) -> None:
    if raw is None:
        raise ControlError("ContractJsonFile is required and must be inside the consumer repository .tmp directory")
    try:
        repo_root = repo.resolve()
        contract_path = Path(raw).resolve()
        relative = contract_path.relative_to(repo_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ControlError(
            "ContractJsonFile must resolve inside the consumer repository .tmp directory"
        ) from exc
    if len(relative.parts) < 2 or relative.parts[0] != ".tmp":
        raise ControlError("ContractJsonFile must be inside the consumer repository .tmp directory")


def _initial_state(args: argparse.Namespace, repo: Path) -> tuple[dict[str, Any], dict[str, str]]:
    contract = _json_file_arg(args.ContractJsonFile, "ContractJsonFile")
    if isinstance(contract, dict) and isinstance(contract.get("six_points"), dict):
        points = contract["six_points"]
        for field, point in {"objective": "do", "scope_in": "change_areas", "scope_out": "do_not",
                             "acceptance": "acceptance", "stop_conditions": "risks"}.items():
            if field not in contract and point in points:
                contract[field] = copy.deepcopy(points[point])
        if isinstance(contract.get("decisions"), list) and points.get("implementation") not in contract["decisions"]:
            contract["decisions"].insert(0, points.get("implementation"))
    errors = _validate_contract(contract)
    if isinstance(contract, dict):
        errors.extend(_requirement_errors(contract, required=contract.get("workflow_revision") == 3))
    if errors:
        raise ControlError(*errors)
    if not args.Title or not args.Owner:
        raise ControlError("Title and Owner are required")
    state = copy.deepcopy(contract)
    state.update(
        {
            "task_id": args.TaskId,
            "title": args.Title,
            "owner": args.Owner,
            "status": "active",
            "current_phase": "planning",
            "version": 3,
            "checkout_binding": _sha(str(repo.resolve())),
            "workspace": {
                "repo_root": "<repo-root>",
                "checkout_kind": "primary",
                "branch": "unresolved",
                "head": "0" * 40,
                "dirty_paths": [],
                "write_overlap": [],
                "overlap_decision": {
                    "status": "pending",
                    "summary": "Workspace evidence must be captured before implementation dispatch.",
                    "baseline_hashes": {},
                },
            },
            "review_policy": {
                "max_fix_rounds": 3,
                "scope_expansion_requires_escalation": True,
            },
            "findings": {},
            "next_action": {"kind": "dispatch_ready_subtask"},
        }
    )
    state["approval"] = copy.deepcopy(contract["approval"])
    if state.get('workflow_revision') == 3 or any(t.get('planned_agent_key') is not None for t in state.get('subtasks', [])):
        if any(not t.get('planned_agent_key') for t in state['subtasks']):
            raise ControlError('all subtasks must declare planned_agent_key before approval')
        if any(t.get('plan_source_subtask_id') for t in state['subtasks']):
            raise ControlError('initial subtasks cannot declare a derived plan source')
        state['approval']['planned_subtask_ids'] = [t['subtask_id'] for t in state['subtasks']]
    state["approval"]["contract_sha256"] = _contract_hash(state)
    state["approval"]["approved_at"] = _now()
    rendered = _render_artifacts(args.TaskId, args.Title, state)
    state["artifact_sha256"] = {name: _sha(text.encode("utf-8")) for name, text in rendered.items()}
    state["updated_at"] = _now()
    errors = _state_model_errors(repo, state)
    if errors:
        raise ControlError(*errors)
    return state, rendered


def _init(
    args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any], rendered: dict[str, str]
) -> dict[str, Any]:
    if paths["state.json"].exists():
        raise ControlError("task already exists")
    for name, text in rendered.items():
        _atomic_write(paths[name], text)
    _atomic_write(paths["events.jsonl"], "")
    _append_event(paths["events.jsonl"], args.TaskId, "task_initialized")
    _write_state(paths, state)
    return {"ok": True, "task_id": args.TaskId, "status": state["status"], "next_action": state["next_action"]}


def _accept_artifact_update(
    args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    for _, name in ARTIFACTS:
        if not paths[name].is_file():
            errors.append(f"{name} is missing")
    errors.extend(_canonical_schema_errors(state))
    errors.extend(_validate_contract(state))
    if state.get("approval", {}).get("contract_sha256") != _contract_hash(state):
        errors.append("approval is stale because the six-point contract changed")
    errors.extend(_artifact_projection_errors(paths, state))
    for name in ("task.md", "plan.md", "execution.md", "acceptance.md"):
        if paths[name].is_file() and args.TaskId not in paths[name].read_text(encoding="utf-8"):
            errors.append(f"{name} does not identify task {args.TaskId}")
    if errors:
        raise ControlError(*errors)

    artifact_order = ("task.md", "plan.md", "execution.md", "acceptance.md")
    previous = state.get("artifact_sha256", {})
    refreshed = {name: _sha(paths[name].read_bytes()) for name in artifact_order}
    changed = [name for name in artifact_order if previous.get(name) != refreshed[name]]
    state["artifact_sha256"] = refreshed
    _write_state(paths, state)
    _append_event(
        paths["events.jsonl"],
        args.TaskId,
        "artifact_update_accepted",
        changed_artifacts=changed,
        artifact_sha256=state["artifact_sha256"],
    )
    return {
        "ok": True,
        "task_id": args.TaskId,
        "changed_artifacts": changed,
        "artifact_sha256": state["artifact_sha256"],
    }


def _candidate_path_records(repo: Path, kind: str, relative: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def visit(path: Path, logical: str, ancestors: set[Path]) -> None:
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            unresolved = path.resolve(strict=False)
            try:
                unresolved.relative_to(repo)
            except ValueError as exc:
                raise ControlError(f"candidate input path escapes repository: {logical}") from exc
            records.append({"kind": kind, "path": logical, "sha256": "missing"})
            return
        except (OSError, RuntimeError) as exc:
            raise ControlError(f"candidate input path cannot be resolved safely: {logical}: {exc}") from exc
        try:
            target = resolved.relative_to(repo).as_posix()
        except ValueError as exc:
            raise ControlError(f"candidate input path escapes repository: {logical}") from exc
        if resolved.is_dir():
            if resolved in ancestors:
                raise ControlError(f"candidate input directory cycle is not allowed: {logical}")
            children = sorted(path.iterdir(), key=lambda item: item.name)
            if not children:
                records.append({"kind": kind, "path": logical, "target": target, "sha256": "directory"})
            for child in children:
                visit(child, f"{logical.rstrip('/')}/{child.name}", ancestors | {resolved})
            return
        if not resolved.is_file():
            raise ControlError(f"candidate input must be a file or directory: {logical}")
        records.append({"kind": kind, "path": logical, "target": target, "sha256": _sha(resolved.read_bytes())})

    visit(repo / relative, relative, set())
    return records


def _candidate_records(repo: Path, state: dict[str, Any]) -> dict[str, str]:
    """Content inventory shared by integration, review coverage and acceptance."""
    inputs = state['acceptance_gate']['candidate_inputs']
    excluded = _workspace_control_paths(state)
    records: dict[str, str] = {}
    for field in ('code_paths', 'config_paths', 'runtime_input_paths', 'document_paths'):
        for raw in inputs.get(field, []):
            relative = _safe_relative_path(raw)
            if relative is None:
                raise ControlError(f'candidate input path is unsafe: {raw}')
            for record in _candidate_path_records(repo, field, relative):
                if record['path'] not in excluded:
                    records[record['path']] = _sha(record)
    # Point dependencies are inputs too; projects need not repeat each path in
    # the candidate declaration just to prevent an invisible dependency change.
    for item in state['acceptance_gate']['acceptance_items']:
        for raw in item.get('paths', []):
            relative = _safe_relative_path(raw)
            if relative is None:
                raise ControlError(f'acceptance dependency path is unsafe: {raw}')
            for record in _candidate_path_records(repo, 'acceptance_dependency', relative):
                if record['path'] not in excluded:
                    records.setdefault(record['path'], _sha(record))
    return records


def _coverage_inputs_hash(state: dict[str, Any]) -> str:
    gate = state['acceptance_gate']
    return _sha({'inputs': gate['candidate_inputs'], 'acceptance_items': gate['acceptance_items']})


def _checks_errors(checks: Any, purposes: set[str]) -> list[str]:
    if not isinstance(checks, list) or not checks:
        return ['checks must contain concrete commands, scopes, exit results and evidence']
    errors = []
    observed = set()
    for check in checks:
        if not isinstance(check, dict):
            errors.append('checks entry must be an object')
            continue
        purpose = check.get('purpose')
        observed.add(purpose)
        if (not check.get('command') or not check.get('scope') or not check.get('evidence_refs')
                or type(check.get('exit_code')) is not int
                or type(check.get('expected_exit_code')) is not int
                or check.get('exit_code') != check.get('expected_exit_code')):
            errors.append('checks require matching actual/expected exit codes and nonempty evidence')
        if purpose in {'green', 'regression'} and check.get('exit_code') != 0:
            errors.append('green/regression checks must exit zero')
        if purpose == 'red' and check.get('exit_code') == 0:
            errors.append('red checks must observe a real failing exit')
    if purposes - observed:
        errors.append('checks missing required purposes: ' + ', '.join(sorted(purposes - observed)))
    return errors


def _is_product_task(task: dict[str, Any]) -> bool:
    return task.get('stage') == 'integration' or (task.get('stage') == 'work' and task.get('role') not in {'tester', 'doc-curator', 'reviewer'})


def _dependency_ids(task: dict[str, Any], by_id: dict[str, Any]) -> set[str]:
    reachable = set()
    pending = list(task.get('dependencies', []))
    while pending:
        ident = pending.pop()
        if ident not in reachable:
            reachable.add(ident)
            pending.extend(by_id.get(ident, {}).get('dependencies', []))
    return reachable


def _required_checks(state: dict[str, Any], task: dict[str, Any]) -> set[str]:
    if task.get('subtask_id') in state.get('initial_test_owners', []):
        return {'red'}
    return {'red', 'green', 'regression'} if task.get('stage') == 'work' and _is_product_task(task) else {'regression'}


def _usage_errors(evidence: Any, writer: str) -> list[str]:
    if not isinstance(evidence, list) or not evidence:
        return ['usage_evidence requires actual stage-authored operations']
    errors = []
    for use in evidence:
        if not isinstance(use, dict):
            errors.append('usage_evidence entry must be an object')
            continue
        if use.get('written_by') != writer or any(not use.get(k) for k in ('environment', 'tool', 'entry', 'scope', 'result', 'evidence_refs')):
            errors.append('usage_evidence requires this stage writer, environment, tool, entry, scope, result and evidence')
        applicability = use.get('ui_applicability')
        tool = use.get('tool')
        if applicability == 'not_applicable':
            if tool not in {'CLI', 'API'} or not str(use.get('ui_not_applicable_reason', '')).strip():
                errors.append('non-UI use requires actual CLI/API and explicit UI inapplicability reason')
        elif applicability == 'required':
            if tool not in {'Browser', 'Computer Use'} or (tool == 'Computer Use' and use.get('environment') != 'windows_native'):
                errors.append('UI use requires Browser; Computer Use requires Windows native environment')
        else:
            errors.append('usage_evidence must explicitly state UI applicability')
    return errors


def _acceptance_finding(state: dict[str, Any], finding: dict[str, Any]) -> bool:
    return any(t.get('subtask_id') == finding.get('source_subtask_id') and t.get('stage') == 'expensive_acceptance'
               for t in state['subtasks'])


def _finding_observed_in(finding: dict[str, Any], subtask_id: str) -> bool:
    return finding.get('source_subtask_id') == subtask_id or any(
        observation.get('subtask_id') == subtask_id for observation in finding.get('failure_observations', []))


def _is_log_file_scope(relative: str) -> bool:
    return relative.startswith((".tmp/", ".artifacts/")) and relative.endswith(".log")


def _required_work_errors(state: dict[str, Any]) -> list[str]:
    unfinished = [task['subtask_id'] for task in state['subtasks']
                  if task.get('stage') == 'work' and task.get('status') != 'completed']
    return ['all required work must complete before integration: ' + ', '.join(unfinished)] if unfinished else []


def _integration_errors(repo: Path, state: dict[str, Any]) -> list[str]:
    errors = _required_work_errors(state)
    integrations = [t for t in state['subtasks'] if t.get('stage') == 'integration']
    latest = integrations[-1] if integrations else {}
    if (latest.get('status') != 'completed'
            or latest.get('result', {}).get('tested_candidate_fingerprint') != _approved_fingerprint(repo, state)):
        errors.append('latest integration coverage must include current candidate and formal documents')
    if any(f.get('status') in {'awaiting_re_review', 'awaiting_retest'}
           and f.get('fixed_after_integration') == latest.get('subtask_id') for f in state.get('findings', {}).values()):
        errors.append('fix_delta requires a new integration before review or acceptance')
    return errors


def _approved_fingerprint(repo: Path, state: dict[str, Any]) -> str:
    """Only a recorded, hash-bound document closeout can retain an accepted candidate."""
    actual = _candidate_fingerprint(repo, state)
    sync = state.get('acceptance_gate', {}).get('documentation_sync', {})
    if not sync:
        return actual
    gate = state.get('acceptance_gate', {})
    docs = [t for t in state['subtasks'] if t.get('stage') == 'final_documentation']
    doc = docs[0] if len(docs) == 1 else {}
    result = doc.get('result', {})
    declaration = result.get('documentation_sync', {})
    passed = next((a for a in reversed(gate.get('attempts', [])) if a.get('candidate_id') == gate.get('current_candidate', {}).get('candidate_id') and a.get('outcome') == 'pass'), {})
    changed = _document_delta(repo, state, passed)
    if (sync.get('after_fingerprint') == actual and sync.get('before_fingerprint') == gate.get('current_candidate', {}).get('fingerprint')
            and sync.get('coverage_inputs_sha256') == _coverage_inputs_hash(state)
            and doc.get('status') == 'completed' and result.get('status') == 'completed'
            and sync.get('written_by') == result.get('written_by') == doc.get('dispatch', {}).get('platform_agent_id')
            and changed is not None and set(sync.get('changed_paths', [])) == changed
            and set(result.get('changed_files', [])) - _workspace_control_paths(state) == changed
            and set(declaration.get('changed_paths', [])) == changed
            and changed.issubset(declaration.get('checked_paths', []))
            and bool(declaration.get('reason')) and declaration.get('reason') == sync.get('reason')
            and all(declaration.get(k) is False for k in ('behavior_changed', 'contract_changed', 'configuration_changed'))):
        return sync['before_fingerprint']
    return actual


def _acceptor_errors(state: dict[str, Any], agent_id: str) -> list[str]:
    implementers = {t['dispatch']['platform_agent_id'] for t in state['subtasks'] if t.get('dispatch')
        and _is_product_task(t)}
    implementers.update(f.get('routed_to', {}).get('platform_agent_id') for f in state.get('findings', {}).values())
    return ['acceptance identity must be independent of implementation, integration and repairs'] if agent_id in implementers else []


def _acceptance_started(state: dict[str, Any]) -> bool:
    """A terminal first attempt must descend from a controller-verified complete review."""
    gate = state.get('acceptance_gate', {})
    attempts = [a for a in gate.get('attempts', []) if not a.get('withdrawal')]
    if not attempts:
        return False
    first = attempts[0]
    source = next((t for t in state['subtasks'] if t.get('subtask_id') == first.get('subtask_id')), {})
    baseline = first.get('review_baseline', {})
    reviews = [t for t in state['subtasks'] if t.get('stage') == 'pre_acceptance_review' and t.get('status') == 'completed']
    return bool(first.get('outcome') in {'pass', 'partial_pass', 'product_failure', 'environment_failure', 'effect_failure'}
                and (first.get('mode') == 'full' or first.get('point_results')) and source.get('status') in {'completed', 'blocked'}
                and source.get('result', {}).get('expensive_acceptance', {}).get('outcome') == first.get('outcome')
                and baseline.get('candidate_id') == first.get('candidate_id')
                and baseline.get('review_ids') == [t['subtask_id'] for t in reviews]
                and baseline.get('review_sha256') == _sha([t['result']['review'] for t in reviews])
                and any(t.get('result', {}).get('review', {}).get('kind') == 'task' for t in reviews))


def _review_entry_errors(repo: Path, state: dict[str, Any]) -> list[str]:
    return [] if _acceptance_started(state) else _review_coverage_errors(repo, state)


def _review_coverage_errors(repo: Path, state: dict[str, Any]) -> list[str]:
    records = _candidate_records(repo, state)
    history = [t['result']['review'] for t in state['subtasks']
               if t.get('stage') == 'pre_acceptance_review' and t.get('status') == 'completed'
               and isinstance(t.get('result', {}).get('review'), dict)]
    if not any(r.get('kind') == 'task' for r in history):
        return ['complete independent review coverage is required']
    # Include deleted paths: an incremental reviewer must cover their removal too.
    universe = set(records)
    for review in history:
        universe.update(review.get('coverage_snapshot', {}))
    covered = {}
    for review in history:
        for path in universe:
            if any((path == scope or path.startswith(scope.rstrip("/") + "/")) for scope in review.get('covered_paths', [])):
                covered[path] = review.get('coverage_snapshot', {}).get(path, 'missing')
    missing = [path for path in sorted(universe) if covered.get(path) != records.get(path, 'missing')]
    errors = ['review coverage is stale or missing: ' + ', '.join(missing)] if missing else []
    if not history or history[-1].get('coverage_inputs_sha256') != _coverage_inputs_hash(state):
        errors.append('review coverage is stale for configuration, execution inputs or acceptance contract')
    return errors


def _revision_three_review(repo: Path, state: dict[str, Any], subtask: dict[str, Any], review: dict[str, Any]) -> None:
    if subtask.get('stage') != 'pre_acceptance_review' or review.get('kind') == 'final':
        raise ControlError('revision 3 requires pre-acceptance review, no post-acceptance final review')
    reviewer_id = subtask['dispatch']['platform_agent_id']
    implementers = {t.get('dispatch', {}).get('platform_agent_id') for t in state['subtasks']
                    if _is_product_task(t)}
    implementers.update(f.get('routed_to', {}).get('platform_agent_id') for f in state['findings'].values())
    if reviewer_id in implementers:
        raise ControlError('pre-acceptance reviewer must be independent of implementation and integration')
    usage_errors = _usage_errors(review.get('usage_evidence'), reviewer_id)
    if usage_errors:
        raise ControlError(*usage_errors)
    errors = _integration_errors(repo, state)
    if errors and review.get("verdict") != "fail":
        raise ControlError(*errors)
    integration = [t for t in state["subtasks"] if t.get("stage") == "integration" and t.get("status") == "completed"][-1]
    review["source_candidate_fingerprint"] = integration["result"]["tested_candidate_fingerprint"]
    if review.get('reviewed_candidate_fingerprint') != _candidate_fingerprint(repo, state):
        raise ControlError('review must identify the latest candidate fingerprint from build-review-brief')
    scopes = review.get('covered_paths')
    if (not isinstance(scopes, list) or not scopes or any(_safe_relative_path(p) is None for p in scopes)
            or not review.get('evidence_refs') or not review.get('checks_completed')
            or not isinstance(review.get('checks_not_run'), list)):
        raise ControlError('review requires covered_paths, evidence_refs, checks_completed and checks_not_run')
    records = _candidate_records(repo, state)
    if review.get('kind') == 'task' and any(not any((p == scope or p.startswith(scope.rstrip("/") + "/")) for scope in scopes) for p in records):
        raise ControlError('complete review must cover all declared candidate paths and formal documents')
    review['coverage_snapshot'] = records
    review['coverage_inputs_sha256'] = _coverage_inputs_hash(state)


def _new_finding(state: dict[str, Any], reported: dict[str, Any], discoverer: dict[str, str],
                 source_id: str, reviewer: dict[str, str]) -> dict[str, Any]:
    routed = reported.get('routed_to')
    if not isinstance(routed, dict) or not routed.get('platform_agent_id'):
        raise ControlError('finding requires a root-cause routed_to identity')
    if reported.get('status', 'open') != 'open':
        raise ControlError('new findings must start open')
    integrations = [t for t in state['subtasks'] if t.get('stage') == 'integration' and t.get('dispatch')]
    if not integrations or _identity(integrations[0]['dispatch']) != routed:
        raise ControlError('finding fix owner must be the original integration identity')
    proof = reported.get('regression_proof')
    if (not isinstance(proof, dict) or proof.get('written_by') != discoverer['platform_agent_id']
            or not proof.get('command') or not proof.get('scope') or not proof.get('evidence_refs')
            or type(proof.get('exit_code')) is not int
            or proof.get('exit_code') == 0 or proof.get('exit_code') != proof.get('expected_exit_code')
            or not reported.get('root_cause')):
        raise ControlError('finding requires discoverer-authored regression_proof and root_cause')
    update = reported.get('documentation_update')
    if (not isinstance(reported.get('fix_plan'), str) or not reported['fix_plan'].strip()
            or not isinstance(update, dict) or update.get('written_by') != discoverer['platform_agent_id']
            or update.get('status') not in {'updated', 'not_applicable'}
            or not isinstance(update.get('paths'), list) or not str(update.get('reason', '')).strip()
            or (update.get('status') == 'updated' and not update.get('paths'))):
        raise ControlError('finding requires discoverer fix_plan and authored documentation_update or justified not_applicable')
    acceptance = any(t.get('subtask_id') == source_id and t.get('stage') == 'expensive_acceptance' for t in state['subtasks'])
    if acceptance:
        reviewer = discoverer
    if not any(t.get('dispatch') and _identity(t['dispatch']) == reviewer
               and (t.get('stage') == 'expensive_acceptance' if acceptance else t.get('role') == 'reviewer')
               for t in state['subtasks']):
        raise ControlError('finding requires a real independent review owner')
    if reviewer == routed:
        raise ControlError('finding reviewer must be independent of fix owner')
    finding = copy.deepcopy(reported)
    finding.update(fix_round=0, status='open', discovered_by=discoverer, source_subtask_id=source_id,
                   lineage={'original_implementer': routed, 'original_reviewer': reviewer})
    return finding


def _record_acceptance_findings(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    if state.get('workflow_revision') != 3:
        raise ControlError('record-acceptance-findings requires workflow_revision=3')
    source = _find_subtask(state, args.SubtaskId)
    attempt = next((a for a in state['acceptance_gate']['attempts'] if a['subtask_id'] == args.SubtaskId), {})
    current = state['acceptance_gate'].get('current_candidate', {})
    authorized_effect_repair = (
        source.get('status') == 'blocked'
        and attempt.get('kind') == 'blackbox'
        and attempt.get('outcome') == 'effect_failure'
        and current.get('status') == 'frozen'
        and attempt.get('candidate_id') == current.get('candidate_id')
        and any('repair' in decision.get('allow', []) for decision in attempt.get('decisions', [])
                if isinstance(decision, dict))
    )
    if (source.get('stage') != 'expensive_acceptance' or not source.get('dispatch')
            or (source.get('status') != 'in_progress' and not authorized_effect_repair)):
        raise ControlError('acceptance findings require a real active or failed acceptance dispatch')
    result = _json_file_arg(args.ResultJsonFile, 'ResultJsonFile')
    discoverer = _identity(source['dispatch'])
    if (not isinstance(result, dict) or result.get('written_by') != discoverer['platform_agent_id']
            or not isinstance(result.get('findings'), list) or not result['findings']
            or any(not isinstance(item, dict) for item in result['findings'])):
        raise ControlError('acceptance findings require the actual acceptance writer and nonempty findings')
    if (not attempt or ('outcome' in attempt and not authorized_effect_repair)
            or attempt.get('candidate_id') != current.get('candidate_id')):
        raise ControlError('acceptance finding requires a current pending attempt; historical replay is forbidden')
    for reported in result['findings']:
        ident = reported.get('finding_id')
        if not ident:
            raise ControlError('acceptance finding requires a stable ID')
        reviewer = discoverer
        normalized = {k: v for k, v in reported.items() if k != 'review_owner'}
        acceptance_ids = normalized.get('acceptance_ids')
        required_ids = {a['acceptance_id'] for a in state['acceptance_gate']['acceptance_items']}
        if not isinstance(acceptance_ids, list) or not acceptance_ids or not set(acceptance_ids).issubset(required_ids):
            raise ControlError('acceptance finding must identify affected acceptance_ids')
        validated = _new_finding(state, normalized, discoverer, args.SubtaskId, reviewer)
        existing = state['findings'].get(ident)
        if existing:
            if (not _acceptance_finding(state, existing) or existing.get('discovered_by') != discoverer
                    or existing.get('status') != 'awaiting_retest' or not existing.get('fix_delta')
                    or existing.get('routed_to') != validated['routed_to']
                    or any(o['subtask_id'] == args.SubtaskId or o['candidate_id'] == attempt['candidate_id'] for o in existing.get('failure_observations', []))):
                raise ControlError('only the original acceptor may reopen a stable awaiting_retest finding on a new candidate')
            existing['status'] = 'open'
        else:
            if any(_acceptance_finding(state, f) and f.get('status') != 'closed'
                   and f.get('root_cause') == validated['root_cause'] and f.get('paths') == validated['paths']
                   for f in state['findings'].values()):
                raise ControlError('repeat acceptance defect must retain its stable finding ID')
            existing = state['findings'][ident] = validated
            existing['source_candidate_id'] = attempt['candidate_id']
        fields = ('root_cause', 'fix_plan', 'documentation_update', 'regression_proof', 'acceptance_ids', 'paths', 'summary', 'evidence')
        observation = {key: copy.deepcopy(validated[key]) for key in fields}
        observation.update(subtask_id=args.SubtaskId, candidate_id=attempt['candidate_id'])
        existing.setdefault('failure_observations', []).append(observation)
        # The repair brief uses this observation; the first and prior reports
        # remain immutable in failure_observations with their original lineage.
        existing.update({key: copy.deepcopy(validated[key]) for key in fields})
    _set_next(state, 'dispatch_fix')
    _write_state(paths, state)
    _append_event(paths['events.jsonl'], args.TaskId, 'acceptance_findings_recorded', subtask_id=args.SubtaskId)
    return {'ok': True, 'finding_ids': [f['finding_id'] for f in result['findings']]}


def _create_integration_subtask(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    source = _find_subtask(state, args.SubtaskId)
    if state.get('workflow_revision') != 3 or source.get('stage') != 'integration' or source.get('status') != 'completed':
        raise ControlError('create-integration-subtask requires a completed revision 3 integration')
    if any(t.get('stage') == 'integration' and t.get('status') in {'ready', 'in_progress'} for t in state['subtasks']):
        raise ControlError('an integration is already pending')
    created = copy.deepcopy(source)
    _inherit_plan(created, source)
    root_id = re.sub(r"(?:-integration-\d+)+$", "", args.SubtaskId)
    ident = f"{root_id}-integration-{sum(t.get('stage') == 'integration' for t in state['subtasks']) + 1}"
    created.update(subtask_id=ident, status='ready', dependencies=[args.SubtaskId])
    created.pop('dispatch', None); created.pop('result', None)
    state['subtasks'].append(created)
    _set_next(state, 'dispatch_ready_subtask')
    _write_state(paths, state)
    _append_event(paths['events.jsonl'], args.TaskId, 'integration_subtask_created', subtask_id=ident)
    return {'ok': True, 'subtask_id': ident}


def _candidate_fingerprint(repo: Path, state: dict[str, Any]) -> str:
    return _sha({"records": _candidate_records(repo, state), "inputs": _coverage_inputs_hash(state),
                 "runtime_sha256": tree_manifest(SCRIPT_DIRECTORY.parent)["sha256"]})


def _candidate_staleness_errors(repo: Path, state: dict[str, Any]) -> list[str]:
    if state.get("workflow_revision") != 3:
        return []
    gate = state.get("acceptance_gate")
    current = gate.get("current_candidate") if isinstance(gate, dict) else None
    if not isinstance(current, dict) or "frozen_at" not in current:
        return []
    snapshot = current.get('runtime_snapshot')
    if not isinstance(snapshot, dict):
        return ['frozen candidate requires a retained runtime snapshot']
    try:
        relative = _safe_relative_path(snapshot.get('path'))
        if relative is None or not relative.startswith('.artifacts/gto/'):
            return ['runtime snapshot path is outside retained evidence']
        root = repo / relative
        if not root.resolve().is_relative_to(repo.resolve()):
            return ['runtime snapshot escapes repository']
        manifest = json.loads((root / '.snapshot.json').read_text())
        if manifest.get('sha256') != snapshot['sha256']:
            return ['runtime snapshot binding changed']
        verify_tree(root, manifest)
    except (OSError, ValueError, KeyError) as exc:
        return [f'runtime snapshot unavailable or changed: {exc}']
    try:
        reference = current.get('candidate_archive') or {}
        relative = _safe_relative_path(reference.get('path'))
        if relative is None or not relative.startswith('.artifacts/gto/'):
            return ['candidate archive is missing or outside retained evidence']
        manifest_path = repo / relative
        if manifest_path.is_symlink() or not manifest_path.resolve().is_relative_to(repo.resolve()):
            return ['candidate archive escapes repository']
        raw = manifest_path.read_bytes()
        if _sha(raw) != reference.get('sha256'):
            return ['candidate archive manifest hash changed']
        archive = json.loads(raw)
        if archive.get('candidate_id') != current['candidate_id'] or archive.get('fingerprint') != current['fingerprint']:
            return ['candidate archive binding changed']
        for name, expected in archive['files'].items():
            path = manifest_path.parent / 'files' / name
            if path.is_symlink() or not path.resolve().is_relative_to(manifest_path.parent.resolve()) or _sha(path.read_bytes()) != expected:
                return ['candidate archive content changed: ' + name]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f'candidate archive unavailable: {exc}']
    try:
        fingerprint = _approved_fingerprint(repo, state) if state.get('workflow_revision') == 3 else _candidate_fingerprint(repo, state)
    except ControlError as exc:
        return exc.errors
    if current.get("fingerprint") != fingerprint:
        return ["current candidate is stale because declared candidate inputs changed"]
    return []


def _pre_acceptance_errors(state: dict[str, Any]) -> list[str]:
    errors = _required_work_errors(state) if state.get("workflow_revision") == 3 else []
    subtasks = [item for item in state.get("subtasks", []) if isinstance(item, dict)]
    for item in subtasks:
        if not isinstance(item, dict):
            continue
        if item.get("stage") != "pre_acceptance_review":
            continue
        result = item.get("result")
        review = result.get("review") if isinstance(result, dict) else None
        if item.get("status") != "completed" or not isinstance(review, dict):
            errors.append("pre_acceptance review must complete before expensive acceptance")
            continue
        if review.get("kind") == "re_review":
            continue
        if review.get("kind") != "task":
            errors.append("pre_acceptance review must record a task review result")
            continue
        if review.get("verdict") == "pass" and not review.get("findings"):
            continue
        finding_ids = {
            finding.get("finding_id")
            for finding in review.get("findings", [])
            if isinstance(finding, dict) and finding.get("finding_id")
        }
        reviewer_id = review.get("reviewer_platform_agent_id")
        resolved = bool(finding_ids) and all(
            state.get("findings", {}).get(finding_id, {}).get("status") == "closed"
            for finding_id in finding_ids
        )
        review_history = [
            candidate["result"]["review"]
            for candidate in subtasks
            if candidate is not item
            and candidate.get("stage") == "pre_acceptance_review"
            and candidate.get("status") == "completed"
            and isinstance(candidate.get("result"), dict)
            and isinstance(candidate["result"].get("review"), dict)
            and candidate["result"]["review"].get("kind") == "re_review"
            and candidate["result"]["review"].get("reviewer_platform_agent_id") == reviewer_id
        ]
        closed_by_history = {
            finding.get("finding_id")
            for history in review_history
            for finding in history.get("findings", [])
            if isinstance(finding, dict) and finding.get("status") == "closed"
        }
        resolved = (
            resolved
            and any(history.get("verdict") == "pass" for history in review_history)
            and finding_ids.issubset(closed_by_history)
        )
        if not resolved:
            errors.append("pre_acceptance review findings require same-reviewer re_review/pass after closure")
    if any(item.get("status") != "closed" and not (
            state.get('workflow_revision') == 3 and _acceptance_finding(state, item))
           for item in state.get("findings", {}).values()):
        errors.append("open or blocking finding prevents expensive acceptance")
    return errors


def _current_candidate_errors(repo: Path, state: dict[str, Any]) -> list[str]:
    gate = state.get("acceptance_gate")
    current = gate.get("current_candidate") if isinstance(gate, dict) else None
    if not isinstance(current, dict) or current.get("status") != "frozen" or not current.get("candidate_id"):
        return ["a current frozen candidate is required"]
    return _candidate_staleness_errors(repo, state)


def _current_run_errors(repo: Path, state: dict[str, Any], *, integrity_only: bool = False) -> list[str]:
    current = state.get('acceptance_gate', {}).get('current_candidate')
    if not isinstance(current, dict):
        return []
    projected = point_acceptance.coverage(repo, state, _candidate_records(repo, state))
    errors = [ident + ': ' + item['reason'] for ident, item in projected['points'].items()
              if item['status'] == 'invalid' and not (integrity_only and item.get('invalidation_kind') in {
                  'inputs_changed', 'dependency_not_passing', 'later_failure'})]
    return errors


def _session_summary(repo: Path, state: dict[str, Any]) -> dict[str, Any]:
    acceptance = point_acceptance.coverage(repo, state, _candidate_records(repo, state))
    points = acceptance['points']
    passed = sum(item['status'] == 'pass' for item in points.values())
    return {'acceptance': acceptance,
            'capability_checks': {t['subtask_id']: _capability_errors(repo, state, t)
                                  for t in state['subtasks'] if t.get('status') in {'ready', 'in_progress'}},
            'summary': f'{passed}/{len(points)} acceptance points currently pass; '
                       f'{len(acceptance["rerun_acceptance_ids"])} require execution. '
                       f'{sum(f.get("status") != "closed" for f in state.get("findings", {}).values())} open findings.'}


def _current_acceptance_pass_errors(repo: Path, state: dict[str, Any]) -> list[str]:
    errors = _current_candidate_errors(repo, state) + _current_run_errors(repo, state)
    if state.get("workflow_revision") == 3:
        errors.extend(_integration_errors(repo, state))
        errors.extend(_review_entry_errors(repo, state))
    if errors:
        return errors
    gate = state["acceptance_gate"]
    projected = point_acceptance.coverage(repo, state, _candidate_records(repo, state))
    if state.get('workflow_revision') == 3:
        if projected['rerun_acceptance_ids']:
            return ['current acceptance points require execution: ' + ', '.join(projected['rerun_acceptance_ids'])]
        return []
    candidate_id = gate["current_candidate"]["candidate_id"]
    for kind in ('ordinary', 'blackbox'):
        required = _attempt_acceptance_ids(gate, kind)
        if not required:
            continue
        latest = next((item for item in reversed(gate.get('attempts', []))
                       if item.get('candidate_id') == candidate_id and item.get('kind', 'ordinary') == kind), None)
        coverage = _current_batch_coverage(repo, state, kind, _candidate_records)
        if (not latest or latest.get('outcome') != 'pass') and coverage is None:
            return [f'current candidate has no passing {kind} acceptance evidence']
        if coverage is not None:
            continue
        mapping = latest.get('evidence_by_acceptance_id')
        if not isinstance(mapping, dict) or any(not mapping.get(key) for key in required):
            return [f'current candidate {kind} acceptance evidence mapping is incomplete']
    return []


def _require_stage_gate(repo: Path, state: dict[str, Any], stage: Any, subtask_id: str | None = None) -> None:
    if state.get("workflow_revision") == 3 and stage == "integration":
        errors = _required_work_errors(state)
    elif stage == "expensive_acceptance":
        errors = _pre_acceptance_errors(state) + _current_candidate_errors(repo, state)
        if state.get('workflow_revision') == 3:
            errors += _integration_errors(repo, state) + _review_entry_errors(repo, state)
        if not any(
            isinstance(attempt, dict)
            and "outcome" not in attempt
            and attempt.get("subtask_id") == subtask_id
            for attempt in state.get("acceptance_gate", {}).get("attempts", [])
        ):
            errors.append("expensive acceptance requires a precreated pending attempt")
    elif state.get("workflow_revision") == 3 and stage == "pre_acceptance_review":
        errors = _integration_errors(repo, state)
    elif stage == "final_documentation":
        errors = _current_acceptance_pass_errors(repo, state)
        errors.extend(_required_verification_evidence_errors(repo, state))
    else:
        errors = []
    if errors:
        raise ControlError(*errors)


def _next_attempt_identity(state: dict[str, Any], template_id: str) -> tuple[str, str]:
    attempts = state["acceptance_gate"].get("attempts", [])
    used_attempts = {item.get("attempt_id") for item in attempts if isinstance(item, dict)}
    used_subtasks = {item.get("subtask_id") for item in state.get("subtasks", []) if isinstance(item, dict)}
    number = len(attempts) + 1
    while f"attempt-{number}" in used_attempts or f"{template_id}-attempt-{number}" in used_subtasks:
        number += 1
    return f"attempt-{number}", f"{template_id}-attempt-{number}"


def _product_failure_retry_errors(state: dict[str, Any], attempt: dict[str, Any]) -> list[str]:
    finding_id = attempt.get("finding_id")
    finding = state.get("findings", {}).get(finding_id)
    if not finding_id or not isinstance(finding, dict):
        return ["product failure requires an associated finding"]
    if state.get('workflow_revision') == 3 and _acceptance_finding(state, finding):
        return [] if finding.get('status') in {'awaiting_re_review', 'awaiting_retest', 'closed'} and finding.get('fix_delta') else ['acceptance finding requires original integrator fix_delta before retest']
    if finding.get("status") != "closed" or not isinstance(finding.get("fix_delta"), dict):
        return ["product failure finding must be closed with fix_delta"]
    original_reviewer_id = finding.get("lineage", {}).get("original_reviewer", {}).get("platform_agent_id")
    reviewer_is_known = any(
        item.get("dispatch", {}).get("platform_agent_id") == original_reviewer_id
        for item in state.get("subtasks", [])
        if isinstance(item, dict)
    )
    for subtask in state.get("subtasks", []):
        result = subtask.get("result") if isinstance(subtask, dict) else None
        review = result.get("review") if isinstance(result, dict) else None
        if not isinstance(review, dict) or review.get("kind") != "re_review" or review.get("verdict") != "pass":
            continue
        if reviewer_is_known and review.get("reviewer_platform_agent_id") != original_reviewer_id:
            continue
        if any(item.get("finding_id") == finding_id and item.get("status") == "closed" for item in review.get("findings", [])):
            return []
    return ["product failure finding requires same reviewer re_review/pass"]


def _create_subtask_attempt(
    args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("workflow_revision") != 3:
        raise ControlError("create-subtask-attempt requires workflow_revision=3")
    template = _find_subtask(state, args.SubtaskId)
    if template.get("stage") != "expensive_acceptance":
        raise ControlError("subtask template must be expensive_acceptance")
    gate = state["acceptance_gate"]
    attempts = gate.get("attempts", [])
    policy = gate.get("attempt_policy", {})
    maximum = policy.get("max_expensive_attempts", 4)
    if sum(not a.get('withdrawal') for a in attempts) >= maximum:
        raise ControlError("max_expensive_attempts has been reached")
    errors = _current_candidate_errors(repo, state)
    if errors:
        raise ControlError(*errors)
    current_id = gate["current_candidate"]["candidate_id"]
    kind = getattr(args, "AttemptKind", "ordinary")
    same_candidate = [item for item in attempts if isinstance(item, dict) and item.get("candidate_id") == current_id]
    preparations = [item for item in same_candidate if item.get("kind") == "preparation" and item.get("outcome") == "pass"]
    if kind == "blackbox" and not preparations:
        raise ControlError("blackbox requires a completed preparation for the same candidate")
    required_ids = _attempt_acceptance_ids(gate, kind)
    selection = _json_file_arg(args.ResultJsonFile, 'ResultJsonFile') if args.ResultJsonFile else {}
    if not isinstance(selection, dict) or set(selection) - {'scope_acceptance_ids'}:
        raise ControlError('attempt selection only accepts scope_acceptance_ids')
    current_points = point_acceptance.coverage(repo, state, _candidate_records(repo, state))
    scope = selection.get('scope_acceptance_ids', sorted(required_ids & set(current_points['rerun_acceptance_ids'])))
    if not isinstance(scope, list) or len(scope) != len(set(scope)) or not set(scope) <= required_ids:
        raise ControlError('attempt scope is invalid')
    if kind != 'preparation' and not scope:
        raise ControlError('all requested acceptance points already have valid evidence')
    effect_failures = _effect_failures(state, scope) if kind == 'blackbox' else []
    effect_failure = effect_failures[-1] if effect_failures else None
    if kind == 'blackbox' and not _effect_permission(state, 'next_round', scope):
        raise ControlError('effect failure stop requires an explicit user next_round decision for this scope')
    if any(failure.get('candidate_id') == current_id for failure in effect_failures):
        raise ControlError('authorized next blackbox round requires a new candidate and its preparation')
    if any('outcome' not in a and not a.get('withdrawal') and
           (set(a.get('scope_acceptance_ids', [])) & set(scope) or
            kind == a.get('kind') == 'preparation') for a in attempts):
        raise ControlError('an overlapping acceptance scope is already pending')
    failures_by_scope = [sum(item.get('outcome') == 'environment_failure' and
        ((kind == item.get('kind') == 'preparation') if ident == 'preparation'
         else ident in item.get('scope_acceptance_ids', []) and item.get('kind') != 'preparation')
        for item in same_candidate) for ident in (['preparation'] if kind == 'preparation' else scope)]
    if (any(count >= 1 + policy.get('max_environment_retries_per_candidate', 1) for count in failures_by_scope)
            and not (args.ApprovalBy == 'user' and isinstance(args.ApprovalReason, str) and args.ApprovalReason.strip())):
        raise ControlError("environment retry requires explicit user authorization and a nonempty reason")
    previous_product_failures = [
        item for item in attempts
        if isinstance(item, dict) and item.get("outcome") == "product_failure"
        and set(item.get('scope_acceptance_ids', [])) & set(scope)
    ]
    if previous_product_failures:
        latest = previous_product_failures[-1]
        errors = _product_failure_retry_errors(state, latest)
        if errors:
            raise ControlError(*errors)
    errors = _pre_acceptance_errors(state)
    if errors:
        raise ControlError(*errors)
    number = sum(not a.get('withdrawal') for a in attempts) + 1
    if number >= policy.get("approval_required_from_attempt", 3):
        if not (args.ApprovalBy and args.ApprovalReason):
            raise ControlError("human approval and approval reason are required for this attempt")
    elif bool(args.ApprovalBy) != bool(args.ApprovalReason):
        raise ControlError("approval-by and approval-reason must be supplied together")
    attempt_id, subtask_id = _next_attempt_identity(state, args.SubtaskId)
    attempt: dict[str, Any] = {
        "attempt_id": attempt_id,
        "subtask_id": subtask_id,
        "template_subtask_id": args.SubtaskId,
        "candidate_id": current_id,
        "runtime_sha256": gate["current_candidate"]["runtime_snapshot"]["sha256"],
        "kind": kind,
        "scope_acceptance_ids": scope,
        "point_snapshots": point_acceptance.snapshots(gate, _candidate_records(repo, state)),
    }
    if kind == "blackbox":
        attempt["preparation_attempt_id"] = preparations[-1]["attempt_id"]
        if effect_failure:
            attempt['authorization_attempt_id'] = effect_failure['attempt_id']
    if state.get('workflow_revision') == 3:
        attempt.update(coverage_snapshot=_candidate_records(repo, state), coverage_inputs_sha256=_coverage_inputs_hash(state),
                       review_baseline=copy.deepcopy(gate['current_candidate']['review_baseline']))
    if args.ApprovalBy:
        attempt["approval"] = {"approved_by": args.ApprovalBy, "reason": args.ApprovalReason}
    created = copy.deepcopy(template)
    _inherit_plan(created, template)
    created.update({"subtask_id": subtask_id, "title": f"{template['title']} {attempt_id}", "status": "ready"})
    created.pop("dispatch", None)
    created.pop("result", None)
    if state.get('workflow_revision') == 3 and attempts:
        previous = next((a for a in attempts if a.get('template_subtask_id') == args.SubtaskId and
                         _find_subtask(state, a['subtask_id']).get('dispatch')), None)
        original = _find_subtask(state, previous['subtask_id']) if previous else {}
        if original.get('dispatch'):
            created['acceptance_owner'] = _identity(original['dispatch'])
        if created.get('acceptance_owner'):
            integrations = [t for t in state['subtasks'] if t.get('stage') == 'integration']
            created['dependencies'] = [integrations[-1]['subtask_id']]
    state["subtasks"].append(created)
    attempts.append(attempt)
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "expensive_attempt_created", attempt_id=attempt_id, subtask_id=subtask_id)
    return {"ok": True, "attempt": attempt, "subtask_id": subtask_id}


def _withdraw_attempt(args, paths, state):
    task = _find_subtask(state, args.SubtaskId)
    attempt = next((a for a in state['acceptance_gate']['attempts'] if a['subtask_id'] == args.SubtaskId), None)
    payload = _json_file_arg(args.ResultJsonFile, 'ResultJsonFile')
    if (not isinstance(payload, dict) or set(payload) != {'written_by', 'written_role', 'reason'}
            or payload.get('written_role') != 'coordinator' or not str(payload.get('written_by', '')).strip()
            or not str(payload.get('reason', '')).strip()):
        raise ControlError('withdrawal requires coordinator identity and reason')
    if not attempt or task.get('dispatch') or task.get('result') or 'outcome' in attempt or task.get('status') != 'ready':
        raise ControlError('only an unbound, unexecuted acceptance arrangement can be withdrawn')
    attempt['withdrawal'] = {**payload, 'recorded_at': _now()}
    task['status'] = 'cancelled'
    _write_state(paths, state)
    _append_event(paths['events.jsonl'], args.TaskId, 'acceptance_attempt_withdrawn',
                  attempt_id=attempt['attempt_id'], **payload)
    return {'ok': True, 'attempt_id': attempt['attempt_id'], 'status': 'withdrawn'}


def _close_point_findings(state, subtask, evidence, attempt):
    writer = _identity(subtask['dispatch'])
    passed = set(evidence['passed_acceptance_ids'])
    for finding in state['findings'].values():
        if _finding_observed_in(finding, subtask['subtask_id']) and passed & set(finding.get('acceptance_ids', [])):
            raise ControlError('failed acceptance items cannot be recorded as passed')
    for ident in evidence.get('closed_finding_ids', []):
        finding = state['findings'].get(ident, {})
        if (not _acceptance_finding(state, finding) or finding.get('discovered_by') != writer
                or finding.get('status') not in {'awaiting_re_review', 'awaiting_retest'} or not finding.get('fix_delta')
                or not set(finding.get('acceptance_ids', [])).issubset(passed)):
            raise ControlError('only original acceptor actual passing points can close a fixed finding')
        finding.update(status='closed', closed_at=_now(), closed_by_attempt_id=attempt['attempt_id'])


def _extend_acceptance_budget(
    args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    receipt = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    if not isinstance(receipt, dict):
        raise ControlError("acceptance budget extension receipt must be an object")
    candidate = copy.deepcopy(state)
    gate = candidate.get("acceptance_gate")
    if not isinstance(gate, dict):
        raise ControlError("acceptance budget extension requires acceptance_gate")
    policy = gate.get("attempt_policy")
    if not isinstance(policy, dict):
        raise ControlError("acceptance budget extension requires attempt_policy")
    gate.setdefault("budget_extensions", []).append(copy.deepcopy(receipt))
    policy["max_expensive_attempts"] = receipt.get("max_expensive_attempts")
    errors = _state_model_errors(repo, candidate)
    if errors:
        raise ControlError(*errors)
    _write_state(paths, candidate)
    _append_event(
        paths["events.jsonl"],
        args.TaskId,
        "acceptance_budget_extended",
        previous_max_expensive_attempts=receipt["previous_max_expensive_attempts"],
        max_expensive_attempts=receipt["max_expensive_attempts"],
        approved_by="user",
        approval_evidence_refs=receipt["approval_evidence_refs"],
    )
    return {
        "ok": True,
        "previous_max_expensive_attempts": receipt["previous_max_expensive_attempts"],
        "max_expensive_attempts": receipt["max_expensive_attempts"],
    }


def _acceptance_scope(state, subtask, evidence, attempt):
    """Preparation validates prerequisites; formal observations use point coverage."""
    preparation = evidence.get('preparation', {})
    checks = preparation.get('checks', {})
    if (evidence.get('evidence_by_acceptance_id') or evidence.get('scope_acceptance_ids')
            or not preparation.get('business_input_refs')
            or any(not checks.get(key) for key in
                   ('deployment', 'version', 'environment', 'input_and_session', 'evidence_capture'))):
        raise ControlError('preparation requires five evidence checks and business input references without business acceptance claims')
    evidence['passed_acceptance_ids'] = []


def _document_delta(repo: Path, state: dict[str, Any], passed: dict[str, Any]) -> set[str] | None:
    gate = state['acceptance_gate']
    before = passed.get('coverage_snapshot', {})
    after = _candidate_records(repo, state)
    changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    documents = gate['candidate_inputs'].get('document_paths', [])
    code_scopes = [p for k in ('code_paths', 'config_paths', 'runtime_input_paths') for p in gate['candidate_inputs'].get(k, [])]
    if not passed or passed.get('coverage_inputs_sha256') != _coverage_inputs_hash(state):
        return None
    if any(not any(_paths_overlap(p, d) for d in documents) or any(_paths_overlap(p, c) for c in code_scopes) for p in changed):
        return None
    return changed


def _record_document_sync(repo: Path, state: dict[str, Any], result: dict[str, Any]) -> None:
    gate = state['acceptance_gate']
    current = gate.get('current_candidate', {})
    passed = next((a for a in reversed(gate['attempts']) if a.get('candidate_id') == current.get('candidate_id') and a.get('outcome') == 'pass'), {})
    if not passed and not _current_acceptance_pass_errors(repo, state):
        passed = {
            'coverage_snapshot': _candidate_records(repo, state),
            'coverage_inputs_sha256': _coverage_inputs_hash(state),
        }
    changed = _document_delta(repo, state, passed)
    if changed is None:
        raise ControlError('documentation wording receipt cannot hide executable/configuration/runtime changes or changed contract; return to acceptance')
    declared = set(result['changed_files']) - _workspace_control_paths(state)
    if declared != changed:
        raise ControlError('documentation changed_files must match the actual formal document delta')
    sync = result.get('documentation_sync')
    if changed or sync is not None:
        if (not isinstance(sync, dict) or set(sync.get('changed_paths', [])) != changed
                or not changed.issubset(sync.get('checked_paths', [])) or not str(sync.get('reason', '')).strip()
                or any(sync.get(key) is not False for key in ('behavior_changed', 'contract_changed', 'configuration_changed'))):
            raise ControlError('documentation_sync requires checked delta and justified unchanged behavior/contract/configuration; otherwise return to acceptance')
    if changed:
        gate['documentation_sync'] = {'before_fingerprint': current['fingerprint'], 'after_fingerprint': _candidate_fingerprint(repo, state),
            'coverage_inputs_sha256': _coverage_inputs_hash(state), 'written_by': result['written_by'],
            'changed_paths': sorted(changed), 'reason': sync['reason']}


def _attempt_acceptance_ids(gate: dict[str, Any], kind: str) -> set[str]:
    all_ids = {item['acceptance_id'] for item in gate.get('acceptance_items', [])}
    blackbox_ids = set(gate.get('blackbox_acceptance_ids', []))
    return set() if kind == 'preparation' else blackbox_ids if kind == 'blackbox' else all_ids - blackbox_ids


def _record_expensive_attempt(
    state: dict[str, Any],
    subtask: dict[str, Any],
    result: dict[str, Any],
    *,
    repo: Path | None = None,
) -> None:
    evidence = result.get("expensive_acceptance")
    required = {
        "outcome", "real_call_count", "duration_seconds", "failed_stage",
        "evidence_refs", "evidence_by_acceptance_id",
    }
    if not isinstance(evidence, dict) or not required.issubset(evidence):
        raise ControlError("result.expensive_acceptance is incomplete")
    if not isinstance(evidence.get("failed_stage"), str) or not evidence["failed_stage"].strip():
        raise ControlError('expensive_acceptance.failed_stage must be non-empty; use "none" for a passing attempt')
    outcome = evidence.get("outcome")
    if state.get("workflow_revision") == 3:
        expected_status = "completed" if outcome in {"pass", "partial_pass"} else "blocked"
        if result.get("status") != expected_status:
            raise ControlError("acceptance outcome must match completed/pass or blocked/failure status")
    if outcome not in {"pass", "partial_pass", "product_failure", "environment_failure", "effect_failure"}:
        raise ControlError("expensive acceptance outcome is invalid")
    if not isinstance(evidence.get("real_call_count"), int) or evidence["real_call_count"] < 0:
        raise ControlError("expensive acceptance real_call_count is invalid")
    if not isinstance(evidence.get("duration_seconds"), (int, float)) or evidence["duration_seconds"] < 0:
        raise ControlError("expensive acceptance duration_seconds is invalid")
    if not isinstance(evidence.get("evidence_refs"), list):
        raise ControlError("expensive acceptance evidence_refs must be a list")
    mapping = evidence.get("evidence_by_acceptance_id")
    if not isinstance(mapping, dict):
        raise ControlError("expensive acceptance evidence mapping is invalid")
    gate = state["acceptance_gate"]
    current_attempt = next((item for item in gate.get('attempts', []) if item.get('subtask_id') == subtask.get('subtask_id')), {})
    kind = current_attempt.get('kind', 'ordinary')
    allowed = {'ordinary': {'pass', 'partial_pass', 'product_failure', 'environment_failure'},
               'preparation': {'pass', 'environment_failure'},
               'blackbox': {'pass', 'partial_pass', 'effect_failure', 'environment_failure'}}
    if outcome not in allowed[kind]:
        raise ControlError('outcome is invalid for attempt kind ' + kind)
    if kind == 'blackbox':
        blackbox = evidence.get('blackbox', {})
        if any(not blackbox.get(field) for field in ('session_ids', 'input_refs', 'trace_refs')):
            raise ControlError('blackbox requires session, input and trace references')
        if outcome == 'effect_failure' and not blackbox.get('report_ref'):
            raise ControlError('effect_failure requires a report reference')
        if outcome == 'environment_failure':
            invalid = evidence.get('invalid_observation', {})
            if (invalid.get('reason') not in {'version', 'environment', 'input_or_session', 'evidence_capture'}
                    or not invalid.get('evidence_refs') or not str(invalid.get('summary', '')).strip()):
                raise ControlError('invalid_observation requires a supported reason, evidence and summary')
    required_ids = _attempt_acceptance_ids(gate, kind)
    if state.get("workflow_revision") == 3 and outcome == "product_failure":
        finding = state["findings"].get(evidence.get("finding_id"), {})
        if not _finding_observed_in(finding, subtask["subtask_id"]) or finding.get("discovered_by") != _identity(subtask["dispatch"]):
            raise ControlError("product failure must reference this acceptance identity finding")
    if outcome == "product_failure" and not evidence.get("finding_id"):
        raise ControlError("product_failure requires finding_id")
    current = gate.get("current_candidate")
    if not isinstance(current, dict) or current.get("status") != "frozen":
        raise ControlError("expensive acceptance result requires a current frozen candidate")
    attempts = gate.get("attempts", [])
    attempt = next(
        (item for item in attempts if isinstance(item, dict) and item.get("subtask_id") == subtask.get("subtask_id")),
        None,
    )
    if attempt is None:
        raise ControlError("expensive acceptance result requires a precreated attempt")
    elif "outcome" in attempt:
        raise ControlError("expensive acceptance attempt result is append-only")
    if attempt.get("candidate_id") != current.get("candidate_id"):
        raise ControlError("expensive acceptance attempt candidate is stale")
    if state.get('workflow_revision') == 3:
        errors = _acceptor_errors(state, subtask['dispatch']['platform_agent_id'])
        if errors:
            raise ControlError(*errors)
        errors = _usage_errors(evidence.get('usage_evidence'), subtask['dispatch']['platform_agent_id'])
        if errors:
            raise ControlError(*errors)
        if kind == 'preparation':
            if evidence.get('point_results'):
                raise ControlError('preparation facts cannot claim formal point results; adopt actual observations explicitly')
            _acceptance_scope(state, subtask, evidence, attempt)
        elif evidence.get('evidence_batch_ids') and 'point_results' not in evidence:
            if repo is None:
                raise ControlError("partial acceptance validation requires the consumer repository")
            try:
                _validate_partial_acceptance(repo, state, subtask, evidence, _candidate_records)
            except BatchEvidenceError as exc:
                raise ControlError(str(exc)) from exc
        else:
            try:
                point_acceptance.normalize(gate, attempt, evidence, state['findings'])
                if repo is None:
                    raise ValueError('point evidence validation requires the consumer repository')
                point_acceptance.seal(repo, attempt, evidence)
            except (ValueError, OSError) as exc:
                raise ControlError(str(exc)) from exc
            _close_point_findings(state, subtask, evidence, attempt)
    attempt.update(copy.deepcopy(evidence))


def _freeze_candidate(
    args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("workflow_revision") != 3:
        raise ControlError("freeze-candidate requires workflow_revision=3")
    errors = _pre_acceptance_errors(state)
    if errors:
        raise ControlError(*errors)
    if state.get("workflow_revision") == 3:
        errors = _integration_errors(repo, state) + _review_entry_errors(repo, state)
        if errors:
            raise ControlError(*errors)
    fingerprint = _candidate_fingerprint(repo, state)
    current = {
        "candidate_id": f"candidate-{fingerprint[:16]}",
        "status": "frozen",
        "fingerprint": fingerprint,
        "frozen_at": _now(),
    }
    if state.get('workflow_revision') == 3:
        if _acceptance_started(state):
            first = next(a for a in state['acceptance_gate']['attempts'] if not a.get('withdrawal'))
            current['review_baseline'] = copy.deepcopy(first['review_baseline'])
        else:
            reviews = [t for t in state['subtasks'] if t.get('stage') == 'pre_acceptance_review' and t.get('status') == 'completed']
            current['review_baseline'] = {'candidate_id': current['candidate_id'],
                'review_ids': [t['subtask_id'] for t in reviews], 'review_sha256': _sha([t['result']['review'] for t in reviews])}
        state['acceptance_gate'].pop('documentation_sync', None)
    runtime = tree_manifest(SCRIPT_DIRECTORY.parent)
    relative = f".artifacts/gto/{args.TaskId}/runtimes/{runtime['sha256']}"
    destination = repo / relative
    try:
        if destination.exists():
            verify_tree(destination, runtime)
        else:
            if freeze_tree(SCRIPT_DIRECTORY.parent, destination) != runtime:
                raise ValueError("runtime changed during snapshot capture")
    except (OSError, ValueError) as exc:
        raise ControlError(f"cannot freeze runtime: {exc}") from exc
    current['runtime_snapshot'] = {'path': relative, 'sha256': runtime['sha256']}
    # Retain the declared candidate bytes independently from the mutable checkout.
    archive = repo / '.artifacts/gto' / args.TaskId / 'candidates' / current['candidate_id']
    if any(p.is_symlink() for p in (archive, *archive.parents)):
        raise ControlError('candidate archive path must not contain symlinks')
    records = _candidate_records(repo, state)
    inventory = {'candidate_id': current['candidate_id'], 'fingerprint': fingerprint,
                 'runtime_snapshot': current['runtime_snapshot'], 'records': records,
                 'inputs': state['acceptance_gate']['candidate_inputs'], 'files': {}}
    for relative_path in records:
        source = repo / relative_path
        if source.is_file():
            raw = source.read_bytes()
            inventory['files'][relative_path] = _sha(raw)
            target = archive / 'files' / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != raw:
                raise ControlError('retained candidate bytes changed')
            target.write_bytes(raw)
    archive.mkdir(parents=True, exist_ok=True)
    manifest_path = archive / 'manifest.json'
    manifest_text = json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if manifest_path.exists() and manifest_path.read_text() != manifest_text:
        raise ControlError('retained candidate manifest changed')
    manifest_path.write_text(manifest_text)
    current['candidate_archive'] = {'path': manifest_path.relative_to(repo).as_posix(),
                                    'sha256': _sha(manifest_path.read_bytes())}
    if _candidate_fingerprint(repo, state) != fingerprint:
        raise ControlError('candidate changed during snapshot capture')
    state["acceptance_gate"]["current_candidate"] = current
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "candidate_frozen", candidate_id=current["candidate_id"])
    return {"ok": True, "current_candidate": current}


def _verified_brief_path(repo: Path, raw: Any, expected_sha256: str) -> str:
    relative = _safe_relative_path(raw)
    if relative is None:
        raise ControlError("dispatch requires --brief-path relative to --repo-root, for example .tmp/task/brief.md; absolute paths are not accepted")
    path = repo / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(repo)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        raise ControlError(f"dispatch brief file is unavailable or outside repository: {relative}") from exc
    if not resolved.is_file():
        raise ControlError(f"dispatch brief path is not a file: {relative}")
    actual = _sha(resolved.read_bytes())
    if actual != expected_sha256:
        raise ControlError("dispatch brief sha256 does not match the actual brief file")
    return relative


def _bind(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    subtask = _find_subtask(state, args.SubtaskId)
    errors = _capability_errors(paths["state.json"].parents[4], state, subtask, args.PlatformAgentId)
    if errors:
        raise ControlError(*errors)
    errors = _execution_plan_errors(state)
    if errors:
        raise ControlError(*errors)
    required = (args.AgentKey, args.PlatformAgentId, args.ContextMode, args.BriefKind, args.BriefSha256)
    if not all(required) or not re.fullmatch(r"[0-9a-f]{64}", args.BriefSha256 or ""):
        raise ControlError("dispatch binding fields and a lowercase sha256 are required")
    if subtask.get("status") in {"in_progress", "completed", "blocked", "cancelled"} or subtask.get("dispatch") is not None or subtask.get("result") is not None:
        raise ControlError(f"subtask {args.SubtaskId} is already active or terminal and cannot be rebound")
    if state.get("workflow_revision") == 3:
        if subtask.get("status") != "ready":
            raise ControlError(f"subtask {args.SubtaskId} must be ready before dispatch")
        _require_stage_gate(paths["state.json"].parents[4], state, subtask.get("stage"), args.SubtaskId)
        brief_path = _verified_brief_path(paths["state.json"].parents[4], args.BriefPath, args.BriefSha256)
    statuses = {
        item.get("subtask_id"): item.get("status")
        for item in state.get("subtasks", [])
        if isinstance(item, dict)
    }
    unfinished = [dep for dep in subtask.get("dependencies", []) if statuses.get(dep) != "completed"
                  and not (state.get("workflow_revision") == 3 and subtask.get("stage") == "final_documentation"
                           and _find_subtask(state, dep).get("stage") == "expensive_acceptance"
                           and not _current_acceptance_pass_errors(paths["state.json"].parents[4], state))]
    if unfinished:
        raise ControlError("subtask dependencies are not completed: " + ", ".join(unfinished))
    if state.get('workflow_revision') == 3:
        owners = state.get('initial_test_owners', [])
        if subtask.get('stage') == 'expensive_acceptance':
            errors = _acceptor_errors(state, args.PlatformAgentId)
            if errors:
                raise ControlError(*errors)
        for other in state['subtasks']:
            if other.get('dispatch', {}).get('platform_agent_id') != args.PlatformAgentId:
                continue
            if (subtask.get('role') == 'tester' and subtask.get('stage') == 'work' and _is_product_task(other)
                    or other.get('role') == 'tester' and other.get('stage') == 'work' and _is_product_task(subtask)):
                raise ControlError('tester identity must be independent of implementation and integration')
            if other.get('status') == 'in_progress':
                raise ControlError('one platform identity cannot execute simultaneous subtasks')
        expected_acceptor = subtask.get('acceptance_owner')
        if expected_acceptor and expected_acceptor != {'agent_key': args.AgentKey, 'platform_agent_id': args.PlatformAgentId}:
            raise ControlError('retest must bind to the original acceptance identity')
    if state.get("workflow_revision") == 3 and subtask.get("stage") == "integration":
        owners = [_identity(t["dispatch"]) for t in state["subtasks"] if t.get("stage") == "integration" and t.get("dispatch")]
        if owners and owners[0] != {"agent_key": args.AgentKey, "platform_agent_id": args.PlatformAgentId}:
            raise ControlError("new integration must retain the original integration owner")
    expected_reviewer = subtask.get("lineage", {}).get("original_reviewer")
    if isinstance(expected_reviewer, dict) and (
        args.AgentKey != expected_reviewer.get("agent_key")
        or args.PlatformAgentId != expected_reviewer.get("platform_agent_id")
    ):
        raise ControlError("re-review must bind to the original reviewer")
    errors = _planned_dispatch_errors(state, subtask, args.AgentKey, args.PlatformAgentId)
    if errors:
        raise ControlError(*errors)
    subtask["dispatch"] = {
        "agent_key": args.AgentKey,
        "platform_agent_id": args.PlatformAgentId,
        "context_mode": args.ContextMode,
        "brief_kind": args.BriefKind,
        "brief_sha256": args.BriefSha256,
    }
    if state.get("workflow_revision") == 3:
        subtask["dispatch"]["brief_path"] = brief_path
    subtask["status"] = "in_progress"
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "dispatch_bound", subtask_id=args.SubtaskId)
    return {"ok": True, "subtask_id": args.SubtaskId, "dispatch": subtask["dispatch"]}


def _record_subtask_result(
    args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any], *, persist: bool = True,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    subtask = _find_subtask(state, args.SubtaskId)
    dispatch = subtask.get("dispatch")
    if not dispatch or subtask.get("status") != "in_progress":
        raise ControlError("subtask result requires an active bound dispatch")
    if state.get("workflow_revision") == 3 and subtask.get("role") == "reviewer":
        raise ControlError("reviewer results require record-review-result")
    if result is None:
        result = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    errors = _result_input_errors('record-subtask-result', result)
    if errors:
        raise ControlError('subtask result is incomplete or invalid', *errors)
    required = {
        "status",
        "summary",
        "changed_files",
        "planned_files_not_changed",
        "verification",
        "deviations",
        "blocked_by",
        "risks",
        "follow_up",
        "written_by",
        "written_role",
    }
    if not isinstance(result, dict) or not required.issubset(result):
        raise ControlError("subtask result is incomplete")
    if result["status"] not in {"completed", "blocked"}:
        raise ControlError("subtask result status must be completed or blocked")
    if result["written_by"] != dispatch["platform_agent_id"] or result["written_role"] != dispatch["agent_key"]:
        raise ControlError("subtask result writer does not match bound dispatch")
    verification = result.get("verification")
    if not isinstance(verification, dict) or not verification.get("commands") or not verification.get("result"):
        raise ControlError("subtask result verification is incomplete")
    write_scopes = [
        relative.rstrip("/")
        for relative in (_safe_relative_path(raw) for raw in subtask.get("write_paths", []))
        if relative
    ]
    scope_errors: list[str] = []
    for field in ("changed_files", "planned_files_not_changed"):
        values = result.get(field)
        if not isinstance(values, list):
            scope_errors.append(f"result.{field} must be a list")
            continue
        for raw in values:
            relative = _safe_relative_path(raw)
            if relative is None or not any(
                relative == scope or relative.startswith(scope + "/") for scope in write_scopes
            ):
                scope_errors.append(f"result.{field} path is outside subtask write_paths: {raw}")
    if scope_errors:
        raise ControlError(*scope_errors)
    if state.get("workflow_revision") == 3 and result["status"] == "completed":
        repo = paths["state.json"].parents[4]
        stage = subtask.get("stage")
        if stage in {"work", "integration"}:
            errors = _checks_errors(result.get("checks"), _required_checks(state, subtask))
            if errors:
                raise ControlError(*errors)
            if stage == "integration":
                _require_stage_gate(repo, state, stage)
                integration = result.get("integration")
                documents = state["acceptance_gate"]["candidate_inputs"].get("document_paths", [])
                if not isinstance(integration, dict) or not integration.get("summary") or integration.get("document_paths") != documents:
                    raise ControlError("integration requires explicit integration summary and all formal document_paths")
            result["tested_candidate_fingerprint"] = _candidate_fingerprint(repo, state)
        if stage == "final_documentation":
            subtask['result'] = result
            subtask['status'] = result['status']
            _record_document_sync(repo, state, result)
            _require_stage_gate(repo, state, stage)
    if state.get("workflow_revision") == 3 and subtask.get("stage") == "expensive_acceptance":
        if state.get("workflow_revision") == 3 and result.get("expensive_acceptance", {}).get("outcome") == "pass":
            errors = _current_candidate_errors(paths["state.json"].parents[4], state)
            if errors:
                raise ControlError(*errors)
        if state.get("workflow_revision") == 3:
            errors = _acceptance_review_evidence_errors(paths["state.json"].parents[4], state, subtask, result)
            if errors:
                raise ControlError(*errors)
        errors = acceptance_run_errors(paths["state.json"].parents[4], state, subtask, result)
        if errors:
            raise ControlError(*errors)
        _record_expensive_attempt(state, subtask, result, repo=paths["state.json"].parents[4])
    subtask["result"] = result
    subtask["status"] = result["status"]
    action = _set_next(state, "dispatch_ready_subtask")
    _finish_result(paths, state, args.TaskId, 'subtask_result_recorded', persist, subtask_id=args.SubtaskId)
    return {"ok": True, "subtask_id": args.SubtaskId, "status": subtask["status"], "next_action": action}


def _record_verification_evidence(
    args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    receipt = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    errors = _canonical_schema_errors(receipt, definition="verificationEvidenceReceipt")
    if errors:
        raise ControlError(*(f"verification evidence receipt path/schema invalid: {error}" for error in errors))
    receipts = state.setdefault("verification_evidence_receipts", [])
    identity = (receipt["source_subtask_id"], receipt["evidence_key"])
    previous = next(
        (
            item
            for item in receipts
            if (item.get("source_subtask_id"), item.get("evidence_key")) == identity
        ),
        None,
    )
    if previous is not None:
        if previous == receipt:
            errors = _verification_receipt_errors(repo, state, receipt)
            if errors:
                raise ControlError(*errors)
            return {"ok": True, "already_recorded": True, "receipt": receipt}
        binding_fields = {
            "written_by",
            "written_role",
            "source_result_sha256",
            "candidate_id",
            "candidate_fingerprint",
        }
        if all(previous.get(key) == receipt.get(key) for key in binding_fields):
            raise ControlError("conflicting verification evidence receipt already exists")
    errors = _verification_receipt_errors(repo, state, receipt)
    if errors:
        raise ControlError(*errors)
    receipts.append(copy.deepcopy(receipt))
    _write_state(paths, state)
    _append_event(
        paths["events.jsonl"],
        args.TaskId,
        "verification_evidence_recorded",
        source_subtask_id=receipt["source_subtask_id"],
        evidence_key=receipt["evidence_key"],
    )
    return {"ok": True, "already_recorded": False, "receipt": receipt}


def _record_acceptance_evidence_batch(
    args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("workflow_revision") != 3:
        raise ControlError("acceptance evidence batches require workflow_revision=3")
    payload = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    try:
        duplicate, batch = _add_acceptance_batch(repo, state, payload, _candidate_records)
    except BatchEvidenceError as exc:
        raise ControlError(str(exc)) from exc
    if duplicate:
        return {"ok": True, "already_recorded": True, "batch": batch}
    _write_state(paths, state)
    _append_event(
        paths["events.jsonl"],
        args.TaskId,
        "acceptance_evidence_batch_recorded",
        batch_id=batch["batch_id"],
        source_attempt_id=batch["source_attempt_id"],
    )
    return {"ok": True, "already_recorded": False, "batch": batch}


def _record_acceptance_coverage(
    args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("workflow_revision") != 3:
        raise ControlError("acceptance coverage requires workflow_revision=3")
    payload = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    try:
        duplicate, receipt = _add_acceptance_coverage(repo, state, payload, _candidate_records)
    except BatchEvidenceError as exc:
        raise ControlError(str(exc)) from exc
    if duplicate:
        return {"ok": True, "already_recorded": True, "coverage": receipt}
    _write_state(paths, state)
    _append_event(
        paths["events.jsonl"],
        args.TaskId,
        "acceptance_coverage_recorded",
        coverage_id=receipt["coverage_id"],
        kind=receipt["kind"],
    )
    return {"ok": True, "already_recorded": False, "coverage": receipt}


def _completed_review_result(
    subtask: dict[str, Any], dispatch: dict[str, Any], review: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    normalized_review = copy.deepcopy(review)
    normalized_findings: list[dict[str, Any]] = []
    for reported in review.get("findings", []):
        stored = state.get("findings", {}).get(reported.get("finding_id"), reported)
        normalized_findings.append(
            {
                key: copy.deepcopy(stored[key])
                for key in ("finding_id", "severity", "paths", "summary", "evidence", "status", "fix_round", "routed_to", "fix_delta")
                if key in stored
            }
        )
    normalized_review["findings"] = normalized_findings
    if normalized_review.get("kind") in {"task", "re_review"} and "input_scope" not in normalized_review:
        paths = sorted({path for finding in normalized_findings for path in finding.get("paths", [])})
        normalized_review["input_scope"] = {
            "finding_ids": [finding["finding_id"] for finding in normalized_findings],
            "fix_delta_sha256": _sha([finding.get("fix_delta") for finding in normalized_findings]),
            "paths": paths,
            "evidence_refs": ["structured-review-result"],
        }
    return {
        "status": "completed",
        "summary": f"{normalized_review.get('kind')} review recorded with verdict {normalized_review.get('verdict')}.",
        "changed_files": [],
        "planned_files_not_changed": list(subtask.get("write_paths", [])),
        "verification": {"commands": ["review"], "result": "Structured review result recorded."},
        "deviations": [],
        "blocked_by": [],
        "risks": [],
        "follow_up": [],
        "written_by": dispatch["platform_agent_id"],
        "written_role": dispatch["agent_key"],
        "review": normalized_review,
    }


def _review_purpose(subtask: dict[str, Any]) -> str:
    if isinstance(subtask.get("lineage"), dict) and re.search(r"-rereview-\d+$", str(subtask.get("subtask_id", ""))):
        return "re_review"
    return "task"


def _record_review(args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
    subtask = _find_subtask(state, args.SubtaskId)
    dispatch = subtask.get("dispatch")
    if (
        subtask.get("role") != "reviewer"
        or subtask.get("status") != "in_progress"
        or not isinstance(dispatch, dict)
        or dispatch.get("brief_kind") != "review"
        or subtask.get("result") is not None
    ):
        raise ControlError("review result requires an active bound review subtask without an existing result")
    result = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    errors = _result_input_errors('record-review-result', result)
    if errors:
        raise ControlError(*errors)
    review = result.get("review") if isinstance(result, dict) else None
    if not isinstance(review, dict):
        raise ControlError("result.review is required")
    if review.get("reviewer_platform_agent_id") != dispatch.get("platform_agent_id"):
        raise ControlError("reviewer identity does not match the bound dispatch")
    kind = review.get("kind")
    findings = review.get("findings")
    if kind not in ("task", "re_review") or not isinstance(findings, list):
        raise ControlError("review.kind and review.findings are invalid")
    if state.get("workflow_revision") == 3:
        _revision_three_review(repo, state, subtask, review)
    expected_kind = _review_purpose(subtask)
    if kind != expected_kind:
        raise ControlError(f"review kind {kind} does not match subtask purpose {expected_kind}")
    if kind == "task" and review.get("verdict") == "pass":
        if findings:
            raise ControlError("task review with findings must fail with findings")
        subtask["result"] = _completed_review_result(subtask, dispatch, review, state)
        subtask["status"] = "completed"
        action = _set_next(state, "dispatch_ready_subtask")
    else:
        passing_re_review = kind == "re_review" and review.get("verdict") == "pass"
        if (not passing_re_review and review.get("verdict") != "fail") or (not findings and not (passing_re_review and state.get("workflow_revision") == 3)):
            raise ControlError("a non-passing review must be fail with findings")
        reviewer = _identity(dispatch)
        for reported in findings:
            if not isinstance(reported, dict) or not reported.get("finding_id"):
                raise ControlError("each finding requires finding_id")
            finding_id = reported["finding_id"]
            existing = state["findings"].get(finding_id)
            if existing is None:
                if kind == "re_review" and state.get("workflow_revision") != 3:
                    raise ControlError(f"re-review references unknown finding_id: {finding_id}")
                if passing_re_review:
                    raise ControlError("new findings must be reported in a failing re-review")
                routed = reported.get("routed_to")
                if not isinstance(routed, dict) or not routed.get("platform_agent_id"):
                    raise ControlError(f"finding {finding_id} requires routed_to")
                existing = copy.deepcopy(reported)
                existing.update(
                    {
                        "fix_round": 0,
                        "status": reported.get("status", "open"),
                        "lineage": {"original_implementer": routed, "original_reviewer": reviewer},
                    }
                )
                if state.get("workflow_revision") == 3:
                    existing = _new_finding(state, reported, reviewer, args.SubtaskId, reviewer)
                state["findings"][finding_id] = existing
            else:
                if kind != "re_review":
                    raise ControlError(f"finding_id already exists outside re-review: {finding_id}")
                if reviewer != existing["lineage"]["original_reviewer"]:
                    raise ControlError(f"finding {finding_id} must return to original_reviewer")
                if passing_re_review and reported.get("status") != "closed":
                    raise ControlError(f"passing re-review must report status=closed: {finding_id}")
                if reported.get("status") == "closed":
                    if state.get("workflow_revision") == 3 and (existing.get("status") != "awaiting_re_review" or not existing.get("fix_delta")):
                        raise ControlError(f"finding {finding_id} requires actual fix_delta awaiting re-review")
                    existing["status"] = "closed"
                    existing["closed_at"] = _now()
                else:
                    existing["status"] = "open"
                    if existing["fix_round"] >= state["review_policy"]["max_fix_rounds"]:
                        existing["status"] = "blocked"
                        state["status"] = "blocked"
                        state["current_phase"] = "blocked"
        subtask["result"] = _completed_review_result(subtask, dispatch, review, state)
        subtask["status"] = "completed"
        blocked = next((item for item in state["findings"].values() if item["status"] == "blocked"), None)
        open_finding = next((item for item in state["findings"].values() if item["status"] == "open"), None)
        if blocked:
            action = _set_next(state, "human_adjudication", finding_id=blocked["finding_id"])
        elif open_finding:
            action = _set_next(state, "dispatch_fix", open_finding["lineage"]["original_implementer"], finding_id=open_finding["finding_id"])
        else:
            action = _set_next(state, "dispatch_ready_subtask")
    _finish_result(paths, state, args.TaskId, 'review_recorded', persist, subtask_id=args.SubtaskId, kind=kind)
    return {"ok": True, "next_action": action}


def _create_re_review_subtask(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    if _acceptance_started(state):
        raise ControlError('acceptance has started; changes return to the original acceptor without re-review')
    source = _find_subtask(state, args.SubtaskId)
    if source.get('status') not in {'completed', 'blocked'} or not source.get('dispatch'):
        raise ControlError('re-review source must be a terminal bound review or acceptance')
    if source.get('stage') == 'expensive_acceptance':
        raise ControlError('acceptance findings return directly to the original acceptor, not re-review')
    elif source.get('stage') == 'pre_acceptance_review':
        reviewer = _identity(source['dispatch'])
        findings = [f for f in state['findings'].values() if f['lineage']['original_reviewer'] == reviewer
                    and f.get('status') == 'awaiting_re_review']
    else:
        raise ControlError('re-review source must be a review or acceptance subtask')
    if any(f['lineage']['original_reviewer'] != reviewer for f in findings):
        raise ControlError('split re-reviews by original review owner')
    prior = [t for t in state['subtasks'] if t.get('stage') == 'pre_acceptance_review'
             and t.get('dispatch') and _identity(t['dispatch']) == reviewer and t.get('status') == 'completed']
    if not prior:
        raise ControlError('re-review requires a completed review by the designated owner')
    template = prior[-1]
    if any(t.get('stage') == 'pre_acceptance_review' and t.get('status') in {'ready', 'in_progress'} for t in state['subtasks']):
        raise ControlError('a review is already pending')
    integrations = [t for t in state['subtasks'] if t.get('stage') == 'integration']
    latest = integrations[-1]
    if latest.get('status') != 'completed':
        raise ControlError('re-review requires the new integration to complete')
    created = copy.deepcopy(template)
    _inherit_plan(created, template)
    root = re.sub(r'(?:-rereview-\d+)+$', '', template['subtask_id'])
    ident = f"{root}-rereview-{len(prior)}"
    created.update(subtask_id=ident, title='Scope re-review of latest integration', status='ready',
                   dependencies=[template['subtask_id'], latest['subtask_id']],
                   lineage={'original_implementer': _identity(latest['dispatch']), 'original_reviewer': reviewer})
    created['assignment']['goal'] = 'Review latest changed scope and fixed findings; report new findings with proof.'
    created['assignment']['must_include'] = ['Cover current candidate changes and affected formal documents.',
                                            *[f"Re-review finding {f['finding_id']}." for f in findings]]
    created.pop('dispatch', None); created.pop('result', None)
    state['subtasks'].append(created)
    _set_next(state, 'dispatch_ready_subtask', reviewer)
    _write_state(paths, state)
    _append_event(paths['events.jsonl'], args.TaskId, 're_review_subtask_created', source_subtask_id=args.SubtaskId,
                  subtask_id=ident, finding_ids=[f['finding_id'] for f in findings])
    return {'ok': True, 'subtask_id': ident}




def _depends_on_subtask(
    subtask: dict[str, Any], ancestor_id: str, by_id: dict[str, dict[str, Any]]
) -> bool:
    pending = list(subtask.get("dependencies", []))
    seen: set[str] = set()
    while pending:
        dependency_id = pending.pop()
        if dependency_id == ancestor_id:
            return True
        if dependency_id in seen:
            continue
        seen.add(dependency_id)
        dependency = by_id.get(dependency_id)
        if dependency:
            pending.extend(dependency.get("dependencies", []))
    return False




def _dispatch_fix(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    finding = state.get("findings", {}).get(args.FindingId)
    if not finding or finding.get("status") != "open":
        raise ControlError(f"finding is not dispatchable: {args.FindingId}")
    maximum = state.get("review_policy", {}).get("max_fix_rounds", 3)
    if finding["fix_round"] >= maximum:
        finding["status"] = "blocked"
        state["status"] = "blocked"
        state["current_phase"] = "blocked"
        action = _set_next(state, "human_adjudication", finding_id=args.FindingId)
        _write_state(paths, state)
        return {"ok": True, "finding": finding, "next_action": action}
    finding["fix_round"] += 1
    finding["status"] = "fix_dispatched"
    action = _set_next(state, "perform_fix", finding["lineage"]["original_implementer"], finding_id=args.FindingId)
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "finding_fix_dispatched", finding_id=args.FindingId, fix_round=finding["fix_round"])
    return {"ok": True, "finding": finding, "next_action": action}


def _record_fix(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
    finding = state.get("findings", {}).get(args.FindingId)
    if not finding or finding.get("status") != "fix_dispatched":
        raise ControlError(f"finding has no active fix dispatch: {args.FindingId}")
    result = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    errors = _result_input_errors('record-finding-fix', result)
    if errors:
        raise ControlError(*errors)
    required = ("summary", "changed_files", "sha256", "verification")
    if not isinstance(result, dict) or any(key not in result for key in required):
        raise ControlError("finding fix result is incomplete")
    if not re.fullmatch(r"[0-9a-f]{64}", str(result.get("sha256", ""))):
        raise ControlError("finding fix sha256 is invalid")
    if state.get("workflow_revision") == 3:
        owner = finding["routed_to"]
        if result.get("written_by") != owner["platform_agent_id"] or result.get("written_role") != owner["agent_key"]:
            raise ControlError("fix result writer must match the root-cause fix owner")
        errors = _checks_errors(result.get("checks"), {"red", "green", "regression"})
        scopes = [p for task in state["subtasks"] if task.get("dispatch") and _identity(task["dispatch"]) == owner for p in task["write_paths"]]
        repo = Path(args.RepoRoot).resolve()

        def repair_paths(raw: Any) -> set[str]:
            relative = _safe_relative_path(raw)
            if relative is None:
                raise ControlError('fix path must be a safe repository relative path')
            try:
                physical = (repo / relative).resolve().relative_to(repo).as_posix()
            except (ValueError, OSError, RuntimeError):
                raise ControlError('fix path must not escape the repository')
            return {relative, physical}

        allowed = {p for scope in scopes for p in repair_paths(scope)}
        documents = {p for scope in state['acceptance_gate']['candidate_inputs'].get('document_paths', [])
                     for p in repair_paths(scope)}
        for changed in result['changed_files']:
            targets = repair_paths(changed)
            if any(not any(p == scope or p.startswith(scope.rstrip('/') + '/') for scope in allowed) for p in targets):
                errors.append('fix changed_files must remain inside fix owner write_paths')
            if any(_paths_overlap(p, document) for p in targets for document in documents):
                errors.append('formal document updates belong to the discoverer, not the finding repair owner')
            if any('tests' in Path(p).parts for p in targets):
                errors.append('discoverer tests must not be rewritten by the finding repair owner')
        if errors:
            raise ControlError(*errors)
        finding.setdefault("fix_history", []).append(copy.deepcopy(result))
    finding["fix_delta"] = result
    acceptance = state.get('workflow_revision') == 3 and _acceptance_finding(state, finding)
    finding["status"] = "awaiting_retest" if acceptance else "awaiting_re_review"
    if state.get('workflow_revision') == 3:
        finding['fixed_after_integration'] = [t['subtask_id'] for t in state['subtasks'] if t.get('stage') == 'integration'][-1]
    action = _set_next(state, "dispatch_ready_subtask" if acceptance else "re_review", finding["lineage"]["original_reviewer"], finding_id=args.FindingId)
    _finish_result(paths, state, args.TaskId, 'finding_fix_recorded', persist, finding_id=args.FindingId)
    return {"ok": True, "finding": finding, "next_action": action}


def _build_review_brief(args: argparse.Namespace, repo: Path, state: dict[str, Any]) -> dict[str, Any]:
    subtask = _find_subtask(state, args.SubtaskId)
    brief: dict[str, Any] = {
        "task_id": state["task_id"],
        "subtask_id": args.SubtaskId,
        "assignment": subtask["assignment"],
        "read_paths": subtask["read_paths"],
        "review_target_sha256": _review_target(repo, state),
        "source_manifest": _source_manifest(repo, state),
    }
    if state.get("workflow_revision") == 3:
        brief["candidate_fingerprint"] = _candidate_fingerprint(repo, state)
        brief["candidate_manifest"] = _candidate_records(repo, state)
    if args.FindingId:
        finding = state.get("findings", {}).get(args.FindingId)
        if not finding:
            raise ControlError(f"unknown finding_id: {args.FindingId}")
        brief["finding"] = finding
    return {"ok": True, "brief": brief}


def _git_output(repo: Path, *arguments: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        check=False,
        text=not binary,
    )
    if completed.returncode != 0:
        stderr = completed.stderr
        if isinstance(stderr, bytes):
            stderr = os.fsdecode(stderr)
        detail = str(stderr).strip() or "git command failed"
        raise ControlError(f"prepare-workspace requires a readable Git checkout: {detail}")
    return completed.stdout


def _safe_relative_path(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = raw.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:/", normalized)
        or any(part in {"", ".."} for part in parts)
    ):
        return None
    return '/'.join(part for part in parts if part != '.') or None


def _workspace_control_paths(state: dict[str, Any]) -> set[str]:
    task_id = state["task_id"]
    paths = {
        f"docs/ai/tasks/{task_id}/{name}" if area == "ai" else f"docs/tasks/{task_id}/{name}"
        for area, name in ARTIFACTS
    }
    paths.add(f"docs/ai/tasks/{task_id}/.control.lock")
    return paths


def _git_dirty_paths(repo: Path, excluded: set[str]) -> list[str]:
    raw = _git_output(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all", binary=True)
    assert isinstance(raw, bytes)
    records = raw.split(b"\0")
    dirty: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        status = record[:2]
        candidates = [record[3:]]
        if (status[:1] in {b"R", b"C"} or status[1:2] in {b"R", b"C"}) and index < len(records):
            candidates.append(records[index])
            index += 1
        for candidate in candidates:
            relative = _safe_relative_path(os.fsdecode(candidate))
            if relative and relative not in excluded:
                dirty.add(relative)
    return sorted(dirty)


def _unfinished_write_paths(state: dict[str, Any], excluded: set[str]) -> list[str]:
    declared: set[str] = set()
    for subtask in state.get("subtasks", []):
        if not isinstance(subtask, dict):
            continue
        if subtask.get("status") == "completed" or subtask.get("role") == "reviewer":
            continue
        for raw in subtask.get("write_paths", []):
            relative = _safe_relative_path(raw)
            if relative and relative not in excluded:
                declared.add(relative.rstrip("/"))
    return sorted(declared)


def _paths_overlap(dirty: str, declared: str) -> bool:
    dirty = _safe_relative_path(dirty) or dirty
    declared = _safe_relative_path(declared) or declared
    return dirty == declared or dirty.startswith(declared + "/") or declared.startswith(dirty + "/")


def _workspace_baseline_hash(repo: Path, relative: str) -> str:
    path = repo / relative
    try:
        path.resolve(strict=False).relative_to(repo)
    except ValueError:
        return _sha({"path": relative, "state": "outside-repository"})
    if path.is_symlink():
        return _sha(os.readlink(path).encode("utf-8"))
    if path.is_file():
        return _sha(path.read_bytes())
    return _sha({"path": relative, "state": "missing"})


def _prepare_workspace(
    args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    top_level = Path(str(_git_output(repo, "rev-parse", "--show-toplevel")).strip()).resolve()
    if top_level != repo:
        raise ControlError("RepoRoot must be the Git checkout root")
    branch = str(_git_output(repo, "branch", "--show-current")).strip() or "detached"
    head = str(_git_output(repo, "rev-parse", "HEAD")).strip()

    def git_path(argument: str) -> Path:
        value = Path(str(_git_output(repo, "rev-parse", argument)).strip())
        return (repo / value).resolve() if not value.is_absolute() else value.resolve()

    checkout_kind = "primary" if git_path("--git-dir") == git_path("--git-common-dir") else "linked_worktree"
    excluded = _workspace_control_paths(state)
    dirty_paths = _git_dirty_paths(repo, excluded)
    write_paths = _unfinished_write_paths(state, excluded)
    write_overlap = sorted(
        dirty for dirty in dirty_paths if any(_paths_overlap(dirty, declared) for declared in write_paths)
    )
    summary = (args.WorkspaceSummary or "").strip()
    if not write_overlap:
        decision = "not_required"
        decision_summary = "No dirty path overlaps an unfinished execution subtask write path."
        baseline_hashes: dict[str, str] = {}
    elif summary:
        decision = "resolved"
        decision_summary = summary
        baseline_hashes = {relative: _workspace_baseline_hash(repo, relative) for relative in write_overlap}
    else:
        decision = "pending"
        decision_summary = "Dirty write overlap captured; rerun with --workspace-summary after explicit authorization."
        baseline_hashes = {}

    candidate = copy.deepcopy(state)
    candidate["workspace"] = {
        "repo_root": "<repo-root>",
        "checkout_kind": checkout_kind,
        "branch": branch,
        "head": head,
        "dirty_paths": dirty_paths,
        "write_overlap": write_overlap,
        "overlap_decision": {
            "status": decision,
            "summary": decision_summary,
            "baseline_hashes": baseline_hashes,
        },
    }
    _write_state(paths, candidate)
    event = "workspace_overlap_pending" if decision == "pending" else "workspace_prepared"
    _append_event(
        paths["events.jsonl"],
        args.TaskId,
        event,
        decision=decision,
        dirty_paths=dirty_paths,
        write_overlap=write_overlap,
    )
    if decision == "pending":
        raise ControlError("workspace overlap requires explicit --workspace-summary authorization")
    return {"ok": True, "task_id": args.TaskId, "decision": decision, "workspace": candidate["workspace"]}


def _set_phase(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    order = ("planning", "doc_sync", "test_sync", "code_impl", "review")
    current = state.get("current_phase")
    target = args.Phase
    blocker = state.get("coordinator_blocker")
    if state.get("workflow_revision") == 3 and (target == "blocked" or blocker):
        if blocker and target != blocker["previous_phase"]:
            raise ControlError("coordinator block can only resume its previous_phase")
        if not blocker and (state.get("status") != "active" or current not in order):
            raise ControlError("only an active normal phase may enter a coordinator block")
        result = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
        errors = _canonical_schema_errors(result, definition="result")
        if errors:
            raise ControlError(*errors)
        if result["written_role"] != "coordinator" or not result["summary"].strip() or not result["verification"]["commands"] or not result["verification"]["result"].strip():
            raise ControlError("coordinator block/resume requires coordinator identity and explicit verification")
        if blocker:
            if result["status"] != "completed" or result["blocked_by"] or result["written_by"] != blocker["result"]["written_by"]:
                raise ControlError("resume requires completed result, empty blocked_by and the same coordinator")
            errors = _checks_errors(result.get("checks"), {"regression"})
            if errors:
                raise ControlError(*errors)
            if any(check["exit_code"] != 0 for check in result["checks"]):
                raise ControlError("coordinator resume checks must all succeed")
        elif result["status"] != "blocked" or not result["blocked_by"] or any(not reason.strip() for reason in result["blocked_by"]):
            raise ControlError("coordinator block requires blocked result and non-empty blocked_by")
        candidate = copy.deepcopy(state)
        if blocker:
            candidate.pop("coordinator_blocker")
        else:
            candidate["coordinator_blocker"] = {"previous_phase": current, "result": result}
        candidate.update(status="active" if blocker else "blocked", current_phase=target)
        _set_next(candidate, "dispatch_ready_subtask")
        _write_state(paths, candidate)
        _append_event(paths["events.jsonl"], args.TaskId, "coordinator_resumed" if blocker else "coordinator_blocked",
                      previous_phase=current, current_phase=target, result=result)
        return {"ok": True, "task_id": args.TaskId, "status": candidate["status"], "previous_phase": current, "current_phase": target,
                "next_action": candidate["next_action"]}
    try:
        expected = order[order.index(current) + 1]
    except (ValueError, IndexError):
        raise ControlError(f"phase cannot advance from {current}")
    if target != expected:
        raise ControlError(f"phase transition must be adjacent: {current} -> {expected}")

    candidate = copy.deepcopy(state)
    candidate["current_phase"] = target
    errors = _canonical_schema_errors(candidate)
    errors.extend(_validate_contract(candidate))
    errors.extend(_semantic_errors(candidate))
    if errors:
        raise ControlError(*errors)

    _write_state(paths, candidate)
    _append_event(paths["events.jsonl"], args.TaskId, "phase_changed", previous_phase=current, current_phase=target)
    return {"ok": True, "task_id": args.TaskId, "current_phase": target}


def _finalize(repo: Path, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if state.get("workflow_revision") == 3:
        errors.extend(_current_acceptance_pass_errors(repo, state))
    verification = state.get("verification_contract")
    if not isinstance(verification, dict):
        errors.append("verification_contract is required before finalization")
    else:
        errors.extend(_required_verification_evidence_errors(repo, state))
    if any(item.get("status") != "closed" for item in state.get("findings", {}).values()):
        errors.append("open findings prevent finalization")
    if state.get("workflow_revision") == 3:
        errors.extend(_review_entry_errors(repo, state))
        errors.extend(_integration_errors(repo, state))
        closeouts = [t for t in state["subtasks"] if t.get("stage") == "final_documentation"]
        if not closeouts or closeouts[-1].get("status") != "completed":
            errors.append("final_documentation facts must complete before finalization")
        errors.extend(_artifact_errors(paths, state))
        if errors:
            raise ControlError(*errors)
        state["status"] = "completed"
        _set_next(state, "none")
        _write_state(paths, state)
        return {"ok": True, "status": "completed", **_session_summary(repo, state)}

def _record_blackbox_decision(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    decision = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    attempt = next((item for item in state.get("acceptance_gate", {}).get("attempts", [])
                    if item.get("attempt_id") == decision.get("attempt_id")), None)
    if not attempt or attempt.get("kind") != "blackbox" or attempt.get("outcome") != "effect_failure":
        raise ControlError("decision requires an existing blackbox effect_failure attempt")
    errors = _canonical_schema_errors(decision, definition="blackboxDecision")
    if errors:
        raise ControlError(*errors)
    decisions = attempt.setdefault("decisions", [])
    if any({key: value for key, value in old.items() if key != "recorded_at"} == decision for old in decisions):
        return {"ok": True, "attempt_id": attempt["attempt_id"], "duplicate": True}
    decision["recorded_at"] = _now()
    decisions.append(decision)
    _set_next(state, 'dispatch_ready_subtask')
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "blackbox_decision_recorded", attempt_id=attempt["attempt_id"])
    return {"ok": True, "attempt_id": attempt["attempt_id"], "decision": decision}


def _preflight(repo: Path, paths: dict[str, Path], state: dict[str, Any], subtask_id: str | None = None) -> dict[str, Any]:
    errors = _validate_state(paths, state)
    if state.get("status") != "active" or state.get("current_phase") not in {
        "doc_sync",
        "test_sync",
        "code_impl",
        "review",
    }:
        errors.append("preflight requires an active task in an execution phase after planning")
    if errors:
        raise ControlError(*errors)

    capability_checks = {t['subtask_id']: _capability_errors(repo, state, t)
                         for t in state['subtasks'] if t.get('status') in {'ready', 'in_progress'}}
    if subtask_id:
        selected = _find_subtask(state, subtask_id)
        capability_failures = _capability_errors(repo, state, selected)
        if capability_failures:
            raise ControlError(*capability_failures)
    checks = []
    for _, name in ARTIFACTS:
        path = paths[name]
        checks.append(
            {
                "name": name,
                "path": path.relative_to(repo).as_posix(),
                "exists": True,
                "sha256": _sha(path.read_bytes()),
            }
        )
    return {
        "ok": True,
        "task_id": state["task_id"],
        "current_phase": state["current_phase"],
        "ready_for_delivery_writes": not any(capability_checks.values()) if not subtask_id else True,
        "capability_checks": capability_checks,
        "ready_subtask_ids": [k for k, v in capability_checks.items() if not v],
        "approved_contract_sha256": state["approval"]["contract_sha256"],
        "next_action": state["next_action"],
        "artifact_checks": {"ok": True, "count": len(checks), "items": checks},
    }


RESULT_ACTIONS = ('record-subtask-result', 'record-review-result', 'record-finding-fix')


def _result_input_errors(action: str, payload: Any) -> list[str]:
    definition = {'record-subtask-result': 'result', 'record-review-result': 'review',
                  'record-finding-fix': 'fixDelta'}.get(action)
    if definition is None:
        return ['result-action must select a supported result contract']
    if action == 'record-review-result':
        if not isinstance(payload, dict) or not isinstance(payload.get('review'), dict):
            return ['result.review is required']
        value = payload['review']
    else:
        value = payload
    errors = _canonical_schema_errors(value, definition=definition)
    if action == 'record-subtask-result' and isinstance(value, dict):
        acceptance = value.get('expensive_acceptance')
        if isinstance(acceptance, dict) and acceptance.get('failed_stage') == '':
            errors.append('expensive_acceptance.failed_stage must use "none" when no stage failed')
    # input_scope is derived by _completed_review_result from the actual findings.
    # Validate the derived value in the same final state validation as formal recording.
    if action == 'record-review-result' and 'input_scope' not in value:
        errors = [e for e in errors if e != "schema $: 'input_scope' is a required property"]
    if action == 'record-review-result':
        # Stored findings include controller-owned counters/history; incoming reports
        # may instead be {finding_id, status: closed}. The review handler resolves
        # these against real findings and validates the complete normalized state.
        errors = [e for e in errors if not e.startswith('schema findings.')]
        if isinstance(value.get('findings'), list):
            for index, finding in enumerate(value['findings']):
                if not isinstance(finding, dict) or not isinstance(finding.get('finding_id'), str) or not finding['finding_id'].strip():
                    errors.append(f'review.findings[{index}] requires a nonempty finding_id')
    return errors


def _finish_result(paths: dict[str, Path], state: dict[str, Any], task_id: str,
                   event: str, persist: bool, **extra: Any) -> None:
    if persist:
        _write_state(paths, state)
        _append_event(paths['events.jsonl'], task_id, event, **extra)
    else:
        errors = _state_model_errors(paths['state.json'].parents[4], state)
        if errors:
            raise ControlError(*errors)


def _validate_result(args: argparse.Namespace, repo: Path, paths: dict[str, Path]) -> dict[str, Any]:
    state = _load_state(paths)
    if state.get('task_id') != args.TaskId or state.get('version') != 3:
        raise ControlError('TaskId/version does not match state.json')
    action = args.ResultAction
    errors = _state_model_errors(repo, state)
    errors.extend(_result_input_errors(action, _json_file_arg(args.ResultJsonFile, 'ResultJsonFile')))
    if errors:
        raise ControlError(*errors)
    candidate = copy.deepcopy(state)
    if action == 'record-subtask-result':
        _record_subtask_result(args, paths, candidate, persist=False)
    elif action == 'record-review-result':
        _record_review(args, repo, paths, candidate, persist=False)
    else:
        _record_fix(args, paths, candidate, persist=False)
    return {'ok': True, 'task_id': args.TaskId, 'result_action': action,
            'ready_for_record': True, 'read_only': True,
            'note': 'Formal recording rechecks current state, candidate and evidence.'}


def _prepare_result(args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    from result_preparation import acceptance_result
    try:
        result = acceptance_result(repo, state, _find_subtask(state, args.SubtaskId),
                                   args.RunManifest, args.ObservationFile)
        _record_subtask_result(args, paths, copy.deepcopy(state), persist=False, result=copy.deepcopy(result))
        relative = _safe_relative_path(args.OutputFile)
        if relative is None or not relative.startswith('.tmp/'):
            raise ValueError('generated result output must be a relative path inside repository .tmp')
        target = repo / relative
        if (not target.resolve().is_relative_to(repo) or
                any(p.is_symlink() for p in (target, *target.parents))):
            raise ValueError('generated result output must not traverse symlinks or escape repository')
        target.parent.mkdir(parents=True, exist_ok=True)
        # Publish only a fully checked draft. Failed preparation preserves an old draft.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='.receipt-', delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
        raise ControlError('cannot prepare result: ' + str(exc)) from exc
    return {'ok': True, 'result_file': relative, 'ready_for_record': True,
            'business_executed': False, 'state_changed': False}


def _complete_task(args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    from result_preparation import base_result
    subtask = _find_subtask(state, args.SubtaskId)
    if subtask.get('stage') != 'final_documentation':
        raise ControlError('complete-task requires the bound final_documentation subtask')
    errors = _validate_state(paths, state) + _current_acceptance_pass_errors(repo, state)
    if errors:
        raise ControlError(*errors)
    # This shortcut only reports already accepted bytes, never judges document semantics.
    current_records = _candidate_records(repo, state)
    current = state['acceptance_gate']['current_candidate']
    if _candidate_fingerprint(repo, state) != current['fingerprint']:
        raise ControlError('complete-task requires unchanged accepted candidate and formal documentation')
    try:
        result = base_result(subtask, _session_summary(repo, state)['summary'],
                             ['validate captured evidence and current acceptance coverage'])
    except ValueError as exc:
        raise ControlError(str(exc)) from exc
    result['documentation_sync'] = {
        'checked_paths': sorted(p for p in current_records if any(point_acceptance.overlap(p, d)
            for d in state['acceptance_gate']['candidate_inputs'].get('document_paths', []))),
        'changed_paths': [], 'behavior_changed': False, 'contract_changed': False,
        'configuration_changed': False,
        'reason': 'Automated byte equality check against the accepted candidate; no semantic changes asserted.'}
    _record_subtask_result(args, paths, state, persist=False, result=result)
    # _finalize rechecks independent review, integration, finding closure, evidence
    # and artifacts before its single write. Failures leave the original state intact.
    completed = _finalize(repo, paths, state)
    _append_event(paths['events.jsonl'], args.TaskId, 'facts_closeout_completed', subtask_id=args.SubtaskId)
    return completed


def _run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.Action:
        raise ControlError("Action is required")
    if args.Action == "new-task":
        return _new_task(args)
    if not args.RepoRoot or not args.TaskId:
        raise ControlError("RepoRoot and TaskId are required for this Action")
    repo = Path(args.RepoRoot).resolve()
    paths = _task_paths(repo, args.TaskId)
    if args.Action == 'acceptance-status':
        state = _load_state(paths)
        if state.get('task_id') != args.TaskId or state.get('checkout_binding') != _sha(str(repo)):
            raise ControlError('acceptance status task/checkout binding mismatch')
        return point_acceptance.coverage(repo, state, _candidate_records(repo, state))
    if args.Action == 'validate-result':
        return _validate_result(args, repo, paths)
    if args.Action == "init-task":
        _require_contract_in_repo_tmp(repo, args.ContractJsonFile)
        if paths["state.json"].exists():
            raise ControlError("task already exists")
        state, rendered = _initial_state(args, repo)
        with _task_lock(repo, args.TaskId), _preserve_artifacts_on_io_failure(paths):
            return _init(args, paths, state, rendered)
    if args.Action == "preflight":
        state = _load_state(paths)
        if state.get("task_id") != args.TaskId:
            raise ControlError("TaskId does not match state.json")
        if state.get("version") != 3:
            raise ControlError("state.json version must be 3")
        return _preflight(repo, paths, state, args.SubtaskId)
    with _task_lock(repo, args.TaskId), _preserve_artifacts_on_io_failure(paths):
        state = _load_state(paths)
        if state.get("task_id") != args.TaskId:
            raise ControlError("TaskId does not match state.json")
        if state.get("version") != 3:
            raise ControlError("state.json version must be 3")
        if args.Action == "validate":
            errors = _validate_state(paths, state)
            if errors:
                raise ControlError(*errors)
            return {"ok": True, "task_id": args.TaskId, "status": state["status"], "current_phase": state["current_phase"], "next_action": state["next_action"], **_session_summary(repo, state)}
        if args.Action != "build-review-brief":
            errors = _state_model_errors(
                repo,
                state,
                include_candidate_staleness=args.Action not in {
                    "freeze-candidate", "record-acceptance-impact",
                },
            )
            if errors:
                raise ControlError(*errors)
        if state.get("coordinator_blocker") and args.Action not in {
            "set-phase", "build-review-brief", "accept-artifact-update", "record-subtask-result", "record-review-result",
            "record-acceptance-findings", "record-finding-fix", "record-blackbox-decision", "extend-acceptance-budget",
            "record-verification-evidence", "record-capability-probe", "capture-capability-context",
        }:
            raise ControlError("coordinator block prevents new execution, candidate/attempt creation and finalization; explicitly resume first")
        if _latest_effect_failure(state):
            if args.Action in {'finalize-task', 'complete-task'}:
                raise ControlError('effect failure stop prevents finalization until authorized acceptance passes')
            if args.Action in {'create-integration-subtask', 'dispatch-finding-fix'} and not _effect_permission(state, 'repair'):
                raise ControlError('effect failure stop requires an explicit user repair decision')
            if args.Action == 'bind-dispatch' and _is_product_task(_find_subtask(state, args.SubtaskId)):
                if not _effect_permission(state, 'repair'):
                    raise ControlError('effect failure stop requires an explicit user repair decision')
                original = next((t.get('dispatch') for t in state['subtasks'] if t.get('stage') == 'integration' and t.get('dispatch')), {})
                if args.PlatformAgentId != original.get('platform_agent_id') or args.AgentKey != original.get('agent_key'):
                    raise ControlError('effect repair must retain the original integration identity')
        if args.Action == 'prepare-result':
            return _prepare_result(args, repo, paths, state)
        if args.Action == 'complete-task':
            return _complete_task(args, repo, paths, state)
        if args.Action == "accept-artifact-update":
            return _accept_artifact_update(args, paths, state)
        if args.Action == "capture-capability-context":
            task = _find_subtask(state, args.SubtaskId)
            declarations = _scoped_capabilities(state, task)
            if declarations and not args.PlatformAgentId:
                raise ControlError('capability capture requires actual executor --platform-agent-id')
            return {'ok': True, 'captures': {
                d['capability_id']: _capture_capability_context(repo, d, args.PlatformAgentId)
                for d in declarations}}
        if args.Action == "record-capability-probe":
            task = _find_subtask(state, args.SubtaskId)
            payload = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
            try:
                receipt = _capability_receipt(repo, task, payload)
            except (ValueError, OSError, TypeError, KeyError) as exc:
                raise ControlError(str(exc)) from exc
            receipts = state.setdefault('capability_receipts', [])
            if any(r['subtask_id'] == receipt['subtask_id'] and r['capability_id'] == receipt['capability_id']
                   and r['evidence']['sha256'] == receipt['evidence']['sha256'] for r in receipts):
                raise ControlError('probe evidence already registered; run a new probe')
            latest = next((r for r in reversed(receipts) if r['subtask_id'] == receipt['subtask_id']
                           and r['capability_id'] == receipt['capability_id']), None)
            if latest and dt.datetime.fromisoformat(receipt['recorded_at']) <= dt.datetime.fromisoformat(latest['recorded_at']):
                raise ControlError('probe observation must be newer than the latest registered probe')
            receipts.append(receipt)
            _write_state(paths, state)
            _append_event(paths['events.jsonl'], args.TaskId, 'capability_probe_recorded',
                          subtask_id=task['subtask_id'], capability_id=receipt['capability_id'], status=receipt['status'])
            return {'ok': True, 'receipt': receipt}
        if args.Action == "record-blackbox-decision":
            return _record_blackbox_decision(args, paths, state)
        if args.Action == "extend-acceptance-budget":
            return _extend_acceptance_budget(args, repo, paths, state)
        if args.Action == "bind-dispatch":
            return _bind(args, paths, state)
        if args.Action == "record-subtask-result":
            return _record_subtask_result(args, paths, state)
        if args.Action == "record-verification-evidence":
            return _record_verification_evidence(args, repo, paths, state)
        if args.Action == "record-acceptance-evidence-batch":
            return _record_acceptance_evidence_batch(args, repo, paths, state)
        if args.Action == 'record-acceptance-impact':
            try:
                receipt = point_acceptance.record_impact(repo, state,
                    _json_file_arg(args.ResultJsonFile, 'ResultJsonFile'), _candidate_records(repo, state))
            except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
                raise ControlError('acceptance impact: ' + str(exc)) from exc
            _write_state(paths, state)
            _append_event(paths['events.jsonl'], args.TaskId, 'acceptance_impact_recorded',
                          source_attempt_id=receipt['source_attempt_id'], point_ids=receipt['point_ids'])
            return {'ok': True, 'receipt': receipt}
        if args.Action == "record-acceptance-coverage":
            return _record_acceptance_coverage(args, repo, paths, state)
        if args.Action == "record-acceptance-findings":
            return _record_acceptance_findings(args, paths, state)
        if args.Action == "create-integration-subtask":
            return _create_integration_subtask(args, paths, state)
        if args.Action == "record-review-result":
            return _record_review(args, repo, paths, state)
        if args.Action == "create-re-review-subtask":
            return _create_re_review_subtask(args, paths, state)
        if args.Action == "dispatch-finding-fix":
            return _dispatch_fix(args, paths, state)
        if args.Action == "record-finding-fix":
            return _record_fix(args, paths, state)
        if args.Action == "build-review-brief":
            return _build_review_brief(args, repo, state)
        if args.Action == "prepare-workspace":
            return _prepare_workspace(args, repo, paths, state)
        if args.Action == "set-phase":
            return _set_phase(args, paths, state)
        if args.Action == "freeze-candidate":
            return _freeze_candidate(args, repo, paths, state)
        if args.Action == "create-subtask-attempt":
            return _create_subtask_attempt(args, repo, paths, state)
        if args.Action == 'withdraw-subtask-attempt':
            return _withdraw_attempt(args, paths, state)
        if args.Action == "finalize-task":
            return _finalize(repo, paths, state)
        raise ControlError(f"unsupported Action: {args.Action}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, allow_abbrev=False)
    parser.add_argument(
        "--action",
        dest="Action",
        choices=(
            "new-task",
            "init-task",
            "validate",
            "preflight",
            "validate-result",
            "prepare-result", "complete-task",
            "accept-artifact-update",
            "bind-dispatch",
            "record-subtask-result",
            "record-verification-evidence",
            "record-acceptance-evidence-batch",
            "record-acceptance-coverage",
            "record-blackbox-decision",
            "record-capability-probe", "capture-capability-context",
            "extend-acceptance-budget",
            "record-review-result", "record-acceptance-findings", "create-integration-subtask",
            "create-re-review-subtask",
            "dispatch-finding-fix",
            "record-finding-fix",
            "build-review-brief",
            "prepare-workspace",
            "set-phase",
            "freeze-candidate",
            "create-subtask-attempt",
            "acceptance-status", "withdraw-subtask-attempt", "record-acceptance-impact",
            "finalize-task",
        ),
        help=(
            "new-task, init-task, validate, preflight, accept-artifact-update, bind-dispatch, "
            "record-subtask-result, record-verification-evidence, record-acceptance-evidence-batch, "
            "record-acceptance-coverage, record-review-result, extend-acceptance-budget, dispatch-finding-fix, "
            "create-re-review-subtask, create-final-review-subtask, record-finding-fix, "
            "build-review-brief, prepare-workspace, set-phase, "
            "freeze-candidate, create-subtask-attempt, finalize-task, "
        ),
    )
    parser.add_argument("--repo-root", dest="RepoRoot")
    parser.add_argument("--task-id", dest="TaskId")
    parser.add_argument("--json", dest="Json", action="store_true")
    parser.add_argument("--subtask-id", dest="SubtaskId")
    parser.add_argument("--attempt-kind", dest="AttemptKind", choices=("ordinary", "preparation", "blackbox"), default="ordinary")
    parser.add_argument("--finding-id", dest="FindingId")
    parser.add_argument("--result-json-file", dest="ResultJsonFile")
    parser.add_argument('--run-manifest', dest='RunManifest', help='Captured manifest path relative to repo-root.')
    parser.add_argument('--observation-file', dest='ObservationFile', help='Observation summary sealed by the same run.')
    parser.add_argument('--output-file', dest='OutputFile', help='Generated receipt path inside repository .tmp.')
    parser.add_argument("--contract-json-file", dest="ContractJsonFile")
    parser.add_argument("--title", dest="Title")
    parser.add_argument("--owner", dest="Owner")
    parser.add_argument("--agent-key", dest="AgentKey")
    parser.add_argument("--platform-agent-id", dest="PlatformAgentId")
    parser.add_argument('--result-action', dest='ResultAction', choices=RESULT_ACTIONS,
                        help='For validate-result: the formal result action to preflight without writes.')
    parser.add_argument("--context-mode", dest="ContextMode", choices=("isolated",))
    parser.add_argument("--brief-kind", dest="BriefKind", choices=("subtask", "review"))
    parser.add_argument("--brief-sha256", dest="BriefSha256")
    parser.add_argument("--brief-path", dest="BriefPath")
    parser.add_argument("--slug", dest="Slug")
    parser.add_argument(
        "--phase",
        dest="Phase",
        choices=("planning", "doc_sync", "test_sync", "code_impl", "review", "blocked"),
    )
    parser.add_argument("--workspace-summary", dest="WorkspaceSummary")
    parser.add_argument("--approval-by", dest="ApprovalBy")
    parser.add_argument("--approval-reason", dest="ApprovalReason")
    return parser


def main() -> int:
    try:
        payload = _run(_parser().parse_args())
        code = 0
    except ControlError as exc:
        payload = {"ok": False, "errors": exc.errors}
        code = 2
    except Exception as exc:  # Keep the CLI's stdout contract even for defects.
        payload = {"ok": False, "errors": [f"internal error: {type(exc).__name__}: {exc}"]}
        code = 3
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
