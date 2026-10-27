"""Black-box contract tests for the WSL Python GTO control plane.

Codex decides the semantic six-point task contract.  These tests require the
controller to validate, persist, and advance that already-structured contract;
they deliberately do not ask Python to classify natural language.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = (
    REPO_ROOT
    / "skills"
    / "global-task-orchestrator"
    / "scripts"
    / "orchestrator_ctl.py"
)
TASK_ID = "20300102-030405-control-plane-contract"
IMPLEMENTER = {"agent_key": "backend-implementer", "platform_agent_id": "impl-001"}
REVIEWER = {"agent_key": "reviewer", "platform_agent_id": "review-001"}


def attach_acceptance_run(repo, subtask_id, payload, *, create_fixture_files=False):
    acceptance = payload.get('expensive_acceptance') if isinstance(payload, dict) else None
    if not isinstance(acceptance, dict) or 'run_evidence' in acceptance:
        return
    from test_gto_plan_preflight_contract import load_controller
    load_controller()
    from runtime_evidence import run_command, acceptance_binding, acceptance_evidence_paths, digest
    state = json.loads((repo / 'docs/ai/tasks' / TASK_ID / 'state.json').read_text())
    # Positive contract fixtures generate synthetic output through the captured subprocess.
    # Negative callers never create missing references: their absence remains observable.
    paths = acceptance_evidence_paths(payload)
    generated = [p for p in paths if p.startswith('.artifacts/') and not (repo / p).exists()] if create_fixture_files else []
    script = ('from pathlib import Path; import json; '
              'paths=json.loads(' + repr(json.dumps(generated)) + '); '
              '[(Path(p).parent.mkdir(parents=True,exist_ok=True),Path(p).write_text("synthetic contract fixture; not product acceptance")) for p in paths]; '
              'print("synthetic contract-test execution; not product acceptance")')
    run = run_command(repo / '.artifacts/synthetic-runs',
        [sys.executable, '-c', script],
        cwd=repo, binding=acceptance_binding(state, subtask_id), evidence_paths=acceptance_evidence_paths(payload))
    path = run / 'manifest.json'
    acceptance['run_evidence'] = {'path': path.relative_to(repo).as_posix(), 'sha256': digest(path.read_bytes())}


def six_points() -> dict[str, object]:
    return {
        "do": "Implement the WSL Python control plane.",
        "do_not": ["Do not classify natural language in Python."],
        "change_areas": ["skills/global-task-orchestrator", "tests/harness"],
        "implementation": "Codex supplies semantics; Python performs mechanical gates.",
        "acceptance": ["The current review and independent acceptance gates reach completion."],
        "risks": ["Existing dirty work must be preserved."],
    }


def assignment(goal: str) -> dict[str, object]:
    return {
        "goal": goal,
        "must_include": ["minimal deterministic behavior"],
        "verification": ["Run the focused Python unittest."],
    }


def contract() -> dict[str, object]:
    points = six_points()
    return {
        "six_points": points,
        "objective": points["do"],
        "scope_in": points["change_areas"],
        "scope_out": points["do_not"],
        "acceptance": points["acceptance"],
        "stop_conditions": points["risks"],
        "decisions": [points["implementation"]],
        "approval": {"status": "approved", "approved_by": "user"},
        "verification_contract": {
            "minimal_repro": "The focused fixture fails before implementation.",
            "hit_proof": "The focused fixture directly exercises the gate.",
            "diagnostic_checks": ["Run focused diagnostics."],
            "acceptance_checks": ["Run focused acceptance."],
            "non_goals": ["Do not infer semantics in Python."],
            "review_evidence": [
                "repro_before_fix",
                "pass_after_fix",
                "hit_proof_observed",
                "relevant_regression_ok",
            ],
        },
        "subtasks": [
            {
                "subtask_id": "IMPL-001",
                "title": "Implement control plane",
                "role": "backend-implementer",
                "status": "ready",
                "dependencies": [],
                "read_paths": ["skills/global-task-orchestrator"],
                "write_paths": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
                "assignment": assignment("Implement the controller."),
            },
            {
                "subtask_id": "REVIEW-001",
                "title": "Review implementation",
                "role": "reviewer",
                "status": "ready",
                "dependencies": ["IMPL-001"],
                "read_paths": ["skills/global-task-orchestrator"],
                "write_paths": [],
                "assignment": assignment("Review the implementation."),
            },
            {
                "subtask_id": "REVIEW-002",
                "title": "Re-review implementation",
                "role": "reviewer",
                "status": "pending",
                "dependencies": ["REVIEW-001"],
                "read_paths": ["skills/global-task-orchestrator"],
                "write_paths": [],
                "assignment": assignment("Re-review the same finding."),
            },
            {
                "subtask_id": "FINAL-001",
                "title": "Independent final review",
                "role": "reviewer",
                "status": "pending",
                "dependencies": ["REVIEW-001"],
                "read_paths": ["skills/global-task-orchestrator"],
                "write_paths": [],
                "assignment": assignment("Review the latest scoped change."),
            },
        ],
    }


def finding(finding_id: str, *, status: str = "open") -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "severity": "high",
        "paths": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
        "summary": f"Review finding {finding_id}.",
        "evidence": "Focused review reproduced the issue.",
        "status": status,
        "routed_to": IMPLEMENTER,
    }


def expensive_acceptance_contract() -> dict[str, object]:
    """Current-contract fields; callers supply initial tester ownership and requirement mapping."""
    task_contract = contract()
    task_contract["workflow_revision"] = 3
    stages = (
        ("WORK-001", "backend-implementer", "work", [], ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"]),
        ("INTEGRATE-001", "backend-implementer", "integration", ["WORK-001"], []),
        ("REVIEW-SEC-001", "reviewer", "pre_acceptance_review", ["INTEGRATE-001"], []),
        ("EXPENSIVE-001", "tester", "expensive_acceptance", ["REVIEW-SEC-001"], []),
        ("DOC-FINAL-001", "doc-curator", "final_documentation", ["EXPENSIVE-001"], ["docs"]),
    )
    task_contract["subtasks"] = [
        {
            "subtask_id": ident, "title": stage.replace("_", " "), "role": role, "stage": stage,
            "status": "ready", "dependencies": deps, "read_paths": ["skills/global-task-orchestrator"],
            "write_paths": writes, "assignment": assignment(f"Complete {stage}."),
        }
        for ident, role, stage, deps, writes in stages
    ]
    task_contract["acceptance_gate"] = {
        "candidate_inputs": {
            "code_paths": ["candidate-source.py"],
            "config_paths": ["candidate-config.json"],
            "runtime_inputs": {"provider": "fixture-v1"},
        },
        "current_candidate": None,
        "acceptance_items": [
            {"acceptance_id": "REAL-PATH-001", "evidence_refs": []},
        ],
        "attempt_policy": {
            "max_expensive_attempts": 4,
            "max_full_attempts_per_candidate": 1,
            "max_environment_retries_per_candidate": 1,
            "approval_required_from_attempt": 3,
        },
        "attempts": [],
    }
    return task_contract




def dispatch(agent_key: str, platform_agent_id: str, *, kind: str = "subtask", sha: str = "a") -> dict[str, str]:
    return {"agent_key": agent_key, "platform_agent_id": platform_agent_id, "context_mode": "isolated", "brief_kind": kind, "brief_sha256": sha * 64}


def result(status: str, written_by: str, written_role: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status, "summary": "Focused fixture result.", "changed_files": [],
        "planned_files_not_changed": [], "verification": {"commands": ["fixture-check"], "result": "passed"},
        "deviations": [], "blocked_by": ["fixture"] if status == "blocked" else [], "risks": [], "follow_up": [],
        "written_by": written_by, "written_role": written_role,
    }
    payload.update(extra)
    return payload


def _current_contract():
    if __package__:
        from .test_gto_workflow import workflow_contract
    else:
        from test_gto_workflow import workflow_contract
    return workflow_contract()


class ControlPlaneContractTest(unittest.TestCase):
    def setUp(self) -> None:
        base = REPO_ROOT / ".tmp/control-plane-tests"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.input_temp = tempfile.TemporaryDirectory(dir=base)
        self.repo = Path(self.temp.name)
        self.input_dir = Path(self.input_temp.name)
        self._json_input_index = 0

    def tearDown(self) -> None:
        self.input_temp.cleanup()
        self.temp.cleanup()

    def run_ctl(self, action: str, *, ok: bool = True, **kwargs: object) -> dict[str, object]:
        self.assertTrue(
            CONTROLLER.is_file(),
            f"TDD target is missing: {CONTROLLER.relative_to(REPO_ROOT)}",
        )
        command = [
            "python3",
            str(CONTROLLER),
            "--action",
            action,
            "--repo-root",
            str(self.repo),
            "--task-id",
            TASK_ID,
            "--json",
        ]
        names = {
            "subtask_id": "--subtask-id",
            "finding_id": "--finding-id",
            "result": "--result-json-file",
            "contract": "--contract-json-file",
            "title": "--title",
            "owner": "--owner",
            "agent_key": "--agent-key",
            "platform_agent_id": "--platform-agent-id",
            "context_mode": "--context-mode",
            "brief_kind": "--brief-kind",
            "brief_sha256": "--brief-sha256",
            "brief_path": "--brief-path",
            "phase": "--phase",
            "workspace_summary": "--workspace-summary",
            "approval_by": "--approval-by",
            "approval_reason": "--approval-reason",
        }
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        if action == "bind-dispatch" and state_path.is_file() and "brief_path" not in kwargs:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("workflow_revision") == 3:
                self._json_input_index += 1
                relative = f".tmp/test-brief-{self._json_input_index}.md"
                brief_file = self.repo / relative
                brief_file.parent.mkdir(parents=True, exist_ok=True)
                brief_file.write_text(f"brief:{kwargs.get('subtask_id')}\n", encoding="utf-8")
                kwargs["brief_path"] = relative
                kwargs["brief_sha256"] = hashlib.sha256(brief_file.read_bytes()).hexdigest()
        if action in {'record-subtask-result', 'validate-result'} and 'result' in kwargs:
            attach_acceptance_run(self.repo, kwargs.get('subtask_id'), kwargs['result'], create_fixture_files=ok)
        generated_contract_inputs: list[Path] = []
        for key, value in kwargs.items():
            if key in {"result", "contract"}:
                self._json_input_index += 1
                input_root = self.repo / ".tmp" if key == "contract" else self.input_dir
                input_root.mkdir(parents=True, exist_ok=True)
                payload_file = input_root / f"gto-input-{self._json_input_index}.json"
                payload_file.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                if key == "contract":
                    generated_contract_inputs.append(payload_file)
                encoded = str(payload_file)
            else:
                encoded = str(value)
            command.extend([names[key], encoded])
        try:
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
        finally:
            for payload_file in generated_contract_inputs:
                payload_file.unlink(missing_ok=True)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            if completed.returncode:
                payload = {"ok": False, "errors": [completed.stderr]}
            else:
                self.fail(
                    f"{action} must emit one JSON object; exit={completed.returncode}; "
                    f"stdout={completed.stdout!r}; stderr={completed.stderr!r}; error={exc}"
                )
        if ok:
            self.assertEqual(0, completed.returncode, completed.stderr or payload)
            self.assertTrue(payload.get("ok"), payload)
        else:
            self.assertNotEqual(0, completed.returncode, payload)
            self.assertFalse(payload.get("ok", True), payload)
        return payload

    def init_task(self, task_contract: dict[str, object] | None = None) -> dict[str, object]:
        return self.run_ctl(
            "init-task",
            contract=task_contract or _current_contract(),
            title="Control plane contract",
            owner="main-coordinator",
        )

    def git(self, *arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        return completed.stdout.strip()

    def init_git_checkout(self, *tracked_paths: str) -> str:
        self.git("init", "-b", "main")
        self.git("config", "user.email", "control-plane@example.invalid")
        self.git("config", "user.name", "Control Plane Test")
        for relative in tracked_paths:
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"baseline:{relative}\n", encoding="utf-8")
        marker = self.repo / ".gitkeep"
        marker.write_text("primary checkout\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "baseline")
        return self.git("rev-parse", "HEAD")


    def state(self) -> dict[str, object]:
        path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def write_state(self, state: dict[str, object]) -> None:
        (self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    @staticmethod
    def item(state: dict[str, object], subtask_id: str) -> dict[str, object]:
        return next(item for item in state["subtasks"] if item["subtask_id"] == subtask_id)


    def control_artifacts(self) -> tuple[Path, Path, Path]:
        root = self.repo / "docs" / "ai" / "tasks" / TASK_ID
        return root / "state.json", root / "task.md", root / "events.jsonl"

    def control_artifact_snapshot(self) -> dict[Path, bytes]:
        return {path: path.read_bytes() for path in self.control_artifacts()}






    def assert_phase_projection_and_schema(self, expected_phase: str) -> None:
        state = self.state()
        self.assertEqual(expected_phase, state["current_phase"])
        task_md = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "task.md"
        self.assertIn(f"- current_phase: `{expected_phase}`", task_md.read_text(encoding="utf-8"))
        schema = json.loads(
            (REPO_ROOT / "skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8")
        )
        errors = [error.message for error in Draft202012Validator(schema).iter_errors(state)]
        self.assertEqual([], errors, f"set-phase persisted a schema-invalid state: {errors}")


    def test_init_creates_and_cross_validates_all_six_artifacts(self) -> None:
        payload = self.init_task()
        expected = {
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / name
            for name in ("state.json", "task.md", "events.jsonl")
        } | {
            self.repo / "docs" / "tasks" / TASK_ID / name
            for name in ("plan.md", "execution.md", "acceptance.md")
        }
        self.assertEqual(expected, {path for path in expected if path.is_file()})
        state = self.state()
        self.assertEqual(six_points(), state["six_points"])
        self.assertEqual("approved", state["approval"]["status"])
        self.assertIn("contract_sha256", state["approval"])
        for path in expected - {self.repo / "docs" / "ai" / "tasks" / TASK_ID / "events.jsonl"}:
            self.assertIn(TASK_ID, path.read_text(encoding="utf-8"))
        self.assertEqual(TASK_ID, payload["task_id"])

        required_headings = {
            "plan.md": (
                "施工摘要", "改造要点", "施工流程", "任务表",
            ),
            "execution.md": (
                "施工目标", "前置条件", "执行顺序", "文档先行清单",
                "测试同步清单", "实施批次", "每批写入范围", "验证命令",
                "回退方案", "审查与返工路径",
            ),
            "acceptance.md": ("验收目标", "验收标准", "必备证据", "未决项", "最终结论"),
        }
        task_docs = self.repo / "docs" / "tasks" / TASK_ID
        for name, headings in required_headings.items():
            text = (task_docs / name).read_text(encoding="utf-8")
            for heading in headings:
                self.assertIn(f"## {heading}", text, f"{name} missing {heading}")

        acceptance_path = self.repo / "docs" / "tasks" / TASK_ID / "acceptance.md"
        acceptance_path.write_text(
            acceptance_path.read_text(encoding="utf-8").replace(
                "The current review and independent acceptance gates reach completion.", "A stale acceptance contract."
            ),
            encoding="utf-8",
        )
        invalid = self.run_ctl("validate", ok=False)
        self.assertIn("acceptance.md", " ".join(invalid.get("errors", [])))

    def test_explicit_artifact_update_accepts_maintained_plan_and_execution(self) -> None:
        self.init_task()
        task_root = self.repo / "docs" / "tasks" / TASK_ID
        plan_path = task_root / "plan.md"
        execution_path = task_root / "execution.md"
        plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nApproved plan maintenance.\n", encoding="utf-8")
        execution_path.write_text(
            execution_path.read_text(encoding="utf-8") + "\nApproved execution maintenance.\n",
            encoding="utf-8",
        )

        stale = self.run_ctl("validate", ok=False)
        stale_errors = " ".join(stale.get("errors", []))
        self.assertIn("plan.md", stale_errors)
        self.assertIn("execution.md", stale_errors)

        accepted = self.run_ctl("accept-artifact-update")
        self.assertEqual(["plan.md", "execution.md"], accepted["changed_artifacts"])
        self.run_ctl("validate")
        events = (self.repo / "docs" / "ai" / "tasks" / TASK_ID / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("artifact_update_accepted", events)

    def test_contract_change_invalidates_prior_approval(self) -> None:
        self.init_task()
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        state = self.state()
        state["six_points"]["implementation"] = "Changed after approval."
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        invalid = self.run_ctl("validate", ok=False)
        self.assertIn("approval", " ".join(invalid.get("errors", [])).lower())

    def test_validate_rejects_v3_phase_state_and_projection_contradictions(self) -> None:
        self.init_task()
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        state = self.state()
        state["current_phase"] = "verification"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        invalid_phase = self.run_ctl("validate", ok=False)
        self.assertIn("current_phase", " ".join(invalid_phase.get("errors", [])))

        state["current_phase"] = "code_impl"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        overlap = self.run_ctl("validate", ok=False)
        self.assertIn("overlap", " ".join(overlap.get("errors", [])).lower())

        state["current_phase"] = "doc_sync"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stale_projection = self.run_ctl("validate", ok=False)
        self.assertIn("task.md", " ".join(stale_projection.get("errors", [])))

    def test_set_phase_cli_is_exposed_by_help(self) -> None:
        # Break caught: the phase transition contract exists only in prose and
        # cannot be invoked through the real CLI.
        completed = subprocess.run(
            [sys.executable, str(CONTROLLER), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("set-phase", completed.stdout)
        self.assertIn("--phase", completed.stdout)

    def test_prepare_workspace_cli_is_exposed_by_help(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(CONTROLLER), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("prepare-workspace", completed.stdout)
        self.assertIn("--workspace-summary", completed.stdout)




    def test_set_phase_allows_only_ordered_doc_and_test_transitions(self) -> None:
        # Break caught: a valid planning -> doc_sync -> test_sync sequence is
        # blocked, or succeeds without synchronizing the state projection.
        self.init_task()
        for phase in ("doc_sync", "test_sync"):
            payload = self.run_ctl("set-phase", phase=phase)
            self.assertEqual(phase, payload["current_phase"])
            self.assert_phase_projection_and_schema(phase)

    def test_set_phase_rejects_skips_and_rollbacks_without_mutating_state(self) -> None:
        # Break caught: callers can skip required phases or move the task back
        # to a phase whose completion evidence is no longer trustworthy.
        self.init_task()
        for forbidden in ("code_impl", "review"):
            rejected = self.run_ctl("set-phase", ok=False, phase=forbidden)
            self.assertIn("phase", " ".join(rejected.get("errors", [])).casefold())
            self.assert_phase_projection_and_schema("planning")

        self.run_ctl("set-phase", phase="doc_sync")
        self.run_ctl("set-phase", phase="test_sync")
        for forbidden in ("doc_sync", "planning"):
            rejected = self.run_ctl("set-phase", ok=False, phase=forbidden)
            self.assertIn("phase", " ".join(rejected.get("errors", [])).casefold())
            self.assert_phase_projection_and_schema("test_sync")




    def test_validate_enforces_schema_allowlists_at_root_and_nested_objects(self) -> None:
        self.init_task()
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        original = self.state()

        root_unknown = json.loads(json.dumps(original))
        root_unknown["unexpected_root_field"] = True
        state_path.write_text(json.dumps(root_unknown, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rejected_root = self.run_ctl("validate", ok=False)
        self.assertIn("unexpected_root_field", " ".join(rejected_root.get("errors", [])))

        nested_unknown = json.loads(json.dumps(original))
        nested_unknown["approval"]["unexpected_nested_field"] = True
        state_path.write_text(json.dumps(nested_unknown, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rejected_nested = self.run_ctl("validate", ok=False)
        self.assertIn("unexpected_nested_field", " ".join(rejected_nested.get("errors", [])))

    def test_validate_executes_full_draft_202012_constraints(self) -> None:
        self.init_task()
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        baseline = self.state()
        violations = (
            ("type", lambda state: state["workspace"].__setitem__("dirty_paths", "not-a-list")),
            ("pattern", lambda state: state["subtasks"][0].__setitem__("write_paths", ["/outside"])),
            (
                "maxItems",
                lambda state: state["workspace"].__setitem__(
                    "dirty_paths", [f"noise/{index}.txt" for index in range(501)]
                ),
            ),
            ("format", lambda state: state.__setitem__("updated_at", "not-a-date-time")),
        )
        for label, mutate in violations:
            with self.subTest(label=label):
                invalid = deepcopy(baseline)
                mutate(invalid)
                state_path.write_text(
                    json.dumps(invalid, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                rejected = self.run_ctl("validate", ok=False)
                self.assertTrue(rejected.get("errors"), rejected)

    def test_schema_closes_lifecycle_finding_and_bounds_fix_delta(self) -> None:
        self.init_task()
        schema = json.loads(
            (REPO_ROOT / "skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        baseline = self.state()
        from test_gto_workflow import WorkflowTest
        lifecycle = WorkflowTest.new_finding(self, "SCHEMA-LIFECYCLE-001")
        lifecycle.update(discovered_by=REVIEWER, source_subtask_id='REVIEW-SEC-001')
        lifecycle.update(
            {
                "fix_round": 1,
                "lineage": {
                    "original_implementer": IMPLEMENTER,
                    "original_reviewer": REVIEWER,
                },
                "fix_delta": {
                    "summary": "Minimal fix delta.",
                    "changed_files": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
                    "sha256": "a" * 64,
                    "verification": "Focused schema check passed.",
                },
            }
        )

        valid = deepcopy(baseline)
        valid["findings"] = {lifecycle["finding_id"]: lifecycle}
        self.assertEqual([], list(validator.iter_errors(valid)))

        for missing in ("severity", "paths", "summary", "evidence", "routed_to"):
            with self.subTest(missing=missing):
                invalid = deepcopy(valid)
                del invalid["findings"][lifecycle["finding_id"]][missing]
                self.assertNotEqual([], list(validator.iter_errors(invalid)))

        unexpected = deepcopy(valid)
        unexpected["findings"][lifecycle["finding_id"]]["unexpected"] = True
        self.assertNotEqual([], list(validator.iter_errors(unexpected)))

        oversized = deepcopy(valid)
        oversized["findings"][lifecycle["finding_id"]]["fix_delta"]["changed_files"] = [
            f"noise/{index}.txt" for index in range(501)
        ]
        self.assertNotEqual([], list(validator.iter_errors(oversized)))














    def test_cli_accepts_documented_gnu_long_options(self) -> None:
        contract_file = self.repo / ".tmp" / "contract.json"
        contract_file.parent.mkdir(parents=True, exist_ok=True)
        contract_file.write_text(json.dumps(_current_contract()), encoding="utf-8")
        command = [
            "python3",
            str(CONTROLLER),
            "--action",
            "init-task",
            "--repo-root",
            str(self.repo),
            "--task-id",
            TASK_ID,
            "--json",
            "--contract-json-file",
            str(contract_file),
            "--title",
            "GNU CLI contract",
            "--owner",
            "main-coordinator",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["ok"])

    def test_init_schema_rejection_leaves_no_task_artifacts_or_lock_directory(self) -> None:
        # Break caught: init-task writes task artifacts or creates a lock before
        # the fully constructed candidate state clears canonical schema checks.
        invalid_contract = _current_contract()
        invalid_contract["unexpected_root_field"] = "schema must reject this"
        rejected = self.run_ctl(
            "init-task",
            ok=False,
            contract=invalid_contract,
            title="Control plane contract",
            owner="main-coordinator",
        )
        self.assertIn("unexpected_root_field", " ".join(rejected.get("errors", [])))

        artifact_paths = (
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json",
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / "task.md",
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / "events.jsonl",
            self.repo / "docs" / "tasks" / TASK_ID / "plan.md",
            self.repo / "docs" / "tasks" / TASK_ID / "execution.md",
            self.repo / "docs" / "tasks" / TASK_ID / "acceptance.md",
        )
        self.assertTrue(all(not path.exists() for path in artifact_paths), artifact_paths)
        self.assertFalse((self.repo / "docs" / "ai" / "tasks" / TASK_ID).exists())
        self.assertFalse((self.repo / "docs" / "tasks" / TASK_ID).exists())

    def test_cli_rejects_abbreviated_file_payload_options(self) -> None:
        # Break caught: argparse's default prefix matching revives a deleted
        # inline option through an abbreviated file-option spelling.
        contract_file = self.input_dir / "contract.json"
        contract_file.write_text(json.dumps(_current_contract()), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(CONTROLLER),
                "--action",
                "init-task",
                "--repo-root",
                str(self.repo),
                "--task-id",
                TASK_ID,
                "--contract-json-f",
                str(contract_file),
                "--title",
                "abbreviation probe",
                "--owner",
                "main-coordinator",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("unrecognized arguments", completed.stderr)
        self.assertFalse((self.repo / "docs" / "ai" / "tasks" / TASK_ID).exists())

    def test_cli_rejects_retired_inline_json_payload_flags(self) -> None:
        # Break caught: inline JSON bypasses the file-only boundary and keeps
        # the deprecated argument contract alive.
        accepted: list[str] = []
        for flag in ("--contract-json", "--result-json"):
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "--action",
                    "new-task",
                    "--slug",
                    "inline-payload-probe",
                    "--json",
                    flag,
                    "{}",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode == 0 or "unrecognized arguments" not in completed.stderr:
                accepted.append(flag)
        self.assertEqual([], accepted, f"GTO still accepts inline JSON flags: {accepted}")

    def test_cli_rejects_invalid_fixed_enum_values_during_parsing(self) -> None:
        # Break caught: invalid fixed values reach controller dispatch or are
        # silently ignored instead of failing at argparse's public boundary.
        invalid_options = (
            ("--action", "not-an-action"),
            ("--context-mode", "shared"),
            ("--brief-kind", "anything"),
            ("--phase", "skip-ahead"),
        )
        for option, value in invalid_options:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "--action",
                    "new-task",
                    "--slug",
                    "enum-probe",
                    "--json",
                    option,
                    value,
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode, f"{option} accepted {value}")
            self.assertIn("invalid choice", completed.stderr, f"{option}: {completed.stderr}")

    def test_result_json_file_failures_preserve_control_artifacts(self) -> None:
        # Break caught: a bad result input mutates state/task/events before
        # file loading, JSON parsing, or required-field validation finishes.
        self.init_task()
        self.run_ctl(
            "bind-dispatch",
            subtask_id="TEST-001",
            agent_key="initial-tester",
            platform_agent_id="initial-tester-001",
            context_mode="isolated",
            brief_kind="subtask",
            brief_sha256="1" * 64,
        )
        artifacts = (
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json",
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / "task.md",
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / "events.jsonl",
        )
        before = {path: path.read_bytes() for path in artifacts}
        malformed = self.repo / "malformed-result.json"
        malformed.write_text("not-json", encoding="utf-8")
        incomplete = self.repo / "incomplete-result.json"
        incomplete.write_text("{}", encoding="utf-8")
        for input_path in (self.repo / "missing-result.json", malformed, incomplete):
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "--action",
                    "record-subtask-result",
                    "--repo-root",
                    str(self.repo),
                    "--task-id",
                    TASK_ID,
                    "--subtask-id",
                    "TEST-001",
                    "--result-json-file",
                    str(input_path),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode, completed.stderr)
            self.assertFalse(json.loads(completed.stdout)["ok"])
            self.assertEqual(before, {path: path.read_bytes() for path in artifacts})

    def test_cli_rejects_single_dash_pascal_case_aliases(self) -> None:
        # Break caught: the retired PowerShell-style aliases remain part of the
        # public parser even though the WSL contract documents GNU long options.
        aliases = (
            "-Action", "-RepoRoot", "-TaskId", "-Json", "-SubtaskId",
            "-FindingId", "-ResultJson", "-ContractJson", "-Title", "-Owner",
            "-AgentKey", "-PlatformAgentId", "-ContextMode", "-BriefKind",
            "-BriefSha256", "-Slug", "-Phase", "-WorkspaceSummary",
        )
        accepted: list[str] = []
        for alias in aliases:
            if alias == "-Action":
                arguments = [alias, "new-task", "--slug", "alias-probe", "--json"]
            elif alias == "-Slug":
                arguments = ["--action", "new-task", alias, "alias-probe", "--json"]
            elif alias == "-Json":
                arguments = ["--action", "new-task", "--slug", "alias-probe", alias]
            else:
                arguments = [
                    "--action", "new-task", "--slug", "alias-probe", "--json",
                    alias, "alias-value",
                ]
            completed = subprocess.run(
                [sys.executable, str(CONTROLLER), *arguments],
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode == 0 or "unrecognized arguments" not in completed.stderr:
                accepted.append(alias)
        self.assertEqual([], accepted, f"GTO still accepts single-dash aliases: {accepted}")

    def test_documented_gto_actions_and_flags_exist_in_the_real_cli(self) -> None:
        # Break caught: a maintained skill tells Codex to invoke an action or
        # flag that the executable parser cannot accept.
        documentation = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                REPO_ROOT / "skills/global-task-orchestrator/SKILL.md",
                REPO_ROOT / "skills/global-task-orchestrator/references/state-schema.md",
            )
        )
        self.init_task()
        documented_actions = sorted(set(re.findall(r"--action\s+([a-z][a-z0-9-]+)", documentation)))
        unsupported: list[str] = []
        for action in documented_actions:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "--action",
                    action,
                    "--repo-root",
                    str(self.repo),
                    "--task-id",
                    TASK_ID,
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if "unsupported Action" in completed.stdout + completed.stderr:
                unsupported.append(action)

        self.assertEqual([], unsupported, f"documented GTO actions are not executable: {unsupported}")

    def test_documented_gto_flags_are_exposed_by_the_real_parser(self) -> None:
        documentation = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                REPO_ROOT / "skills/global-task-orchestrator/SKILL.md",
                REPO_ROOT / "skills/global-task-orchestrator/references/state-schema.md",
            )
        )

        help_result = subprocess.run(
            [sys.executable, str(CONTROLLER), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        parser_flags = set(re.findall(r"(?<![a-z0-9-])(--[a-z][a-z0-9-]+)", help_result.stdout))
        documented_flags = set(re.findall(r"(?<![a-z0-9-])(--[a-z][a-z0-9-]+)", documentation))
        self.assertEqual(
            [],
            sorted(documented_flags - parser_flags),
            f"documented GTO flags are absent from --help: {sorted(documented_flags - parser_flags)}",
        )

    def test_project_dispatch_entries_resolve_to_gto_without_role_catalog(self) -> None:
        self.assertEqual([], [path for path in (REPO_ROOT / "agents").rglob("*") if path.is_file()])
        self.assertFalse((REPO_ROOT / "docs/AGENTS.md").exists())
        active_entries = (
            "templates/project/README.md",
            "templates/project/.codex/README.md",
        )
        for relative in active_entries:
            entry = REPO_ROOT / relative
            text = entry.read_text(encoding="utf-8")
            references = re.findall(r"`([^`]*skills/global-task-orchestrator/SKILL\.md)`", text)
            self.assertTrue(references, relative)
            for reference in references:
                self.assertEqual((REPO_ROOT / "skills/global-task-orchestrator/SKILL.md").resolve(),
                                 (entry.parent / reference).resolve())
            self.assertNotIn("codex-role-map", text, relative)

    def test_orchestrator_schema_accepts_v3_and_rejects_v2(self) -> None:
        # Validate real persisted output from the single published contract source.
        skill = REPO_ROOT / "skills/global-task-orchestrator"
        temporary = tempfile.TemporaryDirectory(dir=REPO_ROOT / ".tmp")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.init_task(json.loads((skill / "references/revision-3-contract.example.json").read_text(encoding="utf-8")))
        schema = json.loads((skill / "schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        v3_state = self.state()
        self.assertEqual(3, v3_state["version"])
        self.assertEqual([], [error.message for error in validator.iter_errors(v3_state)])
        v2_state = deepcopy(v3_state)
        v2_state["version"] = 2
        self.assertNotEqual([], [error.message for error in validator.iter_errors(v2_state)],
                            "orchestrator schema must reject version=2")

    def test_current_task_templates_validate_and_use_only_active_commands(self) -> None:
        # Generated state and documents consume one contract; no independent state template.
        skill = REPO_ROOT / "skills/global-task-orchestrator"
        temporary = tempfile.TemporaryDirectory(dir=REPO_ROOT / ".tmp")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        contract = json.loads((skill / "references/revision-3-contract.example.json").read_text(encoding="utf-8"))
        self.init_task(contract)
        schema = json.loads((skill / "schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8"))
        self.assertEqual([], [error.message for error in Draft202012Validator(schema).iter_errors(self.state())])
        self.run_ctl("validate")
        serialized = json.dumps(self.state(), ensure_ascii=False) + "\n" + "\n".join(
            path.read_text(encoding="utf-8") for path in (self.repo / "docs").rglob("*.md"))
        self.assertIsNone(re.search(r"(?i)(?:powershell|\.ps1\b|\.cmd\b)", serialized),
                          "generated task contains retired PowerShell/batch command")
        self.assertIn("workflow.md", serialized, "generated task must reference the workflow source")
        instructions = (skill / "references/controller-guide.md").read_text(encoding="utf-8")
        documented_actions = set(re.findall(r"--action\s+([a-z][a-z0-9-]+)", instructions))
        self.assertTrue(documented_actions, "skill source must expose its active command entrypoints")
        help_result = subprocess.run([sys.executable, str(CONTROLLER), "--help"],
                                     text=True, capture_output=True, check=False)
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        choices = re.search(r"--action\s+\{([^}]+)\}", help_result.stdout)
        self.assertIsNotNone(choices, help_result.stdout)
        self.assertEqual(set(), documented_actions - set(choices.group(1).split(",")),
                         "generated task references unsupported actions")

    def test_new_task_generates_unique_local_time_id_without_creating_state(self) -> None:
        command = [
            "python3",
            str(CONTROLLER),
            "--action",
            "new-task",
            "--slug",
            "control-plane-bootstrap",
            "--json",
        ]
        task_ids = []
        for _ in range(2):
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertRegex(
                payload["task_id"],
                r"^\d{8}-\d{6}-\d{6}-control-plane-bootstrap$",
            )
            task_ids.append(payload["task_id"])
        self.assertEqual(2, len(set(task_ids)))
        self.assertFalse((self.repo / "docs").exists())



































if __name__ == "__main__":
    unittest.main()
