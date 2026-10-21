#!/usr/bin/env python3
"""Task ownership records; never creates/switches worktrees or runs business checks."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

# The generated pair also runs with python -I from an unrelated directory.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_git_workflow import CheckError, git, read_policy

STAGES = ("investigation", "plan", "documentation", "tests", "implementation", "review", "acceptance")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}")
INACTIVE = {"completed", "cancelled"}


class TaskError(Exception):
    def __init__(self, code, exit_code=1):
        self.code, self.exit_code = code, exit_code
        super().__init__(code)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(root):
    # Same canonical JSON string encoding as the existing GTO checkout binding.
    return hashlib.sha256(json.dumps(str(root), ensure_ascii=False,
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError) as exc:
        raise TaskError("RECORD_INVALID", 2) from exc


def inside(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise TaskError("PATH_OUTSIDE_PROJECT")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise TaskError("PATH_OUTSIDE_PROJECT")
    return path


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".writing")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def facts(root):
    root = root.resolve(strict=True)
    _, top = git(root, "rev-parse", "--show-toplevel")
    if Path(top).resolve() != root:
        raise TaskError("CHECKOUT_ROOT_REQUIRED")
    _, common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    _, branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", optional=True)
    _, head = git(root, "rev-parse", "HEAD")
    _, dirty = git(root, "status", "--porcelain=v1", "--untracked-files=normal")
    return root, Path(common).resolve(), branch, head, dirty


def validate_ordinary(value, task_id):
    fields = ("coordinator", "branch", "task_document")
    if (value.get("schema_version") != 1 or value.get("mode") != "ordinary"
            or value.get("task_id") != task_id or not ID.fullmatch(task_id)
            or value.get("status") not in {"active", "blocked", "completed", "cancelled"}
            or value.get("workspace") != "<repo-root>"
            or any(not isinstance(value.get(k), str) or not value[k].strip() for k in fields)):
        raise TaskError("TASK_RECORD_INVALID", 2)


def load_record(row, task_id, common):
    try:
        root = Path(row["workspace"]).resolve(strict=True)
        _, actual_common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if Path(actual_common).resolve() != common:
            raise TaskError("BINDING_REPOSITORY_MISMATCH", 2)
        mode = row["mode"]
        expected = (f"docs/tasks/{task_id}/task.json" if mode == "ordinary"
                    else f"docs/ai/tasks/{task_id}/state.json")
        if mode not in {"ordinary", "gto"} or row["record"] != expected:
            raise TaskError("BINDING_INVALID", 2)
        path = inside(root, expected)
        state = read_json(path)
        if state.get("task_id") != task_id or state.get("checkout_binding") != binding(root):
            raise TaskError("CHECKOUT_BINDING_MISMATCH", 2)
        if mode == "ordinary":
            validate_ordinary(state, task_id)
            if not inside(root, state["task_document"]).is_file():
                raise TaskError("TASK_DOCUMENT_MISSING", 2)
        elif not isinstance(state.get("workspace"), dict):
            raise TaskError("GTO_WORKSPACE_INVALID", 2)
        return root, path, state
    except (KeyError, TypeError, OSError) as exc:
        raise TaskError("BINDING_INVALID", 2) from exc


def discover(root, common):
    index = common / "ai-harness/task-bindings.json"
    rows = {}
    if index.exists():
        data = read_json(index)
        if data.get("schema_version") != 1 or not isinstance(data.get("bindings"), dict):
            raise TaskError("INDEX_INVALID", 2)
        rows = data["bindings"]
        for task_id, row in rows.items():
            if not ID.fullmatch(task_id) or not isinstance(row, dict):
                raise TaskError("INDEX_INVALID", 2)
            load_record(row, task_id, common)
    # Only Git's own known worktrees. Historical/copy documents without a matching
    # checkout binding do not establish ownership; explicitly indexed records do.
    _, listing = git(root, "worktree", "list", "--porcelain")
    for line in listing.splitlines():
        if not line.startswith("worktree "):
            continue
        workspace = Path(line[9:]).resolve()
        if not workspace.is_dir():
            continue
        for mode, pattern in (("ordinary", "docs/tasks/*/task.json"),
                              ("gto", "docs/ai/tasks/*/state.json")):
            for path in workspace.glob(pattern):
                state = read_json(path)
                if state.get("checkout_binding") != binding(workspace):
                    continue
                task_id = state.get("task_id", "")
                if not isinstance(task_id, str) or not ID.fullmatch(task_id):
                    raise TaskError("TASK_ID_INVALID", 2)
                row = dict(workspace=str(workspace), mode=mode,
                           record=path.relative_to(workspace).as_posix())
                if task_id in rows and rows[task_id] != row:
                    raise TaskError("DUPLICATE_TASK_BINDING", 2)
                load_record(row, task_id, common)
                rows[task_id] = row
    return rows


@contextmanager
def ownership_lock(common):
    directory = common / "ai-harness"
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / "task-bindings.lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise TaskError("BINDING_LOCKED") from exc
    try:
        yield
    finally:
        lock.rmdir()


def occupants(rows, root, common):
    return [task_id for task_id, row in rows.items()
            if Path(row["workspace"]).resolve() == root
            and load_record(row, task_id, common)[2].get("status") not in INACTIVE]


def current(rows, task_id, coordinator, common, root=None):
    if task_id not in rows:
        raise TaskError("TASK_NOT_BOUND")
    row = rows[task_id]
    target, path, state = load_record(row, task_id, common)
    if state.get("status") in INACTIVE:
        raise TaskError("TASK_NOT_ACTIVE")
    if root is not None and target != root:
        raise TaskError("WRONG_CHECKOUT")
    branch = state.get("branch") if row["mode"] == "ordinary" else state["workspace"].get("branch")
    _, actual = git(target, "symbolic-ref", "--quiet", "--short", "HEAD", optional=True)
    if branch not in (None, "unresolved") and branch != actual:
        raise TaskError("BRANCH_BINDING_MISMATCH")
    if row["mode"] == "ordinary" and state["coordinator"] != coordinator:
        raise TaskError("HANDOFF_REQUIRED")
    return row, target, path, state


def legacy_binding_valid(root, task_id, coordinator):
    try:
        root, common, _, _, _ = facts(root)
        row, _, _, state = current(discover(root, common), task_id, coordinator, common, root)
        return row["mode"] == "ordinary" and state.get("binding_origin") == "user-confirmed-existing-task"
    except (TaskError, CheckError, ValueError, OSError):
        return False


def evidence_files(root, relative, stage):
    path = inside(root, relative)
    value = read_json(path)
    if (not isinstance(value.get("actor"), str) or not value["actor"].strip()
            or value.get("outcome") not in {"pass", "fail"}
            or not isinstance(value.get("summary"), str) or not value["summary"].strip()
            or not isinstance(value.get("evidence"), list) or not value["evidence"]):
        raise TaskError("EVIDENCE_INVALID")
    references = [relative, *value["evidence"]]
    if stage in {"review", "acceptance"}:
        references.append(value.get("dispatch_evidence"))
    if stage == "tests" and value.get("red_observed") is not True:
        if not isinstance(value.get("not_applicable"), str) or not value["not_applicable"].strip():
            raise TaskError("RED_PROOF_REQUIRED")
    if stage == "acceptance":
        if not isinstance(value.get("checks"), list) or not isinstance(value.get("open_issues"), list):
            raise TaskError("COVERAGE_INVALID")
        for check in value["checks"]:
            if (not isinstance(check, dict) or not isinstance(check.get("id"), str)
                    or check.get("status") not in {"pass", "fail", "not_run", "blocked"}
                    or not isinstance(check.get("evidence"), list)):
                raise TaskError("COVERAGE_INVALID")
            if check["status"] == "pass" and not check["evidence"]:
                raise TaskError("POINT_EVIDENCE_REQUIRED")
            references.extend(check["evidence"])
    manifest = {}
    for reference in references:
        target = inside(root, reference)
        if not target.is_file():
            raise TaskError("EVIDENCE_MISSING")
        manifest[reference] = digest(target)
    return value, manifest


def verified_stages(root, state):
    latest = {"_roles": {"implementers": set()}}
    stages = state.get("stages", [])
    if not isinstance(stages, list):
        raise TaskError("STAGES_INVALID", 2)
    for receipt in stages:
        try:
            for relative, expected in receipt["files"].items():
                target = inside(root, relative)
                if not target.is_file() or digest(target) != expected:
                    raise TaskError("EVIDENCE_CHANGED")
            stage = receipt["stage"]
            if stage not in STAGES:
                raise TaskError("STAGES_INVALID", 2)
            value, manifest = evidence_files(root, receipt["evidence"], stage)
            if manifest != receipt["files"]:
                raise TaskError("EVIDENCE_CHANGED")
            independent(stage, value, latest)
            roles = latest["_roles"]
            if stage in {"tests", "review"}:
                roles.setdefault(stage, value["actor"])
            elif stage == "implementation":
                roles["implementers"].add(value["actor"])
            latest[stage] = value
        except (KeyError, TypeError) as exc:
            raise TaskError("STAGES_INVALID", 2) from exc
    return latest


def independent(stage, value, latest):
    actor = value["actor"]
    roles = latest.get("_roles", {})
    implementers = roles.get("implementers", set())
    tester = roles.get("tests")
    reviewer = roles.get("review")
    if stage in {"tests", "review"} and roles.get(stage) not in (None, actor):
        raise TaskError("ORIGINAL_ROLE_REQUIRED")
    if stage == "tests" and actor in implementers:
        raise TaskError("TESTER_NOT_INDEPENDENT")
    if stage == "implementation" and actor in {tester, reviewer}:
        raise TaskError("IMPLEMENTER_NOT_INDEPENDENT")
    if stage == "review" and (actor in implementers or actor == tester):
        raise TaskError("REVIEW_NOT_INDEPENDENT")
    if stage == "acceptance" and (actor != tester or actor in implementers or actor == reviewer):
        raise TaskError("ACCEPTANCE_NOT_INDEPENDENT")


def success(**values):
    return dict(ok=True, **values)


def execute(args):
    root, common, branch, head, dirty = facts(args.repo_root)
    if args.task_id and not ID.fullmatch(args.task_id):
        raise TaskError("TASK_ID_INVALID")
    if args.action in {"inspect", "resume", "check"}:
        rows = discover(root, common)
        if args.action == "inspect":
            if args.task_id and args.task_id in rows:
                _, _, known = load_record(rows[args.task_id], args.task_id, common)
                _, target, _, state = current(rows, args.task_id, known.get("coordinator", ""), common)
                return success(decision="reuse", workspace=str(target), task_id=args.task_id,
                               mode=rows[args.task_id]["mode"], branch=state.get("branch"))
            owners = occupants(rows, root, common)
            return success(decision="occupied" if owners else "unowned_changes" if dirty else "available",
                           occupants=owners, branch=branch, dirty=bool(dirty))
        row, target, _, state = current(rows, args.task_id, args.coordinator, common,
                                       root if args.action == "check" else None)
        if row["mode"] == "ordinary":
            verified_stages(target, state)
        return success(decision="reuse", task_id=args.task_id, workspace=str(target),
                       mode=row["mode"], branch=state.get("branch", state.get("workspace", {}).get("branch"))
                       if isinstance(state.get("workspace"), dict) else state.get("branch"))

    # Fail before creating even a lock for invalid project configuration.
    policy = read_policy(root) if args.action in {"begin", "adopt"} else None
    with ownership_lock(common):
        rows = discover(root, common)
        task_id = args.task_id or ("task-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                                   + "-" + uuid.uuid4().hex[:8])
        if args.action in {"begin", "adopt", "register-gto"}:
            if args.action == "register-gto":
                relative = f"docs/ai/tasks/{task_id}/state.json"
                row = dict(workspace=str(root), mode="gto", record=relative)
                _, _, state = load_record(row, task_id, common)
                if task_id in rows and rows[task_id] != row:
                    raise TaskError("TASK_ALREADY_BOUND")
                competing = set(occupants(rows, root, common)) - {task_id}
                if competing:
                    raise TaskError("WORKSPACE_OCCUPIED")
                expected_branch = state["workspace"].get("branch")
                if expected_branch not in (None, "unresolved", branch):
                    raise TaskError("BRANCH_BINDING_MISMATCH")
                rows[task_id] = row
                atomic(common / "ai-harness/task-bindings.json", dict(schema_version=1, bindings=rows))
                return success(task_id=task_id, mode="gto", decision="reuse", workspace=str(root))
            if not args.coordinator.strip():
                raise TaskError("COORDINATOR_REQUIRED")
            if args.action == "adopt" and not args.basis.strip():
                raise TaskError("ADOPTION_BASIS_REQUIRED")
            if task_id in rows:
                raise TaskError("TASK_ALREADY_BOUND")
            if occupants(rows, root, common):
                raise TaskError("WORKSPACE_OCCUPIED")
            if not branch or branch in {policy["main_branch"], policy.get("production_branch")}:
                raise TaskError("TASK_BRANCH_REQUIRED")
            if args.action == "begin":
                if dirty:
                    raise TaskError("UNOWNED_CHANGES")
                if not any(branch.startswith(p) and len(branch) > len(p) for p in policy["task_prefixes"]):
                    raise TaskError("BRANCH_NAME")
            relative = f"docs/tasks/{task_id}/task.json"
            path = inside(root, relative)
            document = f"docs/tasks/{task_id}/task.md"
            doc_path = inside(root, document)
            if path.exists() and args.action != "adopt":
                raise TaskError("TASK_RECORD_EXISTS")
            points = args.point or ["delivery"]
            if len(set(points)) != len(points) or any(not ID.fullmatch(p) for p in points):
                raise TaskError("ACCEPTANCE_POINTS_INVALID")
            state = read_json(path) if path.exists() else {}
            if state:
                validate_ordinary(state, task_id)
                if state["coordinator"] != args.coordinator or state["branch"] != branch:
                    raise TaskError("ADOPTION_BINDING_MISMATCH")
                if state.get("checkout_binding") not in (None, binding(root)):
                    raise TaskError("CHECKOUT_BINDING_MISMATCH")
                if state.get("status") in INACTIVE:
                    raise TaskError("TASK_NOT_ACTIVE")
            state = {**state, "schema_version": 1, "mode": "ordinary", "task_id": task_id,
                     "status": state.get("status", "active"), "phase": state.get("phase", "investigation"),
                     "branch": branch, "workspace": "<repo-root>", "checkout_binding": binding(root),
                     "coordinator": args.coordinator, "task_document": document,
                     "acceptance_points": state.get("acceptance_points", points),
                     "stages": state.get("stages", []), "baseline_head": state.get("baseline_head", head),
                     "binding_origin": "user-confirmed-existing-task" if args.action == "adopt" else "new-task"}
            if args.action == "adopt":
                state["adoption_basis"] = args.basis
            rows[task_id] = dict(workspace=str(root), mode="ordinary", record=relative)
            # Validate everything before writes. A crash after the task write can be
            # recovered from its checkout binding by read-only discovery.
            if not doc_path.exists():
                doc_path.parent.mkdir(parents=True, exist_ok=True)
                doc_path.write_text(f"# {args.title or task_id}\n\n## 目标与范围\n"
                                    "按已批准方案补充，未填写不能视为施工已获批准。\n\n"
                                    "## 实施步骤\n调查与方案 → 文档 → 测试 → 实现 → 独立 review → 验收。\n\n"
                                    "## 验收点与证据\n" +
                                    "\n".join(f"- {p}: 未执行；补充判定条件及原始证据。" for p in points) +
                                    "\n\n## 未解决事项与接续\n尚未完成。\n", encoding="utf-8")
            atomic(path, state)
            atomic(common / "ai-harness/task-bindings.json", dict(schema_version=1, bindings=rows))
            return success(task_id=task_id, workspace=str(root), branch=branch, decision="reuse")

        row, target, path, state = current(rows, task_id, args.coordinator, common, root)
        if row["mode"] != "ordinary":
            raise TaskError("USE_FROZEN_GTO_ENTRY")
        if args.action == "handoff":
            if not args.writes_stopped or not args.next_coordinator.strip() or not args.basis.strip():
                raise TaskError("STOP_WRITES_BEFORE_HANDOFF")
            state.setdefault("handoffs", []).append(dict(previous=state["coordinator"],
                next=args.next_coordinator, basis=args.basis))
            state["coordinator"] = args.next_coordinator
            atomic(path, state)
            return success(task_id=task_id, coordinator=args.next_coordinator)
        latest = verified_stages(root, state)
        if args.action == "record-stage":
            if args.stage not in STAGES:
                raise TaskError("STAGE_REQUIRED")
            if any(latest.get(s, {}).get("outcome") != "pass" for s in STAGES[:STAGES.index(args.stage)]):
                raise TaskError("PREVIOUS_STAGE_NOT_PASSED")
            value, manifest = evidence_files(root, args.evidence, args.stage)
            independent(args.stage, value, latest)
            state.setdefault("stages", []).append(dict(stage=args.stage, evidence=args.evidence, files=manifest))
            state["phase"] = args.stage
            atomic(path, state)
            return success(task_id=task_id, recorded_outcome=value["outcome"])
        if args.action == "complete":
            if any(latest.get(s, {}).get("outcome") != "pass" for s in STAGES):
                raise TaskError("STAGES_INCOMPLETE")
            if state["stages"][-1]["stage"] != "acceptance":
                raise TaskError("COVERAGE_STALE")
            for stage in ("implementation", "review", "acceptance"):
                independent(stage, latest[stage], latest)
            acceptance = latest["acceptance"]
            checks = {c["id"]: c for c in acceptance["checks"]}
            points = state.get("acceptance_points")
            if (not isinstance(points, list) or not points or acceptance["open_issues"]
                    or any(checks.get(p, {}).get("status") != "pass" for p in points)):
                raise TaskError("COVERAGE_INCOMPLETE")
            state["status"] = "completed"
            atomic(path, state)
            return success(task_id=task_id, status="completed", cleanup="report-only")
        raise TaskError("ACTION_INVALID")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--action", choices=["inspect", "begin", "adopt", "resume", "check", "handoff",
                                           "record-stage", "complete", "register-gto"], required=True)
    parser.add_argument("--task-id", default="")
    parser.add_argument("--coordinator", default="")
    parser.add_argument("--next-coordinator", default="")
    parser.add_argument("--writes-stopped", action="store_true")
    parser.add_argument("--basis", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--point", action="append")
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--evidence", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.action not in {"inspect", "begin"} and not args.task_id:
            raise TaskError("TASK_ID_REQUIRED")
        result = execute(args)
        code = 0
    except TaskError as exc:
        result, code = dict(ok=False, decision="blocked", errors=[exc.code]), exc.exit_code
    except (ValueError, KeyError, TypeError, OSError, CheckError) as exc:
        result, code = dict(ok=False, decision="blocked", errors=["CONFIG_OR_GIT_INVALID"],
                            detail=type(exc).__name__), 2
    print(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
