#!/usr/bin/env python3
import argparse
import ctypes
import datetime as dt
import errno
import hashlib
import json
import math
import os
import pathlib
import re
import stat
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

if os.name == "posix":
    import fcntl


MAX_SIGNATURE_SOURCE_LENGTH = 4096
MAX_STORED_SIGNATURE_LENGTH = 512
MAX_STORED_COMMAND_LENGTH = 512
MAX_STORED_ERROR_LENGTH = 512
MAX_STORED_RESOLUTION_LENGTH = 768
MAX_STORED_REASON_LENGTH = 256
MAX_PROJECTS_SEEN = 32
MAX_CASE_COUNT = 1024
MEMORY_LOCK_TIMEOUT_MS = 15000
VALID_SCOPE_KINDS = {"candidate_global", "candidate_project", "global", "project"}
CASE_ID_PATTERN = re.compile(r"^CASE-[a-f0-9]{16}$")
HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class MemoryErrorRuntime(Exception):
    pass


def normalize_user_path(path_value: str) -> Optional[str]:
    if not path_value or not str(path_value).strip():
        return None
    expanded = os.path.expandvars(str(path_value))
    expanded = os.path.expanduser(expanded)
    return os.path.abspath(expanded)


def get_default_codex_home() -> str:
    env_codex_home = normalize_user_path(os.environ.get("CODEX_HOME", ""))
    if env_codex_home:
        return env_codex_home
    return os.path.join(os.path.expanduser("~"), ".codex")


def limit_string_length(text: Optional[str], max_length: int, suffix: str = " <truncated>") -> str:
    if text is None:
        return ""
    value = str(text)
    if len(value) <= max_length:
        return value
    if max_length <= 0:
        return ""
    safe_suffix = "" if (not suffix or len(suffix) >= max_length) else suffix
    return value[: max_length - len(safe_suffix)] + safe_suffix


def normalize_final_path(path_value: str) -> str:
    if path_value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path_value[8:]
    if path_value.startswith("\\\\?\\"):
        return path_value[4:]
    if path_value.startswith("\\??\\"):
        return path_value[4:]
    return path_value


def existing_ancestor(path_value: str, allow_missing: bool) -> (str, List[str]):
    full_path = os.path.abspath(path_value)
    missing_segments: List[str] = []
    probe = full_path
    while not os.path.exists(probe):
        if not allow_missing:
            raise MemoryErrorRuntime(f"Path not found: {full_path}")
        leaf = os.path.basename(probe)
        if not leaf:
            raise MemoryErrorRuntime(f"Cannot resolve canonical path without existing ancestor: {full_path}")
        missing_segments.insert(0, leaf)
        parent = os.path.dirname(probe)
        if not parent or parent == probe:
            raise MemoryErrorRuntime(f"Cannot resolve canonical path without existing ancestor: {full_path}")
        probe = parent
    return probe, missing_segments


def get_canonical_path(path_value: str, allow_missing: bool = False) -> str:
    if not path_value or not str(path_value).strip():
        raise MemoryErrorRuntime("Path is empty")
    probe, missing_segments = existing_ancestor(path_value, allow_missing=allow_missing)
    canonical = normalize_final_path(str(pathlib.Path(probe).resolve(strict=True)))
    for segment in missing_segments:
        canonical = os.path.abspath(os.path.join(canonical, segment))
    return canonical


def has_reparse_point(path_value: str) -> bool:
    try:
        st = os.lstat(path_value)
    except OSError:
        return False
    file_attributes = getattr(st, "st_file_attributes", 0)
    if file_attributes and (file_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        return True
    return os.path.islink(path_value)


def assert_no_reparse_point_traversal(root_path: str, candidate_path: str, description: str) -> None:
    full_root = os.path.abspath(root_path).rstrip("\\/")
    full_candidate = os.path.abspath(candidate_path)
    if len(full_candidate) <= len(full_root):
        return
    relative_remainder = full_candidate[len(full_root) :].lstrip("\\/")
    if not relative_remainder:
        return
    current_path = full_root
    for segment in re.split(r"[\\/]+", relative_remainder):
        if not segment:
            continue
        current_path = os.path.join(current_path, segment)
        if not os.path.exists(current_path):
            break
        if has_reparse_point(current_path):
            raise MemoryErrorRuntime(f"{description} contains reparse point traversal: {current_path}")


def get_normalized_directory_prefix(path_value: str) -> str:
    full_path = get_canonical_path(path_value, allow_missing=True)
    if full_path.endswith(os.sep) or full_path.endswith("/"):
        return full_path
    return full_path + os.sep


def startswith_path(candidate: str, prefix: str) -> bool:
    if os.name == "nt":
        return candidate.lower().startswith(prefix.lower())
    return candidate.startswith(prefix)


def test_path_within_root(root_path: str, candidate_path: str) -> bool:
    root_prefix = get_normalized_directory_prefix(root_path)
    full_candidate = get_canonical_path(candidate_path, allow_missing=True)
    within_root = startswith_path(full_candidate, root_prefix)
    if within_root:
        assert_no_reparse_point_traversal(root_path, candidate_path, "memory root path")
    return within_root


def resolve_path_within_root(root_path: str, relative_path: str) -> str:
    candidate = os.path.abspath(os.path.join(root_path, relative_path.replace("/", os.sep)))
    textual_root_prefix = os.path.abspath(root_path).rstrip("\\/") + os.sep
    if startswith_path(candidate, textual_root_prefix):
        assert_no_reparse_point_traversal(root_path, candidate, "memory root path")
    if not test_path_within_root(root_path, candidate):
        raise MemoryErrorRuntime(f"Resolved path escapes memory root: {relative_path}")
    return candidate


def read_json_object(path_value: str, default_value: Any) -> Any:
    if not os.path.exists(path_value):
        return default_value
    with open(path_value, "r", encoding="utf-8-sig") as handle:
        raw = handle.read()
    if not raw.strip():
        return default_value
    return json.loads(raw)


def write_json_object(path_value: str, data: Any) -> None:
    parent = os.path.dirname(path_value)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path_value)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def get_string_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_iso_timestamp() -> str:
    return dt.datetime.now().astimezone().isoformat()


