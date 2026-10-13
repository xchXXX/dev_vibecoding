"""Deterministic contracts for the layered GTO black-box runner.

These tests never start Codex, a namespace, L5, L6, or a complete black-box task.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "gto_blackbox_runner", ROOT / "tests/benchmarks/gto_blackbox.py"
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
FIXTURE = ROOT / "tests/fixtures/gto-blackbox-methodology/l3-cross-project-restore"


class LayeredBlackboxContractTest(unittest.TestCase):
    maxDiff = None

    def card(self, level="L3", scenario_id="l3-cross-project-restore"):
        card = json.loads((FIXTURE / "scenario-card.json").read_text())
        card["level"] = level
        card["scenario_id"] = scenario_id
        return card

    @staticmethod
    def context(**overrides):
        context = {
            "task_id": "task-current",
            "candidate_fingerprint": "a" * 64,
            "formal_round": 2,
        }
        context.update(overrides)
        return context

    def approval(self, scenario_id="l6-endurance", **overrides):
        approval = {
            **self.context(),
            "scenario_id": scenario_id,
            "approved_by": "user",
            "approved_at": "2026-09-14T08:00:00+00:00",
        }
        approval.update(overrides)
        return approval

    def test_scenario_card_requires_portable_contract_and_known_level(self):
        validate = getattr(RUNNER, "validate_scenario_card", None)
        self.assertTrue(callable(validate), "runner must validate portable scenario cards")
        required = {
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
        card = self.card()
        self.assertEqual(required, set(card))
        self.assertEqual(card, validate(card))
        for level in ("L0", "L1", "L2", "L3", "L4", "L5", "L6"):
            with self.subTest(accepted_level=level):
                self.assertEqual(level, validate({**card, "level": level})["level"])
        for run_policy in (
            "preparation_only",
            "targeted_once",
            "conditional_once",
            "complete_once",
            "explicit_approval_once",
        ):
            with self.subTest(accepted_run_policy=run_policy):
                self.assertEqual(
                    run_policy,
                    validate({**card, "run_policy": run_policy})["run_policy"],
                )
        for field in sorted(required):
            with self.subTest(missing=field):
                incomplete = dict(card)
                incomplete.pop(field)
                with self.assertRaisesRegex(ValueError, field):
                    validate(incomplete)
        with self.assertRaisesRegex(ValueError, "level|L0|L6"):
            validate({**card, "level": "L7"})
        with self.assertRaisesRegex(ValueError, "run_policy|policy"):
            validate({**card, "run_policy": "targeted"})

    def test_simple_complete_blackbox_requires_all_seven_conditions(self):
        allowed = getattr(RUNNER, "simple_complete_blackbox_allowed", None)
        self.assertTrue(callable(allowed), "runner must enforce every low-cost eligibility condition")
        conditions = {
            "single_agent": True,
            "local_lightweight_dependencies": True,
            "fast_execution": True,
            "small_deterministic_data": True,
            "within_cost_budget": True,
            "cheaper_than_targeted_fixture": True,
            "no_duplicate_candidate_evidence": True,
        }
        self.assertTrue(allowed(conditions))
        for field in conditions:
            with self.subTest(rejected_condition=field):
                self.assertFalse(allowed({**conditions, field: False}))
        with self.assertRaisesRegex(ValueError, "single_agent"):
            allowed({key: value for key, value in conditions.items() if key != "single_agent"})

    def test_default_selector_excludes_l6_and_honors_task_prohibitions(self):
        select = getattr(RUNNER, "select_default_scenarios", None)
        self.assertTrue(callable(select), "runner must have a deterministic default selector")
        cards = [
            self.card("L1", "plan-response"),
            self.card("L5", "tiny-complete"),
            self.card("L6", "real-endurance"),
        ]
        self.assertEqual(
            ["plan-response", "tiny-complete"],
            [card["scenario_id"] for card in select(cards)],
        )
        self.assertEqual(
            ["plan-response"],
            [
                card["scenario_id"]
                for card in select(cards, prohibited_levels={"L5", "L6"})
            ],
        )

    def test_scenario_budget_and_ids_are_mechanically_enforced(self):
        validate = RUNNER.validate_scenario_card
        select = RUNNER.select_default_scenarios
        for invalid_budget in (
            {},
            {"max_attempts": 0},
            {"max_attempts": -1},
            {"max_attempts": "one"},
            {"": 1},
        ):
            with self.subTest(invalid_budget=invalid_budget):
                with self.assertRaisesRegex(ValueError, "budget|cost_budget"):
                    validate({**self.card(), "cost_budget": invalid_budget})

        duplicate = self.card("L2", "duplicate-id")
        with self.assertRaisesRegex(ValueError, "duplicate|scenario_id|unique"):
            select([duplicate, dict(duplicate)])

        for required_limit in ("max_seconds", "max_attempts", "max_scenarios"):
            with self.subTest(missing_required_limit=required_limit):
                budget = dict(self.card()["cost_budget"])
                budget.pop(required_limit)
                with self.assertRaisesRegex(ValueError, required_limit):
                    validate({**self.card(), "cost_budget": budget})

    def test_run_and_probe_enforce_max_seconds_and_stop_only_owned_process(self):
        wait_for_process = getattr(RUNNER, "wait_for_scenario_process", None)
        self.assertTrue(
            callable(wait_for_process),
            "runner needs one deterministic budgeted wait used by run and probe",
        )

        class TimedOutProcess:
            def __init__(self):
                self.wait_timeouts = []

            def wait(self, timeout=None):
                self.wait_timeouts.append(timeout)
                raise subprocess.TimeoutExpired("owned-scenario", timeout)

        for mode in ("run", "probe"):
            with self.subTest(mode=mode):
                process = TimedOutProcess()
                stopped = []

                def stop_owned(value):
                    stopped.append(value)
                    return {"reaped": True, "escalated": False}

                card = self.card("L2", f"budget-{mode}")
                card["cost_budget"]["max_seconds"] = 3
                result = wait_for_process(
                    process,
                    card,
                    mode=mode,
                    stop_owned=stop_owned,
                )
                self.assertEqual([3], process.wait_timeouts)
                self.assertEqual([process], stopped)
                self.assertTrue(result["timed_out"])
                self.assertEqual("cost_budget.max_seconds", result["stop_reason"])
                self.assertTrue(result["cleanup"]["reaped"])

        main_source = Path(RUNNER.__file__).read_text()
        main_body = main_source.split("def main():", 1)[1]
        self.assertIn(
            "wait_for_scenario_process(",
            main_body,
            "the real run/probe entry must not bypass the budgeted wait helper",
        )

    def test_result_records_accept_only_the_five_shared_classifications(self):
        build = getattr(RUNNER, "build_scenario_result", None)
        self.assertTrue(callable(build), "runner must write one shared result vocabulary")
        statuses = (
            "PASS",
            "EFFECT_FAIL",
            "PREPARATION_INVALID",
            "NOT_OBSERVED",
            "INCONCLUSIVE",
        )
        for status in statuses:
            with self.subTest(status=status):
                result = build(
                    self.card(), status=status, observed=status != "NOT_OBSERVED",
                    evidence=["evidence/result.json"],
                )
                self.assertEqual(status, result["status"])
                self.assertEqual("l3-cross-project-restore", result["scenario_id"])
                self.assertIn("observed", result)
                self.assertEqual(["evidence/result.json"], result["evidence"])
        for obsolete in ("blocked", "untriggered", "platform-static-pass"):
            with self.subTest(obsolete=obsolete):
                with self.assertRaisesRegex(ValueError, "status|classification"):
                    build(self.card(), status=obsolete, observed=False, evidence=[])

    def test_l6_approval_matches_current_context_and_is_consumed_once(self):
        consume = getattr(RUNNER, "consume_l6_approval", None)
        self.assertTrue(callable(consume), "runner must consume a current, one-run L6 approval")
        card = self.card("L6", "l6-endurance")
        context = self.context()
        consumed = set()
        token = consume(card, context, self.approval(), consumed)
        self.assertIn(token, consumed)
        with self.assertRaisesRegex(ValueError, "consum|used|once|single"):
            consume(card, context, self.approval(), consumed)

        mismatches = {
            "task_id": "another-task",
            "candidate_fingerprint": "b" * 64,
            "formal_round": 1,
            "scenario_id": "another-scenario",
            "approved_by": "coordinator",
            "approved_at": "",
        }
        for field, wrong in mismatches.items():
            with self.subTest(binding=field):
                with self.assertRaisesRegex(ValueError, field):
                    consume(card, context, self.approval(**{field: wrong}), set())
        for field in (
            "task_id", "candidate_fingerprint", "formal_round", "scenario_id",
            "approved_by", "approved_at",
        ):
            with self.subTest(missing_binding=field):
                incomplete = self.approval()
                incomplete.pop(field)
                with self.assertRaisesRegex(ValueError, field):
                    consume(card, context, incomplete, set())
        with self.assertRaisesRegex(ValueError, "approved_at"):
            consume(card, context, self.approval(approved_at="yesterday"), set())

    def test_l6_rejection_happens_before_any_launcher_side_effect(self):
        launch = getattr(RUNNER, "launch_scenario", None)
        self.assertTrue(callable(launch), "runner must gate L6 before invoking a launcher")
        launched = []

        def launcher(card):
            launched.append(card["scenario_id"])
            return "started"

        with self.assertRaisesRegex(ValueError, "task_id"):
            launch(
                self.card("L6", "l6-endurance"),
                self.context(),
                self.approval(task_id="historical-task"),
                set(),
                launcher,
            )
        self.assertEqual([], launched)
        self.assertEqual(
            "started",
            launch(self.card("L2", "preflight"), self.context(), None, set(), launcher),
        )
        self.assertEqual(["preflight"], launched)

    def test_l6_requires_explicit_approval_policy_before_launcher(self):
        launched = []

        def launcher(card):
            launched.append(card["scenario_id"])
            return "started"

        card = self.card("L6", "l6-endurance")
        card["run_policy"] = "targeted_once"
        with self.assertRaisesRegex(ValueError, "run_policy|explicit_approval_once"):
            RUNNER.launch_scenario(
                card,
                self.context(),
                self.approval(),
                set(),
                launcher,
            )
        self.assertEqual([], launched)

    def test_l6_launcher_requires_existing_attempt_event_carrier(self):
        launched = []
        card = self.card("L6", "l6-endurance")
        card["run_policy"] = "explicit_approval_once"
        with self.assertRaisesRegex(ValueError, "attempt_events_path|event"):
            RUNNER.launch_scenario(
                card,
                self.context(),
                json.loads(json.dumps(self.approval())),
                set(),
                lambda value: launched.append(value),
            )
        self.assertEqual([], launched)

    def test_l6_approval_consumption_survives_a_fresh_process_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt_events = Path(temporary) / "attempt-events.jsonl"
            context = self.context(attempt_events_path=str(attempt_events))
            card = self.card("L6", "l6-endurance")
            card["run_policy"] = "explicit_approval_once"
            approval = self.approval()
            RUNNER.launch_scenario(
                card, context, json.loads(json.dumps(approval)), set(), lambda _: "started"
            )
            self.assertTrue(
                attempt_events.is_file(),
                "a real L6 attempt must append its consumption to the existing attempt event evidence",
            )
            events = [json.loads(line) for line in attempt_events.read_text().splitlines()]
            self.assertEqual("approval_consumed", events[-1]["event"])
            self.assertEqual("l6-endurance", events[-1]["scenario_id"])

            fresh_spec = importlib.util.spec_from_file_location(
                "gto_blackbox_runner_fresh", ROOT / "tests/benchmarks/gto_blackbox.py"
            )
            fresh_runner = importlib.util.module_from_spec(fresh_spec)
            fresh_spec.loader.exec_module(fresh_runner)
            with self.assertRaisesRegex(ValueError, "consum|used|once|single"):
                fresh_runner.launch_scenario(
                    card,
                    context,
                    json.loads(json.dumps(approval)),
                    set(),
                    lambda _: "must-not-start",
                )

    def test_main_gates_l6_before_any_runner_side_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            isolated_root = Path(temporary)
            card_path = isolated_root / "l6-card.json"
            context_path = isolated_root / "context.json"
            card = self.card("L6", "l6-endurance")
            card["run_policy"] = "explicit_approval_once"
            card_path.write_text(json.dumps(card) + "\n")
            context_path.write_text(json.dumps(self.context()) + "\n")
            argv = [
                "gto_blackbox.py",
                "--mode", "run",
                "--scenario-card", str(card_path),
                "--current-context", str(context_path),
            ]
            with (
                mock.patch.object(RUNNER, "ROOT", isolated_root),
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    RUNNER,
                    "namespace_lifecycle_probe",
                    side_effect=AssertionError("namespace probe ran before the L6 gate"),
                ),
                mock.patch.object(
                    RUNNER.subprocess,
                    "Popen",
                    side_effect=AssertionError("Popen ran before the L6 gate"),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "approval|L6"):
                    RUNNER.main()
            self.assertFalse((isolated_root / ".artifacts").exists())
            self.assertFalse((isolated_root / ".tmp").exists())

    def test_main_does_not_consume_l6_approval_before_preparation_is_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            isolated_root = Path(temporary)
            attempt_events = isolated_root / "attempt-events.jsonl"
            card_path = isolated_root / "l6-card.json"
            context_path = isolated_root / "context.json"
            approval_path = isolated_root / "approval.json"
            card = self.card("L6", "l6-endurance")
            card["run_policy"] = "explicit_approval_once"
            card_path.write_text(json.dumps(card) + "\n")
            context_path.write_text(json.dumps(
                self.context(attempt_events_path=str(attempt_events))
            ) + "\n")
            approval_path.write_text(json.dumps(self.approval()) + "\n")
            argv = [
                "gto_blackbox.py", "--mode", "run",
                "--scenario-card", str(card_path),
                "--current-context", str(context_path),
                "--approval", str(approval_path),
            ]
            with (
                mock.patch.object(RUNNER, "ROOT", isolated_root),
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                with self.assertRaises(KeyError):
                    RUNNER.main()
            self.assertFalse(
                attempt_events.exists(),
                "a preparation failure before the business launcher must not consume approval",
            )

    def test_stage_fixture_is_hash_checked_before_an_atomic_copy(self):
        copy_fixture = getattr(RUNNER, "copy_validated_stage_fixture", None)
        self.assertTrue(callable(copy_fixture), "runner must validate and copy prebuilt stage fixtures")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "restored"
            result = copy_fixture(FIXTURE / "stage-fixture", destination)
            self.assertEqual(
                {
                    "business-root/request.txt",
                    "state-slice.json",
                    "tool-root/installed.marker",
                },
                set(result["files"]),
            )
            self.assertEqual("restore existing task\n", (destination / "business-root/request.txt").read_text())
            self.assertEqual("review", json.loads((destination / "state-slice.json").read_text())["current_phase"])

            tampered = Path(temporary) / "tampered"
            shutil.copytree(FIXTURE / "stage-fixture", tampered)
            (tampered / "state-slice.json").write_text('{"current_phase":"done"}\n')
            rejected_destination = Path(temporary) / "must-not-exist"
            with self.assertRaisesRegex(ValueError, "hash|manifest|fixture"):
                copy_fixture(tampered, rejected_destination)
            self.assertFalse(rejected_destination.exists(), "invalid fixture must leave no partial destination")

    def test_stage_fixture_rejects_hash_valid_but_invalid_state_structure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "invalid-structure"
            fixture.mkdir()
            state = fixture / "state-slice.json"
            state.write_text(json.dumps({
                "task_id": "fixture-existing-task",
                "current_phase": "not-a-real-phase",
                "tool_root": "../same-root",
                "business_root": "../same-root",
            }) + "\n")
            manifest = {
                "schema_version": 1,
                "files": {
                    "state-slice.json": hashlib.sha256(state.read_bytes()).hexdigest(),
                },
            }
            (fixture / "fixture-manifest.json").write_text(json.dumps(manifest) + "\n")
            destination = root / "must-not-exist"
            with self.assertRaisesRegex(ValueError, "structure|phase|root|fixture"):
                RUNNER.copy_validated_stage_fixture(fixture, destination)
            self.assertFalse(destination.exists())

    def test_stage_fixture_rejects_hash_valid_but_invalid_candidate_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "invalid-candidate"
            shutil.copytree(FIXTURE / "stage-fixture", fixture)
            marker = fixture / "tool-root/installed.marker"
            marker.write_text("global-task-orchestrator revision not-a-version\n")
            manifest_path = fixture / "fixture-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"]["tool-root/installed.marker"] = hashlib.sha256(
                marker.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest) + "\n")
            destination = root / "must-not-exist"
            with self.assertRaisesRegex(ValueError, "candidate|compatibility|marker|revision"):
                RUNNER.copy_validated_stage_fixture(fixture, destination)
            self.assertFalse(destination.exists())

    def test_access_evidence_separates_memory_sources_and_cfm_strictness(self):
        summarize = getattr(RUNNER, "summarize_access_evidence", None)
        self.assertTrue(callable(summarize), "runner must keep Memory and CFM evidence in separate accounts")
        accesses = [
            {"source": "MEMORY.md", "path": "/codex/memories/MEMORY.md"},
            {"source": "rollout_summaries", "path": "/codex/memories/rollout_summaries/r.jsonl"},
            {"source": "other_long_term_memory", "path": "/codex/memories/skills/gto/SKILL.md"},
            {"source": "CFM", "operation": "record-failure", "failure_chain_id": "failure-1", "failure_kind": "unexpected_failure"},
            {"source": "CFM", "operation": "query-before-retry", "failure_chain_id": "failure-1", "failure_kind": "unexpected_failure"},
            {"source": "CFM", "operation": "record-success", "failure_chain_id": "failure-1", "failure_kind": "unexpected_failure"},
        ]
        report = summarize(accesses)
        self.assertEqual(1, report["memory_md"]["access_count"])
        self.assertEqual(1, report["rollout_summaries"]["access_count"])
        self.assertEqual(1, report["other_long_term_memory"]["access_count"])
        self.assertEqual(3, report["cfm"]["access_count"])
        self.assertTrue(report["cfm"]["strict_failure_chain"])

        non_failure_use = accesses + [
            {"source": "CFM", "operation": "browse-unrelated-history", "failure_chain_id": ""}
        ]
        self.assertFalse(summarize(non_failure_use)["cfm"]["strict_failure_chain"])

    def test_access_report_has_four_state_observations_and_rejects_tdd_red_as_strict_cfm(self):
        empty = RUNNER.summarize_access_evidence([])
        for key in ("memory_md", "rollout_summaries", "other_long_term_memory", "cfm"):
            self.assertIn(
                empty[key].get("observation"),
                {"observed_read", "observed_not_read", "unknown", "not_applicable"},
            )

        expected_red_chain = [
            {
                "source": "CFM",
                "operation": operation,
                "failure_chain_id": "expected-red",
                "failure_kind": "expected_tdd_red",
            }
            for operation in ("record-failure", "query-before-retry", "record-success")
        ]
        self.assertFalse(
            RUNNER.summarize_access_evidence(expected_red_chain)["cfm"]["strict_failure_chain"]
        )

        unclassified_chain = [
            {
                "source": "CFM",
                "operation": operation,
                "failure_chain_id": "unclassified-failure",
            }
            for operation in ("record-failure", "query-before-retry", "record-success")
        ]
        self.assertEqual(
            "unknown",
            RUNNER.summarize_access_evidence(unclassified_chain)["cfm"]["strict_failure_chain"],
            "operation names alone do not prove a real unexpected command failure",
        )


if __name__ == "__main__":
    unittest.main()
