"""Isolated GTO behavior runs. The scorer remains outside the mounted filesystem."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/gto-workflow"
sys.path.insert(0, str(ROOT / 'scripts'))
from runtime_common import MANAGED_WSL_RUNTIME_FILES, load_windows_external_capabilities
sys.path.insert(0, str(ROOT / 'skills/global-task-orchestrator/scripts'))
from runtime_evidence import copy_installed_gto


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()
            and p.name != "auth.json"}


SCENARIO_CARD_FIELDS = {
    "scenario_id",
    "target_behavior",
    "initial_state",
    "business_prompt",
    "trigger",
    "observable_evidence",
    "forbidden_behavior",
    "stop_condition",
    "preparation_checks",
    "cost_budget",
    "cleanup",
    "level",
    "run_policy",
}
SCENARIO_LEVELS = {f"L{number}" for number in range(7)}
RUN_POLICIES = {
    "preparation_only",
    "targeted_once",
    "conditional_once",
    "complete_once",
    "explicit_approval_once",
}
SCENARIO_STATUSES = {
    "PASS",
    "EFFECT_FAIL",
    "PREPARATION_INVALID",
    "NOT_OBSERVED",
    "INCONCLUSIVE",
}
SIMPLE_COMPLETE_CONDITIONS = {
    "single_agent",
    "local_lightweight_dependencies",
    "fast_execution",
    "small_deterministic_data",
    "within_cost_budget",
    "cheaper_than_targeted_fixture",
    "no_duplicate_candidate_evidence",
}
L6_APPROVAL_FIELDS = (
    "task_id",
    "candidate_fingerprint",
    "formal_round",
    "scenario_id",
    "approved_by",
    "approved_at",
)
REQUIRED_BUDGET_LIMITS = ("max_seconds", "max_attempts", "max_scenarios")


def validate_scenario_card(card):
    if not isinstance(card, dict):
        raise ValueError("scenario card must be an object")
    for field in sorted(SCENARIO_CARD_FIELDS):
        if field not in card:
            raise ValueError(f"scenario card missing {field}")
    if card["level"] not in SCENARIO_LEVELS:
        raise ValueError("scenario card level must be one of L0 through L6")
    if card["run_policy"] not in RUN_POLICIES:
        raise ValueError("scenario card run_policy is not a known policy")
    for field in (
            "scenario_id", "target_behavior", "initial_state", "business_prompt",
            "trigger", "stop_condition", "cleanup"):
        if not isinstance(card[field], str) or not card[field].strip():
            raise ValueError(f"scenario card {field} must be a non-empty string")
    for field in ("observable_evidence", "forbidden_behavior", "preparation_checks"):
        if (not isinstance(card[field], list)
                or any(not isinstance(value, str) or not value.strip() for value in card[field])):
            raise ValueError(f"scenario card {field} must be a list of strings")
    budget = card["cost_budget"]
    if (not isinstance(budget, dict) or not budget
            or any(not isinstance(key, str) or not key.strip() for key in budget)
            or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
                   for value in budget.values())):
        raise ValueError("scenario card cost_budget must contain named positive integer limits")
    for field in REQUIRED_BUDGET_LIMITS:
        if field not in budget:
            raise ValueError(f"scenario card cost_budget missing {field}")
    return card


def simple_complete_blackbox_allowed(conditions):
    if not isinstance(conditions, dict):
        raise ValueError("simple complete black-box conditions must be an object")
    for field in sorted(SIMPLE_COMPLETE_CONDITIONS):
        if field not in conditions:
            raise ValueError(f"simple complete black-box conditions missing {field}")
        if not isinstance(conditions[field], bool):
            raise ValueError(f"simple complete black-box condition {field} must be boolean")
    return all(conditions[field] for field in SIMPLE_COMPLETE_CONDITIONS)


def select_default_scenarios(cards, prohibited_levels=None):
    prohibited = set(prohibited_levels or ()) | {"L6"}
    unknown = prohibited - SCENARIO_LEVELS
    if unknown:
        raise ValueError("prohibited_levels contains an unknown level")
    selected = []
    scenario_ids = set()
    for card in cards:
        validate_scenario_card(card)
        scenario_id = card["scenario_id"]
        if scenario_id in scenario_ids:
            raise ValueError(f"duplicate scenario_id is not allowed: {scenario_id}")
        scenario_ids.add(scenario_id)
        if card["level"] not in prohibited:
            selected.append(card)
    return selected


def build_scenario_result(card, *, status, observed, evidence):
    validate_scenario_card(card)
    if status not in SCENARIO_STATUSES:
        raise ValueError("status must use a shared scenario classification")
    if not isinstance(observed, bool):
        raise ValueError("observed must be boolean")
    if (not isinstance(evidence, list)
            or any(not isinstance(item, str) or not item.strip() for item in evidence)):
        raise ValueError("evidence must be a list of paths or references")
    return {
        "scenario_id": card["scenario_id"],
        "level": card["level"],
        "status": status,
        "observed": observed,
        "evidence": list(evidence),
    }


def _validate_l6_approval(card, context, approval):
    validate_scenario_card(card)
    if card["level"] != "L6":
        raise ValueError("L6 approval can only be consumed for an L6 scenario")
    if not isinstance(context, dict):
        raise ValueError("current context must be an object")
    for field in ("task_id", "candidate_fingerprint", "formal_round"):
        if field not in context or context[field] in (None, ""):
            raise ValueError(f"current context missing {field}")
    if not isinstance(approval, dict):
        raise ValueError("current L6 approval must be an object")
    expected = {
        "task_id": context.get("task_id"),
        "candidate_fingerprint": context.get("candidate_fingerprint"),
        "formal_round": context.get("formal_round"),
        "scenario_id": card["scenario_id"],
        "approved_by": "user",
    }
    for field in L6_APPROVAL_FIELDS:
        if field not in approval:
            raise ValueError(f"L6 approval missing {field}")
        if field != "approved_at" and approval[field] != expected[field]:
            raise ValueError(f"L6 approval {field} does not match the current run")
    approved_at = approval["approved_at"]
    try:
        parsed = datetime.fromisoformat(approved_at)
    except (TypeError, ValueError):
        raise ValueError("L6 approval approved_at must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ValueError("L6 approval approved_at must include a timezone")
    token_payload = {field: approval[field] for field in L6_APPROVAL_FIELDS}
    token = hashlib.sha256(json.dumps(
        token_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return token


def _append_l6_consumption_event(path, token, approval):
    path = Path(path)
    if not path.parent.is_dir():
        raise ValueError("attempt_events_path must point into an existing attempt evidence directory")
    if path.is_symlink():
        raise ValueError("attempt_events_path must not be a symlink")
    event = {
        "event": "approval_consumed",
        "approval_token": token,
        **{field: approval[field] for field in L6_APPROVAL_FIELDS},
    }
    line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
    import fcntl
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            stream.seek(0)
            for number, existing_line in enumerate(stream, 1):
                try:
                    existing = json.loads(existing_line)
                except json.JSONDecodeError:
                    raise ValueError(
                        f"attempt event evidence contains invalid JSON at line {number}"
                    ) from None
                if (existing.get("event") == "approval_consumed"
                        and existing.get("approval_token") == token):
                    raise ValueError("L6 approval was already consumed; it is single-use")
            stream.seek(0, os.SEEK_END)
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _check_l6_consumption_event(path, token):
    path = Path(path)
    if not path.parent.is_dir():
        raise ValueError("attempt_events_path must point into an existing attempt evidence directory")
    if path.is_symlink():
        raise ValueError("attempt_events_path must not be a symlink")
    if not path.exists():
        return
    import fcntl
    with path.open("r", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
        try:
            for number, existing_line in enumerate(stream, 1):
                try:
                    existing = json.loads(existing_line)
                except json.JSONDecodeError:
                    raise ValueError(
                        f"attempt event evidence contains invalid JSON at line {number}"
                    ) from None
                if (existing.get("event") == "approval_consumed"
                        and existing.get("approval_token") == token):
                    raise ValueError("L6 approval was already consumed; it is single-use")
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def consume_l6_approval(card, context, approval, consumed):
    token = _validate_l6_approval(card, context, approval)
    if not hasattr(consumed, "add") or not hasattr(consumed, "__contains__"):
        raise ValueError("consumed approvals must be a mutable set-like collection")
    if token in consumed:
        raise ValueError("L6 approval was already consumed; it is single-use and once only")
    attempt_events_path = context.get("attempt_events_path")
    if attempt_events_path:
        _append_l6_consumption_event(attempt_events_path, token, approval)
    consumed.add(token)
    return token


def launch_scenario(card, context, approval, consumed, launcher):
    if not callable(launcher):
        raise ValueError("launcher must be callable")
    prelaunch_scenario(card, context, approval, consumed)
    if card["level"] == "L6":
        consume_l6_approval(card, context, approval, consumed)
    return launcher(card)


def prelaunch_scenario(card, context, approval, consumed, prohibited_levels=None):
    validate_scenario_card(card)
    prohibited = set(prohibited_levels or ())
    if card["level"] == "L6":
        token = _validate_l6_approval(card, context, approval)
        if card["run_policy"] != "explicit_approval_once":
            raise ValueError("L6 run_policy must be explicit_approval_once")
        if "L6" in prohibited:
            raise ValueError("L6 is prohibited by the current task")
        if not context.get("attempt_events_path"):
            raise ValueError("L6 current context must provide attempt_events_path evidence")
        _check_l6_consumption_event(context["attempt_events_path"], token)
    else:
        selected = select_default_scenarios([card], prohibited_levels=prohibited)
        if not selected:
            raise ValueError(f"scenario level {card['level']} is prohibited by the current task")
    return card


def wait_for_scenario_process(process, card, *, mode, stop_owned=None):
    validate_scenario_card(card)
    if mode not in {"run", "probe"}:
        raise ValueError("budgeted process wait mode must be run or probe")
    timeout = card["cost_budget"]["max_seconds"]
    if stop_owned is None:
        stop_owned = stop_owned_process
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        cleanup = stop_owned(process)
        return {
            "exit_code": getattr(process, "returncode", None),
            "timed_out": True,
            "stop_reason": "cost_budget.max_seconds",
            "cleanup": cleanup,
        }
    return {
        "exit_code": exit_code,
        "timed_out": False,
        "stop_reason": "process_exit",
        "cleanup": {"reaped": True, "escalated": False},
    }


def _expected_gto_candidate_marker():
    contract_path = (ROOT / "skills/global-task-orchestrator/references/"
                     "revision-3-contract.example.json")
    try:
        contract = json.loads(contract_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"candidate compatibility contract cannot be read: {error}") from None
    revision = contract.get("workflow_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
        raise ValueError("candidate compatibility contract has an invalid revision")
    return f"global-task-orchestrator revision {revision}"


def copy_validated_stage_fixture(source, destination, expected_candidate_marker=None):
    source, destination = Path(source), Path(destination)
    manifest_path = source / "fixture-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"fixture manifest cannot be read: {error}") from None
    declared = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(declared, dict):
        raise ValueError("fixture manifest has an invalid schema")
    actual = {}
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("fixture must not contain symlinks")
        if path.is_file() and path != manifest_path:
            relative = path.relative_to(source).as_posix()
            actual[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != declared:
        raise ValueError("fixture hash manifest does not match source files")
    try:
        state = json.loads((source / "state-slice.json").read_text())
        marker = (source / "tool-root/installed.marker").read_text().strip()
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"fixture structure cannot be read: {error}") from None
    valid_phases = {"planning", "doc_sync", "test_sync", "code_impl", "review", "blocked"}
    if (not isinstance(state, dict)
            or not isinstance(state.get("task_id"), str) or not state["task_id"].strip()
            or state.get("current_phase") not in valid_phases
            or not isinstance(state.get("tool_root"), str) or not state["tool_root"].strip()
            or not isinstance(state.get("business_root"), str) or not state["business_root"].strip()
            or Path(state["tool_root"]) == Path(state["business_root"])):
        raise ValueError("fixture state structure, phase, task identity, or root separation is invalid")
    expected_marker = expected_candidate_marker or _expected_gto_candidate_marker()
    if marker != expected_marker:
        raise ValueError("fixture candidate compatibility marker is invalid")
    if destination.exists() or destination.is_symlink():
        raise ValueError("fixture destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        for relative in sorted(actual):
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"files": sorted(actual)}


def summarize_access_evidence(accesses):
    if not isinstance(accesses, list) or any(not isinstance(item, dict) for item in accesses):
        raise ValueError("access evidence must be a list of objects")
    source_keys = {
        "MEMORY.md": "memory_md",
        "rollout_summaries": "rollout_summaries",
        "other_long_term_memory": "other_long_term_memory",
        "CFM": "cfm",
    }
    report = {key: {"access_count": 0, "accesses": [], "observation": "unknown"}
              for key in source_keys.values()}
    unknown_sources = []
    for access in accesses:
        key = source_keys.get(access.get("source"))
        if key is None:
            unknown_sources.append(access)
            continue
        report[key]["access_count"] += 1
        report[key]["accesses"].append(dict(access))
        observation = access.get("observation", "observed_read")
        if observation not in {
                "observed_read", "observed_not_read", "unknown", "not_applicable"}:
            raise ValueError("access observation must use the shared four-state vocabulary")
    for key, item in report.items():
        observations = [access.get("observation", "observed_read")
                        for access in item["accesses"]]
        if "observed_read" in observations:
            item["observation"] = "observed_read"
        elif observations and len(set(observations)) == 1:
            item["observation"] = observations[0]
        elif observations:
            item["observation"] = "unknown"
    cfm_accesses = report["cfm"]["accesses"]
    if not cfm_accesses:
        report["cfm"]["observation"] = "not_applicable"
        strict = "not_applicable"
    else:
        chains = {}
        strict = True
        evidence_incomplete = False
        for access in cfm_accesses:
            chain = access.get("failure_chain_id")
            operation = access.get("operation")
            failure_kind = access.get("failure_kind")
            if (failure_kind == "expected_tdd_red"
                    or access.get("purpose") in {"business_lookup", "unrelated_history"}):
                strict = False
            elif failure_kind != "unexpected_failure":
                evidence_incomplete = True
            if not isinstance(chain, str) or not chain or operation not in {
                    "record-failure", "query-before-retry", "record-success"}:
                strict = False
                continue
            chains.setdefault(chain, []).append(operation)
        expected = ["record-failure", "query-before-retry", "record-success"]
        if strict and chains:
            if all(operations == expected for operations in chains.values()):
                strict = "unknown" if evidence_incomplete else True
            elif all(operations == expected[:len(operations)] for operations in chains.values()):
                strict = "unknown"
            else:
                strict = False
        else:
            strict = False
    report["cfm"]["strict_failure_chain"] = strict
    report["unknown_sources"] = unknown_sources
    return report


def public_plugin_config(settings, declaration_path):
    """Preserve declared disk states, not plugin credentials or runtime access."""
    declaration, errors = load_windows_external_capabilities(declaration_path)
    if errors:
        raise RuntimeError('invalid installed Windows capability declaration')
    plugins = settings.get('plugins', {})
    if not isinstance(plugins, dict):
        raise RuntimeError('invalid installed plugin configuration')
    names = sorted({name for item in declaration['capabilities'] for name in item['required_plugins']})
    result = ''
    for name in names:
        if name not in plugins:
            continue
        entry = plugins[name]
        enabled = entry.get('enabled', True) if isinstance(entry, dict) else None
        if not isinstance(enabled, bool):
            raise RuntimeError('invalid installed plugin enabled state: ' + name)
        result += f'\n[plugins.{json.dumps(name)}]\nenabled = {str(enabled).lower()}\n'
    return result



def check_public_schema_source():
    legacy = ROOT / 'schemas/orchestrator-task-state.schema.json'
    if legacy.exists() or legacy.is_symlink():
        raise RuntimeError('legacy GTO root schema source must be retired before preparation')


def copy_installed_environment(host_codex, isolated_codex, runtime):
    """Copy only public, bootstrap-bound entry/runtime bytes and their audit sources."""
    check_public_schema_source()
    def read(root, relative):
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError('public environment source escapes its declared root: ' + relative)
        return path.read_bytes()

    receipt_relative = '.ai-harness/bootstrap.receipt.json'
    receipt_bytes = read(host_codex, receipt_relative)
    receipt = json.loads(receipt_bytes)
    if receipt.get('harness_root') != str(ROOT) or receipt.get('codex_home') != str(host_codex):
        raise RuntimeError('bootstrap receipt installation identity mismatch')
    contents = {receipt_relative: receipt_bytes, 'AGENTS.md': read(host_codex, 'AGENTS.md')}
    template = 'templates/codex/AGENTS.global.md'
    if (receipt.get('template_path') != str(ROOT / template)
            or receipt.get('target_path') != str(host_codex / 'AGENTS.md')
            or receipt.get('template_sha256') != hashlib.sha256(read(ROOT, template)).hexdigest()
            or receipt.get('target_sha256') != hashlib.sha256(contents['AGENTS.md']).hexdigest()):
        raise RuntimeError('bootstrap entry/template hash or path drift')
    entries = receipt.get('managed_runtime_files', [])
    expected_targets = {str(host_codex / '.ai-harness/runtime/wsl-environment' / target) for target, _ in MANAGED_WSL_RUNTIME_FILES}
    if len(entries) != len(expected_targets) or {e.get('target_path') for e in entries} != expected_targets:
        raise RuntimeError('bootstrap runtime inventory differs from the explicit public allowlist')
    sources = {}
    for target, source in MANAGED_WSL_RUNTIME_FILES:
        relative = '.ai-harness/runtime/wsl-environment/' + target
        entry = next(e for e in entries if e['target_path'] == str(host_codex / relative))
        source_bytes, target_bytes = read(ROOT, source), read(host_codex, relative)
        if (entry.get('source_path') != str(ROOT / source)
                or entry.get('source_sha256') != hashlib.sha256(source_bytes).hexdigest()
                or entry.get('target_sha256') != hashlib.sha256(target_bytes).hexdigest()
                or source_bytes != target_bytes):
            raise RuntimeError('bootstrap runtime source/target drift: ' + source)
        contents[relative], sources[source] = target_bytes, source_bytes
    for root, items in ((isolated_codex, contents), (runtime, sources)):
        for relative, data in items.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return {'installed_hashes': {p: hashlib.sha256(b).hexdigest() for p, b in contents.items()},
            'audit_source_hashes': {p: hashlib.sha256(b).hexdigest() for p, b in sources.items()}}


def stop_owned_process(process, grace_seconds=10):
    """Only accepts a Popen launched by this runner with start_new_session=True."""
    evidence = {"reaped": process is None, "escalated": False}
    if process is None:
        return evidence
    if process.poll() is not None:
        process.wait()
        evidence["reaped"] = True
        return evidence
    if os.getpgid(process.pid) != process.pid:
        raise RuntimeError("refusing to signal a process without its own session group")
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        evidence["escalated"] = True
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=grace_seconds)
    evidence["reaped"] = process.poll() is not None
    return evidence


def namespace_lifecycle_probe():
    """Prove namespace exit removes a child that starts its own process session."""
    script = ("import os,subprocess,sys; "
              "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],"
              "start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
              "print(os.readlink('/proc/self/ns/pid'),flush=True)")
    command = ["bwrap", "--unshare-user", "--unshare-pid", "--die-with-parent",
               "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib",
               "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
               "--tmpfs", "/tmp", "--chdir", "/tmp", "/usr/bin/python3", "-c", script]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    namespace = result.stdout.strip()
    survivors = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdecimal():
            try:
                if os.readlink(entry / "ns/pid") == namespace:
                    survivors.append(int(entry.name))
            except (FileNotFoundError, PermissionError):
                pass
    return {"exit_code": result.returncode, "namespace": namespace, "survivors": survivors,
            "ok": result.returncode == 0 and namespace.startswith("pid:[") and not survivors}


def preserve_owned_evidence(project, codex_home, evidence):
    shutil.copytree(project, evidence / "project-after", symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__"))
    sessions = codex_home / "sessions"
    if sessions.is_dir():
        for source in sessions.rglob("*.jsonl"):
            if source.is_symlink():
                continue
            target = evidence / "session-traces" / source.relative_to(sessions)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _read_json_object(path, label):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} cannot be read as JSON: {error}") from None
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("inspect", "probe", "run"), default="inspect")
    parser.add_argument("--scenario", choices=("normal", "review-boundaries", "entry-precision", "project-config"), default="normal")
    parser.add_argument("--scenario-card")
    parser.add_argument("--current-context")
    parser.add_argument("--approval")
    parser.add_argument("--prohibit-level", action="append", default=[], choices=sorted(SCENARIO_LEVELS))
    args = parser.parse_args()
    scenario_card = None
    current_context = None
    approval = None
    consumed_approvals = set()
    if args.mode in {"probe", "run"}:
        if not args.scenario_card:
            raise ValueError(f"--scenario-card is required for --mode {args.mode}")
        if not args.current_context:
            raise ValueError(f"--current-context is required for --mode {args.mode}")
        scenario_card = _read_json_object(args.scenario_card, "scenario card")
        current_context = _read_json_object(args.current_context, "current context")
        if args.approval:
            approval = _read_json_object(args.approval, "L6 approval")
        prelaunch_scenario(
            scenario_card,
            current_context,
            approval,
            consumed_approvals,
            prohibited_levels=args.prohibit_level,
        )
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + args.mode
    evidence = ROOT / ".artifacts/gto-workflow/blackbox" / run_id
    evidence.mkdir(parents=True, exist_ok=False)
    if scenario_card is not None:
        write_json(evidence / "scenario-card.json", scenario_card)
        write_json(evidence / "current-context.json", current_context)
    temp_base = ROOT / ".tmp/gto-workflow/blackbox"
    temp_base.mkdir(parents=True, exist_ok=True)
    host_codex = Path(os.environ["CODEX_HOME"])
    binary = Path(shutil.which("codex")).resolve()
    # Read only non-secret, explicitly selected settings; never copy host configuration.
    settings = tomllib.loads((host_codex / "config.toml").read_text())
    model = settings.get("model", "gpt-6-astra")
    effort = settings.get("model_reasoning_effort", "high")
    process = None
    cleanup = {"run_id": run_id, "temp_removed": False, "process_reaped": False}
    try:
        check_public_schema_source()
        frozen = json.loads((FIXTURES / "manifest.json").read_text())["fixtures"]
        actual = {name: digest for name, digest in hashes(FIXTURES).items() if name != "manifest.json"}
        if actual != frozen:
            raise RuntimeError("frozen fixture manifest differs; review and refreeze before running")
        temporary_context = tempfile.TemporaryDirectory(prefix=run_id + "-", dir=temp_base)
        temporary = temporary_context.name
        run = Path(temporary)
        project, home, runtime = [run / p for p in ("project", "home", "harness")]
        for p in (project, home, runtime):
            p.mkdir()
        empty_memory = run / "empty-memory"
        empty_memory.mkdir()
        scenario = FIXTURES / args.scenario
        shutil.copytree(FIXTURES / "normal/project", project, dirs_exist_ok=True)
        if args.scenario != "normal":
            shutil.copytree(scenario / "project", project, dirs_exist_ok=True)
        # Only support rules/scripts/docs come from the declared harness. Executed GTO
        # code and its schema below always come from the receipt-bound installation.
        for relative in ("rules", "schemas", "scripts", "templates"):
            source_root = ROOT / relative
            if any(not p.resolve().is_relative_to(ROOT.resolve()) for p in [source_root, *source_root.rglob('*')]):
                raise RuntimeError('public support source escapes the declared harness: ' + relative)
            shutil.copytree(ROOT / relative, runtime / relative,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for relative in ("docs/SUBAGENT_GOVERNANCE.md", "docs/ARCHITECTURE.md",
                         "docs/CODEX_COMPAT.md", "docs/PROJECT_TEMPLATE.md",
                         "config/ai/wsl-tool-baseline.json"):
            source = ROOT / relative
            if source.is_file():
                if not source.resolve().is_relative_to(ROOT.resolve()):
                    raise RuntimeError('public document source escapes the declared harness: ' + relative)
                target = runtime / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        codex_home = run / "codex-home"
        codex_home.mkdir()
        installed = copy_installed_gto(host_codex, codex_home)
        write_json(evidence / 'default-installed-source-hashes.json', installed)
        receipt = json.loads((codex_home / '.ai-harness/codex-sync.receipt.json').read_text())
        declared_harness = receipt['harness_root']
        if Path(declared_harness).resolve() != ROOT.resolve():
            raise RuntimeError('default installation declares a different harness; explicit source review is required')
        logical_codex_home = receipt['codex_home']
        if logical_codex_home != str(host_codex) or not host_codex.is_absolute():
            raise RuntimeError('sync receipt CODEX_HOME identity mismatch')
        shutil.copytree(codex_home / 'skills', runtime / 'skills')
        environment = copy_installed_environment(host_codex, codex_home, runtime)
        write_json(evidence / 'default-entry-hashes.json', {
            **environment,
            'namespace_harness_path': declared_harness,
            'namespace_codex_home': logical_codex_home,
            'mapping': 'Synthetic allowlisted runtime mounted at original declared path; installed entry bytes unchanged.'})
        config = (f'model = {json.dumps(model)}\nmodel_reasoning_effort = {json.dumps(effort)}\n'
                  'approval_policy = "never"\nsandbox_mode = "workspace-write"\n'
                  '[features]\nmulti_agent = true\nmemories = false\napps = false\n'
                  'plugins = false\nshell_snapshot = false\n'
                  '[sandbox_workspace_write]\nnetwork_access = true\n')
        config += public_plugin_config(settings, codex_home /
            '.ai-harness/runtime/wsl-environment/config/windows-external-capabilities.json')
        (codex_home / "config.toml").write_text(config)
        (evidence / "isolated-config.toml").write_text(config)
        write_json(evidence / "candidate-hashes.json", hashes(runtime))
        write_json(evidence / "fixture-hashes.json", hashes(project))
        subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        subprocess.run(["git", "-C", str(project), "add", "--all"], check=True)
        subprocess.run(["git", "-C", str(project), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                        "commit", "--quiet", "-m", "Frozen business fixture"], check=True)
        baseline = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"],
                                  check=True, text=True, capture_output=True)
        (evidence / "fixture-commit.txt").write_text(baseline.stdout)
        prompt = (scenario_card["business_prompt"] if scenario_card is not None else
                  (FIXTURES / "platform-probe.txt" if args.mode == "probe"
                   else scenario / "prompt.txt").read_text())
        (evidence / "prompt.txt").write_text(prompt)
        argv = ["bwrap", "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
                "--die-with-parent", "--new-session", "--ro-bind", "/usr", "/usr",
                "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
                "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
                "--tmpfs", "/tmp", "--dir", "/etc", "--ro-bind", "/etc/ssl", "/etc/ssl",
                "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
                "--ro-bind", "/etc/hosts", "/etc/hosts",
                "--dir", "/opt/bin", "--ro-bind", str(binary), "/opt/bin/codex",
                "--ro-bind", str(binary.parent / "codex-code-mode-host"), "/opt/bin/codex-code-mode-host",
                "--bind", str(project), "/project", "--bind", str(home), "/home/agent",
                "--bind", str(codex_home), logical_codex_home,
                "--ro-bind", str(empty_memory), logical_codex_home + "/memories",
                "--ro-bind", str(runtime), "/harness",
                "--ro-bind", str(runtime), declared_harness,
                "--ro-bind", str(host_codex / "auth.json"), logical_codex_home + "/auth.json",
                "--chdir", "/project", "--clearenv", "--setenv", "HOME", "/home/agent",
                "--setenv", "CODEX_HOME", logical_codex_home,
                "--setenv", "PATH", "/opt/bin:/usr/local/bin:/usr/bin:/bin",
                "--setenv", "LANG", "C.UTF-8", "--setenv", "PYTHONDONTWRITEBYTECODE", "1"]
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "all_proxy", "no_proxy"):
            if key in os.environ:
                argv.extend(["--setenv", key, os.environ[key]])
        # /usr/local/bin Node commands are symlinks into this public, versioned tool install.
        native_node = Path(shutil.which("node")).resolve()
        if native_node.is_relative_to("/opt"):
            node_install = native_node.parent.parent
            argv.extend(["--ro-bind", str(node_install), str(node_install)])
        # Proxy values can include credentials; evidence contains names only.
        recorded = list(argv)
        for index, value in enumerate(recorded):
            if index > 1 and recorded[index - 2] == "--setenv" and "proxy" in recorded[index - 1].lower():
                recorded[index] = "<inherited privately>"
        write_json(evidence / "launcher.json", {"argv": recorded, "mode": args.mode,
                   "fresh": "new exec; new physical CODEX_HOME at original logical path; no resume/fork; no host history mounts",
                   "auth": "read-only bind; never copied, parsed, hashed or printed"})
        lifecycle = namespace_lifecycle_probe()
        write_json(evidence / "namespace-lifecycle.json", lifecycle)
        if not lifecycle["ok"]:
            raise RuntimeError("namespace child cleanup proof failed")
        write_json(evidence / "installed-hashes.json", hashes(codex_home))
        shutil.copy2(codex_home / '.ai-harness/codex-sync.receipt.json', evidence / 'codex-sync.receipt.json')
        shutil.copy2(codex_home / '.ai-harness/bootstrap.receipt.json', evidence / 'bootstrap.receipt.json')
        check = subprocess.run(argv + ["python3", "-c",
            "import json,os; from pathlib import Path; print(json.dumps({'cwd':os.getcwd(),"
            "'hidden':{p:not Path(p).exists() for p in ['/harness/tests','/harness/docs/tasks',"
            "'/harness/docs/ai'," + repr(logical_codex_home + '/sessions') + "," + repr(logical_codex_home + '/history.jsonl') + ","
            + repr(declared_harness + '/tests') + "," + repr(declared_harness + '/docs/tasks') + ","
            + repr(declared_harness + '/docs/ai') + "]},"
            "'memory_empty':not any((Path(os.environ['CODEX_HOME'])/'memories').iterdir()),"
            "'skill':(Path(os.environ['CODEX_HOME'])/'skills/global-task-orchestrator/SKILL.md').is_file()}))"],
            text=True, capture_output=True)
        (evidence / "boundary.stdout").write_text(check.stdout)
        (evidence / "boundary.stderr").write_text(check.stderr)
        if check.returncode or not all(json.loads(check.stdout)["hidden"].values()) or not json.loads(check.stdout)["memory_empty"]:
            raise RuntimeError("filesystem boundary probe failed")
        doctor = subprocess.run(argv + ['python3', logical_codex_home + '/.ai-harness/runtime/wsl-environment/bin/doctor-core.py',
            '--repo-root', declared_harness, '--codex-home', logical_codex_home, '--json'], text=True, capture_output=True)
        write_json(evidence / 'namespace-doctor.json', {'exit_code': doctor.returncode,
            'stdout': doctor.stdout, 'stderr': doctor.stderr})
        if doctor.returncode:
            raise RuntimeError('installed environment doctor failed in final namespace; model invocation blocked')
        visible = subprocess.run(argv + ["codex", "debug", "prompt-input", prompt], text=True, capture_output=True)
        (evidence / "visible-prompt.json").write_text(visible.stdout)
        (evidence / "visible-prompt.stderr").write_text(visible.stderr)
        if visible.returncode:
            raise RuntimeError("visible prompt inspection failed")
        if args.mode == "inspect":
            write_json(evidence / "result.json", {"status": "platform-static-pass", "model_called": False})
        else:
            command = argv + ["codex", "exec", "--json", "--color", "never", prompt]
            if scenario_card["level"] == "L6":
                consume_l6_approval(
                    scenario_card, current_context, approval, consumed_approvals
                )
            with (evidence / "events.jsonl").open("w") as stdout, (evidence / "stderr.log").open("w") as stderr:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
                write_json(evidence / "process.json", {"pid": process.pid, "run_id": run_id})
                wait_result = wait_for_scenario_process(
                    process, scenario_card, mode=args.mode
                )
                code = wait_result["exit_code"]
                cleanup.update(wait_result["cleanup"])
                write_json(evidence / "budget-wait.json", wait_result)
            write_json(evidence / "result.json", {"status": "needs-independent-grading", "exit_code": code,
                                                 "formal_acceptance": args.mode == "run",
                                                 "timed_out": wait_result["timed_out"],
                                                 "stop_reason": wait_result["stop_reason"]})
        cleanup["process_reaped"] = process is None or process.poll() is not None
    except BaseException as error:
        write_json(evidence / "runner-error.json", {"type": type(error).__name__, "message": str(error),
                                                   "gto_verdict": "not-graded"})
        raise
    finally:
        try:
            cleanup.update(stop_owned_process(process))
        except BaseException as error:
            cleanup["process_cleanup_error"] = str(error)
        finally:
            try:
                if process is not None:
                    preserve_owned_evidence(project, codex_home, evidence)
            except BaseException as error:
                cleanup["preservation_error"] = str(error)
            finally:
                try:
                    if "temporary_context" in locals():
                        temporary_context.cleanup()
                except BaseException as error:
                    cleanup["temp_cleanup_error"] = str(error)
                cleanup["temp_removed"] = not ("run" in locals() and run.exists())
                cleanup["process_reaped"] = process is None or process.poll() is not None
                write_json(evidence / "cleanup.json", cleanup)
                print(evidence)


if __name__ == "__main__":
    main()
