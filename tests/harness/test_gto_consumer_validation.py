"""BBX-003: public document validators must accept ordinary consumer roots."""
from __future__ import annotations

import json
import hashlib
import shutil
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_control_plane as legacy
import test_gto_workflow as workflow


ROOT = Path(__file__).resolve().parents[2]
VALIDATORS = ("validate_plan_docs.py", "validate_doc_routing.py")
TASK_DOCUMENTS = {
    "plan.md": """# 订单预览方案
## 任务目标
新增订单退款预览。
## 背景与问题
现有工具只支持报价。
## 范围
订单领域与命令入口。
## 非目标
不执行实际支付。
## 约束与依赖
只使用 Python 标准库。
## 方案摘要
按行计算整数退款金额。
## 风险与回退
报价回归时恢复原入口。
## 验收标准
部分退款返回精确整数金额。
## 阶段划分
同步契约、实现、审查、验收。
## 需先同步的核心文档与测试
更新退款契约并补部分退款入口测试。
""",
    "execution.md": """# 订单预览施工
## 施工目标
交付退款预览命令。
## 前置条件
已批准业务范围。
## 执行顺序
先测试再实现，随后审查和验收。
## 文档先行清单
同步退款输入与输出契约。
## 测试同步清单
补充部分退款与非法数量测试。
## 实施批次
订单领域和命令入口作为一个批次。
## 每批写入范围
订单代码、测试和业务文档。
## 验证命令
python3 -m unittest discover -s tests
## 回退方案
恢复原报价入口。
## 审查与返工路径
独立审查发现问题后由原实现者修复并复审。
""",
    "acceptance.md": """# 订单预览验收
## 验收目标
确认退款预览与报价兼容。
## 验收标准
输入合法时返回精确金额，非法数量被拒绝。
## 必备证据
保存真实命令退出状态与测试结果。
## 未决项
业务验收尚未执行。
## 最终结论
当前仅完成方案，等待实施与独立验收。
""",
}


class ConsumerDocumentValidationTest(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / ".tmp/gto-workflow/blackbox"
        temporary_root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="consumer-validation-", dir=temporary_root)
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name)
        self.consumer = self.scratch / "consumer"
        task = self.consumer / "docs/tasks/refund-preview"
        task.mkdir(parents=True)
        for name, content in TASK_DOCUMENTS.items():
            (task / name).write_text(content, encoding="utf-8")

    def invoke(self, script: str, consumer: Path):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script),
             "--repo-root", str(consumer), "--json"],
            cwd=self.scratch, text=True, capture_output=True, timeout=20,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual("", result.stderr, result.stderr)
        return result, json.loads(result.stdout)

    def assert_consumer_accepted(self, script: str):
        self.assertEqual(["docs"], sorted(path.name for path in self.consumer.iterdir()))
        self.assertFalse((self.consumer / "rules/registry/RULES_ENTRY.md").exists())
        result, payload = self.invoke(script, self.consumer)
        self.assertEqual(0, result.returncode, payload)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(str(self.consumer.resolve()), payload["repo_root"])
        self.assertEqual(1, payload["checked_task_count"])
        self.assertEqual([], payload["errors"])

    def test_plan_cli_accepts_valid_consumer_without_harness_markers(self):
        self.assert_consumer_accepted("validate_plan_docs.py")

    def test_routing_cli_accepts_valid_consumer_without_harness_markers(self):
        self.assert_consumer_accepted("validate_doc_routing.py")

    def test_document_clis_reject_nonexistent_root(self):
        for script in VALIDATORS:
            with self.subTest(script=script):
                result, payload = self.invoke(script, self.scratch / "missing")
                self.assertNotEqual(0, result.returncode, payload)
                self.assertFalse(payload["ok"], payload)
                self.assertTrue(payload["errors"], payload)

    def test_document_clis_reject_file_as_root(self):
        file_root = self.scratch / "file-root"
        file_root.write_text("This is a file, not a project directory.\n", encoding="utf-8")
        for script in VALIDATORS:
            with self.subTest(script=script):
                result, payload = self.invoke(script, file_root)
                self.assertNotEqual(0, result.returncode, payload)
                self.assertFalse(payload["ok"], payload)
                self.assertTrue(payload["errors"], payload)


