"""Regression contract for Plan presentation and pre-delivery write gates."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from test_gto_workflow import workflow_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = REPO_ROOT / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
TASK_ID = "20310102-030405-plan-preflight-contract"
CONTROL_FILES = (
    f"docs/ai/tasks/{TASK_ID}/state.json",
    f"docs/ai/tasks/{TASK_ID}/task.md",
    f"docs/ai/tasks/{TASK_ID}/events.jsonl",
    f"docs/tasks/{TASK_ID}/plan.md",
    f"docs/tasks/{TASK_ID}/execution.md",
    f"docs/tasks/{TASK_ID}/acceptance.md",
)


def load_controller():
    spec = importlib.util.spec_from_file_location("gto_plan_preflight_controller", CONTROLLER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load controller: {CONTROLLER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan_output_contract() -> dict[str, object]:
    return {
        "six_points": {
            "do": "修复订单预览错误。",
            "do_not": ["不改变支付流程。"],
            "change_areas": ["modules/orders", "tests/orders"],
            "implementation": "先同步契约和行为测试，再由整合者实现。",
            "acceptance": ["真实订单预览显示正确金额。"],
            "risks": ["保留现有未提交订单夹具。"],
        },
        "requirements": [
            {
                "id": "REQ-01",
                "requirement": "订单预览金额与已保存订单一致。",
                "owner": "T-TEST",
                "acceptance_ids": ["AC-01"],
            }
        ],
        "workflow": {
            "source": "skills/global-task-orchestrator/references/workflow.md",
            "rework_routes": {
                "review": {
                    "discoverer": "original_reviewer",
                    "fixer": "original_integrator",
                    "verifier": "original_reviewer",
                },
                "acceptance": {
                    "discoverer": "original_acceptance_owner",
                    "fixer": "original_integrator",
                    "verifier": "original_acceptance_owner",
                },
            },
        },
        "tasks": [
            {
                "id": "T-TEST",
                "phase": "test_sync",
                "owner": "independent_tester",
                "planned_agent_key": "A",
                "goal": "建立金额错误的预期 Red。",
                "dependencies": [],
                "inputs": ["订单契约与现有控制器入口"],
                "write_paths": ["tests/orders"],
                "done_when": ["最小测试以目标断言失败。"],
            }
        ],
    }


class PlanOutputContractTest(unittest.TestCase):
    def test_current_documentation_does_not_route_to_removed_usage_modes(self):
        historical_roots = (
            REPO_ROOT / 'docs/tasks',
            REPO_ROOT / 'docs/ai/tasks',
            REPO_ROOT / 'docs/ai/runs',
        )
        current_documents = [REPO_ROOT / 'README.md', REPO_ROOT / 'schemas/README.md']
        current_documents.extend(
            path for path in (REPO_ROOT / 'docs').rglob('*.md')
            if not any(path.is_relative_to(root) for root in historical_roots)
        )
        stale_references = [
            f'{path.relative_to(REPO_ROOT)}:{line_number}: {line}'
            for path in current_documents
            for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
            if re.search(r'\busage-modes\b', line)
        ]
        self.assertEqual([], stale_references,
                         'Current documentation must route to the existing Plan/workflow references')

    def test_plan_and_workflow_references_resolve_with_heading_anchors(self):
        references = CONTROLLER.parent.parent / 'references'
        self.assertFalse((references / 'usage-modes.md').exists())
        for name in ('plan-guide.md', 'workflow.md'):
            for target in re.findall(r'\]\(([^)]+)\)', (references / name).read_text()):
                path, _, anchor = target.partition('#')
                destination = references / path
                with self.subTest(source=name, target=target):
                    self.assertTrue(destination.is_file(), target)
                    if anchor:
                        headings = re.findall(r'^#{1,6} (.+)$', destination.read_text(), re.M)
                        anchors = [re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-') for heading in headings]
                        self.assertIn(anchor, anchors)

    def test_current_workflow_source_replaces_removed_entry(self):
        controller = load_controller()
        value = plan_output_contract()
        self.assertEqual([], controller.validate_plan_output_contract(value))
        value["workflow"]["source"] = "skills/global-task-orchestrator/references/usage-modes.md"
        self.assertIn("workflow_source", controller.validate_plan_output_contract(value))

    def test_semantic_contract_rejects_missing_source_and_each_rework_route(self):
        controller = load_controller()
        validator = getattr(controller, "validate_plan_output_contract", None)
        self.assertIsNotNone(
            validator,
            "controller must expose validate_plan_output_contract for the pre-approval Plan contract",
        )

        valid = plan_output_contract()
        self.assertEqual([], validator(valid))

        mutations = {
            "workflow_source": lambda value: value["workflow"].pop("source"),
            "review_rework_route": lambda value: value["workflow"]["rework_routes"].pop("review"),
            "acceptance_rework_route": lambda value: value["workflow"]["rework_routes"].pop("acceptance"),
        }
        for expected_error, mutate in mutations.items():
            with self.subTest(expected_error=expected_error):
                candidate = deepcopy(valid)
                mutate(candidate)
                self.assertIn(expected_error, validator(candidate))


class DeliveryWritePreflightCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = REPO_ROOT / ".tmp/gto-plan-preflight-tests"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.temp_root)
        self.repo = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()
        try:
            self.temp_root.rmdir()
        except OSError:
            pass

    def run_ctl(self, action: str, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = subprocess.run(
            [
                "python3",
                str(CONTROLLER),
                "--action",
                action,
                "--repo-root",
                str(self.repo),
                "--task-id",
                TASK_ID,
                "--json",
                *extra,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"ok": False, "errors": [completed.stderr or completed.stdout]}
        return completed, payload

    def write_contract(self, relative: str) -> Path:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(workflow_contract(), ensure_ascii=False), encoding="utf-8")
        return path

    def init_from(self, contract_file: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        return self.run_ctl(
            "init-task",
            "--title",
            "Plan preflight contract",
            "--owner",
            "main-coordinator",
            "--contract-json-file",
            str(contract_file),
        )

    def test_init_rejects_delivery_file_as_contract_input(self):
        forbidden_input = self.write_contract("requirements.txt")

        completed, payload = self.init_from(forbidden_input)

        self.assertNotEqual(0, completed.returncode, payload)
        self.assertFalse(payload.get("ok", True), payload)
        self.assertIn(".tmp", " ".join(payload.get("errors", [])))
        self.assertFalse((self.repo / CONTROL_FILES[0]).exists())

    def test_preflight_is_read_only_after_validated_control_plane(self):
        completed, payload = self.init_from(self.write_contract(".tmp/approved-contract.json"))
        self.assertEqual(0, completed.returncode, payload)
        completed, payload = self.run_ctl("set-phase", "--phase", "doc_sync")
        self.assertEqual(0, completed.returncode, payload)
        before = {
            relative: hashlib.sha256((self.repo / relative).read_bytes()).hexdigest()
            for relative in CONTROL_FILES
        }

        completed, payload = self.run_ctl("preflight")

        self.assertEqual(0, completed.returncode, payload)
        self.assertTrue(payload.get("ok"), payload)
        self.assertTrue(payload.get("ready_for_delivery_writes"), payload)
        after = {
            relative: hashlib.sha256((self.repo / relative).read_bytes()).hexdigest()
            for relative in CONTROL_FILES
        }
        self.assertEqual(before, after)

    def test_initialized_artifacts_route_to_current_references_and_resume_read_only(self):
        completed, payload = self.init_from(self.write_contract(".tmp/approved-contract.json"))
        self.assertEqual(0, completed.returncode, payload)
        before = {relative: (self.repo / relative).read_bytes() for relative in CONTROL_FILES}
        for name in ("plan.md", "execution.md"):
            value = (self.repo / f"docs/tasks/{TASK_ID}/{name}").read_text()
            self.assertIn("references/workflow.md", value)
            self.assertNotIn("usage-modes.md", value)
        completed, payload = self.run_ctl("validate")
        self.assertEqual(0, completed.returncode, payload)
        self.assertEqual(before, {relative: (self.repo / relative).read_bytes() for relative in CONTROL_FILES})


if __name__ == "__main__":
    unittest.main()
