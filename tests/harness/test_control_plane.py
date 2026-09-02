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


def six_points() -> dict[str, object]:
    return {
        "do": "Implement the WSL Python control plane.",
        "do_not": ["Do not classify natural language in Python."],
        "change_areas": ["skills/global-task-orchestrator", "tests/harness"],
        "implementation": "Codex supplies semantics; Python performs mechanical gates.",
        "acceptance": ["The deterministic review loop reaches final/pass."],
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
                "independent_final_review",
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
                "dependencies": ["REVIEW-002"],
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


class ControlPlaneContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.input_temp = tempfile.TemporaryDirectory()
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
            "phase": "--phase",
            "workspace_summary": "--workspace-summary",
        }
        for key, value in kwargs.items():
            if key in {"result", "contract"}:
                self._json_input_index += 1
                payload_file = self.input_dir / f"gto-input-{self._json_input_index}.json"
                payload_file.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                encoded = str(payload_file)
            else:
                encoded = str(value)
            command.extend([names[key], encoded])
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
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
            contract=task_contract or contract(),
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

    def prepare_lifecycle(self) -> None:
        if not (self.repo / ".git").exists():
            self.init_git_checkout(
                "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
            )
        self.init_task()
        dispatches = (
            ("IMPL-001", IMPLEMENTER, "subtask", "1" * 64),
            ("REVIEW-001", REVIEWER, "review", "2" * 64),
            ("REVIEW-002", REVIEWER, "review", "3" * 64),
            (
                "FINAL-001",
                {"agent_key": "final-reviewer", "platform_agent_id": "final-001"},
                "review",
                "4" * 64,
            ),
        )
        for subtask_id, identity, brief_kind, brief_sha256 in dispatches:
            self.run_ctl(
                "bind-dispatch",
                subtask_id=subtask_id,
                agent_key=identity["agent_key"],
                platform_agent_id=identity["platform_agent_id"],
                context_mode="isolated",
                brief_kind=brief_kind,
                brief_sha256=brief_sha256,
            )
        self.run_ctl(
            "record-subtask-result",
            subtask_id="IMPL-001",
            result={
                "status": "completed",
                "summary": "Focused implementation completed.",
                "changed_files": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
                "planned_files_not_changed": [],
                "verification": {"commands": ["python3 -m unittest"], "result": "passed"},
                "deviations": [],
                "blocked_by": [],
                "risks": [],
                "follow_up": [],
                "written_by": IMPLEMENTER["platform_agent_id"],
                "written_role": IMPLEMENTER["agent_key"],
                "review_evidence": {
                    "repro_before_fix": "Observed expected Red.",
                    "pass_after_fix": "Focused test passed.",
                    "hit_proof_observed": "Rollback-sensitive assertion passed.",
                    "relevant_regression_ok": "Relevant regression passed.",
                },
            },
        )

    def state(self) -> dict[str, object]:
        path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def assert_phase_projection_and_schema(self, expected_phase: str) -> None:
        state = self.state()
        self.assertEqual(expected_phase, state["current_phase"])
        task_md = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "task.md"
        self.assertIn(f"- current_phase: `{expected_phase}`", task_md.read_text(encoding="utf-8"))
        schema = json.loads(
            (REPO_ROOT / "schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8")
        )
        errors = [error.message for error in Draft202012Validator(schema).iter_errors(state)]
        self.assertEqual([], errors, f"set-phase persisted a schema-invalid state: {errors}")

    def record_review(self, subtask_id: str, kind: str, findings: list[dict[str, object]]) -> dict[str, object]:
        reviewer_id = "final-001" if kind == "final" else REVIEWER["platform_agent_id"]
        review = {
            "kind": kind,
            "verdict": "pass" if not findings else "fail",
            "reviewer_platform_agent_id": reviewer_id,
            "findings": findings,
        }
        if kind == "final":
            brief = self.run_ctl("build-review-brief", subtask_id=subtask_id)
            review["reviewed_change_sha256"] = brief["brief"]["review_target_sha256"]
        return self.run_ctl(
            "record-review-result",
            subtask_id=subtask_id,
            result={"review": review},
        )

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
                "任务目标", "背景与问题", "范围", "非目标", "约束与依赖",
                "方案摘要", "风险与回退", "验收标准", "阶段划分",
                "需先同步的核心文档与测试",
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
                "The deterministic review loop reaches final/pass.", "A stale acceptance contract."
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

    def test_prepare_workspace_records_not_required_without_owned_overlap(self) -> None:
        head = self.init_git_checkout(
            "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
        )
        task_contract = contract()
        task_contract["subtasks"][1]["write_paths"] = ["notes.txt"]
        self.init_task(task_contract)
        (self.repo / "notes.txt").write_text("unrelated dirty work\n", encoding="utf-8")

        payload = self.run_ctl("prepare-workspace")
        workspace = self.state()["workspace"]
        self.assertEqual("not_required", payload["decision"])
        self.assertEqual("primary", workspace["checkout_kind"])
        self.assertEqual("main", workspace["branch"])
        self.assertEqual(head, workspace["head"])
        self.assertEqual(["notes.txt"], workspace["dirty_paths"])
        self.assertEqual([], workspace["write_overlap"])
        self.assertEqual("not_required", workspace["overlap_decision"]["status"])
        self.assertEqual({}, workspace["overlap_decision"]["baseline_hashes"])

    def test_prepare_workspace_persists_pending_capture_before_requiring_authorization(self) -> None:
        target = "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
        self.init_git_checkout(target)
        self.init_task()
        (self.repo / target).write_text("existing unowned change\n", encoding="utf-8")

        rejected = self.run_ctl("prepare-workspace", ok=False)
        workspace = self.state()["workspace"]
        self.assertIn("workspace-summary", " ".join(rejected.get("errors", [])).casefold())
        self.assertEqual([target], workspace["dirty_paths"])
        self.assertEqual([target], workspace["write_overlap"])
        self.assertEqual("pending", workspace["overlap_decision"]["status"])
        self.assertEqual({}, workspace["overlap_decision"]["baseline_hashes"])
        events = (
            self.repo / "docs" / "ai" / "tasks" / TASK_ID / "events.jsonl"
        ).read_text(encoding="utf-8")
        self.assertIn("workspace_overlap_pending", events)

    def test_prepare_workspace_recomputes_drift_then_unblocks_code_impl(self) -> None:
        first = "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
        second = "schemas/orchestrator-task-state.schema.json"
        self.init_git_checkout(first, second)
        task_contract = contract()
        task_contract["subtasks"][0]["write_paths"].append(second)
        self.init_task(task_contract)
        (self.repo / first).write_text("first dirty version\n", encoding="utf-8")
        self.run_ctl("prepare-workspace", ok=False)

        (self.repo / first).write_text("second dirty version\n", encoding="utf-8")
        (self.repo / second).write_text("new overlapping path\n", encoding="utf-8")
        summary = "Approved preservation of the current overlapping work."
        payload = self.run_ctl("prepare-workspace", workspace_summary=summary)
        workspace = self.state()["workspace"]
        self.assertEqual("resolved", payload["decision"])
        self.assertEqual([second, first], workspace["write_overlap"])
        self.assertEqual("resolved", workspace["overlap_decision"]["status"])
        self.assertEqual(summary, workspace["overlap_decision"]["summary"])
        self.assertEqual(
            {
                first: hashlib.sha256(b"second dirty version\n").hexdigest(),
                second: hashlib.sha256(b"new overlapping path\n").hexdigest(),
            },
            workspace["overlap_decision"]["baseline_hashes"],
        )

        for phase in ("doc_sync", "test_sync", "code_impl"):
            self.run_ctl("set-phase", phase=phase)
        self.assert_phase_projection_and_schema("code_impl")

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

    def test_set_phase_reuses_verification_workspace_and_review_evidence_gates(self) -> None:
        # Break caught: set-phase writes a privileged phase directly instead of
        # applying the same validation gates used by the control plane.
        self.init_task()
        self.run_ctl("set-phase", phase="doc_sync")
        self.run_ctl("set-phase", phase="test_sync")
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"

        state = self.state()
        verification_contract = state.pop("verification_contract")
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        missing_verification = self.run_ctl("set-phase", ok=False, phase="code_impl")
        self.assertIn("verification", " ".join(missing_verification.get("errors", [])).casefold())
        self.assert_phase_projection_and_schema("test_sync")

        state = self.state()
        state["verification_contract"] = verification_contract
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        unresolved_workspace = self.run_ctl("set-phase", ok=False, phase="code_impl")
        self.assertIn("workspace", " ".join(unresolved_workspace.get("errors", [])).casefold())
        self.assert_phase_projection_and_schema("test_sync")

        state = self.state()
        state["workspace"]["overlap_decision"]["status"] = "not_required"
        state["workspace"]["overlap_decision"]["summary"] = "No overlap requires adjudication."
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.run_ctl("set-phase", phase="code_impl")
        self.assert_phase_projection_and_schema("code_impl")

        missing_evidence = self.run_ctl("set-phase", ok=False, phase="review")
        self.assertIn("evidence", " ".join(missing_evidence.get("errors", [])).casefold())
        self.assert_phase_projection_and_schema("code_impl")

        self.run_ctl(
            "bind-dispatch",
            subtask_id="IMPL-001",
            agent_key=IMPLEMENTER["agent_key"],
            platform_agent_id=IMPLEMENTER["platform_agent_id"],
            context_mode="isolated",
            brief_kind="subtask",
            brief_sha256="1" * 64,
        )
        self.run_ctl(
            "record-subtask-result",
            subtask_id="IMPL-001",
            result={
                "status": "completed",
                "summary": "Implementation evidence completed.",
                "changed_files": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
                "planned_files_not_changed": [],
                "verification": {"commands": ["python3 -m unittest"], "result": "passed"},
                "deviations": [],
                "blocked_by": [],
                "risks": [],
                "follow_up": [],
                "written_by": IMPLEMENTER["platform_agent_id"],
                "written_role": IMPLEMENTER["agent_key"],
                "review_evidence": {
                    "repro_before_fix": "Observed expected Red.",
                    "pass_after_fix": "Focused test passed.",
                    "hit_proof_observed": "Hit proof passed.",
                    "relevant_regression_ok": "Regression passed.",
                },
            },
        )
        self.run_ctl("set-phase", phase="review")
        self.assert_phase_projection_and_schema("review")

    def test_doc_curator_custom_evidence_unblocks_review_but_reviewer_evidence_does_not(self) -> None:
        # Break caught: review applies a role-specific evidence allowlist, so
        # a completed doc-curator cannot satisfy a contract's custom required
        # evidence while a reviewer must never satisfy it.
        task_contract = contract()
        task_contract["verification_contract"]["review_evidence"] = ["tooling_rule_index_green"]
        task_contract["subtasks"].insert(
            0,
            {
                "subtask_id": "DOC-001",
                "title": "Index tooling rules",
                "role": "doc-curator",
                "status": "ready",
                "dependencies": [],
                "read_paths": ["rules"],
                "write_paths": ["docs"],
                "assignment": assignment("Publish TOOL-RULE-003 evidence."),
            },
        )
        self.init_task(task_contract)
        self.run_ctl("set-phase", phase="doc_sync")
        self.run_ctl("set-phase", phase="test_sync")
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        state = self.state()
        state["workspace"]["overlap_decision"] = {
            "status": "not_required",
            "summary": "No overlap requires adjudication.",
            "baseline_hashes": {},
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.run_ctl("set-phase", phase="code_impl")

        state = self.state()
        reviewer = next(item for item in state["subtasks"] if item["subtask_id"] == "REVIEW-001")
        reviewer["status"] = "completed"
        reviewer["result"] = {
            "status": "completed",
            "summary": "Reviewer cannot supply implementation evidence.",
            "changed_files": [],
            "planned_files_not_changed": [],
            "verification": {"commands": ["review"], "result": "passed"},
            "deviations": [],
            "blocked_by": [],
            "risks": [],
            "follow_up": [],
            "written_by": REVIEWER["platform_agent_id"],
            "written_role": REVIEWER["agent_key"],
            "review_evidence": {"tooling_rule_index_green": "Reviewer claim."},
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rejected = self.run_ctl("set-phase", ok=False, phase="review")
        self.assertIn("tooling_rule_index_green", " ".join(rejected.get("errors", [])))
        self.assert_phase_projection_and_schema("code_impl")

        self.run_ctl(
            "bind-dispatch",
            subtask_id="DOC-001",
            agent_key="doc-001",
            platform_agent_id="doc-001",
            context_mode="isolated",
            brief_kind="subtask",
            brief_sha256="d" * 64,
        )
        self.run_ctl(
            "record-subtask-result",
            subtask_id="DOC-001",
            result={
                "status": "completed",
                "summary": "TOOL-RULE-003 indexed.",
                "changed_files": ["docs/TOOL-RULE-003.md"],
                "planned_files_not_changed": [],
                "verification": {"commands": ["python3 -m unittest"], "result": "passed"},
                "deviations": [],
                "blocked_by": [],
                "risks": [],
                "follow_up": [],
                "written_by": "doc-001",
                "written_role": "doc-001",
                "review_evidence": {"tooling_rule_index_green": "TOOL-RULE-003 verified."},
            },
        )
        self.run_ctl("set-phase", phase="review")
        self.assert_phase_projection_and_schema("review")

    def test_validate_rejects_impossible_dependency_dispatch_and_result_states(self) -> None:
        self.init_task()
        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        state = self.state()
        review = next(item for item in state["subtasks"] if item["subtask_id"] == "REVIEW-001")
        review["status"] = "completed"
        review["dispatch"] = {
            "agent_key": "reviewer",
            "platform_agent_id": "review-001",
            "context_mode": "isolated",
            "brief_kind": "review",
            "brief_sha256": "a" * 64,
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        invalid = self.run_ctl("validate", ok=False)
        errors = " ".join(invalid.get("errors", [])).lower()
        self.assertIn("result", errors)
        self.assertIn("depend", errors)

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
            (REPO_ROOT / "schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        baseline = self.state()
        lifecycle = finding("SCHEMA-LIFECYCLE-001")
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

    def test_record_finding_fix_rejects_schema_capacity_without_mutating_state(self) -> None:
        source = self.repo / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
        source.parent.mkdir(parents=True)
        source.write_text("controller\n", encoding="utf-8")
        self.prepare_lifecycle()
        self.record_review("REVIEW-001", "task", [finding("SCHEMA-FIX-DELTA-002")])
        self.run_ctl("dispatch-finding-fix", finding_id="SCHEMA-FIX-DELTA-002")

        rejected = self.run_ctl(
            "record-finding-fix",
            ok=False,
            finding_id="SCHEMA-FIX-DELTA-002",
            result={
                "summary": "Oversized fix delta.",
                "changed_files": [f"noise/{index}.txt" for index in range(501)],
                "sha256": "b" * 64,
                "verification": "Must be rejected by the canonical schema.",
            },
        )
        self.assertTrue(rejected.get("errors"), rejected)
        stored = self.state()["findings"]["SCHEMA-FIX-DELTA-002"]
        self.assertEqual("fix_dispatched", stored["status"])
        self.assertNotIn("fix_delta", stored)

    def test_same_finding_crosses_review_subtasks_and_returns_to_lineage(self) -> None:
        self.prepare_lifecycle()
        first = self.record_review("REVIEW-001", "task", [finding("F-ONE")])
        self.assertEqual("dispatch_fix", first["next_action"]["kind"])
        self.assertEqual(IMPLEMENTER, first["next_action"]["target"])

        # Merely validating or projecting evidence must not consume a fix round.
        self.run_ctl("validate")
        self.run_ctl("build-review-brief", subtask_id="REVIEW-001", finding_id="F-ONE")
        self.assertEqual(0, self.state()["findings"]["F-ONE"]["fix_round"])

        dispatched = self.run_ctl("dispatch-finding-fix", finding_id="F-ONE")
        self.assertEqual(1, dispatched["finding"]["fix_round"])
        self.assertEqual(IMPLEMENTER, dispatched["next_action"]["target"])
        fixed = self.run_ctl(
            "record-finding-fix",
            finding_id="F-ONE",
            result={
                "summary": "Fixed F-ONE.",
                "changed_files": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
                "sha256": "a" * 64,
                "verification": "Focused test passed.",
            },
        )
        self.assertEqual("re_review", fixed["next_action"]["kind"])
        self.assertEqual(REVIEWER, fixed["next_action"]["target"])

        rereview = self.run_ctl(
            "record-review-result",
            subtask_id="REVIEW-002",
            result={
                "review": {
                    "kind": "re_review",
                    "verdict": "pass",
                    "reviewer_platform_agent_id": REVIEWER["platform_agent_id"],
                    "findings": [finding("F-ONE", status="closed")],
                }
            },
        )
        self.assertEqual("final_review", rereview["next_action"]["kind"])
        self.assertEqual("closed", self.state()["findings"]["F-ONE"]["status"])

    def test_re_review_pass_rejects_open_or_unknown_findings(self) -> None:
        # Break caught: a passing re-review can leave an existing finding open
        # or close a finding that was never routed through review lineage.
        self.prepare_lifecycle()
        self.record_review("REVIEW-001", "task", [finding("F-PASS-GATE")])
        self.run_ctl("dispatch-finding-fix", finding_id="F-PASS-GATE")
        self.run_ctl(
            "record-finding-fix",
            finding_id="F-PASS-GATE",
            result={
                "summary": "Fix ready for review.",
                "changed_files": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
                "sha256": "a" * 64,
                "verification": "Focused test passed.",
            },
        )
        for reported, expected in (
            (finding("F-PASS-GATE"), "closed"),
            (finding("F-UNKNOWN", status="closed"), "unknown"),
        ):
            with self.subTest(finding_id=reported["finding_id"]):
                rejected = self.run_ctl(
                    "record-review-result",
                    ok=False,
                    subtask_id="REVIEW-002",
                    result={
                        "review": {
                            "kind": "re_review",
                            "verdict": "pass",
                            "reviewer_platform_agent_id": REVIEWER["platform_agent_id"],
                            "findings": [reported],
                        }
                    },
                )
                self.assertIn(expected, " ".join(rejected.get("errors", [])).casefold())

    def test_task_and_final_pass_reject_findings(self) -> None:
        # Break caught: only a re-review/pass may close existing findings;
        # task and final passing verdicts must remain finding-free.
        self.prepare_lifecycle()
        task_rejected = self.run_ctl(
            "record-review-result",
            ok=False,
            subtask_id="REVIEW-001",
            result={
                "review": {
                    "kind": "task",
                    "verdict": "pass",
                    "reviewer_platform_agent_id": REVIEWER["platform_agent_id"],
                    "findings": [finding("F-TASK-PASS")],
                }
            },
        )
        self.assertIn("fail with findings", " ".join(task_rejected.get("errors", [])))
        final_rejected = self.run_ctl(
            "record-review-result",
            ok=False,
            subtask_id="FINAL-001",
            result={
                "review": {
                    "kind": "final",
                    "verdict": "pass",
                    "reviewer_platform_agent_id": "final-001",
                    "findings": [finding("F-FINAL-PASS")],
                }
            },
        )
        self.assertIn("cannot contain findings", " ".join(final_rejected.get("errors", [])))

    def test_fix_rounds_are_per_finding_and_r3_open_blocks(self) -> None:
        self.prepare_lifecycle()
        self.record_review("REVIEW-001", "task", [finding("F-A"), finding("F-B")])
        self.run_ctl("dispatch-finding-fix", finding_id="F-A")
        self.assertEqual(1, self.state()["findings"]["F-A"]["fix_round"])
        self.assertEqual(0, self.state()["findings"]["F-B"]["fix_round"])

        for expected_round in (1, 2, 3):
            self.run_ctl("dispatch-finding-fix", finding_id="F-B")
            current = self.state()["findings"]["F-B"]
            self.assertEqual(expected_round, current["fix_round"])
            self.run_ctl(
                "record-finding-fix",
                finding_id="F-B",
                result={
                    "summary": f"Attempted F-B round {expected_round}.",
                    "changed_files": ["skills/global-task-orchestrator/scripts/orchestrator_ctl.py"],
                    "sha256": f"{expected_round}" * 64,
                    "verification": "The finding remains reproducible.",
                },
            )
            self.record_review("REVIEW-002", "re_review", [finding("F-B")])

        state = self.state()
        self.assertEqual("blocked", state["status"])
        self.assertEqual("blocked", state["current_phase"])
        self.assertEqual("blocked", state["findings"]["F-B"]["status"])
        self.assertEqual("human_adjudication", state["next_action"]["kind"])

    def test_finalize_requires_independent_latest_final_pass_and_no_open_finding(self) -> None:
        self.prepare_lifecycle()
        rejected = self.run_ctl("finalize-task", ok=False)
        self.assertIn("final/pass", " ".join(rejected.get("errors", [])))

        self.record_review("FINAL-001", "final", [])
        completed = self.run_ctl("finalize-task")
        self.assertEqual("completed", completed["status"])
        self.assertEqual("completed", self.state()["status"])

    def test_review_target_tracks_scoped_source_and_final_fail_routes_fix(self) -> None:
        source = self.repo / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
        source.parent.mkdir(parents=True)
        source.write_text("first\n", encoding="utf-8")
        self.prepare_lifecycle()
        first = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]["review_target_sha256"]
        source.write_text("second\n", encoding="utf-8")
        second = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]["review_target_sha256"]
        self.assertNotEqual(first, second)

        failed = self.record_review("FINAL-001", "final", [finding("GTO-FINAL-COVERAGE-002")])
        self.assertEqual("dispatch_fix", failed["next_action"]["kind"])
        self.assertEqual(IMPLEMENTER, failed["next_action"]["target"])

    def test_registered_finding_path_keeps_controller_in_final_source_manifest(self) -> None:
        source = self.repo / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
        fix_test = self.repo / "tests" / "harness" / "test_control_plane.py"
        source.parent.mkdir(parents=True)
        fix_test.parent.mkdir(parents=True)
        source.write_text("finding scoped controller v1\n", encoding="utf-8")
        fix_test.write_text("finding fix test v1\n", encoding="utf-8")
        self.prepare_lifecycle()

        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        state = self.state()
        implementation = next(item for item in state["subtasks"] if item["subtask_id"] == "IMPL-001")
        implementation["result"]["changed_files"] = []
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.record_review("REVIEW-001", "task", [finding("FINAL-SCOPE-003")])
        self.run_ctl("dispatch-finding-fix", finding_id="FINAL-SCOPE-003")
        self.run_ctl(
            "record-finding-fix",
            finding_id="FINAL-SCOPE-003",
            result={
                "summary": "Added the focused regression test.",
                "changed_files": ["tests/harness/test_control_plane.py"],
                "sha256": "b" * 64,
                "verification": "Focused test passed.",
            },
        )

        first = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]
        manifest_paths = {entry["path"] for entry in first["source_manifest"]}
        self.assertIn("skills/global-task-orchestrator/scripts/orchestrator_ctl.py", manifest_paths)
        self.assertIn("tests/harness/test_control_plane.py", manifest_paths)
        source.write_text("finding scoped controller v2\n", encoding="utf-8")
        controller_hash = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]["review_target_sha256"]
        self.assertNotEqual(first["review_target_sha256"], controller_hash)
        fix_test.write_text("finding fix test v2\n", encoding="utf-8")
        test_hash = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]["review_target_sha256"]
        self.assertNotEqual(controller_hash, test_hash)

    def test_final_manifest_adds_unreported_git_changes_and_deletions_only_within_task_scope(self) -> None:
        reported = "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
        unreported = "skills/global-task-orchestrator/scripts/helper.py"
        deleted = "skills/global-task-orchestrator/scripts/retired.py"
        noise = "unrelated/noise.txt"
        self.init_git_checkout(reported, unreported, deleted, noise)
        task_contract = contract()
        task_contract["subtasks"][0]["write_paths"] = [
            "skills/global-task-orchestrator/scripts",
            "docs",
        ]
        self.init_task(task_contract)
        (self.repo / reported).write_text("reported change\n", encoding="utf-8")
        (self.repo / unreported).write_text("unreported change\n", encoding="utf-8")
        (self.repo / deleted).unlink()
        (self.repo / noise).write_text("out-of-scope noise\n", encoding="utf-8")
        self.run_ctl(
            "bind-dispatch",
            subtask_id="IMPL-001",
            agent_key=IMPLEMENTER["agent_key"],
            platform_agent_id=IMPLEMENTER["platform_agent_id"],
            context_mode="isolated",
            brief_kind="subtask",
            brief_sha256="1" * 64,
        )
        self.run_ctl(
            "record-subtask-result",
            subtask_id="IMPL-001",
            result={
                "status": "completed",
                "summary": "Implementation self-reported one file.",
                "changed_files": [reported],
                "planned_files_not_changed": [],
                "verification": {"commands": ["python3 -m unittest"], "result": "passed"},
                "deviations": [],
                "blocked_by": [],
                "risks": [],
                "follow_up": [],
                "written_by": IMPLEMENTER["platform_agent_id"],
                "written_role": IMPLEMENTER["agent_key"],
            },
        )

        brief = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]
        manifest = {entry["path"]: entry["sha256"] for entry in brief["source_manifest"]}
        self.assertEqual(
            {reported, unreported, deleted},
            set(manifest),
            "final manifest must add actual in-scope Git changes without absorbing repository noise",
        )
        self.assertEqual("missing", manifest[deleted])
        control_prefixes = (
            f"docs/ai/tasks/{TASK_ID}/",
            f"docs/tasks/{TASK_ID}/",
        )
        self.assertFalse(any(path.startswith(control_prefixes) for path in manifest))

    def test_subtask_result_file_lists_cannot_escape_original_write_paths(self) -> None:
        self.init_task()
        self.run_ctl(
            "bind-dispatch",
            subtask_id="IMPL-001",
            agent_key=IMPLEMENTER["agent_key"],
            platform_agent_id=IMPLEMENTER["platform_agent_id"],
            context_mode="isolated",
            brief_kind="subtask",
            brief_sha256="1" * 64,
        )

        def result(changed_files: list[str], planned_files_not_changed: list[str]) -> dict[str, object]:
            return {
                "status": "completed",
                "summary": "Attempted result outside the assigned scope.",
                "changed_files": changed_files,
                "planned_files_not_changed": planned_files_not_changed,
                "verification": {"commands": ["python3 -m unittest"], "result": "passed"},
                "deviations": [],
                "blocked_by": [],
                "risks": [],
                "follow_up": [],
                "written_by": IMPLEMENTER["platform_agent_id"],
                "written_role": IMPLEMENTER["agent_key"],
            }

        invalid_changed = self.run_ctl(
            "record-subtask-result",
            ok=False,
            subtask_id="IMPL-001",
            result=result(["agents/README.md"], []),
        )
        self.assertIn("write_paths", " ".join(invalid_changed.get("errors", [])))
        invalid_planned = self.run_ctl(
            "record-subtask-result",
            ok=False,
            subtask_id="IMPL-001",
            result=result([], ["agents/README.md"]),
        )
        self.assertIn("write_paths", " ".join(invalid_planned.get("errors", [])))
        implementation = next(
            item for item in self.state()["subtasks"] if item["subtask_id"] == "IMPL-001"
        )
        self.assertEqual("in_progress", implementation["status"])
        self.assertNotIn("result", implementation)

    def test_final_pass_is_rejected_after_reviewed_source_changes(self) -> None:
        source = self.repo / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
        source.parent.mkdir(parents=True)
        source.write_text("reviewed\n", encoding="utf-8")
        self.prepare_lifecycle()
        reviewed = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]["review_target_sha256"]
        source.write_text("changed after review\n", encoding="utf-8")
        rejected = self.run_ctl(
            "record-review-result",
            ok=False,
            subtask_id="FINAL-001",
            result={
                "review": {
                    "kind": "final",
                    "verdict": "pass",
                    "reviewer_platform_agent_id": "final-001",
                    "reviewed_change_sha256": reviewed,
                    "findings": [],
                }
            },
        )
        self.assertIn("latest", " ".join(rejected.get("errors", [])).lower())

    def test_final_target_excludes_only_current_task_control_artifacts(self) -> None:
        source = self.repo / "skills" / "global-task-orchestrator" / "scripts" / "orchestrator_ctl.py"
        source.parent.mkdir(parents=True)
        source.write_text("real scoped source\n", encoding="utf-8")
        self.prepare_lifecycle()

        state_path = self.repo / "docs" / "ai" / "tasks" / TASK_ID / "state.json"
        state = self.state()
        implementation = next(item for item in state["subtasks"] if item["subtask_id"] == "IMPL-001")
        implementation["result"]["changed_files"].extend(
            [f"docs/ai/tasks/{TASK_ID}", f"docs/tasks/{TASK_ID}"]
        )
        state["findings"]["GTO-FINAL-SELFREF-003"] = {
            **finding("GTO-FINAL-SELFREF-003", status="closed"),
            "paths": [
                f"docs/ai/tasks/{TASK_ID}/state.json",
                f"docs/ai/tasks/{TASK_ID}/events.jsonl",
                f"docs/ai/tasks/{TASK_ID}/.control.lock",
                f"docs/tasks/{TASK_ID}/acceptance.md",
                "skills/global-task-orchestrator/scripts/orchestrator_ctl.py",
            ],
            "fix_round": 1,
            "lineage": {"original_implementer": IMPLEMENTER, "original_reviewer": REVIEWER},
            "closed_at": "2030-01-02T03:04:05+00:00",
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        brief = self.run_ctl("build-review-brief", subtask_id="FINAL-001")["brief"]
        manifest_paths = {entry["path"] for entry in brief["source_manifest"]}
        self.assertIn("skills/global-task-orchestrator/scripts/orchestrator_ctl.py", manifest_paths)
        self.assertFalse(any(path.startswith(f"docs/ai/tasks/{TASK_ID}/") for path in manifest_paths))
        self.assertFalse(any(path.startswith(f"docs/tasks/{TASK_ID}/") for path in manifest_paths))

        self.record_review("FINAL-001", "final", [])
        completed = self.run_ctl("finalize-task")
        self.assertEqual("completed", completed["status"])

    def test_cli_accepts_documented_gnu_long_options(self) -> None:
        contract_file = self.repo / "contract.json"
        contract_file.write_text(json.dumps(contract()), encoding="utf-8")
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
        invalid_contract = contract()
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
        contract_file.write_text(json.dumps(contract()), encoding="utf-8")
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
            subtask_id="IMPL-001",
            agent_key=IMPLEMENTER["agent_key"],
            platform_agent_id=IMPLEMENTER["platform_agent_id"],
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
                    "IMPL-001",
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

    def test_agent_catalog_uses_live_assignment_and_dispatch_without_v2_role_map(self) -> None:
        role_map = REPO_ROOT / "agents/codex-role-map.json"
        self.assertFalse(role_map.exists(), "active agents must not retain the v2 role-map compatibility layer")
        active_entries = (
            "agents/README.md",
            "docs/AGENTS.md",
            "templates/project/README.md",
            "templates/project/docs/ai/README.md",
            "templates/project/config/ai/README.md",
        )
        for relative in active_entries:
            catalog = (REPO_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("agent_type", catalog, relative)
            self.assertNotIn("codex-role-map", catalog, relative)
            for required in ("task.md", "assignment", "spawn_agent", "platform_agent_id", "dispatch"):
                self.assertIn(required, catalog, f"{relative} must document live dispatch field {required}")

    def test_orchestrator_schema_accepts_v3_and_rejects_v2(self) -> None:
        # Break caught: the persisted task contract silently keeps the v2/v3
        # dual track after v3 becomes the only active state version.
        schema = json.loads(
            (REPO_ROOT / "schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        v3_state = json.loads(
            (REPO_ROOT / "templates/orchestrator/state.template.json").read_text(encoding="utf-8")
        )
        self.assertEqual([], [error.message for error in validator.iter_errors(v3_state)])
        v2_state = deepcopy(v3_state)
        v2_state["version"] = 2
        self.assertNotEqual(
            [],
            [error.message for error in validator.iter_errors(v2_state)],
            "orchestrator schema must reject version=2",
        )

    def test_current_task_templates_validate_and_use_only_active_commands(self) -> None:
        # Break caught: a shipped task template remains on an old schema or
        # routes verification through deleted PowerShell entrypoints.
        schema = json.loads(
            (REPO_ROOT / "schemas/orchestrator-task-state.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        templates = (
            REPO_ROOT / "templates/orchestrator/state.template.json",
            REPO_ROOT / "templates/task-state.example.json",
        )
        violations: dict[str, list[str]] = {}
        for path in templates:
            payload = json.loads(path.read_text(encoding="utf-8"))
            errors = [error.message for error in validator.iter_errors(payload)]
            serialized = json.dumps(payload, ensure_ascii=False)
            if re.search(r"(?i)(?:powershell|\.ps1\b|\.cmd\b)", serialized):
                errors.append("contains retired PowerShell/batch command")
            documented_actions = set(re.findall(r"--action\s+([a-z][a-z0-9-]+)", serialized))
            for action in sorted(documented_actions):
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
                    errors.append(f"contains unsupported action {action}")
            if errors:
                violations[path.relative_to(REPO_ROOT).as_posix()] = errors
        self.assertEqual({}, violations, f"current task templates are stale: {violations}")

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
