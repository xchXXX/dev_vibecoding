"""Independent CLI contracts for user-authorized, append-only budget extension.

All approvals and receipts below are synthetic test fixtures, never business
acceptance evidence. No product models or browser operations are executed.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_gto_workflow import workflow_contract

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
TASK_ID = "20300102-030405-control-plane-contract"


class AcceptanceBudgetTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".tmp/gto-acceptance-budget-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.inputs = self.repo / ".tmp"
        self.inputs.mkdir()
        self.control = self.repo / "docs/ai/tasks" / TASK_ID
        self.sequence = 0
        contract = self.inputs / "contract.json"
        contract.write_text(json.dumps(workflow_contract()), encoding="utf-8")
        self.call("init-task", title="Budget extension fixture", owner="coordinator",
                  contract_json_file=contract)
        evidence = self.repo / "docs/tasks" / TASK_ID / "plan.md"
        evidence.write_text(evidence.read_text() + "\nSynthetic explicit user budget authorization.\n")
        self.call("accept-artifact-update")

    def call(self, action, *, ok=True, result=None, **arguments):
        command = [sys.executable, "-B", str(CONTROLLER), "--action", action,
                   "--repo-root", str(self.repo), "--task-id", TASK_ID, "--json"]
        if result is not None:
            self.sequence += 1
            path = self.inputs / f"result-{self.sequence}.json"
            path.write_text(json.dumps(result), encoding="utf-8")
            arguments["result_json_file"] = path
        for name, value in arguments.items():
            command.extend(["--" + name.replace("_", "-"), str(value)])
        completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
        if completed.stdout.strip():
            payload = json.loads(completed.stdout)
        else:
            payload = {"ok": False, "errors": [completed.stderr]}
        self.assertEqual(ok, completed.returncode == 0, payload)
        self.assertEqual(ok, payload.get("ok"), payload)
        return payload

    def state(self):
        return json.loads((self.control / "state.json").read_text())

    def snapshot(self):
        paths = list(self.control.glob("*.json*")) + list(self.control.glob("*.md"))
        paths += list((self.repo / "docs/tasks" / TASK_ID).glob("*.md"))
        return {str(path.relative_to(self.repo)): path.read_bytes() for path in paths}

    def decision(self, previous=4, maximum=8):
        return {"written_by": "/root", "written_role": "coordinator",
                "approved_by": "user", "reason": "Explicit user authorization to finish real acceptance.",
                "approval_evidence_refs": [f"docs/tasks/{TASK_ID}/plan.md"],
                "previous_max_expensive_attempts": previous,
                "max_expensive_attempts": maximum}

    def block(self):
        examples = ROOT / "skills/global-task-orchestrator/references/revision-3-results.example.json"
        receipt = json.loads(examples.read_text())["coordinator_blocked"]
        receipt["written_by"] = "/root"
        self.call("set-phase", phase="blocked", result=receipt)

    def test_explicit_extension_is_append_only_and_does_not_change_other_gates(self):
        before = self.state()
        self.assertEqual(4, before["acceptance_gate"]["attempt_policy"]["max_expensive_attempts"])
        events_before = (self.control / "events.jsonl").read_bytes()
        first = self.decision()
        self.call("extend-acceptance-budget", result=first)
        after = self.state()
        self.assertEqual(8, after["acceptance_gate"]["attempt_policy"]["max_expensive_attempts"])
        self.assertEqual([first], after["acceptance_gate"]["budget_extensions"])
        expected = deepcopy(before["acceptance_gate"])
        expected["attempt_policy"]["max_expensive_attempts"] = 8
        expected["budget_extensions"] = [first]
        self.assertEqual(expected, after["acceptance_gate"])
        for key in ("task_id", "status", "current_phase", "subtasks", "findings", "approval"):
            self.assertEqual(before[key], after[key], key)
        self.assertTrue((self.control / "events.jsonl").read_bytes().startswith(events_before))
        events = [json.loads(line) for line in (self.control / "events.jsonl").read_text().splitlines()]
        self.assertEqual("acceptance_budget_extended", events[-1]["event"])
        self.call("validate")
        second = self.decision(8, 12)
        self.call("extend-acceptance-budget", result=second)
        self.assertEqual([first, second], self.state()["acceptance_gate"]["budget_extensions"])
        self.call("validate")

    def test_invalid_or_unapproved_extension_is_rejected_without_artifact_changes(self):
        cases = [{"approved_by": ""}, {"approved_by": "coordinator"}, {"reason": ""},
                 {"approval_evidence_refs": []}, {"written_by": ""}, {"written_role": "tester"},
                 {"previous_max_expensive_attempts": 3}, {"max_expensive_attempts": 4},
                 {"max_expensive_attempts": 2}, {"max_expensive_attempts": True},
                 {"max_expensive_attempts": 8.5}]
        for patch in cases:
            with self.subTest(patch=patch):
                receipt = self.decision()
                receipt.update(patch)
                before = self.snapshot()
                self.call("extend-acceptance-budget", result=receipt, ok=False)
                self.assertEqual(before, self.snapshot())

    def test_blocked_extension_cannot_resume_create_attempt_or_finalize(self):
        self.block()
        before = self.state()
        self.call("extend-acceptance-budget", result=self.decision())
        after = self.state()
        for key in ("status", "current_phase", "next_action", "coordinator_blocker", "subtasks", "findings"):
            self.assertEqual(before[key], after[key], key)
        self.call("validate")
        for action, arguments in [("create-subtask-attempt", {"subtask_id": "EXPENSIVE-001"}),
                                  ("freeze-candidate", {}), ("finalize-task", {})]:
            with self.subTest(action=action):
                unchanged = self.snapshot()
                self.call(action, ok=False, **arguments)
                self.assertEqual(unchanged, self.snapshot())

    def test_extension_cannot_supply_candidate_review_or_acceptance_evidence(self):
        self.call("extend-acceptance-budget", result=self.decision())
        self.assertEqual([], self.state()["acceptance_gate"]["attempts"])
        for action, arguments in [("create-subtask-attempt", {"subtask_id": "EXPENSIVE-001"}),
                                  ("freeze-candidate", {}), ("finalize-task", {})]:
            with self.subTest(action=action):
                before = self.snapshot()
                self.call(action, ok=False, **arguments)
                self.assertEqual(before, self.snapshot())

    def test_manual_budget_change_without_authorization_chain_fails_validation(self):
        value = self.state()
        value["acceptance_gate"]["attempt_policy"]["max_expensive_attempts"] = 8
        (self.control / "state.json").write_text(json.dumps(value), encoding="utf-8")
        self.call("validate", ok=False)

    def test_existing_attempt_candidate_and_bound_identities_survive_extension(self):
        from test_gto_workflow import WorkflowTest

        fixture = WorkflowTest()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.start()
        fixture.integrate()
        fixture.review()
        fixture.accept()
        before = fixture.state()
        self.assertTrue(before["acceptance_gate"]["attempts"])
        self.assertTrue(before["acceptance_gate"]["current_candidate"])
        fixture.run_ctl("extend-acceptance-budget", result=self.decision())
        after = fixture.state()
        self.assertEqual(before["acceptance_gate"]["attempts"], after["acceptance_gate"]["attempts"])
        self.assertEqual(before["acceptance_gate"]["current_candidate"],
                         after["acceptance_gate"]["current_candidate"])
        self.assertEqual(before["subtasks"], after["subtasks"])
        self.assertEqual(before["findings"], after["findings"])
        self.assertEqual(before["approval"], after["approval"])
        fixture.run_ctl("validate")


if __name__ == "__main__":
    unittest.main()
