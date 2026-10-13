"""Verification-evidence receipts preserve terminal acceptance history.

These tests use the public controller against a temporary consumer repository.
They do not edit a real task state or claim that fixture evidence is real product
acceptance.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path

import test_control_plane as legacy
import test_gto_workflow as workflow


GENERIC_KEY = "acceptance_output_index"
SECOND_KEY = "functional_surface_index"
EVIDENCE_REF = ".artifacts/acceptance-output.json"


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class VerificationEvidenceHarness(unittest.TestCase):
    setUp = workflow.WorkflowTest.setUp
    tearDown = workflow.WorkflowTest.tearDown
    run_ctl = legacy.ControlPlaneContractTest.run_ctl
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state
    write_state = legacy.ControlPlaneContractTest.write_state
    git = legacy.ControlPlaneContractTest.git
    init_git_checkout = legacy.ControlPlaneContractTest.init_git_checkout
    bind = workflow.WorkflowTest.bind
    work_result = workflow.WorkflowTest.work_result
    integrate = workflow.WorkflowTest.integrate
    review_payload = workflow.WorkflowTest.review_payload
    review = workflow.WorkflowTest.review
    published_result = workflow.WorkflowTest.published_result

    def contract(self, *keys: str) -> dict[str, object]:
        payload = workflow.workflow_contract()
        payload["verification_contract"]["review_evidence"] = [
            "pass_after_fix",
            *keys,
        ]
        return payload

    def write_evidence(self, relative: str = EVIDENCE_REF, text: str = "fixture evidence\n") -> Path:
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def start_acceptance(
        self,
        *,
        keys: tuple[str, ...] = (GENERIC_KEY,),
        evidence_ref: str = EVIDENCE_REF,
        closeout_document_paths: tuple[str, ...] = (),
    ):
        self.init_git_checkout("candidate-source.py", "candidate-config.json", "docs/contract.md")
        payload = self.contract(*keys)
        if closeout_document_paths:
            closeout = next(
                item
                for item in payload["subtasks"]
                if item.get("stage") == "final_documentation"
            )
            closeout["write_paths"] = [
                *closeout["write_paths"],
                *closeout_document_paths,
            ]
        self.init_task(payload)
        self.run_ctl("prepare-workspace")
        self.integrate()
        self.review()
        self.run_ctl("freeze-candidate")
        attempt = self.run_ctl(
            "create-subtask-attempt", subtask_id="EXPENSIVE-001"
        )
        state = self.state()
        self.assertEqual(
            state["acceptance_gate"]["current_candidate"]["runtime_snapshot"]["sha256"],
            next(item for item in state["acceptance_gate"]["attempts"]
                 if item["subtask_id"] == attempt["subtask_id"])["runtime_sha256"],
        )
        self.bind(attempt["subtask_id"], agent="accept-001", role="tester")
        self.write_evidence(evidence_ref)
        result = legacy.result(
            "completed",
            "accept-001",
            "tester",
            expensive_acceptance={
                "outcome": "pass",
                "real_call_count": 1,
                "duration_seconds": 1,
                "failed_stage": "none",
                "evidence_refs": [evidence_ref],
                "evidence_by_acceptance_id": {
                    "REAL-PATH-001": [evidence_ref]
                },
                "mode": "full",
                "scope_acceptance_ids": ["REAL-PATH-001"],
                "usage_evidence": workflow.usage("accept-001", "accept"),
            },
        )
        self.run_ctl(
            "record-subtask-result", subtask_id=attempt["subtask_id"], result=result
        )
        return attempt["subtask_id"]

    def source(self, subtask_id: str) -> dict[str, object]:
        return next(
            item for item in self.state()["subtasks"] if item["subtask_id"] == subtask_id
        )

    def receipt(
        self,
        source_subtask_id: str,
        *,
        evidence_key: str = GENERIC_KEY,
        evidence_refs: list[str] | None = None,
        written_by: str = "accept-001",
        written_role: str = "tester",
    ) -> dict[str, object]:
        state = self.state()
        source = next(
            item for item in state["subtasks"] if item["subtask_id"] == source_subtask_id
        )
        candidate = state["acceptance_gate"]["current_candidate"]
        return {
            "written_by": written_by,
            "written_role": written_role,
            "source_subtask_id": source_subtask_id,
            "source_result_sha256": canonical_sha256(source["result"]),
            "candidate_id": candidate["candidate_id"],
            "candidate_fingerprint": candidate["fingerprint"],
            "evidence_key": evidence_key,
            "evidence_refs": evidence_refs or [EVIDENCE_REF],
        }

    def record_receipt(self, value: dict[str, object], *, ok: bool = True):
        return self.run_ctl("record-verification-evidence", result=value, ok=ok)

    def public_call(self, action: str, **arguments: object):
        controller = Path(
            __import__("os").environ.get("GTO_CONTROLLER_UNDER_TEST", legacy.CONTROLLER)
        )
        command = [
            sys.executable,
            "-B",
            str(controller),
            "--action",
            action,
            "--repo-root",
            str(self.repo),
            "--task-id",
            legacy.TASK_ID,
            "--json",
        ]
        for name, value in arguments.items():
            if name == "result":
                self._json_input_index += 1
                path = self.input_dir / f"verification-input-{self._json_input_index}.json"
                path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                command.extend(["--result-json-file", str(path)])
            else:
                command.extend(["--" + name.replace("_", "-"), str(value)])
        completed = subprocess.run(
            command,
            cwd=self.input_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"ok": False, "errors": [completed.stderr or completed.stdout]}
        return completed, payload

    def six_artifacts(self) -> dict[str, bytes]:
        task = self.repo / "docs" / "ai" / "tasks" / legacy.TASK_ID
        contract = self.repo / "docs" / "tasks" / legacy.TASK_ID
        paths = [
            task / "state.json",
            task / "task.md",
            task / "events.jsonl",
            contract / "plan.md",
            contract / "execution.md",
            contract / "acceptance.md",
        ]
        return {str(path): path.read_bytes() for path in paths}

    def close(self):
        brief = self.repo / ".tmp" / "closeout-brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("Synchronize already accepted facts.\n", encoding="utf-8")
        self.run_ctl(
            "bind-dispatch",
            subtask_id="DOC-FINAL-001",
            agent_key="doc-curator",
            platform_agent_id="docs-001",
            context_mode="isolated",
            brief_kind="subtask",
            brief_path=".tmp/closeout-brief.md",
            brief_sha256=hashlib.sha256(brief.read_bytes()).hexdigest(),
        )
        self.run_ctl(
            "record-subtask-result",
            subtask_id="DOC-FINAL-001",
            result=legacy.result("completed", "docs-001", "doc-curator"),
        )


class VerificationEvidenceReceiptTest(VerificationEvidenceHarness):
    def test_original_acceptor_appends_only_a_reference_and_exact_replay_is_idempotent(self):
        source_id = self.start_acceptance()
        original_result = deepcopy(self.source(source_id)["result"])
        original_hash = canonical_sha256(original_result)
        receipt = self.receipt(source_id)

        self.record_receipt(receipt)
        after_first = self.six_artifacts()
        saved = self.state()
        self.assertEqual(original_result, self.source(source_id)["result"])
        self.assertEqual(original_hash, canonical_sha256(self.source(source_id)["result"]))
        self.assertEqual(
            [receipt],
            [
                {key: item[key] for key in receipt}
                for item in saved["verification_evidence_receipts"]
            ],
        )
        self.assertNotIn("outcome", saved["verification_evidence_receipts"][0])
        self.assertNotIn("summary", saved["verification_evidence_receipts"][0])

        replay = self.record_receipt(receipt)
        self.assertTrue(replay.get("already_recorded"))
        self.assertEqual(after_first, self.six_artifacts())

    def test_identity_hash_candidate_and_conflicting_duplicate_are_rejected_atomically(self):
        source_id = self.start_acceptance()
        valid = self.receipt(source_id)
        self.record_receipt(valid)

        cases = []
        wrong_identity = deepcopy(valid)
        wrong_identity["written_by"] = "different-acceptor"
        cases.append(("identity", wrong_identity))
        wrong_hash = deepcopy(valid)
        wrong_hash["source_result_sha256"] = "0" * 64
        cases.append(("hash", wrong_hash))
        wrong_candidate = deepcopy(valid)
        wrong_candidate["candidate_id"] = "candidate-stale"
        cases.append(("candidate", wrong_candidate))
        conflict = deepcopy(valid)
        conflict["evidence_refs"] = [".artifacts/different.json"]
        self.write_evidence(".artifacts/different.json")
        cases.append(("conflict", conflict))

        for label, value in cases:
            with self.subTest(label=label):
                before = self.six_artifacts()
                rejected = self.record_receipt(value, ok=False)
                self.assertIn(label, " ".join(rejected["errors"]).casefold())
                self.assertEqual(before, self.six_artifacts())

    def test_unregistered_missing_traversal_and_symlink_evidence_are_rejected_atomically(self):
        source_id = self.start_acceptance()
        self.write_evidence(".artifacts/not-in-source.json")
        cases = [
            ("registered", [".artifacts/not-in-source.json"]),
            ("path", ["../outside-verification-evidence.log"]),
        ]
        for label, refs in cases:
            with self.subTest(label=label):
                before = self.six_artifacts()
                rejected = self.record_receipt(
                    self.receipt(source_id, evidence_refs=refs), ok=False
                )
                self.assertRegex(" ".join(rejected["errors"]).casefold(), label)
                self.assertEqual(before, self.six_artifacts())

        (self.repo / EVIDENCE_REF).unlink()
        before = self.six_artifacts()
        missing = self.record_receipt(self.receipt(source_id), ok=False)
        self.assertRegex(" ".join(missing["errors"]).casefold(), "exist|missing")
        self.assertEqual(before, self.six_artifacts())

    def test_registered_symlink_cannot_escape_the_consumer_repository(self):
        link_ref = ".artifacts/escape.log"
        source_id = self.start_acceptance(evidence_ref=link_ref)
        link = self.repo / link_ref
        link.unlink()
        outside = self.repo.parent / "outside-verification-evidence.log"
        outside.write_text("outside\n", encoding="utf-8")
        link.symlink_to(outside)
        before = self.six_artifacts()
        rejected = self.record_receipt(
            self.receipt(source_id, evidence_refs=[link_ref]), ok=False
        )
        self.assertRegex(" ".join(rejected["errors"]).casefold(), "symlink|outside|path")
        self.assertEqual(before, self.six_artifacts())

    def test_receipt_stops_counting_if_its_terminal_source_changes(self):
        source_id = self.start_acceptance()
        self.record_receipt(self.receipt(source_id))
        state = self.state()
        source = next(item for item in state["subtasks"] if item["subtask_id"] == source_id)
        source["result"]["summary"] = "Tampered terminal result."
        self.write_state(state)

        before = self.six_artifacts()
        brief = self.repo / ".tmp" / "stale-closeout.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("Attempt close with stale evidence.\n", encoding="utf-8")
        rejected = self.run_ctl(
            "bind-dispatch",
            subtask_id="DOC-FINAL-001",
            agent_key="doc-curator",
            platform_agent_id="docs-001",
            context_mode="isolated",
            brief_kind="subtask",
            brief_path=".tmp/stale-closeout.md",
            brief_sha256=hashlib.sha256(brief.read_bytes()).hexdigest(),
            ok=False,
        )
        self.assertRegex(" ".join(rejected["errors"]).casefold(), "hash|evidence|stale")
        self.assertEqual(before, self.six_artifacts())

    def test_receipt_rejects_an_actual_executable_candidate_change(self):
        source_id = self.start_acceptance()
        (self.repo / "candidate-source.py").write_text(
            "executable behavior changed after acceptance\n", encoding="utf-8"
        )
        before = self.six_artifacts()
        rejected = self.record_receipt(self.receipt(source_id), ok=False)
        self.assertRegex(
            " ".join(rejected["errors"]).casefold(),
            "candidate|fingerprint|stale|coverage",
        )
        self.assertEqual(before, self.six_artifacts())

    def test_receipt_writer_must_match_both_dispatch_and_terminal_result_author(self):
        source_id = self.start_acceptance()
        state = self.state()
        source = next(item for item in state["subtasks"] if item["subtask_id"] == source_id)
        source["result"]["written_by"] = "different-result-author"
        self.write_state(state)
        receipt = self.receipt(source_id)
        before = self.six_artifacts()
        rejected = self.record_receipt(receipt, ok=False)
        self.assertRegex(
            " ".join(rejected["errors"]).casefold(),
            "writer|author|dispatch|identity|result",
        )
        self.assertEqual(before, self.six_artifacts())

    def test_blocked_task_accepts_valid_receipt_without_resuming_or_changing_next_action(self):
        source_id = self.start_acceptance()
        blocked = self.published_result("coordinator_blocked")
        self.run_ctl("set-phase", phase="blocked", result=blocked)
        before = self.state()

        self.record_receipt(self.receipt(source_id))
        after = self.state()
        self.assertEqual("blocked", after["status"])
        self.assertEqual("human_adjudication", after["next_action"]["kind"])
        self.assertEqual(before["coordinator_blocker"], after["coordinator_blocker"])


if __name__ == "__main__":
    unittest.main()
