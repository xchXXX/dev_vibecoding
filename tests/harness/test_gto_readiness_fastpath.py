"""Readiness must not scan acceptance before a frozen candidate exists."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from test_gto_plan_preflight_contract import REPO_ROOT, load_controller


def readiness_state(candidate=None):
    return {
        "workflow_revision": 3,
        "status": "active",
        "current_phase": "test_sync",
        "acceptance_gate": {"current_candidate": candidate},
        "subtasks": [
            {"subtask_id": "DONE", "stage": "work", "status": "completed"},
            {"subtask_id": "NEXT", "stage": "work", "status": "pending",
             "dependencies": ["DONE"]},
            {"subtask_id": "ACCEPT", "stage": "expensive_acceptance",
             "status": "pending", "dependencies": ["DONE"]},
            {"subtask_id": "DOC", "stage": "final_documentation",
             "status": "pending", "dependencies": ["ACCEPT"]},
        ],
    }


class ReadinessFastpathTest(unittest.TestCase):
    def setUp(self):
        self.controller = load_controller()

    def test_unfrozen_candidate_does_not_enter_full_acceptance_gate(self):
        candidates = (None, {}, {"status": "draft", "candidate_id": "c1"},
                      {"status": "frozen"}, {"status": "frozen", "candidate_id": ""})
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                state = readiness_state(candidate)
                with patch.object(
                    self.controller, "_current_acceptance_pass_errors",
                    side_effect=AssertionError("UNEXPECTED_FULL_ACCEPTANCE_SCAN_WITHOUT_FROZEN_CANDIDATE"),
                ) as gate:
                    self.controller._refresh_subtask_readiness(REPO_ROOT, state)
                gate.assert_not_called()
                self.assertEqual(state["subtasks"][1]["status"], "ready")
                self.assertEqual(state["subtasks"][2]["status"], "pending")
                self.assertEqual(state["subtasks"][3]["status"], "pending")

    def test_ordinary_successor_requires_no_acceptance_scan(self):
        state = readiness_state()
        state["subtasks"] = state["subtasks"][:2]
        with patch.object(self.controller, "_current_acceptance_pass_errors",
                          side_effect=AssertionError("ordinary work scanned acceptance")) as gate:
            self.controller._refresh_subtask_readiness(REPO_ROOT, state)
        gate.assert_not_called()
        self.assertEqual(state["subtasks"][1]["status"], "ready")

    def test_frozen_candidate_keeps_full_gate_and_denies_failed_coverage(self):
        state = readiness_state({"status": "frozen", "candidate_id": "c1"})
        with patch.object(self.controller, "_current_acceptance_pass_errors",
                          return_value=["acceptance coverage incomplete"]) as gate:
            self.controller._refresh_subtask_readiness(REPO_ROOT, state)
        gate.assert_called_once_with(REPO_ROOT, state)
        self.assertEqual(state["subtasks"][3]["status"], "pending")
        self.assertEqual(state["subtasks"][1]["status"], "ready")

    def test_frozen_candidate_passes_only_after_full_gate_succeeds(self):
        state = readiness_state({"status": "frozen", "candidate_id": "c1"})
        with patch.object(self.controller, "_current_acceptance_pass_errors",
                          return_value=[]) as gate:
            self.controller._refresh_subtask_readiness(REPO_ROOT, state)
        gate.assert_called_once_with(REPO_ROOT, state)
        self.assertEqual(state["subtasks"][3]["status"], "ready")
        self.assertEqual(state["subtasks"][2]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