def convert_to_validated_double(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except Exception as exc:
        raise MemoryErrorRuntime(f"{field_name} must be numeric.") from exc
    if math.isnan(number) or math.isinf(number):
        raise MemoryErrorRuntime(f"{field_name} must be a finite number.")
    return number


def get_normalized_scope_confidence(value: Any, field_name: str = "scope_confidence") -> float:
    number = convert_to_validated_double(value, field_name)
    if number < 0.0 or number > 1.0:
        raise MemoryErrorRuntime(f"{field_name} must be between 0 and 1.")
    return round(number, 2)


def redact_sensitive_text(text: str) -> str:
    if not text or not str(text).strip():
        return ""
    value = str(text)
    substitutions = [
        (re.compile(r"(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----"), "<redacted-private-key>"),
        (re.compile(r"(?im)\b(authorization)\b\s*:\s*[A-Za-z]+\s+[^\s'\"`,;]+"), r"\1: <redacted>"),
        (re.compile(r"(?im)(https?://)([^\s/@:]+):([^\s/@]+)@"), r"\1<redacted>@"),
        (re.compile(r"(?im)\b([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASS(?:PHRASE)?|API[_\-]?KEY|ACCESS[_\-]?KEY|PRIVATE[_\-]?KEY|CLIENT[_\-]?SECRET)[A-Z0-9_]*)\b\s*[:=]\s*([^\r\n]+)"), r"\1=<redacted>"),
        (re.compile(r"(?im)\b(api[_\-]?key|token|password|passphrase|secret|client[_\-]?secret|access[_\-]?token|refresh[_\-]?token|session[_\-]?token)\b\s*[:=]\s*([^\r\n]+)"), r"\1=<redacted>"),
        (re.compile(r"(?<![A-Za-z0-9])(github_pat_[A-Za-z0-9_]{20,})(?![A-Za-z0-9])"), "<redacted-github-token>"),
        (re.compile(r"(?<![A-Za-z0-9])(gh[pousr]_[A-Za-z0-9]{20,})(?![A-Za-z0-9])"), "<redacted-github-token>"),
        (re.compile(r"(?<![A-Za-z0-9])(xox[baprs]-[A-Za-z0-9\-]{10,})(?![A-Za-z0-9])"), "<redacted-slack-token>"),
        (re.compile(r"(?<![A-Za-z0-9])(sk-[A-Za-z0-9]{20,})(?![A-Za-z0-9])"), "<redacted-api-key>"),
        (re.compile(r"(?<![A-Za-z0-9])(AKIA[0-9A-Z]{16})(?![A-Za-z0-9])"), "<redacted-aws-key>"),
        (re.compile(r"(?<![A-Za-z0-9])(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})(?![A-Za-z0-9])"), "<redacted-jwt>"),
        (re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9+/]{48,}={0,2}|[A-Fa-f0-9]{48,})(?![A-Za-z0-9])"), "<redacted-secret>"),
    ]
    for pattern, replacement in substitutions:
        value = pattern.sub(replacement, value)
    return value


def get_sanitized_stored_text(text: str, max_length: int) -> str:
    widened = max(max_length * 4, max_length)
    value = redact_sensitive_text(limit_string_length(text, widened))
    return limit_string_length(value.strip(), max_length)


