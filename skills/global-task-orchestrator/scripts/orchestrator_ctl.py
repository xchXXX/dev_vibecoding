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
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator, FormatChecker


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
    schema_errors = _canonical_schema_errors(state)
    if schema_errors:
        raise ControlError(*schema_errors)
    rendered = _render_artifacts(state["task_id"], state["title"], state)
    action = state.get("next_action", {}).get("kind", "not_initialized")
    task_body = (
        f"- status: `{state.get('status', 'draft')}`\n"
        f"- current_phase: `{state.get('current_phase', 'planning')}`\n"
        f"- next_action: `{action}`"
    )
    conclusion = (
        "独立 final/pass 已覆盖最新 scoped source manifest，任务完成。"
        if state.get("status") == "completed"
        else "任务尚未完成，不得宣称 final/pass。"
    )
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


def _load_state(paths: dict[str, Path]) -> dict[str, Any]:
    try:
        value = json.loads(paths["state.json"].read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlError("state.json does not exist") from exc
    except json.JSONDecodeError as exc:
        raise ControlError(f"state.json is invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ControlError("state.json root must be an object")
    return value


def _require_text(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")


def _require_text_list(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{name} must be a non-empty string list")


def _validate_contract(contract: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["contract must be an object"]
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
    return errors


def _contract_hash(state: dict[str, Any]) -> str:
    return _sha(state.get("six_points"))


def _render_artifacts(task_id: str, title: str, contract: dict[str, Any]) -> dict[str, str]:
    points = contract["six_points"]

    def bullets(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values)

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
    plan = (
        header
        + f"\n## 任务目标\n\n{points['do']}\n"
        + "\n## 背景与问题\n\n当前任务已由用户确认六要点，需要以文档、测试、实现和审查证据保持同一目标。\n"
        + f"\n## 范围\n\n{bullets(points['change_areas'])}\n"
        + f"\n## 非目标\n\n{bullets(points['do_not'])}\n"
        + f"\n## 约束与依赖\n\n{bullets(points['risks'])}\n"
        + f"\n## 方案摘要\n\n{points['implementation']}\n"
        + f"\n## 风险与回退\n\n{bullets(points['risks'])}\n"
        + f"\n## 验收标准\n\n{bullets(points['acceptance'])}\n"
        + "\n## 阶段划分\n\n1. 文档与测试先行。\n2. 按互斥写入范围实施。\n3. 统一验证并进入 review / fix / re-review。\n"
        + "\n## 需先同步的核心文档与测试\n\n- 同步任务涉及的长期真源文档。\n- 建立能直接命中目标问题的最小测试。\n"
    )
    execution = (
        header
        + f"\n## 施工目标\n\n{points['do']}\n"
        + "\n## 前置条件\n\n- 用户已确认六要点任务合同。\n- 写入前已冻结范围、验收和风险。\n"
        + f"\n## 执行顺序\n\n{points['implementation']}\n"
        + "\n## 文档先行清单\n\n- 先同步长期真源和任务施工文档。\n"
        + "\n## 测试同步清单\n\n- 先建立最小 Red，再实施 Green 和相关回归。\n"
        + f"\n## 实施批次\n\n{bullets(points['change_areas'])}\n"
        + f"\n## 每批写入范围\n\n{bullets(points['change_areas'])}\n"
        + f"\n## 验证命令\n\n{bullets(points['acceptance'])}\n"
        + f"\n## 回退方案\n\n{bullets(points['risks'])}\n"
        + "\n## 审查与返工路径\n\n独立 reviewer 记录稳定 finding_id；原实现者修复，同一 reviewer re-review，直至可验收。\n"
    )
    conclusion = (
        "独立 final/pass 已覆盖最新 scoped source manifest，任务完成。"
        if contract.get("status") == "completed"
        else "任务尚未完成，不得宣称 final/pass。"
    )
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
    conclusion = (
        "独立 final/pass 已覆盖最新 scoped source manifest，任务完成。"
        if state.get("status") == "completed"
        else "任务尚未完成，不得宣称 final/pass。"
    )
    acceptance_text = paths["acceptance.md"].read_text(encoding="utf-8") if paths["acceptance.md"].is_file() else ""
    if conclusion not in acceptance_text:
        errors.append("acceptance.md current conclusion is stale")
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


def _canonical_schema_errors(state: dict[str, Any]) -> list[str]:
    schema_path = Path(__file__).resolve().parents[3] / "schemas" / "orchestrator-task-state.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlError(f"canonical state schema is unavailable: {exc}") from exc
    if not isinstance(schema, dict):
        raise ControlError("canonical state schema root must be an object")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ControlError(f"canonical state schema is invalid: {exc}") from exc
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    errors = sorted(
        validator.iter_errors(state),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return [
        f"schema {'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in errors
    ]


def _validate_state(paths: dict[str, Path], state: dict[str, Any]) -> list[str]:
    errors = _canonical_schema_errors(state)
    errors.extend(_validate_contract(state))
    errors.extend(_semantic_errors(state))
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
        if item.get("status") == "completed" and any(statuses.get(dep) != "completed" for dep in dependencies):
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
    if state.get("approval", {}).get("contract_sha256") != _contract_hash(state):
        errors.append("approval is stale because the six-point contract changed")
    errors.extend(_artifact_errors(paths, state))
    return errors


def _semantic_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    phases = {"planning", "doc_sync", "test_sync", "code_impl", "review", "blocked"}
    if state.get("current_phase") not in phases:
        errors.append("current_phase is not a valid v3 phase")
    if state.get("status") not in {"active", "blocked", "completed"}:
        errors.append("status is not valid for v3")
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
        required = set(verification.get("review_evidence", [])) - {"independent_final_review"}
        observed = _observed_pre_final_evidence(state, required)
        missing = sorted(required - observed)
        if missing:
            errors.append("verification evidence is missing before review: " + ", ".join(missing))
    return errors


def _observed_pre_final_evidence(state: dict[str, Any], required: set[str]) -> set[str]:
    observed: set[str] = set()
    for subtask in state.get("subtasks", []):
        if not isinstance(subtask, dict) or subtask.get("status") != "completed" or subtask.get("role") == "reviewer":
            continue
        evidence = subtask.get("result", {}).get("review_evidence", {})
        if isinstance(evidence, dict):
            observed.update(key for key, value in evidence.items() if key in required and value)
    return observed


def _find_subtask(state: dict[str, Any], subtask_id: str | None) -> dict[str, Any]:
    for subtask in state.get("subtasks", []):
        if subtask.get("subtask_id") == subtask_id:
            return subtask
    raise ControlError(f"unknown subtask_id: {subtask_id}")


def _identity(dispatch: dict[str, Any]) -> dict[str, str]:
    return {"agent_key": dispatch["agent_key"], "platform_agent_id": dispatch["platform_agent_id"]}


def _final_reviewer(state: dict[str, Any]) -> dict[str, str] | None:
    for item in state.get("subtasks", []):
        if item.get("dispatch") and item.get("role") == "reviewer" and "final" in item.get("title", "").lower():
            return _identity(item["dispatch"])
    return None


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


def _set_next(state: dict[str, Any], kind: str, target: dict[str, str] | None = None, **extra: Any) -> dict[str, Any]:
    action = {"kind": kind, **extra}
    if target is not None:
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


def _initial_state(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, str]]:
    contract = _json_file_arg(args.ContractJsonFile, "ContractJsonFile")
    errors = _validate_contract(contract)
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
                "require_independent_final_review": True,
                "scope_expansion_requires_escalation": True,
            },
            "findings": {},
            "next_action": {"kind": "dispatch_ready_subtask"},
        }
    )
    state["approval"] = copy.deepcopy(contract["approval"])
    state["approval"]["contract_sha256"] = _contract_hash(state)
    state["approval"]["approved_at"] = _now()
    rendered = _render_artifacts(args.TaskId, args.Title, state)
    state["artifact_sha256"] = {name: _sha(text.encode("utf-8")) for name, text in rendered.items()}
    state["updated_at"] = _now()
    schema_errors = _canonical_schema_errors(state)
    if schema_errors:
        raise ControlError(*schema_errors)
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


def _bind(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    subtask = _find_subtask(state, args.SubtaskId)
    required = (args.AgentKey, args.PlatformAgentId, args.ContextMode, args.BriefKind, args.BriefSha256)
    if not all(required) or not re.fullmatch(r"[0-9a-f]{64}", args.BriefSha256 or ""):
        raise ControlError("dispatch binding fields and a lowercase sha256 are required")
    subtask["dispatch"] = {
        "agent_key": args.AgentKey,
        "platform_agent_id": args.PlatformAgentId,
        "context_mode": args.ContextMode,
        "brief_kind": args.BriefKind,
        "brief_sha256": args.BriefSha256,
    }
    subtask["status"] = "in_progress"
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "dispatch_bound", subtask_id=args.SubtaskId)
    return {"ok": True, "subtask_id": args.SubtaskId, "dispatch": subtask["dispatch"]}


def _record_subtask_result(
    args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]
) -> dict[str, Any]:
    subtask = _find_subtask(state, args.SubtaskId)
    dispatch = subtask.get("dispatch")
    if not dispatch or subtask.get("status") != "in_progress":
        raise ControlError("subtask result requires an active bound dispatch")
    result = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
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
    subtask["result"] = result
    subtask["status"] = result["status"]
    action = _set_next(state, "dispatch_ready_subtask")
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "subtask_result_recorded", subtask_id=args.SubtaskId)
    return {"ok": True, "subtask_id": args.SubtaskId, "status": subtask["status"], "next_action": action}


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
        "written_role": subtask["role"],
        "review": normalized_review,
    }


