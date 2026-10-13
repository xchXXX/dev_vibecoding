"""Deterministic validation for append-only acceptance evidence batches."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


SHA256 = re.compile(r"[0-9a-f]{64}")


class BatchEvidenceError(ValueError):
    """A batch or coverage payload does not satisfy the frozen contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(data).hexdigest()


def _relative(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise BatchEvidenceError("batch reference path must be a non-empty repository-relative path")
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
        raise BatchEvidenceError("batch reference path must be a safe repository-relative path")
    return "/".join(part for part in parts if part != ".")


def _file(repo: Path, ref: Any, *, pointer: bool, json_required: bool = True) -> tuple[Path, Any]:
    required = {"path", "sha256"} | ({"pointer"} if pointer else set())
    allowed = required | ({"pointer"} if not pointer else set())
    if not isinstance(ref, dict) or not required.issubset(ref) or set(ref) - allowed:
        raise BatchEvidenceError("batch reference fields are invalid")
    relative = _relative(ref["path"])
    if relative.startswith(".tmp/"):
        raise BatchEvidenceError("batch evidence must be retained outside .tmp")
    expected = ref.get("sha256")
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        raise BatchEvidenceError("batch reference sha256 is invalid")
    path = repo / relative
    if any(p.is_symlink() for p in (path, *path.parents) if p != repo.parent):
        raise BatchEvidenceError("batch reference must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(repo.resolve())
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        raise BatchEvidenceError("batch reference is missing or outside the repository") from exc
    if not resolved.is_file() or digest(resolved.read_bytes()) != expected:
        raise BatchEvidenceError("batch reference file hash does not match")
    if not json_required:
        return resolved, None
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchEvidenceError("batch reference must be valid UTF-8 JSON") from exc
    return resolved, document


def _tokens(pointer: Any) -> list[str]:
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise BatchEvidenceError("batch JSON pointer is invalid")
    if not pointer:
        return []
    values: list[str] = []
    for token in pointer[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", token):
            raise BatchEvidenceError("batch JSON pointer escape is invalid")
        values.append(token.replace("~1", "/").replace("~0", "~"))
    return values


def _select(document: Any, pointer: Any) -> Any:
    value = document
    for token in _tokens(pointer):
        if isinstance(value, list):
            if not token.isdigit() or int(token) >= len(value):
                raise BatchEvidenceError("batch JSON pointer does not resolve")
            value = value[int(token)]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise BatchEvidenceError("batch JSON pointer does not resolve")
    return value


def _value(repo: Path, ref: Any) -> tuple[Any, Any]:
    _, document = _file(repo, ref, pointer=True)
    return document, _select(document, ref["pointer"])


def _attempt(state: dict[str, Any], attempt_id: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    attempt = next(
        (
            item
            for item in state.get("acceptance_gate", {}).get("attempts", [])
            if isinstance(item, dict) and item.get("attempt_id") == attempt_id
        ),
        None,
    )
    if attempt is None:
        raise BatchEvidenceError("batch source attempt does not exist")
    source = next(
        (
            item
            for item in state.get("subtasks", [])
            if isinstance(item, dict) and item.get("subtask_id") == attempt.get("subtask_id")
        ),
        None,
    )
    if source is None or source.get("stage") != "expensive_acceptance" or not source.get("dispatch"):
        raise BatchEvidenceError("batch source attempt is not a bound acceptance subtask")
    return attempt, source


def _required_acceptance_ids(gate: dict[str, Any], kind: str) -> set[str]:
    all_ids = {item.get("acceptance_id") for item in gate.get("acceptance_items", [])}
    blackbox = set(gate.get("blackbox_acceptance_ids", []))
    return blackbox if kind == "blackbox" else all_ids - blackbox


def _contract(
    repo: Path,
    ref: Any,
    state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    _, contract = _file(repo, ref, pointer=False)
    if not isinstance(contract, dict) or set(contract) != {"kind", "fixture", "required_units"}:
        raise BatchEvidenceError("batch contract fields are invalid")
    kind = contract.get("kind")
    if kind not in {"ordinary", "blackbox"}:
        raise BatchEvidenceError("batch contract kind must be ordinary or blackbox")
    fixture = contract.get("fixture")
    if not isinstance(fixture, dict) or set(fixture) != {
        "path", "sha256", "collection_pointer", "id_pointer"
    }:
        raise BatchEvidenceError("batch fixture contract is invalid")
    _, fixture_document = _file(repo, {"path": fixture["path"], "sha256": fixture["sha256"]}, pointer=False)
    collection = _select(fixture_document, fixture["collection_pointer"])
    if not isinstance(collection, list) or not collection:
        raise BatchEvidenceError("batch fixture collection must be a non-empty array")
    fixture_units: dict[str, Any] = {}
    for item in collection:
        unit_id = _select(item, fixture["id_pointer"])
        if not isinstance(unit_id, str) or not unit_id or unit_id in fixture_units:
            raise BatchEvidenceError("batch fixture unit IDs must be non-empty and unique")
        fixture_units[unit_id] = item
    required = contract.get("required_units")
    if not isinstance(required, list) or not required:
        raise BatchEvidenceError("batch contract required_units must be non-empty")
    by_id: dict[str, dict[str, Any]] = {}
    for item in required:
        if not isinstance(item, dict) or set(item) != {
            "unit_id", "acceptance_id", "current_input", "raw_selectors"
        }:
            raise BatchEvidenceError("batch contract unit fields are invalid")
        unit_id = item.get("unit_id")
        current_input = item.get("current_input")
        pointers = current_input.get("pointers") if isinstance(current_input, dict) else None
        if (
            unit_id in by_id
            or unit_id not in fixture_units
            or not isinstance(pointers, dict)
            or not pointers
            or any(not isinstance(name, str) or not name or not isinstance(pointer, str) for name, pointer in pointers.items())
        ):
            raise BatchEvidenceError("batch contract current input mapping is invalid")
        for pointer in pointers.values():
            _select(fixture_units[unit_id], pointer)
        selectors = item.get("raw_selectors")
        if selectors is not None:
            if not isinstance(selectors, dict) or set(selectors) != {
                "unit_id", "execution_status", "executed_values"
            }:
                raise BatchEvidenceError("batch contract raw selectors are invalid")
            if any(
                not isinstance(selectors.get(name), str)
                for name in ("unit_id", "execution_status")
            ):
                raise BatchEvidenceError("batch contract raw selector pointers are invalid")
            executed_values = selectors.get("executed_values")
            if (
                not isinstance(executed_values, list)
                or not executed_values
                or any(type(value) not in {str, bool} for value in executed_values)
                or len({canonical(value) for value in executed_values}) != len(executed_values)
            ):
                raise BatchEvidenceError("batch contract executed values are invalid")
        by_id[unit_id] = item
    if set(by_id) != set(fixture_units):
        raise BatchEvidenceError("batch contract must cover the complete fixture collection")
    expected_acceptance = _required_acceptance_ids(state["acceptance_gate"], kind)
    if {item["acceptance_id"] for item in required} != expected_acceptance:
        raise BatchEvidenceError("batch contract must cover all acceptance IDs for its kind")
    return contract, by_id, fixture_units


def _projection(document: Any, pointers: dict[str, Any]) -> dict[str, Any]:
    return {name: _select(document, pointer) for name, pointer in sorted(pointers.items())}


def _prefix(prefix: list[str], value: list[str]) -> bool:
    return value[: len(prefix)] == prefix


def _score(repo: Path, ref: Any, unit_id: str, projection_sha: str, writer: str) -> None:
    _, normalized = _value(repo, ref)
    fields = {
        "unit_id", "outcome", "raw_sha256", "input_sha256", "written_by",
        "source_score", "source_score_selectors",
    }
    if not isinstance(normalized, dict) or set(normalized) != fields:
        raise BatchEvidenceError("normalized score record fields are invalid")
    if (
        normalized.get("unit_id") != unit_id
        or str(normalized.get("outcome", "")).casefold() != "pass"
        or normalized.get("input_sha256") != projection_sha
        or normalized.get("written_by") != writer
    ):
        raise BatchEvidenceError("normalized score record does not match the batch unit")
    source_ref = normalized.get("source_score")
    source_document, selected = _value(repo, source_ref)
    if not isinstance(selected, dict):
        raise BatchEvidenceError("source score pointer must select an object")
    selectors = normalized.get("source_score_selectors")
    if not isinstance(selectors, dict) or set(selectors) != {"unit_id", "outcome", "written_by"}:
        raise BatchEvidenceError("source score selectors are invalid")
    selected_tokens = _tokens(source_ref["pointer"])
    selector_tokens = {name: _tokens(pointer) for name, pointer in selectors.items()}
    for name in ("unit_id", "outcome"):
        if not _prefix(selected_tokens, selector_tokens[name]) or len(selector_tokens[name]) <= len(selected_tokens):
            raise BatchEvidenceError("source score selector escapes the selected score object")
    writer_tokens = selector_tokens["written_by"]
    writer_parent = writer_tokens[:-1]
    if not (
        (_prefix(selected_tokens, writer_tokens) and len(writer_tokens) > len(selected_tokens))
        or (_prefix(writer_parent, selected_tokens) and len(writer_tokens) == len(writer_parent) + 1)
    ):
        raise BatchEvidenceError("source score writer selector must use the score object or ancestor metadata")
    selected_unit = _select(source_document, selectors["unit_id"])
    selected_outcome = _select(source_document, selectors["outcome"])
    selected_writer = _select(source_document, selectors["written_by"])
    if selected_unit != unit_id or str(selected_outcome).casefold() != "pass" or selected_writer != writer:
        raise BatchEvidenceError("source score values do not prove this passing unit and writer")


def _reviewer(state: dict[str, Any], reviewer_id: str, writer: str) -> None:
    matches = [
        item
        for item in state.get("subtasks", [])
        if isinstance(item, dict)
        and item.get("role") == "reviewer"
        and item.get("status") == "completed"
        and item.get("dispatch", {}).get("platform_agent_id") == reviewer_id
        and item.get("result", {}).get("review", {}).get("verdict") == "pass"
    ]
    implementers = {
        item.get("dispatch", {}).get("platform_agent_id")
        for item in state.get("subtasks", [])
        if item.get("role") != "reviewer"
    }
    if not matches or reviewer_id == writer or reviewer_id in implementers:
        raise BatchEvidenceError("applicability review requires a real independent passing reviewer")


def _delta(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"path": path, "before": before.get(path), "after": after.get(path)}
        for path in sorted(set(before) | set(after))
        if before.get(path) != after.get(path)
    ]


def validate_batch(
    repo: Path,
    state: dict[str, Any],
    batch: Any,
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
    *,
    require_current_applicability: bool = True,
) -> dict[str, Any]:
    required = {
        "batch_id", "source_attempt_id", "written_by", "written_role",
        "contract", "units", "applicability_review",
    }
    if not isinstance(batch, dict) or set(batch) != required:
        raise BatchEvidenceError("acceptance evidence batch fields are invalid")
    if not isinstance(batch.get("batch_id"), str) or not batch["batch_id"]:
        raise BatchEvidenceError("acceptance evidence batch_id is invalid")
    attempt, source = _attempt(state, batch.get("source_attempt_id"))
    if attempt.get("outcome") in {"product_failure", "effect_failure"}:
        raise BatchEvidenceError("failed product or effect attempts cannot contribute reusable batch evidence")
    dispatch = source["dispatch"]
    result = source.get("result")
    if (
        batch.get("written_by") != dispatch.get("platform_agent_id")
        or batch.get("written_role") != dispatch.get("agent_key")
        or (isinstance(result, dict) and (
            result.get("written_by") != batch.get("written_by")
            or result.get("written_role") != batch.get("written_role")
        ))
    ):
        raise BatchEvidenceError("batch writer must match the source dispatch and result")
    contract, contract_units, fixture_units = _contract(repo, batch.get("contract"), state)
    if contract["kind"] != attempt.get("kind", "ordinary"):
        raise BatchEvidenceError("batch contract kind does not match its source attempt")
    frozen = state.get("acceptance_gate", {}).get("batch_contracts", {}).get(contract["kind"])
    if frozen is not None and frozen != batch["contract"]:
        raise BatchEvidenceError("batch contract is already frozen for this acceptance kind")
    units = batch.get("units")
    if not isinstance(units, list) or not units:
        raise BatchEvidenceError("acceptance evidence batch units must be non-empty")
    unit_ids: list[str] = []
    raw_identities: list[tuple[str, str]] = []
    historical_refs = set()
    if isinstance(result, dict):
        source_evidence = result.get("expensive_acceptance", {})
        historical_refs.update(source_evidence.get("evidence_refs", []))
        for refs in source_evidence.get("evidence_by_acceptance_id", {}).values():
            if isinstance(refs, list):
                historical_refs.update(ref for ref in refs if isinstance(ref, str))
    for unit in units:
        if not isinstance(unit, dict) or set(unit) != {"unit_id", "acceptance_id", "raw", "input", "score"}:
            raise BatchEvidenceError("acceptance evidence unit fields are invalid")
        unit_id = unit.get("unit_id")
        expected = contract_units.get(unit_id)
        if expected is None or unit.get("acceptance_id") != expected.get("acceptance_id") or unit_id in unit_ids:
            raise BatchEvidenceError("acceptance evidence unit does not match the frozen contract")
        raw_ref = unit.get("raw")
        if not isinstance(raw_ref, dict) or set(raw_ref) not in ({"path", "sha256"}, {"path", "sha256", "pointer"}):
            raise BatchEvidenceError("raw evidence reference must be a fileRef or valueRef")
        selectors = expected["raw_selectors"]
        if "pointer" in raw_ref:
            raw_path, raw_document = _file(repo, raw_ref, pointer=True)
            raw = _select(raw_document, raw_ref["pointer"])
            if selectors is None:
                raise BatchEvidenceError("pointed raw evidence requires frozen raw selectors")
            if not isinstance(raw, dict):
                raise BatchEvidenceError("pointed raw evidence must select an object")
            selected_id = _select(raw, selectors["unit_id"])
            selected_status = _select(raw, selectors["execution_status"])
            if selected_id != unit_id:
                raise BatchEvidenceError("pointed raw evidence unit ID does not match")
            if canonical(selected_status) not in {
                canonical(value) for value in selectors["executed_values"]
            }:
                raise BatchEvidenceError("pointed raw evidence status is not an executed value")
        else:
            if selectors is not None:
                raise BatchEvidenceError("whole-file raw evidence requires null raw selectors")
            raw_path, _ = _file(repo, raw_ref, pointer=False, json_required=False)
        if isinstance(result, dict) and raw_ref["path"] not in historical_refs:
            raise BatchEvidenceError("terminal source raw evidence is not registered by its result")
        input_ref = unit.get("input")
        if not isinstance(input_ref, dict) or set(input_ref) != {"path", "sha256", "pointers"}:
            raise BatchEvidenceError("batch input reference is invalid")
        if isinstance(result, dict) and input_ref["path"] not in historical_refs:
            raise BatchEvidenceError("terminal source input evidence is not registered by its result")
        _, input_document = _file(
            repo, {"path": input_ref["path"], "sha256": input_ref["sha256"]}, pointer=False
        )
        pointers = input_ref.get("pointers")
        expected_names = set(expected["current_input"]["pointers"])
        if not isinstance(pointers, dict) or set(pointers) != expected_names:
            raise BatchEvidenceError("batch input projection names do not match the contract")
        projection = _projection(input_document, pointers)
        current_projection = _projection(
            fixture_units[unit_id], expected["current_input"]["pointers"]
        )
        if digest(projection) != digest(current_projection):
            raise BatchEvidenceError("archived input projection does not match the current fixture")
        _score(repo, unit.get("score"), unit_id, digest(projection), batch["written_by"])
        _, normalized = _value(repo, unit["score"])
        if normalized.get("raw_sha256") != unit["raw"]["sha256"]:
            raise BatchEvidenceError("normalized score raw hash does not match")
        resolved_raw = raw_path.relative_to(repo.resolve()).as_posix()
        raw_identities.append((resolved_raw, raw_ref.get("pointer", "")))
        unit_ids.append(unit_id)
    if len(raw_identities) != len(set(raw_identities)):
        raise BatchEvidenceError("acceptance evidence batch repeats a raw source")
    _, review = _file(repo, batch.get("applicability_review"), pointer=False)
    review_fields = {
        "written_by", "written_role", "source_attempt_id", "source_candidate_id",
        "current_candidate_id", "source_coverage_sha256", "current_coverage_sha256",
        "delta_sha256", "changed_paths", "unit_ids", "units_sha256",
        "input_projection_complete", "compatible", "reason", "evidence_refs",
    }
    if not isinstance(review, dict) or set(review) != review_fields:
        raise BatchEvidenceError("applicability review fields are invalid")
    _reviewer(state, review.get("written_by"), batch["written_by"])
    current = state.get("acceptance_gate", {}).get("current_candidate", {})
    source_records = attempt.get("coverage_snapshot")
    review_candidate_id = review.get("current_candidate_id")
    historical = review_candidate_id != current.get("candidate_id")
    if require_current_applicability and historical:
        raise BatchEvidenceError("applicability review does not target the current candidate")
    expected_review = {
        "source_attempt_id": attempt.get("attempt_id"),
        "source_candidate_id": attempt.get("candidate_id"),
        "source_coverage_sha256": digest(source_records),
        "unit_ids": unit_ids,
        "units_sha256": digest(units),
    }
    if require_current_applicability:
        current_snapshot = current_records(repo, state)
        delta = _delta(source_records if isinstance(source_records, dict) else {}, current_snapshot)
        expected_review.update({
            "current_candidate_id": current.get("candidate_id"),
            "current_coverage_sha256": digest(current_snapshot),
            "delta_sha256": digest(delta),
            "changed_paths": [item["path"] for item in delta],
        })
    if any(review.get(key) != value for key, value in expected_review.items()):
        raise BatchEvidenceError("applicability review does not bind the complete batch and candidate delta")
    if not require_current_applicability and (
        not isinstance(review_candidate_id, str)
        or not SHA256.fullmatch(str(review.get("current_coverage_sha256", "")))
        or not SHA256.fullmatch(str(review.get("delta_sha256", "")))
        or not isinstance(review.get("changed_paths"), list)
    ):
        raise BatchEvidenceError("historical applicability review binding is malformed")
    if review.get("written_role") != "reviewer" or review.get("input_projection_complete") is not True or review.get("compatible") is not True or not str(review.get("reason", "")).strip():
        raise BatchEvidenceError("applicability review must explicitly approve complete compatible input projections")
    refs = review.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        raise BatchEvidenceError("applicability review requires evidence references")
    for ref in refs:
        _file(repo, ref, pointer=False, json_required=False)
    return {
        "kind": contract["kind"],
        "target_candidate_id": review_candidate_id,
        "unit_ids": unit_ids,
        "raw_identities": raw_identities,
    }


def validate_all_batches(
    repo: Path,
    state: dict[str, Any],
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, Any] = {}
    seen_units: set[tuple[str, ...]] = set()
    seen_raw: set[tuple[str, ...]] = set()
    gate = state.get("acceptance_gate", {})
    batches = gate.get("evidence_batches", [])
    if not isinstance(batches, list):
        return ["acceptance evidence batches must be a list"]
    for index, batch in enumerate(batches, 1):
        try:
            details = validate_batch(
                repo, state, batch, current_records, require_current_applicability=False
            )
            batch_id = batch["batch_id"]
            if batch_id in seen_ids and seen_ids[batch_id] != batch:
                raise BatchEvidenceError("acceptance evidence batch ID conflicts")
            seen_ids[batch_id] = batch
            for unit_id in details["unit_ids"]:
                identity = (details["kind"], details["target_candidate_id"], unit_id)
                if identity in seen_units:
                    raise BatchEvidenceError("acceptance evidence unit is repeated across batches")
                seen_units.add(identity)
            for identity in details["raw_identities"]:
                candidate_identity = (details["target_candidate_id"], *identity)
                if candidate_identity in seen_raw:
                    raise BatchEvidenceError("raw acceptance evidence is repeated across batches")
                seen_raw.add(candidate_identity)
        except (BatchEvidenceError, KeyError, TypeError) as exc:
            errors.append(f"acceptance evidence batch {index}: {exc}")
    return errors


def add_batch(
    repo: Path,
    state: dict[str, Any],
    payload: Any,
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> tuple[bool, dict[str, Any]]:
    gate = state["acceptance_gate"]
    batches = gate.setdefault("evidence_batches", [])
    previous = next((item for item in batches if item.get("batch_id") == payload.get("batch_id")), None) if isinstance(payload, dict) else None
    if previous is not None:
        if previous == payload:
            validate_batch(
                repo, state, payload, current_records, require_current_applicability=False
            )
            return True, previous
        raise BatchEvidenceError("conflicting acceptance evidence batch ID already exists")
    details = validate_batch(repo, state, payload, current_records)
    for existing in batches:
        other = validate_batch(
            repo, state, existing, current_records, require_current_applicability=False
        )
        if details["target_candidate_id"] != other["target_candidate_id"]:
            continue
        if set(details["unit_ids"]) & set(other["unit_ids"]):
            raise BatchEvidenceError("acceptance evidence unit is repeated across batches")
        if set(details["raw_identities"]) & set(other["raw_identities"]):
            raise BatchEvidenceError("raw acceptance evidence is repeated across batches")
    gate.setdefault("batch_contracts", {})[details["kind"]] = deepcopy(payload["contract"])
    batches.append(deepcopy(payload))
    return False, payload


def validate_partial(
    repo: Path,
    state: dict[str, Any],
    subtask: dict[str, Any],
    evidence: dict[str, Any],
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> None:
    attempt = next(
        item
        for item in state["acceptance_gate"].get("attempts", [])
        if item.get("subtask_id") == subtask.get("subtask_id")
    )
    if attempt.get("kind", "ordinary") == "preparation" or evidence.get("mode") != "partial" or evidence.get("failed_stage") != "none":
        raise BatchEvidenceError("partial_pass requires a non-preparation partial attempt with failed_stage=none")
    ids = evidence.get("evidence_batch_ids")
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise BatchEvidenceError("partial_pass requires unique evidence_batch_ids")
    batches = [
        item for item in state["acceptance_gate"].get("evidence_batches", [])
        if item.get("batch_id") in ids
    ]
    if len(batches) != len(ids) or any(item.get("source_attempt_id") != attempt.get("attempt_id") for item in batches):
        raise BatchEvidenceError("partial_pass batches must belong to this attempt")
    unit_ids = [unit["unit_id"] for batch in batches for unit in batch["units"]]
    contract, contract_units, _ = _contract(repo, batches[0]["contract"], state)
    if set(unit_ids) != set(evidence.get("executed_unit_ids", [])) or not set(unit_ids) < set(contract_units):
        raise BatchEvidenceError("partial_pass executed units must exactly match a proper contract subset")
    acceptance_ids = {unit["acceptance_id"] for batch in batches for unit in batch["units"]}
    if set(evidence.get("scope_acceptance_ids", [])) != acceptance_ids:
        raise BatchEvidenceError("partial_pass acceptance scope must match executed units")
    raw_paths = {unit["raw"]["path"] for batch in batches for unit in batch["units"]}
    if not raw_paths.issubset(set(evidence.get("evidence_refs", []))):
        raise BatchEvidenceError("partial_pass must register every batch raw evidence path")
    mapping = evidence.get("evidence_by_acceptance_id", {})
    if set(mapping) != acceptance_ids or any(not set(mapping[key]).issubset(raw_paths) or not mapping[key] for key in mapping):
        raise BatchEvidenceError("partial_pass evidence mapping exceeds or misses executed units")
    for batch in batches:
        validate_batch(repo, state, batch, current_records)


def _coverage_validation(
    repo: Path,
    state: dict[str, Any],
    payload: dict[str, Any],
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
    *,
    allow_historical: bool = False,
    enforce_latest: bool = True,
) -> dict[str, Any]:
    required = {"coverage_id", "kind", "candidate_id", "contract_sha256", "batch_ids", "written_by", "written_role"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise BatchEvidenceError("acceptance coverage fields are incomplete")
    kind = payload.get("kind")
    if kind not in {"ordinary", "blackbox"}:
        raise BatchEvidenceError("acceptance coverage kind is invalid")
    current = state.get("acceptance_gate", {}).get("current_candidate", {})
    if not allow_historical and payload.get("candidate_id") != current.get("candidate_id"):
        raise BatchEvidenceError("acceptance coverage candidate is not current")
    require_current_applicability = (
        not allow_historical or payload.get("candidate_id") == current.get("candidate_id")
    )
    batch_ids = payload.get("batch_ids")
    if not isinstance(batch_ids, list) or not batch_ids or len(batch_ids) != len(set(batch_ids)):
        raise BatchEvidenceError("acceptance coverage batch_ids must be non-empty and unique")
    by_id = {item.get("batch_id"): item for item in state["acceptance_gate"].get("evidence_batches", [])}
    if any(batch_id not in by_id for batch_id in batch_ids):
        raise BatchEvidenceError("acceptance coverage references an unknown batch")
    batches = [by_id[batch_id] for batch_id in batch_ids]
    if any(batch["contract"]["sha256"] != payload.get("contract_sha256") for batch in batches):
        raise BatchEvidenceError("acceptance coverage contract hash does not match every batch")
    contract, contract_units, _ = _contract(repo, batches[0]["contract"], state)
    if contract["kind"] != kind:
        raise BatchEvidenceError("acceptance coverage kind does not match its contract")
    units: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {}
    for batch in batches:
        details = validate_batch(
            repo,
            state,
            batch,
            current_records,
            require_current_applicability=require_current_applicability,
        )
        if details["target_candidate_id"] != payload.get("candidate_id"):
            raise BatchEvidenceError("acceptance coverage batch applicability targets another candidate")
        attempt, source = _attempt(state, batch["source_attempt_id"])
        if source.get("status") not in {"completed", "blocked"} or "outcome" not in attempt:
            raise BatchEvidenceError("acceptance coverage source attempt is not honestly terminal")
        if batch.get("written_by") != payload.get("written_by") or batch.get("written_role") != payload.get("written_role"):
            raise BatchEvidenceError("acceptance coverage writer must match every batch writer")
        for unit in batch["units"]:
            if unit["unit_id"] in units:
                raise BatchEvidenceError("acceptance coverage overlaps a unit")
            units[unit["unit_id"]] = unit
            sources[unit["unit_id"]] = attempt["attempt_id"]
    if set(units) != set(contract_units):
        raise BatchEvidenceError("acceptance coverage does not cover the complete contract unit set")
    candidate_attempts = [
        item for item in state["acceptance_gate"].get("attempts", [])
        if item.get("candidate_id") == current.get("candidate_id") and item.get("kind", "ordinary") == kind
    ]
    latest = candidate_attempts[-1] if candidate_attempts else None
    if enforce_latest and (latest is None or latest.get("outcome") in {"product_failure", "environment_failure", "effect_failure"} and latest.get("attempt_id") not in set(sources.values())):
        raise BatchEvidenceError("later acceptance failure invalidates prior coverage")
    return {
        **{key: deepcopy(payload[key]) for key in required},
        "request_sha256": digest({key: payload[key] for key in required}),
        "same_round_full_execution": False,
        "unit_sources": [
            {
                "unit_id": unit_id,
                "acceptance_id": units[unit_id]["acceptance_id"],
                "source_attempt_id": sources[unit_id],
                "batch_id": next(batch["batch_id"] for batch in batches if any(unit["unit_id"] == unit_id for unit in batch["units"])),
            }
            for unit_id in sorted(units)
        ],
    }


def add_coverage(
    repo: Path,
    state: dict[str, Any],
    payload: Any,
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> tuple[bool, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise BatchEvidenceError("acceptance coverage payload must be an object")
    receipts = state["acceptance_gate"].setdefault("coverage_receipts", [])
    request_sha = digest(payload)
    previous = next((item for item in receipts if item.get("coverage_id") == payload.get("coverage_id")), None)
    if previous is not None:
        if previous.get("request_sha256") == request_sha:
            _coverage_validation(repo, state, payload, current_records)
            return True, previous
        raise BatchEvidenceError("conflicting acceptance coverage ID already exists")
    receipt = _coverage_validation(repo, state, payload, current_records)
    receipts.append(receipt)
    return False, receipt


def validate_coverages(
    repo: Path,
    state: dict[str, Any],
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    receipts = state.get("acceptance_gate", {}).get("coverage_receipts", [])
    if not isinstance(receipts, list):
        return ["acceptance coverage receipts must be a list"]
    for index, receipt in enumerate(receipts, 1):
        try:
            payload = {
                key: receipt[key]
                for key in ("coverage_id", "kind", "candidate_id", "contract_sha256", "batch_ids", "written_by", "written_role")
            }
            expected = _coverage_validation(
                repo,
                state,
                payload,
                current_records,
                allow_historical=True,
                enforce_latest=False,
            )
            if receipt != expected:
                raise BatchEvidenceError("acceptance coverage derived fields do not match")
        except (BatchEvidenceError, KeyError, TypeError) as exc:
            errors.append(f"acceptance coverage receipt {index}: {exc}")
    return errors


def current_coverage(
    repo: Path,
    state: dict[str, Any],
    kind: str,
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> dict[str, Any] | None:
    candidate = state.get("acceptance_gate", {}).get("current_candidate")
    if not isinstance(candidate, dict):
        return None
    current_id = candidate.get("candidate_id")
    for receipt in reversed(state.get("acceptance_gate", {}).get("coverage_receipts", [])):
        if receipt.get("kind") != kind or receipt.get("candidate_id") != current_id:
            continue
        payload = {
            key: receipt[key]
            for key in ("coverage_id", "kind", "candidate_id", "contract_sha256", "batch_ids", "written_by", "written_role")
        }
        try:
            expected = _coverage_validation(repo, state, payload, current_records)
        except (BatchEvidenceError, KeyError, TypeError):
            return None
        return receipt if receipt == expected else None
    return None


def coverage_evidence_sources(
    repo: Path,
    state: dict[str, Any],
    required: set[str],
    current_records: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> list[tuple[str, str, str]]:
    sources: list[tuple[str, str, str]] = []
    for kind in ("ordinary", "blackbox"):
        receipt = current_coverage(repo, state, kind, current_records)
        if receipt is None:
            continue
        by_id = {item["batch_id"]: item for item in state["acceptance_gate"].get("evidence_batches", [])}
        for batch_id in receipt["batch_ids"]:
            batch = by_id[batch_id]
            _, source = _attempt(state, batch["source_attempt_id"])
            evidence = source.get("result", {}).get("review_evidence", {})
            if isinstance(evidence, dict):
                sources.extend(
                    (source["subtask_id"], key, value)
                    for key, value in evidence.items()
                    if key in required and isinstance(value, str)
                )
    return sources