class ConvergenceResumeTest(unittest.TestCase):
    setUp = workflow.WorkflowTest.setUp
    tearDown = workflow.WorkflowTest.tearDown
    run_ctl = legacy.ControlPlaneContractTest.run_ctl
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state

    def test_frozen_legacy_state_without_requirements_resumes_without_migration(self):
        fixture = ROOT / 'tests/harness/fixtures/harness-minimal-convergence/legacy-no-requirements'
        provenance = json.loads((fixture / 'provenance.json').read_text())
        for relative, digest in provenance['artifacts'].items():
            self.assertEqual(digest, hashlib.sha256((fixture / relative).read_bytes()).hexdigest())
        shutil.copytree(fixture / 'docs', self.repo / 'docs')
        before = {p.relative_to(self.repo).as_posix(): p.read_bytes()
                  for p in self.repo.rglob('*') if p.is_file() and p.name != '.control.lock'}
        self.assertFalse(any(value.startswith('REQ-') for value in self.state()['decisions']))
        self.assertEqual('doc_sync', self.state()['current_phase'])
        # Public controller read entry: no init, migration, or writable phase transition.
        validated = self.run_ctl('validate')
        self.assertTrue(validated['ok'], validated)
        after = {p.relative_to(self.repo).as_posix(): p.read_bytes()
                 for p in self.repo.rglob('*') if p.is_file() and p.name != '.control.lock'}
        self.assertEqual(before, after, '历史活动任务不能因新清单合同被隐式迁移')

    def test_phase_io_failure_preserves_previous_six_artifacts_and_is_diagnosable(self):
        # Synthetic projects only; inject one actual write failure, retaining model gates and real I/O.
        original_repo = self.repo
        for fault in ('state_replace', 'event_append'):
            with self.subTest(fault=fault):
                self.repo = original_repo / fault
                self.repo.mkdir()
                self.init_task(workflow.workflow_contract())
                artifacts = [p for p in self.repo.rglob('*') if p.is_file() and p.name != '.control.lock']
                self.assertEqual(6, len(artifacts))
                before = {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in artifacts}
                script = self.input_dir / f'inject-{fault}.py'
                script.write_text("""import importlib.util, os, sys
from pathlib import Path
controller, fault = sys.argv[1:3]
sys.argv = [controller] + sys.argv[3:]
spec = importlib.util.spec_from_file_location('fault_controller', controller)
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
original_replace, original_open = os.replace, Path.open
fired = False
def replace(source, destination, *args, **kwargs):
    global fired
    if not fired and fault == 'state_replace' and Path(destination).name == 'state.json':
        fired = True
        raise OSError('T1 injected state_replace')
    return original_replace(source, destination, *args, **kwargs)
def opened(path, mode='r', *args, **kwargs):
    global fired
    if not fired and fault == 'event_append' and path.name == 'events.jsonl' and 'a' in mode:
        fired = True
        raise OSError('T1 injected event_append')
    return original_open(path, mode, *args, **kwargs)
os.replace, Path.open = replace, opened
code = ctl.main()
assert fired, 'injection target was not reached'
raise SystemExit(code)
""")
                completed = subprocess.run([sys.executable, '-B', str(script), str(legacy.CONTROLLER), fault,
                    '--action', 'set-phase', '--repo-root', str(self.repo), '--task-id', legacy.TASK_ID,
                    '--phase', 'doc_sync', '--json'], text=True, capture_output=True, timeout=30)
                self.assertNotEqual(0, completed.returncode)
                response = json.loads(completed.stdout)
                self.assertIn('T1 injected ' + fault, str(response), '必须命中指定持久化位置且保留诊断')
                after = {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in artifacts}
                with self.subTest(boundary='previous_facts'):
                    self.assertEqual(before, after, '失败命令不能把六工件拆成新旧两组事实')
                with self.subTest(boundary='readable_after_failure'):
                    self.run_ctl('validate')
        self.repo = original_repo

    def test_validate_reports_actual_phase_after_document_transition(self):
        self.init_task(workflow.workflow_contract())
        self.run_ctl('set-phase', phase='doc_sync')
        validated = self.run_ctl('validate')
        self.assertEqual('doc_sync', validated.get('current_phase'), validated)

    def test_resume_from_other_cwd_separates_consumer_root_from_tool_root(self):
        self.init_task(workflow.workflow_contract())
        self.run_ctl('set-phase', phase='doc_sync')
        artifact_paths = [p for p in self.repo.rglob('*') if p.is_file() and p.name != '.control.lock']
        before = {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in artifact_paths}
        self.assertFalse((self.repo / 'skills').exists())
        self.assertFalse((self.repo / 'rules').exists())
        packaged_entry = ROOT / 'skills/global-task-orchestrator/scripts/start_session.py'
        entry = packaged_entry
        completed = subprocess.run([sys.executable, '-B', str(entry), '--repo-root', str(self.repo),
                                    '--task-id', legacy.TASK_ID, '--json'],
                                   cwd=self.input_dir, text=True, capture_output=True, timeout=30)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload['ok'], payload)
        self.assertEqual('doc_sync', payload['current_phase'])
        self.assertEqual(legacy.TASK_ID, payload['task_id'])
        after = {p.relative_to(self.repo).as_posix(): p.read_bytes()
                 for p in self.repo.rglob('*') if p.is_file() and p.name != '.control.lock'}
        self.assertEqual(before, after, '恢复不重建任务，也不改写已有合同/事件')


if __name__ == "__main__":
    unittest.main()