def _record_review(args: argparse.Namespace, repo: Path, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    subtask = _find_subtask(state, args.SubtaskId)
    result = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    review = result.get("review") if isinstance(result, dict) else None
    if not isinstance(review, dict):
        raise ControlError("result.review is required")
    dispatch = subtask.get("dispatch")
    if not dispatch or review.get("reviewer_platform_agent_id") != dispatch.get("platform_agent_id"):
        raise ControlError("reviewer identity does not match the bound dispatch")
    kind = review.get("kind")
    findings = review.get("findings")
    if kind not in ("task", "re_review", "final") or not isinstance(findings, list):
        raise ControlError("review.kind and review.findings are invalid")
    if kind == "final" and review.get("verdict") == "pass":
        if findings:
            raise ControlError("final/pass cannot contain findings")
        target = _review_target(repo, state)
        if review.get("reviewed_change_sha256") != target:
            raise ControlError("final review does not cover the latest change hash")
        implementer_ids = {
            item.get("dispatch", {}).get("platform_agent_id")
            for item in state.get("subtasks", [])
            if item.get("role") != "reviewer"
        }
        if dispatch.get("platform_agent_id") in implementer_ids:
            raise ControlError("final reviewer must be independent")
        state["final_review"] = {
            "verdict": "pass",
            "reviewer": _identity(dispatch),
            "reviewed_change_sha256": target,
        }
        subtask["result"] = _completed_review_result(subtask, dispatch, review, state)
        subtask["status"] = "completed"
        action = _set_next(state, "finalize")
    else:
        passing_re_review = kind == "re_review" and review.get("verdict") == "pass"
        if (not passing_re_review and review.get("verdict") != "fail") or not findings:
            raise ControlError("a non-passing review must be fail with findings")
        reviewer = _identity(dispatch)
        for reported in findings:
            if not isinstance(reported, dict) or not reported.get("finding_id"):
                raise ControlError("each finding requires finding_id")
            finding_id = reported["finding_id"]
            existing = state["findings"].get(finding_id)
            if existing is None:
                if kind == "re_review":
                    raise ControlError(f"re-review references unknown finding_id: {finding_id}")
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
                state["findings"][finding_id] = existing
            else:
                if kind != "re_review":
                    raise ControlError(f"finding_id already exists outside re-review: {finding_id}")
                if reviewer != existing["lineage"]["original_reviewer"]:
                    raise ControlError(f"finding {finding_id} must return to original_reviewer")
                if passing_re_review and reported.get("status") != "closed":
                    raise ControlError(f"passing re-review must report status=closed: {finding_id}")
                if reported.get("status") == "closed":
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
            action = _set_next(state, "final_review", _final_reviewer(state))
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "review_recorded", subtask_id=args.SubtaskId, kind=kind)
    return {"ok": True, "next_action": action}