def normalize_signature_text(text: str, preserve_line_breaks: bool = False) -> str:
    limited = limit_string_length(text, MAX_SIGNATURE_SOURCE_LENGTH, suffix="")
    normalized = redact_sensitive_text(limited).strip().lower()
    if preserve_line_breaks:
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[\t\f\v ]+", " ", normalized)
        normalized = re.sub(r"\n+", "\n", normalized)
        return normalized
    return re.sub(r"\s+", " ", normalized)


def get_error_signature_line(error_value: str) -> str:
    normalized = normalize_signature_text(error_value, preserve_line_breaks=True)
    if not normalized.strip():
        return ""
    return normalized.split("\n", 1)[0].strip()


def get_case_signature(command_value: str, error_value: str) -> Dict[str, str]:
    normalized_command = normalize_signature_text(command_value)
    normalized_error = get_error_signature_line(error_value)
    if not normalized_command or not normalized_error:
        raise MemoryErrorRuntime("command/error cannot be empty when computing failure signature.")
    return {
        "signature": get_string_sha256(f"{normalized_command}|{normalized_error}"),
        "command_signature": normalized_command,
        "error_signature": normalized_error,
    }


def get_canonical_project_id(value: str) -> str:
    if not value or not str(value).strip():
        return "unknown-project"
    return re.sub(r"[^a-z0-9.\-_]", "-", str(value).strip().lower())


def get_default_scope_reason(scope_kind_value: str) -> str:
    return {
        "candidate_global": "Fix looks like an environment-wide issue; keep candidate_global first.",
        "candidate_project": "Fix depends on project-specific context; keep candidate_project first.",
        "global": "Validated across projects as a stable global solution.",
        "project": "Only validated in project-specific context.",
    }.get(scope_kind_value, "")


def ensure_array_contains(items: List[str], value: str) -> List[str]:
    result: List[str] = []
    for item in items:
        text = str(item)
        if text and text not in result:
            result.append(text)
    if value not in result:
        result.append(value)
    return result[-MAX_PROJECTS_SEEN:]


def get_timestamp_sort_key(timestamp: str) -> float:
    try:
        return dt.datetime.fromisoformat(timestamp).timestamp()
    except Exception:
        return 0.0


def limit_failure_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Pending failures are unresolved work, not a cache. Dropping old entries can
    # silently remove the only retry-gate evidence for a failure.
    return [event for event in events if event is not None]


def get_storage_tier(case_data: Dict[str, Any]) -> str:
    tier = str(case_data.get("storage_tier", "active"))
    if tier not in {"active", "archived"}:
        raise MemoryErrorRuntime(f"case has invalid storage_tier: {case_data.get('case_id')}")
    return tier


def get_active_case_count(case_by_id: Dict[str, Dict[str, Any]]) -> int:
    return sum(1 for case_data in case_by_id.values() if get_storage_tier(case_data) == "active")


def archive_cold_active_case(
    storage: Dict[str, str],
    catalog: Dict[str, Any],
    changed_cases: Dict[str, Dict[str, Any]],
    *,
    excluded_case_ids: Optional[set[str]] = None,
) -> Dict[str, Any]:
    excluded = excluded_case_ids or set()
    candidates = [
        entry
        for entry in catalog["by_id"].values()
        if entry.get("case_id") not in excluded
        and get_storage_tier(entry) == "active"
    ]
    candidates.sort(
        key=lambda entry: (
            0 if entry.get("has_solution") is False else (1 if "has_solution" not in entry else 2),
            get_timestamp_sort_key(
                str(
                    entry.get("last_hit_at")
                    or entry.get("last_verified_at")
                    or entry.get("updated_at")
                    or entry.get("created_at")
                    or ""
                )
            ),
            str(entry.get("case_id", "")),
        )
    )
    for entry in candidates:
        case_id = entry["case_id"]
        case_data = changed_cases.get(case_id) or load_case_data(storage, entry)
        if not str(case_data.get("solution", "")).strip():
            case_data["storage_tier"] = "archived"
            case_data["archived_at"] = get_iso_timestamp()
            case_data["archive_reason"] = "capacity_unresolved"
            changed_cases[case_id] = case_data
            put_case_in_catalog(catalog, case_data)
            return case_data
        if int(case_data.get("stats", {}).get("verify_count", 0)) <= 0:
            entry["has_solution"] = True
            continue
        case_data["storage_tier"] = "archived"
        case_data["archived_at"] = get_iso_timestamp()
        case_data["archive_reason"] = "capacity_cold"
        changed_cases[case_id] = case_data
        put_case_in_catalog(catalog, case_data)
        return case_data
    raise MemoryErrorRuntime("active case capacity reached and no stable cold case can be archived.")


