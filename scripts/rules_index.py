"""Mechanical parser, validator and metadata-index generator for rules."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


RULE_KINDS = {"policy", "workflow", "architecture", "quality", "stack", "style"}
RULE_SCOPES = {"global", "project", "path"}
RULE_ACTIVATIONS = {"always_on", "model_decision", "path", "manual"}
RULE_STATUSES = {"active", "deprecated", "draft"}
RULE_ENFORCEMENTS = {"advisory", "executable_backed"}
RULE_OVERRIDE_MODES = {"merge", "replace"}
ARRAY_FIELDS = {"paths", "intents", "overrides"}
REQUIRED_FIELDS = {
    "id", "title", "subject", "scope", "kind", "priority", "activation", "paths",
    "intents", "owner", "status", "summary", "linked_skill", "enforcement",
    "overrideable", "override_mode", "overrides", "override_reason",
}


def _parse_scalar(text: str) -> Any:
    value = text.strip()
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str, set[str]]:
    raw = path.read_text(encoding="utf-8-sig")
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", raw, re.DOTALL)
    if not match:
        raise ValueError(f"{path}: missing complete frontmatter")
    values: dict[str, Any] = {}
    array_syntax: set[str] = set()
    pending: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        array_item = re.match(r"^\s+-\s*(.+?)\s*$", line)
        if array_item:
            if pending is None:
                raise ValueError(f"{path}: array item without field")
            values[pending].append(_parse_scalar(array_item.group(1)))
            continue
        field = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not field:
            raise ValueError(f"{path}: invalid frontmatter line: {line}")
        key, text = field.groups()
        if text == "":
            values[key] = []
            array_syntax.add(key)
            pending = key
        elif text.strip().startswith("[") and text.strip().endswith("]"):
            try:
                parsed = ast.literal_eval(text.strip())
            except (SyntaxError, ValueError) as error:
                raise ValueError(f"{path}: invalid array for {key}: {error}") from error
            if not isinstance(parsed, (list, tuple)):
                raise ValueError(f"{path}: {key} must be an array")
            values[key] = list(parsed)
            array_syntax.add(key)
            pending = None
        else:
            values[key] = _parse_scalar(text)
            pending = None
    return values, raw[match.end():].strip(), array_syntax


def _is_chinese_file_name(stem: str) -> bool:
    return not re.search(r"[A-Za-z0-9]", stem) and bool(re.search(r"[\u3400-\u9fff]", stem))


def _rule_record(root: Path, path: Path, source_label: str) -> dict[str, Any]:
    values, body, array_syntax = parse_frontmatter(path)
    record = dict(values)
    record.update(
        body=body,
        file_path=path.relative_to(root).as_posix(),
        file_name=path.name,
        file_base_name=path.stem,
        kind_dir=path.parent.name,
        source_label=source_label,
        present_fields=sorted(values),
        array_syntax=sorted(array_syntax),
        merged_from_ids=[],
    )
    return record


def _validate_rule(rule: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    path = rule.get("file_path", "<unknown>")
    missing = sorted(REQUIRED_FIELDS - set(rule.get("present_fields", [])))
    errors.extend(f"{path}: missing field {field}" for field in missing)
    expected = {
        "id": str, "title": str, "subject": str, "scope": str, "kind": str,
        "priority": int, "activation": str, "paths": list, "intents": list,
        "owner": str, "status": str, "summary": str, "linked_skill": str,
        "enforcement": str, "overrideable": bool, "override_mode": str,
        "overrides": list, "override_reason": str,
    }
    for field, kind in expected.items():
        if field in rule and (not isinstance(rule[field], kind) or (kind is int and isinstance(rule[field], bool))):
            errors.append(f"{path}: invalid type for {field}")
    for field in ARRAY_FIELDS:
        if field in rule and field not in rule.get("array_syntax", []):
            errors.append(f"{path}: {field} must use array syntax")
        if isinstance(rule.get(field), list) and not all(isinstance(item, str) for item in rule[field]):
            errors.append(f"{path}: {field} only accepts strings")
    for field, allowed in (
        ("scope", RULE_SCOPES), ("kind", RULE_KINDS), ("activation", RULE_ACTIVATIONS),
        ("status", RULE_STATUSES), ("enforcement", RULE_ENFORCEMENTS),
        ("override_mode", RULE_OVERRIDE_MODES),
    ):
        if field in rule and rule[field] not in allowed:
            errors.append(f"{path}: invalid {field}: {rule[field]}")
    if rule.get("kind") != rule.get("kind_dir"):
        errors.append(f"{path}: directory kind differs from frontmatter kind")
    if not _is_chinese_file_name(str(rule.get("file_base_name", ""))):
        errors.append(f"{path}: rule filename must be Chinese")
    if (rule.get("scope") == "path" or rule.get("activation") == "path") and not rule.get("paths"):
        errors.append(f"{path}: path-scoped rule requires paths")
    if rule.get("overrides") and not str(rule.get("override_reason", "")).strip():
        errors.append(f"{path}: override_reason required when overrides is non-empty")
    skill = rule.get("linked_skill")
    if skill and rule.get("source_label") == "local" and not (repo_root / "skills" / skill / "SKILL.md").is_file():
        errors.append(f"{path}: linked_skill target missing: {skill}")
    return errors


def build_rules_model(repo_root: Path, global_roots: Iterable[Path] = ()) -> dict[str, Any]:
    local: list[dict[str, Any]] = []
    imported: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    for path in sorted((repo_root / "rules" / "items").rglob("*.md")):
        try:
            local.append(_rule_record(repo_root, path, "local"))
        except ValueError as error:
            errors.append(str(error))
    normalized_roots = [Path(root).expanduser().resolve() for root in global_roots]
    for number, root in enumerate(normalized_roots, 1):
        for path in sorted((root / "rules" / "items").rglob("*.md")):
            try:
                rule = _rule_record(root, path, f"global:<global-rules-root:{number}>")
                if rule.get("scope") != "project":
                    imported.append(rule)
            except ValueError as error:
                errors.append(str(error))
    for rule in imported + local:
        errors.extend(_validate_rule(rule, repo_root))
    all_rules = imported + local
    by_id: dict[str, dict[str, Any]] = {}
    for rule in all_rules:
        rule_id = rule.get("id")
        if rule_id in by_id:
            errors.append(f"duplicate rule id: {rule_id}")
        elif isinstance(rule_id, str):
            by_id[rule_id] = rule
    suppressed: set[str] = set()
    relations: list[dict[str, str]] = []
    for rule in local:
        for target_id in rule.get("overrides", []):
            target = by_id.get(target_id)
            if target is None:
                errors.append(f"{rule['file_path']}: overrides target missing: {target_id}")
                continue
            if not target.get("overrideable"):
                errors.append(f"{rule['file_path']}: overrides non-overrideable target: {target_id}")
                continue
            suppressed.add(target_id)
            relations.append({"resolution_kind": "explicit_override", "source_id": rule["id"], "target_id": target_id, "override_mode": rule["override_mode"]})
    active_by_subject: dict[str, list[dict[str, Any]]] = {}
    for rule in all_rules:
        if rule.get("id") not in suppressed:
            active_by_subject.setdefault(str(rule.get("subject")), []).append(rule)
    for subject, group in active_by_subject.items():
        if len(group) <= 1:
            continue
        ids = {rule.get("id") for rule in group}
        if not any(ids.intersection(set(rule.get("overrides", []))) for rule in group):
            errors.append(f"subject conflict without explicit overrides: {subject} ({', '.join(sorted(map(str, ids)))})")
    return {
        "repo_root": repo_root,
        "local_rules": local,
        "global_rules": imported,
        "relations": relations,
        "global_roots": normalized_roots,
        "errors": errors,
        "warnings": warnings,
    }


def _public_rule(rule: dict[str, Any], *, include_body: bool = False) -> dict[str, Any]:
    fields = [
        "id", "title", "subject", "scope", "kind", "priority", "activation", "paths",
        "intents", "owner", "status", "summary", "linked_skill", "enforcement",
        "overrideable", "override_mode", "overrides", "file_path",
    ]
    if include_body:
        fields.extend(["override_reason", "body", "source_label", "merged_from_ids"])
    return {field: rule.get(field) for field in fields}


def artifacts_for_model(model: dict[str, Any]) -> dict[str, str]:
    local_rules = sorted(model["local_rules"], key=lambda item: str(item["id"]))
    fingerprint = hashlib.sha256(
        json.dumps([_public_rule(rule, include_body=True) for rule in local_rules], ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    discovery = {
        "mode": "explicit" if model["global_roots"] else "none",
        "roots": [f"<global-rules-root:{number}>" for number, _ in enumerate(model["global_roots"], 1)],
        "discovered": bool(model["global_roots"]),
        "searched": [f"<global-rules-root:{number}>/rules/items" for number, _ in enumerate(model["global_roots"], 1)],
    }
    index = {
        "schema_version": "2.0",
        "source_fingerprint": fingerprint,
        "repo_root": "<repo-root>",
        "local_rule_count": len(local_rules),
        "global_rules": discovery,
        "rules": [_public_rule(rule) for rule in local_rules],
        "warnings": model["warnings"],
    }
    lines = ["# Rules Index", "", "本文件由 `python3 scripts/generate_rules_index.py` 生成；不要手工编辑。", "", f"- source fingerprint: `{fingerprint}`", f"- local rules: {len(local_rules)}", "", "| id | scope | activation | priority | source |", "|---|---|---|---:|---|"]
    lines.extend(f"| `{rule['id']}` | `{rule['scope']}` | `{rule['activation']}` | {rule['priority']} | `{rule['file_path']}` |" for rule in local_rules)
    return {
        "RULES_INDEX.json": json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        "RULES_INDEX.md": "\n".join(lines) + "\n",
    }