def _dispatch_fix(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    finding = state.get("findings", {}).get(args.FindingId)
    if not finding or finding.get("status") not in ("open", "fix_dispatched"):
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


def _record_fix(args: argparse.Namespace, paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    finding = state.get("findings", {}).get(args.FindingId)
    if not finding or finding.get("status") != "fix_dispatched":
        raise ControlError(f"finding has no active fix dispatch: {args.FindingId}")
    result = _json_file_arg(args.ResultJsonFile, "ResultJsonFile")
    required = ("summary", "changed_files", "sha256", "verification")
    if not isinstance(result, dict) or any(key not in result for key in required):
        raise ControlError("finding fix result is incomplete")
    if not re.fullmatch(r"[0-9a-f]{64}", str(result.get("sha256", ""))):
        raise ControlError("finding fix sha256 is invalid")
    finding["fix_delta"] = result
    finding["status"] = "awaiting_re_review"
    action = _set_next(state, "re_review", finding["lineage"]["original_reviewer"], finding_id=args.FindingId)
    _write_state(paths, state)
    _append_event(paths["events.jsonl"], args.TaskId, "finding_fix_recorded", finding_id=args.FindingId)
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
    return normalized


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
    verification = state.get("verification_contract")
    if not isinstance(verification, dict):
        errors.append("verification_contract is required before finalization")
    else:
        required_evidence = set(verification.get("review_evidence", [])) - {"independent_final_review"}
        observed = _observed_pre_final_evidence(state, required_evidence)
        missing = sorted(required_evidence - observed)
        if missing:
            errors.append("verification evidence is missing: " + ", ".join(missing))
    if any(item.get("status") != "closed" for item in state.get("findings", {}).values()):
        errors.append("open findings prevent finalization")
    final = state.get("final_review")
    if not final or final.get("verdict") != "pass":
        errors.append("independent final/pass is required")
    elif final.get("reviewed_change_sha256") != _review_target(repo, state):
        errors.append("independent final/pass is stale")
    if errors:
        raise ControlError(*errors)
    state["status"] = "completed"
    _set_next(state, "none")
    _write_state(paths, state)
    return {"ok": True, "status": "completed"}


def _run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.Action:
        raise ControlError("Action is required")
    if args.Action == "new-task":
        return _new_task(args)
    if not args.RepoRoot or not args.TaskId:
        raise ControlError("RepoRoot and TaskId are required for this Action")
    repo = Path(args.RepoRoot).resolve()
    paths = _task_paths(repo, args.TaskId)
    if args.Action == "init-task":
        if paths["state.json"].exists():
            raise ControlError("task already exists")
        state, rendered = _initial_state(args)
        with _task_lock(repo, args.TaskId):
            return _init(args, paths, state, rendered)
    with _task_lock(repo, args.TaskId):
        state = _load_state(paths)
        if state.get("task_id") != args.TaskId:
            raise ControlError("TaskId does not match state.json")
        if state.get("version") != 3:
            raise ControlError("state.json version must be 3")
        if args.Action == "validate":
            errors = _validate_state(paths, state)
            if errors:
                raise ControlError(*errors)
            return {"ok": True, "task_id": args.TaskId, "status": state["status"], "next_action": state["next_action"]}
        if args.Action == "accept-artifact-update":
            return _accept_artifact_update(args, paths, state)
        if args.Action == "bind-dispatch":
            return _bind(args, paths, state)
        if args.Action == "record-subtask-result":
            return _record_subtask_result(args, paths, state)
        if args.Action == "record-review-result":
            return _record_review(args, repo, paths, state)
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
            "accept-artifact-update",
            "bind-dispatch",
            "record-subtask-result",
            "record-review-result",
            "dispatch-finding-fix",
            "record-finding-fix",
            "build-review-brief",
            "prepare-workspace",
            "set-phase",
            "finalize-task",
        ),
        help=(
            "new-task, init-task, validate, accept-artifact-update, bind-dispatch, "
            "record-subtask-result, record-review-result, dispatch-finding-fix, "
            "record-finding-fix, build-review-brief, prepare-workspace, set-phase, finalize-task"
        ),
    )
    parser.add_argument("--repo-root", dest="RepoRoot")
    parser.add_argument("--task-id", dest="TaskId")
    parser.add_argument("--json", dest="Json", action="store_true")
    parser.add_argument("--subtask-id", dest="SubtaskId")
    parser.add_argument("--finding-id", dest="FindingId")
    parser.add_argument("--result-json-file", dest="ResultJsonFile")
    parser.add_argument("--contract-json-file", dest="ContractJsonFile")
    parser.add_argument("--title", dest="Title")
    parser.add_argument("--owner", dest="Owner")
    parser.add_argument("--agent-key", dest="AgentKey")
    parser.add_argument("--platform-agent-id", dest="PlatformAgentId")
    parser.add_argument("--context-mode", dest="ContextMode", choices=("isolated",))
    parser.add_argument("--brief-kind", dest="BriefKind", choices=("subtask", "review"))
    parser.add_argument("--brief-sha256", dest="BriefSha256")
    parser.add_argument("--slug", dest="Slug")
    parser.add_argument(
        "--phase",
        dest="Phase",
        choices=("planning", "doc_sync", "test_sync", "code_impl", "review", "blocked"),
    )
    parser.add_argument("--workspace-summary", dest="WorkspaceSummary")
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
