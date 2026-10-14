"""BBX-001 root-blocker CLI contracts; fixture receipts do not prove CFM execution."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
TASK_ID = "20300102-030405-example-task"


class CoordinatorBlockingTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".tmp/gto-workflow/blackbox"
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="coordinator-blocking-", dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name)
        self.repo = self.scratch / "consumer"
        self.repo.mkdir()
        self.input_dir = self.repo / ".tmp"
        self.input_dir.mkdir()
        self.sequence = 0
        self.artifacts = self.repo / "docs/ai/tasks" / TASK_ID
        contract = json.loads((ROOT / "skills/global-task-orchestrator/references/revision-3-contract.example.json").read_text())
        self.ctl("init-task", contract=contract, title="Coordinator blocker contract", owner="coordinator-001")
        self.original_phase = self.state()["current_phase"]

    def ctl(self, action, *, ok=True, **arguments):
        command = [sys.executable, "-B", str(CONTROLLER), "--action", action,
                   "--repo-root", str(self.repo), "--task-id", TASK_ID, "--json"]
        for name, value in arguments.items():
            if name in {"contract", "result"}:
                self.sequence += 1
                source = self.input_dir / f"input-{self.sequence}.json"
                source.write_text(json.dumps(value), encoding="utf-8")
                command.extend([f"--{name}-json-file", str(source)])
            else:
                command.extend(["--" + name.replace("_", "-"), str(value)])
        completed = subprocess.run(command, cwd=self.repo, text=True, capture_output=True,
                                   timeout=20, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual("", completed.stderr, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(ok, completed.returncode == 0, payload)
        self.assertEqual(ok, payload["ok"], payload)
        return payload

    def state(self):
        return json.loads((self.artifacts / "state.json").read_text())

    def events(self):
        return [json.loads(line) for line in (self.artifacts / "events.jsonl").read_text().splitlines()]

    def receipt(self, *, recovered=False):
        commands = (["project-env-doctor --project-root .", "command-failure-memory --action query-before-retry"]
                    if recovered else ["test -d required-cfm-store"])
        return {
            "status": "completed" if recovered else "blocked",
            "summary": "Fixture recovery and history query recorded." if recovered else "Required external CFM is inaccessible.",
            "changed_files": [], "planned_files_not_changed": [],
            "verification": {"commands": commands, "result": "Fixture checks succeeded; see recovery receipt." if recovered else "CFM directory check exited 1."},
            "deviations": [], "blocked_by": [] if recovered else ["Required external CFM is inaccessible."],
            "risks": [], "follow_up": [], "written_by": "coordinator-001", "written_role": "coordinator",
            "checks": [{"purpose": "regression", "command": command, "scope": ["docs/tasks/" + TASK_ID],
                        "exit_code": 0 if recovered else 1, "expected_exit_code": 0 if recovered else 1,
                        "evidence_refs": [".artifacts/recovery.log" if recovered else ".artifacts/cfm-blocked.log"]}
                       for command in commands],
        }

    def block(self):
        result = self.receipt()
        self.ctl("set-phase", phase="blocked", result=result)
        return result

    def test_block_receipt_is_saved_and_validation_and_fact_receipt_remain_available(self):
        receipt = self.block()
        state = self.state()
        self.assertEqual("blocked", state["status"])
        self.assertEqual("blocked", state["current_phase"])
        self.assertEqual({"previous_phase": self.original_phase, "result": receipt}, state["coordinator_blocker"])
        self.ctl("validate")
        execution = self.repo / "docs/tasks" / TASK_ID / "execution.md"
        execution.write_text(execution.read_text() + "\n已记录外部 CFM 不可达，未重试受阻链。\n")
        self.ctl("accept-artifact-update")
        self.ctl("validate")
        self.assertEqual("blocked", self.state()["status"])
        event = next(event for event in self.events() if event["event"] == "coordinator_blocked")
        self.assertEqual(receipt, event["result"])
        self.assertEqual(self.original_phase, event["previous_phase"])
        self.assertEqual("blocked", event["current_phase"])

    def test_blocked_task_rejects_dispatch_attempt_freeze_and_finalization(self):
        self.block()
        brief = self.repo / ".tmp/work-brief.md"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("Implement the approved example scope.\n")
        actions = [
            ("bind-dispatch", {"subtask_id": "WORK-001", "agent_key": "backend-implementer",
                               "platform_agent_id": "impl-001", "context_mode": "isolated",
                               "brief_kind": "subtask", "brief_path": ".tmp/work-brief.md",
                               "brief_sha256": hashlib.sha256(brief.read_bytes()).hexdigest()}),
            ("create-subtask-attempt", {"subtask_id": "ACCEPT-001"}),
            ("freeze-candidate", {}), ("finalize-task", {}),
        ]
        for action, arguments in actions:
            with self.subTest(action=action):
                before = (self.artifacts / "state.json").read_bytes()
                rejected = self.ctl(action, ok=False, **arguments)
                self.assertIn("block", json.dumps(rejected).lower(), rejected)
                self.assertEqual(before, (self.artifacts / "state.json").read_bytes())

    def test_explicit_resume_returns_only_to_original_phase_and_preserves_history(self):
        blocked_receipt = self.block()
        recovered = self.receipt(recovered=True)
        before = (self.artifacts / "state.json").read_bytes()
        self.ctl("set-phase", phase="review", result=recovered, ok=False)
        self.assertEqual(before, (self.artifacts / "state.json").read_bytes())
        self.ctl("set-phase", phase=self.original_phase, result=recovered)
        state = self.state()
        self.assertEqual("active", state["status"])
        self.assertEqual(self.original_phase, state["current_phase"])
        self.assertIsNone(state.get("coordinator_blocker"))
        self.ctl("validate")
        history = [event for event in self.events() if event["event"] in {"coordinator_blocked", "coordinator_resumed"}]
        self.assertEqual(["coordinator_blocked", "coordinator_resumed"], [event["event"] for event in history])
        self.assertEqual(blocked_receipt, history[0]["result"])
        self.assertEqual(recovered, history[1]["result"])
        self.assertEqual("blocked", history[1]["previous_phase"])
        self.assertEqual(self.original_phase, history[1]["current_phase"])

    def test_resume_requires_complete_successful_receipt_from_same_coordinator(self):
        self.block()
        invalid = [None]
        for patch in ({"verification": {"commands": [], "result": ""}},
                      {"checks": []}, {"blocked_by": ["CFM still unavailable"]},
                      {"written_by": "other-coordinator"}, {"written_role": "reviewer"}):
            receipt = self.receipt(recovered=True)
            receipt.update(patch)
            invalid.append(receipt)
        receipt = deepcopy(self.receipt(recovered=True))
        receipt["checks"][0]["exit_code"] = 1
        invalid.append(receipt)
        for index, receipt in enumerate(invalid):
            with self.subTest(receipt=index):
                before = (self.artifacts / "state.json").read_bytes()
                arguments = {} if receipt is None else {"result": receipt}
                self.ctl("set-phase", phase=self.original_phase, ok=False, **arguments)
                self.assertEqual(before, (self.artifacts / "state.json").read_bytes())

    def test_root_identity_can_block_and_resume_without_rewriting_real_author(self):
        """BBX-004: developer instructions and list_agents expose bare /root."""
        blocked = self.receipt()
        blocked["written_by"] = "/root"
        self.ctl("set-phase", phase="blocked", result=blocked)
        self.assertEqual("/root", self.state()["coordinator_blocker"]["result"]["written_by"])
        self.ctl("validate")
        recovered = self.receipt(recovered=True)
        recovered["written_by"] = "/root"
        self.ctl("set-phase", phase=self.original_phase, result=recovered)
        self.ctl("validate")
        self.assertEqual("active", self.state()["status"])
        self.assertEqual(self.original_phase, self.state()["current_phase"])
        history = [event for event in self.events()
                   if event["event"] in {"coordinator_blocked", "coordinator_resumed"}]
        self.assertEqual([blocked, recovered], [event["result"] for event in history])

    def test_preparation_recovery_preserves_attempt_budget_without_claiming_effect_round(self):
        """只验证已有准备阻塞恢复渠道；不冒充尚缺机器载荷的正式效果停止证明。"""
        before = deepcopy(self.state()['acceptance_gate'])
        blocked = self.receipt()
        blocked['summary'] = '投放候选与安装记录不一致，正式效果观察尚未开始。'
        blocked['blocked_by'] = ['准备检查：候选与安装记录不一致。']
        self.ctl('set-phase', phase='blocked', result=blocked)
        recovered = self.receipt(recovered=True)
        recovered['summary'] = '准备复查通过；只恢复可测试性，不声称正式首轮效果通过。'
        self.ctl('set-phase', phase=self.original_phase, result=recovered)
        self.assertEqual(before, self.state()['acceptance_gate'])
        self.assertEqual(self.original_phase, self.state()['current_phase'])
        history = [event for event in self.events()
                   if event['event'] in {'coordinator_blocked', 'coordinator_resumed'}]
        self.assertEqual([blocked, recovered], [event['result'] for event in history])

    def test_root_identity_schema_preserves_child_opaque_and_invalid_path_boundaries(self):
        schema = json.loads((ROOT / "skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json").read_text())
        accepted = ("/root", "/root/implementation", "/root/team/reviewer", "coordinator-001")
        rejected = ("../root", "/root/..", "/root//child", "/root/child/", "/tmp/root", "C:\\root", "/root/child/../other")
        for definition in ("writerIdentity", "platformAgentId"):
            validator = Draft202012Validator({"$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"})
            for identity in accepted + rejected:
                with self.subTest(definition=definition, identity=identity):
                    self.assertEqual(identity in accepted, validator.is_valid(identity))

        # Platform identities must not loosen logical owner/role identifiers.
        fields = {"owner": schema["properties"]["owner"],
                  "agent_key": schema["$defs"]["dispatch"]["properties"]["agent_key"]}
        for name, field in fields.items():
            with self.subTest(field=name):
                validator = Draft202012Validator({"$defs": schema["$defs"], **field})
                self.assertTrue(validator.is_valid("coordinator-001"))
                self.assertFalse(validator.is_valid("/root"))


if __name__ == "__main__":
    unittest.main()
