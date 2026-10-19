"""End-to-end CLI gates for required verification evidence at acceptance/CLOSE."""
from __future__ import annotations

import hashlib
from copy import deepcopy

import test_control_plane as legacy
import test_gto_workflow as workflow
from test_gto_verification_evidence import (
    EVIDENCE_REF,
    GENERIC_KEY,
    SECOND_KEY,
    VerificationEvidenceHarness,
)


class VerificationEvidenceAcceptanceTest(VerificationEvidenceHarness):
    def other_template_contract(self):
        payload = self.contract(GENERIC_KEY)
        template = next(item for item in payload["subtasks"]
            if item.get("stage") == "expensive_acceptance")
        other = deepcopy(template)
        other["subtask_id"] = "EXPENSIVE-002"
        other["assignment"]["required_verification_evidence"] = {"ordinary": [GENERIC_KEY]}
        payload["subtasks"].append(other)
        return payload

    def test_review_rejects_direct_evidence_owned_by_another_template(self):
        self.begin(self.other_template_contract())
        attempt_id = self.create_attempt("ordinary")
        self.write_evidence()
        before = self.six_artifacts()
        completed, response = self.public_call(
            "record-subtask-result", subtask_id=attempt_id,
            result=self.acceptance_result(key=GENERIC_KEY),
        )
        self.assertNotEqual(0, completed.returncode,
            f"template accepted another template's key: {response}")
        self.assertFalse(response.get("ok"), response)
        self.assertEqual(before, self.six_artifacts())

    def test_review_rejects_receipt_owned_by_another_template(self):
        self.begin(self.other_template_contract())
        attempt_id = self.create_attempt("ordinary")
        self.write_evidence()
        self.run_ctl("record-subtask-result", subtask_id=attempt_id,
            result=self.acceptance_result())
        before = self.six_artifacts()
        completed, response = self.public_call(
            "record-verification-evidence", result=self.receipt(attempt_id),
        )
        self.assertNotEqual(0, completed.returncode,
            f"receipt accepted another template's key: {response}")
        self.assertFalse(response.get("ok"), response)
        self.assertEqual(before, self.six_artifacts())

    def test_review_rejects_direct_evidence_owned_by_another_attempt_kind(self):
        self.begin(self.assigned_contract(kind="blackbox", key=GENERIC_KEY))
        attempt_id = self.create_attempt("ordinary")
        self.write_evidence()
        before = self.six_artifacts()
        completed, response = self.public_call(
            "record-subtask-result", subtask_id=attempt_id,
            result=self.acceptance_result(key=GENERIC_KEY),
        )
        self.assertNotEqual(0, completed.returncode,
            f"ordinary accepted blackbox-owned key: {response}")
        self.assertFalse(response.get("ok"), response)
        self.assertEqual(before, self.six_artifacts())

    def test_review_rejects_receipt_owned_by_another_attempt_kind(self):
        self.begin(self.assigned_contract(kind="blackbox", key=GENERIC_KEY))
        attempt_id = self.create_attempt("ordinary")
        self.write_evidence()
        self.run_ctl("record-subtask-result", subtask_id=attempt_id,
            result=self.acceptance_result())
        before = self.six_artifacts()
        completed, response = self.public_call(
            "record-verification-evidence", result=self.receipt(attempt_id),
        )
        self.assertNotEqual(0, completed.returncode,
            f"ordinary receipt accepted blackbox-owned key: {response}")
        self.assertFalse(response.get("ok"), response)
        self.assertEqual(before, self.six_artifacts())

    def assigned_contract(self, *, kind: str, key: str) -> dict[str, object]:
        payload = self.contract(key)
        template = next(
            item
            for item in payload["subtasks"]
            if item.get("stage") == "expensive_acceptance"
        )
        template["assignment"]["required_verification_evidence"] = {kind: [key]}
        return payload

    def begin(self, payload: dict[str, object]):
        self.init_git_checkout("candidate-source.py", "candidate-config.json", "docs/contract.md")
        self.init_task(payload)
        self.run_ctl("prepare-workspace")
        self.integrate()
        self.review()
        self.run_ctl("freeze-candidate")

    def create_attempt(self, kind: str = "ordinary") -> str:
        arguments = {"subtask_id": "EXPENSIVE-001", "attempt_kind": kind}
        if len(self.state()["acceptance_gate"]["attempts"]) + 1 >= 3:
            arguments.update(
                approval_by="user",
                approval_reason="Fixture authorizes the bounded third deterministic attempt.",
            )
        completed, created = self.public_call("create-subtask-attempt", **arguments)
        self.assertEqual(0, completed.returncode, created)
        self.assertTrue(created.get("ok"), created)
        self.bind(created["subtask_id"], agent="accept-001", role="tester")
        return created["subtask_id"]

    def acceptance_result(
        self,
        *,
        kind: str = "ordinary",
        key: str | None = None,
        evidence_ref: str = EVIDENCE_REF,
    ) -> dict[str, object]:
        ids = [] if kind == "preparation" else ["REAL-PATH-001"]
        evidence = {
            "outcome": "pass",
            "real_call_count": 0,
            "duration_seconds": 1,
            "failed_stage": "none",
            "evidence_refs": [evidence_ref],
            "evidence_by_acceptance_id": {
                ident: [evidence_ref] for ident in ids
            },
            "mode": "full",
            "scope_acceptance_ids": ids,
            "usage_evidence": workflow.usage("accept-001", kind),
        }
        if kind == "preparation":
            evidence["preparation"] = {
                "checks": {
                    name: [f".artifacts/{name}.log"]
                    for name in (
                        "deployment",
                        "version",
                        "environment",
                        "input_and_session",
                        "evidence_capture",
                    )
                },
                "business_input_refs": ["candidate-config.json"],
            }
        result = legacy.result(
            "completed", "accept-001", "tester", expensive_acceptance=evidence
        )
        if key is not None:
            result["review_evidence"] = {key: evidence_ref}
        return result

    def test_assigned_key_missing_is_rejected_during_acceptance_without_any_write(self):
        self.begin(self.assigned_contract(kind="ordinary", key=GENERIC_KEY))
        attempt_id = self.create_attempt()
        self.write_evidence()
        before = self.six_artifacts()

        rejected = self.run_ctl(
            "record-subtask-result",
            subtask_id=attempt_id,
            result=self.acceptance_result(),
            ok=False,
        )
        self.assertRegex(" ".join(rejected["errors"]).casefold(), "verification|evidence|missing")
        self.assertEqual(before, self.six_artifacts())
        attempt = self.state()["acceptance_gate"]["attempts"][-1]
        self.assertNotIn("outcome", attempt)
        self.assertEqual("in_progress", self.source(attempt_id)["status"])

    def test_assigned_key_accepts_only_a_registered_existing_reference(self):
        self.begin(self.assigned_contract(kind="ordinary", key=GENERIC_KEY))
        attempt_id = self.create_attempt()
        self.write_evidence()
        self.run_ctl(
            "record-subtask-result",
            subtask_id=attempt_id,
            result=self.acceptance_result(key=GENERIC_KEY),
        )
        saved = self.source(attempt_id)["result"]
        self.assertEqual({GENERIC_KEY: EVIDENCE_REF}, saved["review_evidence"])
        self.assertNotIn("summary", saved["review_evidence"][GENERIC_KEY])

    def test_unassigned_extra_review_evidence_still_requires_a_contract_key_and_registered_ref(self):
        self.begin(self.contract(GENERIC_KEY))
        attempt_id = self.create_attempt()
        self.write_evidence()
        self.write_evidence(".artifacts/not-registered.json")
        invalid = [
            ("contract", {"undeclared_evidence_key": EVIDENCE_REF}),
            ("reference", {GENERIC_KEY: "Observed passing behavior in prose."}),
            ("registered", {GENERIC_KEY: ".artifacts/not-registered.json"}),
        ]
        for label, review_evidence in invalid:
            with self.subTest(label=label):
                result = self.acceptance_result()
                result["review_evidence"] = review_evidence
                before = self.six_artifacts()
                rejected = self.run_ctl(
                    "record-subtask-result",
                    subtask_id=attempt_id,
                    result=result,
                    ok=False,
                )
                self.assertRegex(
                    " ".join(rejected["errors"]).casefold(), label
                )
                self.assertEqual(before, self.six_artifacts())
                self.assertNotIn(
                    "outcome", self.state()["acceptance_gate"]["attempts"][-1]
                )

        self.run_ctl(
            "record-subtask-result",
            subtask_id=attempt_id,
            result=self.acceptance_result(key=GENERIC_KEY),
        )

    def test_blackbox_assignment_does_not_apply_to_preparation(self):
        payload = self.assigned_contract(kind="blackbox", key=GENERIC_KEY)
        payload["acceptance_gate"]["blackbox_acceptance_ids"] = ["REAL-PATH-001"]
        self.begin(payload)
        attempt_id = self.create_attempt("preparation")
        self.write_evidence()
        for name in (
            "deployment",
            "version",
            "environment",
            "input_and_session",
            "evidence_capture",
        ):
            self.write_evidence(f".artifacts/{name}.log")
        self.run_ctl(
            "record-subtask-result",
            subtask_id=attempt_id,
            result=self.acceptance_result(kind="preparation"),
        )
        self.assertEqual("pass", self.state()["acceptance_gate"]["attempts"][-1]["outcome"])

    def test_unassigned_evidence_key_blocks_closeout_until_original_author_receipt(self):
        source_id = self.start_acceptance()
        source_before = deepcopy(self.source(source_id)["result"])
        brief = self.repo / ".tmp" / "missing-evidence-closeout.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("Close only after verification evidence is complete.\n", encoding="utf-8")
        before = self.six_artifacts()
        rejected = self.run_ctl(
            "bind-dispatch",
            subtask_id="DOC-FINAL-001",
            agent_key="doc-curator",
            platform_agent_id="docs-001",
            context_mode="isolated",
            brief_kind="subtask",
            brief_path=".tmp/missing-evidence-closeout.md",
            brief_sha256=hashlib.sha256(brief.read_bytes()).hexdigest(),
            ok=False,
        )
        self.assertIn(GENERIC_KEY, " ".join(rejected["errors"]))
        self.assertEqual(before, self.six_artifacts())

        self.record_receipt(self.receipt(source_id))
        self.close()
        completed = self.run_ctl("finalize-task")
        self.assertEqual("completed", completed["status"])
        self.assertEqual(source_before, self.source(source_id)["result"])

    def test_receipt_accepts_the_approved_candidate_after_documentation_only_closeout(self):
        source_id = self.start_acceptance(
            keys=(), closeout_document_paths=("docs/contract.md",)
        )
        brief = self.repo / ".tmp" / "documentation-only-closeout.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("Synchronize wording without behavior changes.\n", encoding="utf-8")
        self.run_ctl(
            "bind-dispatch",
            subtask_id="DOC-FINAL-001",
            agent_key="doc-curator",
            platform_agent_id="docs-001",
            context_mode="isolated",
            brief_kind="subtask",
            brief_path=".tmp/documentation-only-closeout.md",
            brief_sha256=hashlib.sha256(brief.read_bytes()).hexdigest(),
        )
        document = self.repo / "docs" / "contract.md"
        document.write_text("Documentation wording after acceptance.\n", encoding="utf-8")
        closeout = legacy.result(
            "completed",
            "docs-001",
            "doc-curator",
            changed_files=["docs/contract.md"],
            documentation_sync={
                "changed_paths": ["docs/contract.md"],
                "checked_paths": ["docs/contract.md"],
                "reason": "Wording only; accepted behavior and configuration are unchanged.",
                "behavior_changed": False,
                "contract_changed": False,
                "configuration_changed": False,
            },
        )
        self.run_ctl(
            "record-subtask-result", subtask_id="DOC-FINAL-001", result=closeout
        )
        state = self.state()
        before_fingerprint = state["acceptance_gate"]["current_candidate"]["fingerprint"]
        after_fingerprint = state["acceptance_gate"]["documentation_sync"]["after_fingerprint"]
        self.assertNotEqual(before_fingerprint, after_fingerprint)

        # Reproduce a pre-feature terminal task whose contract required one more
        # index than its old controller knew how to collect.  Contract approval
        # is unchanged because the approved six points and REQ rows are unchanged.
        state["verification_contract"]["review_evidence"].append(GENERIC_KEY)
        self.write_state(state)
        source_before = deepcopy(self.source(source_id)["result"])
        self.record_receipt(self.receipt(source_id))
        self.assertEqual(source_before, self.source(source_id)["result"])
        self.assertEqual(
            before_fingerprint,
            self.state()["verification_evidence_receipts"][-1]["candidate_fingerprint"],
        )

    def test_two_generic_keys_from_ordinary_and_blackbox_sources_are_aggregated(self):
        payload = self.contract(GENERIC_KEY, SECOND_KEY)
        gate = payload["acceptance_gate"]
        blackbox_item = deepcopy(gate["acceptance_items"][0])
        blackbox_item["acceptance_id"] = "BBX-001"
        gate["acceptance_items"].append(blackbox_item)
        gate["blackbox_acceptance_ids"] = ["BBX-001"]
        template = next(
            item
            for item in payload["subtasks"]
            if item.get("stage") == "expensive_acceptance"
        )
        template["assignment"]["required_verification_evidence"] = {
            "ordinary": [GENERIC_KEY],
            "blackbox": [SECOND_KEY],
        }
        self.begin(payload)

        ordinary_id = self.create_attempt("ordinary")
        self.write_evidence(EVIDENCE_REF)
        ordinary = self.acceptance_result(key=GENERIC_KEY)
        self.run_ctl("record-subtask-result", subtask_id=ordinary_id, result=ordinary)

        preparation_id = self.create_attempt("preparation")
        for name in (
            "deployment",
            "version",
            "environment",
            "input_and_session",
            "evidence_capture",
        ):
            self.write_evidence(f".artifacts/{name}.log")
        self.run_ctl(
            "record-subtask-result",
            subtask_id=preparation_id,
            result=self.acceptance_result(kind="preparation"),
        )

        blackbox_ref = ".artifacts/blackbox-output.json"
        self.write_evidence(blackbox_ref)
        blackbox_id = self.create_attempt("blackbox")
        blackbox = self.acceptance_result(
            kind="ordinary", key=SECOND_KEY, evidence_ref=blackbox_ref
        )
        blackbox["expensive_acceptance"]["scope_acceptance_ids"] = ["BBX-001"]
        blackbox["expensive_acceptance"]["evidence_by_acceptance_id"] = {
            "BBX-001": [blackbox_ref]
        }
        blackbox["expensive_acceptance"]["blackbox"] = {
            "session_ids": ["fixture-session"],
            "input_refs": ["candidate-config.json"],
            "trace_refs": [blackbox_ref],
            "report_ref": ".artifacts/blackbox-report.md",
        }
        self.run_ctl("record-subtask-result", subtask_id=blackbox_id, result=blackbox)

        self.close()
        self.assertEqual("completed", self.run_ctl("finalize-task")["status"])


if __name__ == "__main__":
    import unittest

    unittest.main()