def ensure_active_capacity(
    storage: Dict[str, str],
    catalog: Dict[str, Any],
    changed_cases: Dict[str, Dict[str, Any]],
    *,
    excluded_case_ids: Optional[set[str]] = None,
) -> Optional[Dict[str, Any]]:
    if get_active_case_count(catalog["by_id"]) < MAX_CASE_COUNT:
        return None
    return archive_cold_active_case(
        storage, catalog, changed_cases, excluded_case_ids=excluded_case_ids
    )


def coerce_projects_seen(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def ensure_stats(case_data: Dict[str, Any]) -> None:
    stats_value = case_data.get("stats")
    if not isinstance(stats_value, dict):
        stats_value = {"hit_count": 0, "verify_count": 0, "incident_count": 0}
        case_data["stats"] = stats_value
    for field in ("hit_count", "verify_count", "incident_count"):
        value = int(stats_value.get(field, 0))
        if value < 0:
            raise MemoryErrorRuntime(f"case stat must be non-negative: {case_data.get('case_id')}.{field}")
        stats_value[field] = value


def assert_valid_case_data(case_data: Dict[str, Any]) -> None:
    if case_data is None:
        raise MemoryErrorRuntime("case data is null")
    if not case_data.get("schema_version"):
        case_data["schema_version"] = "1.0"
    case_data["storage_tier"] = get_storage_tier(case_data)
    case_id = str(case_data.get("case_id", ""))
    signature = str(case_data.get("signature", ""))
    if not CASE_ID_PATTERN.match(case_id):
        raise MemoryErrorRuntime(f"case is missing a valid case_id: {case_id}")
    if not HEX64_PATTERN.match(signature):
        raise MemoryErrorRuntime(f"case is missing a valid signature: {case_id}")
    scope_kind = str(case_data.get("scope_kind", ""))
    if scope_kind not in VALID_SCOPE_KINDS:
        raise MemoryErrorRuntime(f"case is missing a valid scope_kind: {case_id}")
    case_data["scope_confidence"] = get_normalized_scope_confidence(case_data.get("scope_confidence"), f"scope_confidence for {case_id}")
    case_data["command_signature"] = limit_string_length(str(case_data.get("command_signature", "")), MAX_STORED_SIGNATURE_LENGTH, suffix="")
    case_data["error_signature"] = limit_string_length(str(case_data.get("error_signature", "")), MAX_STORED_SIGNATURE_LENGTH, suffix="")
    if not case_data["command_signature"] or not case_data["error_signature"]:
        raise MemoryErrorRuntime(f"case is missing signature text: {case_id}")
    case_data["command_excerpt"] = get_sanitized_stored_text(str(case_data.get("command_excerpt", "")), MAX_STORED_COMMAND_LENGTH)
    case_data["error_excerpt"] = get_sanitized_stored_text(str(case_data.get("error_excerpt", "")), MAX_STORED_ERROR_LENGTH)
    case_data["solution"] = get_sanitized_stored_text(str(case_data.get("solution", "")), MAX_STORED_RESOLUTION_LENGTH)
    case_data["scope_reason"] = get_sanitized_stored_text(str(case_data.get("scope_reason", "")), MAX_STORED_REASON_LENGTH)
    if not case_data["scope_reason"]:
        raise MemoryErrorRuntime(f"case is missing scope_reason: {case_id}")
    normalized_projects: List[str] = []
    for project_id in coerce_projects_seen(case_data.get("projects_seen")):
        canonical_project_id = get_canonical_project_id(project_id)
        if canonical_project_id not in normalized_projects:
            normalized_projects.append(canonical_project_id)
    normalized_projects = normalized_projects[-MAX_PROJECTS_SEEN:]
    if not normalized_projects:
        raise MemoryErrorRuntime(f"case is missing projects_seen: {case_id}")
    case_data["projects_seen"] = normalized_projects
    ensure_stats(case_data)
    for field in ("created_at", "updated_at"):
        if not str(case_data.get(field, "")).strip():
            raise MemoryErrorRuntime(f"case is missing {field}: {case_id}")


def get_memory_lock_name(memory_root: str) -> str:
    lock_identity = normalize_user_path(memory_root) or os.path.abspath(memory_root)
    if os.name == "nt":
        lock_identity = lock_identity.lower()
    return f"Local\\AiHarness.CommandFailureMemory.{get_string_sha256(lock_identity)[:24]}"


class NamedMutex:
    WAIT_OBJECT_0 = 0x00000000
    WAIT_ABANDONED = 0x00000080

    def __init__(self, name: str, timeout_ms: int):
        self.name = name
        self.timeout_ms = timeout_ms
        self.handle = None

    def __enter__(self):
        if os.name != "nt":
            return self
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise MemoryErrorRuntime("failed to create failure-memory lock mutex.")
        wait_result = kernel32.WaitForSingleObject(ctypes.c_void_p(handle), self.timeout_ms)
        if wait_result not in (self.WAIT_OBJECT_0, self.WAIT_ABANDONED):
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            raise MemoryErrorRuntime(f"timed out waiting for failure-memory lock after {self.timeout_ms} ms.")
        self.handle = handle
        return self

    def __exit__(self, exc_type, exc, tb):
        if os.name != "nt" or not self.handle:
            return False
        kernel32 = ctypes.windll.kernel32
        try:
            kernel32.ReleaseMutex(ctypes.c_void_p(self.handle))
        except Exception:
            pass
        kernel32.CloseHandle(ctypes.c_void_p(self.handle))
        self.handle = None
        return False


def invoke_with_memory_lock(memory_root: str, callback):
    lock_name = get_memory_lock_name(memory_root)
    if os.name == "nt":
        with NamedMutex(lock_name, MEMORY_LOCK_TIMEOUT_MS):
            return callback()
    os.makedirs(memory_root, exist_ok=True)
    lock_path = os.path.join(memory_root, ".store.lock")
    with open(lock_path, "a+b") as lock_handle:
        deadline = time.monotonic() + (MEMORY_LOCK_TIMEOUT_MS / 1000.0)
        while True:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise MemoryErrorRuntime(
                        f"timed out waiting for failure-memory lock after {MEMORY_LOCK_TIMEOUT_MS} ms."
                    ) from exc
                time.sleep(0.05)
        try:
            return callback()
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def new_memory_storage(memory_root: str) -> Dict[str, str]:
    cases_root = resolve_path_within_root(memory_root, "cases")
    runtime_root = resolve_path_within_root(memory_root, "runtime")
    os.makedirs(cases_root, exist_ok=True)
    os.makedirs(runtime_root, exist_ok=True)
    return {
        "memory_root": memory_root,
        "cases_root": cases_root,
        "runtime_root": runtime_root,
        "index_path": resolve_path_within_root(memory_root, "index.json"),
        "failure_events_path": resolve_path_within_root(memory_root, "runtime/failure-events.json"),
    }


def get_empty_index_data() -> Dict[str, Any]:
    return {"schema_version": "1.0", "updated_at": "", "cases": []}


def get_empty_failure_data() -> Dict[str, Any]:
    return {"schema_version": "1.0", "updated_at": "", "events": []}


def resolve_case_file_path(cases_root: str, case_id: str) -> str:
    if not CASE_ID_PATTERN.match(case_id):
        raise MemoryErrorRuntime(f"invalid case_id rejected: {case_id}")
    return resolve_path_within_root(cases_root, f"{case_id}.json")


def new_case_id(signature: str, case_by_id: Dict[str, Dict[str, Any]]) -> str:
    prefix = signature[:16]
    case_id = f"CASE-{prefix}"
    if case_id not in case_by_id:
        return case_id
    while True:
        candidate = f"CASE-{os.urandom(8).hex()}"
        if candidate not in case_by_id:
            return candidate


def get_case_catalog(storage: Dict[str, str]) -> Dict[str, Any]:
    index_data = read_json_object(storage["index_path"], get_empty_index_data())
    cases_value = index_data.get("cases")
    if not isinstance(cases_value, list):
        index_data["cases"] = []
    entry_by_id: Dict[str, Dict[str, Any]] = {}
    entry_by_signature: Dict[str, List[Dict[str, Any]]] = {}
    for entry in index_data["cases"]:
        if not isinstance(entry, dict):
            continue
        entry = dict(entry)
        case_id = str(entry.get("case_id", ""))
        signature = str(entry.get("signature", ""))
        if not CASE_ID_PATTERN.match(case_id) or not HEX64_PATTERN.match(signature):
            continue
        entry["case_id"] = case_id
        entry["signature"] = signature
        entry["storage_tier"] = get_storage_tier(entry)
        ensure_stats(entry)
        entry_by_id[case_id] = entry
        entry_by_signature.setdefault(signature, []).append(entry)
    index_data["cases"] = [entry_by_id[case_id] for case_id in sorted(entry_by_id)]
    return {"index_data": index_data, "by_id": entry_by_id, "by_signature": entry_by_signature}


def load_case_data(storage: Dict[str, str], entry: Dict[str, Any]) -> Dict[str, Any]:
    case_path = resolve_case_file_path(storage["cases_root"], entry["case_id"])
    case_data = read_json_object(case_path, None)
    if not isinstance(case_data, dict):
        raise MemoryErrorRuntime(f"case file is missing or invalid: {entry['case_id']}")
    if "storage_tier" not in case_data:
        case_data["storage_tier"] = get_storage_tier(entry)
    assert_valid_case_data(case_data)
    if case_data["case_id"] != entry["case_id"] or case_data["signature"] != entry["signature"]:
        raise MemoryErrorRuntime(f"case index metadata mismatch: {entry['case_id']}")
    return case_data


def case_to_index_entry(case_data: Dict[str, Any]) -> Dict[str, Any]:
    assert_valid_case_data(case_data)
    entry = {
        "case_id": case_data["case_id"],
        "signature": case_data["signature"],
        "scope_kind": case_data["scope_kind"],
        "scope_confidence": case_data["scope_confidence"],
        "scope_reason": case_data["scope_reason"],
        "projects_seen": list(case_data["projects_seen"]),
        "stats": dict(case_data["stats"]),
        "created_at": case_data["created_at"],
        "updated_at": case_data["updated_at"],
        "storage_tier": case_data["storage_tier"],
        "has_solution": bool(str(case_data.get("solution", "")).strip()),
        "last_verified_at": str(case_data.get("last_verified_at", "")),
        "last_hit_at": str(case_data.get("last_hit_at", "")),
    }
    for field in ("archived_at", "reactivated_at", "archive_reason"):
        if str(case_data.get(field, "")):
            entry[field] = str(case_data[field])
    return entry


def put_case_in_catalog(catalog: Dict[str, Any], case_data: Dict[str, Any]) -> None:
    entry = case_to_index_entry(case_data)
    old_entry = catalog["by_id"].get(entry["case_id"])
    if old_entry is not None:
        old_signature_entries = catalog["by_signature"].get(old_entry["signature"], [])
        catalog["by_signature"][old_entry["signature"]] = [
            item for item in old_signature_entries if item["case_id"] != entry["case_id"]
        ]
    catalog["by_id"][entry["case_id"]] = entry
    catalog["by_signature"].setdefault(entry["signature"], []).append(entry)


def save_case_catalog(
    storage: Dict[str, str], catalog: Dict[str, Any], changed_cases: Dict[str, Dict[str, Any]]
) -> None:
    for case_id in sorted(changed_cases):
        case_data = changed_cases[case_id]
        assert_valid_case_data(case_data)
        write_json_object(resolve_case_file_path(storage["cases_root"], case_id), case_data)
        put_case_in_catalog(catalog, case_data)
    case_entries = [catalog["by_id"][case_id] for case_id in sorted(catalog["by_id"])]
    index_data = {"schema_version": "1.0", "updated_at": get_iso_timestamp(), "cases": case_entries}
    write_json_object(storage["index_path"], index_data)


def get_failure_events_data(storage: Dict[str, str]) -> Dict[str, Any]:
    data = read_json_object(storage["failure_events_path"], get_empty_failure_data())
    events = data.get("events")
    data["events"] = limit_failure_events(events if isinstance(events, list) else [])
    return data


def save_failure_events_data(storage: Dict[str, str], data: Dict[str, Any]) -> None:
    data["schema_version"] = "1.0"
    data["updated_at"] = get_iso_timestamp()
    data["events"] = limit_failure_events(list(data.get("events", [])))
    write_json_object(storage["failure_events_path"], data)


def update_case_scope_convergence(case_data: Dict[str, Any], current_project_id: str, project_specific_evidence: bool) -> None:
    case_data["projects_seen"] = ensure_array_contains(coerce_projects_seen(case_data.get("projects_seen")), current_project_id)
    project_count = len(case_data["projects_seen"])
    if case_data["scope_kind"] == "candidate_project" and project_count >= 2:
        case_data["scope_kind"] = "global"
        if float(case_data.get("scope_confidence", 0.0)) < 0.85:
            case_data["scope_confidence"] = get_normalized_scope_confidence(0.85)
        if not str(case_data.get("scope_reason", "")).strip():
            case_data["scope_reason"] = "candidate_project converged to global after multi-project verification."
    elif case_data["scope_kind"] == "candidate_global" and project_count <= 1 and project_specific_evidence:
        case_data["scope_kind"] = "project"
        if float(case_data.get("scope_confidence", 0.0)) > 0.70:
            case_data["scope_confidence"] = get_normalized_scope_confidence(0.70)
        if not str(case_data.get("scope_reason", "")).strip():
            case_data["scope_reason"] = "candidate_global converged to project due to project-specific evidence."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--action", dest="Action", required=True, choices=["record-failure", "query-before-retry", "record-success", "inspect"])
    parser.add_argument("--codex-home", dest="CodexHome", default="")
    parser.add_argument("--project-id", dest="ProjectId", default="")
    parser.add_argument("--command-text", dest="CommandText", default="")
    parser.add_argument("--error-text", dest="ErrorText", default="")
    parser.add_argument("--resolution", dest="Resolution", default="")
    parser.add_argument("--scope-kind", dest="ScopeKind", default="")
    parser.add_argument("--scope-confidence", dest="ScopeConfidence", type=float, default=None)
    parser.add_argument("--scope-reason", dest="ScopeReason", default="")
    parser.add_argument("--project-specific", dest="ProjectSpecific", action="store_true")
    parser.add_argument("--json", dest="Json", action="store_true")
    parser.add_argument("-h", "--help", action="help")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    codex_home = normalize_user_path(args.CodexHome) if args.CodexHome else get_default_codex_home()
    memory_root = os.path.abspath(os.path.join(codex_home, "memories", "command-failure-memory"))
    if not test_path_within_root(codex_home, memory_root):
        raise MemoryErrorRuntime(f"memory root must stay under codex_home: codex_home={codex_home}, memory_root={memory_root}")

    storage = new_memory_storage(memory_root)
    project = get_canonical_project_id(args.ProjectId)
    now = get_iso_timestamp()

    def run_action() -> Dict[str, Any]:
        action = args.Action
        if action == "record-failure":
            sig = get_case_signature(args.CommandText, args.ErrorText)
            events_data = get_failure_events_data(storage)
            matched = None
            events: List[Dict[str, Any]] = []
            for entry in events_data.get("events", []):
                if not isinstance(entry, dict):
                    continue
                if entry.get("signature") == sig["signature"] and entry.get("project_id") == project:
                    matched = entry
                events.append(entry)
            if matched is None:
                matched = {
                    "signature": sig["signature"],
                    "command_signature": limit_string_length(sig["command_signature"], MAX_STORED_SIGNATURE_LENGTH, suffix=""),
                    "error_signature": limit_string_length(sig["error_signature"], MAX_STORED_SIGNATURE_LENGTH, suffix=""),
                    "project_id": project,
                    "first_failed_at": now,
                    "last_failed_at": now,
                    "failure_count": 1,
                    "last_query_at": "",
                }
                events.append(matched)
            else:
                matched["last_failed_at"] = now
                matched["failure_count"] = int(matched.get("failure_count", 0)) + 1
            events_data["events"] = events
            save_failure_events_data(storage, events_data)
            return {
                "ok": True,
                "action": action,
                "signature": sig["signature"],
                "project_id": project,
                "failure_count": int(matched["failure_count"]),
                "query_performed": False,
                "query_should_happen_before_retry": True,
                "memory_root": memory_root,
            }

        if action == "query-before-retry":
            sig = get_case_signature(args.CommandText, args.ErrorText)
            events_data = get_failure_events_data(storage)
            event = None
            for entry in events_data.get("events", []):
                if isinstance(entry, dict) and entry.get("signature") == sig["signature"] and entry.get("project_id") == project:
                    event = entry
                    break
            if event is None:
                return {
                    "ok": True,
                    "action": action,
                    "signature": sig["signature"],
                    "project_id": project,
                    "query_permitted": False,
                    "reason": "retry_gate_not_met",
                    "suggestions": [],
                    "memory_root": memory_root,
                }
            event["last_query_at"] = now
            save_failure_events_data(storage, events_data)
            catalog = get_case_catalog(storage)
            changed_cases: Dict[str, Dict[str, Any]] = {}
            suggestions: List[Dict[str, Any]] = []
            exact_entries = catalog["by_signature"].get(sig["signature"], [])
            exact_case_ids = {entry["case_id"] for entry in exact_entries}
            for entry in exact_entries:
                case_data = load_case_data(storage, entry)
                reactivated = get_storage_tier(case_data) == "archived"
                if reactivated:
                    ensure_active_capacity(
                        storage, catalog, changed_cases, excluded_case_ids=exact_case_ids
                    )
                    case_data["storage_tier"] = "active"
                    case_data["reactivated_at"] = now
                case_data["updated_at"] = now
                ensure_stats(case_data)
                case_data["stats"]["hit_count"] = int(case_data["stats"]["hit_count"]) + 1
                case_data["last_hit_at"] = now
                suggestions.append(
                    {
                        "case_id": case_data["case_id"],
                        "scope_kind": case_data["scope_kind"],
                        "scope_confidence": case_data["scope_confidence"],
                        "scope_reason": case_data["scope_reason"],
                        "solution": case_data["solution"],
                        "stats": case_data["stats"],
                        "projects_seen": list(case_data["projects_seen"]),
                        "storage_tier": case_data["storage_tier"],
                        "reactivated": reactivated,
                    }
                )
                changed_cases[case_data["case_id"]] = case_data
                put_case_in_catalog(catalog, case_data)
            if suggestions:
                save_case_catalog(storage, catalog, changed_cases)
            return {
                "ok": True,
                "action": action,
                "signature": sig["signature"],
                "project_id": project,
                "query_permitted": True,
                "reason": "retry_gate_passed",
                "suggestions": suggestions,
                "memory_root": memory_root,
            }

        if action == "record-success":
            if not str(args.Resolution).strip():
                raise MemoryErrorRuntime("resolution is required for record-success.")
            sig = get_case_signature(args.CommandText, args.ErrorText)
            catalog = get_case_catalog(storage)
            changed_cases: Dict[str, Dict[str, Any]] = {}
            case_data = None
            existing_entries = catalog["by_signature"].get(sig["signature"], [])
            if existing_entries:
                case_data = load_case_data(storage, existing_entries[0])
            created_new_case = False
            if case_data is None:
                if not args.ScopeKind:
                    raise MemoryErrorRuntime("scope_kind is required when no equivalent case exists.")
                if args.ScopeKind not in VALID_SCOPE_KINDS:
                    raise MemoryErrorRuntime(f"invalid scope_kind: {args.ScopeKind}")
                ensure_active_capacity(storage, catalog, changed_cases)
                case_id = new_case_id(sig["signature"], catalog["by_id"])
                confidence = (
                    get_normalized_scope_confidence(args.ScopeConfidence)
                    if args.ScopeConfidence is not None
                    else (0.60 if args.ScopeKind.startswith("candidate_") else 0.80)
                )
                scope_reason = (
                    get_sanitized_stored_text(args.ScopeReason, MAX_STORED_REASON_LENGTH)
                    if args.ScopeReason.strip()
                    else get_sanitized_stored_text(get_default_scope_reason(args.ScopeKind), MAX_STORED_REASON_LENGTH)
                )
                case_data = {
                    "schema_version": "1.0",
                    "case_id": case_id,
                    "signature": sig["signature"],
                    "command_signature": limit_string_length(sig["command_signature"], MAX_STORED_SIGNATURE_LENGTH, suffix=""),
                    "error_signature": limit_string_length(sig["error_signature"], MAX_STORED_SIGNATURE_LENGTH, suffix=""),
                    "command_excerpt": get_sanitized_stored_text(args.CommandText, MAX_STORED_COMMAND_LENGTH),
                    "error_excerpt": get_sanitized_stored_text(args.ErrorText, MAX_STORED_ERROR_LENGTH),
                    "scope_kind": args.ScopeKind,
                    "scope_confidence": get_normalized_scope_confidence(confidence),
                    "scope_reason": scope_reason,
                    "projects_seen": [project],
                    "solution": get_sanitized_stored_text(args.Resolution, MAX_STORED_RESOLUTION_LENGTH),
                    "stats": {"hit_count": 0, "verify_count": 1, "incident_count": 1},
                    "created_at": now,
                    "updated_at": now,
                    "last_verified_at": "",
                    "last_hit_at": "",
                    "storage_tier": "active",
                }
                created_new_case = True

            assert_valid_case_data(case_data)
            ensure_stats(case_data)
            if not str(case_data.get("solution", "")).strip() and args.Resolution.strip():
                case_data["solution"] = get_sanitized_stored_text(args.Resolution, MAX_STORED_RESOLUTION_LENGTH)
            case_data["stats"]["verify_count"] = int(case_data["stats"]["verify_count"]) + 1
            case_data["last_verified_at"] = now
            case_data["updated_at"] = now
            update_case_scope_convergence(case_data, project, args.ProjectSpecific)
            changed_cases[case_data["case_id"]] = case_data
            put_case_in_catalog(catalog, case_data)
            save_case_catalog(storage, catalog, changed_cases)

            events_data = get_failure_events_data(storage)
            events_data["events"] = [
                entry
                for entry in events_data.get("events", [])
                if not (
                    isinstance(entry, dict)
                    and entry.get("signature") == sig["signature"]
                    and entry.get("project_id") == project
                )
            ]
            save_failure_events_data(storage, events_data)
            return {
                "ok": True,
                "action": action,
                "signature": sig["signature"],
                "project_id": project,
                "created_new_case": created_new_case,
                "case_id": case_data["case_id"],
                "scope_kind": case_data["scope_kind"],
                "scope_confidence": case_data["scope_confidence"],
                "scope_reason": case_data["scope_reason"],
                "stats": case_data["stats"],
                "projects_seen": list(case_data["projects_seen"]),
                "memory_root": memory_root,
            }

        catalog = get_case_catalog(storage)
        events_data = get_failure_events_data(storage)
        active_case_count = get_active_case_count(catalog["by_id"])
        return {
            "ok": True,
            "action": action,
            "memory_root": memory_root,
            "index_path": storage["index_path"],
            "failure_events_path": storage["failure_events_path"],
            "case_count": len(catalog["by_id"]),
            "active_case_count": active_case_count,
            "archived_case_count": len(catalog["by_id"]) - active_case_count,
            "pending_failure_count": len(events_data["events"]),
            "cases": list(catalog["index_data"].get("cases", [])),
        }

    payload = invoke_with_memory_lock(memory_root, run_action)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except MemoryErrorRuntime as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
