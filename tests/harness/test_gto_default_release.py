"""Release integration must preserve revision 3's completion gates."""
from __future__ import annotations

import json
import importlib.util
import shutil
import subprocess
import sys
import unittest

import test_control_plane as legacy
import test_gto_workflow as workflow

SPEC = importlib.util.spec_from_file_location('convergence_release_controller', legacy.CONTROLLER)
ctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ctl)


class DefaultReleaseTest(unittest.TestCase):
    setUp = workflow.WorkflowTest.setUp
    tearDown = workflow.WorkflowTest.tearDown
    run_ctl = legacy.ControlPlaneContractTest.run_ctl
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state
    git = legacy.ControlPlaneContractTest.git
    init_git_checkout = legacy.ControlPlaneContractTest.init_git_checkout

    def test_revision_three_cannot_use_legacy_completion_waiver(self):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(workflow.workflow_contract())
        before = self.state()
        result = self.run_ctl(
            'reconcile-task-completion', approval_by='user',
            approval_reason='No separate final review is needed for revision 3.',
            result={'reconciliation': {
                'candidate_commit': self.git('rev-parse', 'HEAD').strip(),
                'acceptance_passed': True,
                'acceptance_evidence': ['Claimed acceptance without a candidate.'],
                'documents_synced': True,
                'closed_finding_ids': [],
                'final_review_waived': True,
            }}, ok=False,
        )
        self.assertIn('invalid choice', json.dumps(result))
        self.assertEqual(before, self.state())


def requirement_contract():
    """沿用已批准任务的 decisions 编号格式，不新增机器字段。"""
    payload = workflow.workflow_contract()
    payload['decisions'] = [value for value in payload['decisions'] if not value.startswith('REQ-')]
    payload['decisions'].extend([
        'REQ-01｜保留订单金额的精确小数｜落实：WORK-001｜验收：REAL-PATH-001',
        'REQ-02｜无效订单返回实际行号｜落实：WORK-001｜验收：REAL-PATH-001',
    ])
    next(t for t in payload['subtasks'] if t['subtask_id'] == 'WORK-001')['assignment']['must_include'] = [
        '落实 REQ-01、REQ-02。']
    return payload


def requirement_index(payload, ident):
    return next(i for i, value in enumerate(payload['decisions']) if value.startswith(ident + '｜'))


class ConvergenceArtifactTest(unittest.TestCase):
    setUp = workflow.WorkflowTest.setUp
    tearDown = workflow.WorkflowTest.tearDown
    run_ctl = legacy.ControlPlaneContractTest.run_ctl
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state

    def test_generated_plan_and_skill_use_compact_human_facing_layout(self):
        payload = requirement_contract()
        rendered = ctl._render_artifacts(legacy.TASK_ID, '订单合同', payload)
        plan = rendered['plan.md']
        skill = (legacy.REPO_ROOT / 'skills/global-task-orchestrator/SKILL.md').read_text(encoding='utf-8')

        for heading in ('## 施工摘要', '## 改造要点', '## 施工流程', '## 任务表'):
            self.assertEqual(1, plan.count(heading), heading)
        for stale in ('## 背景与问题', '## 风险与回退', '六要点'):
            self.assertNotIn(stale, plan)
        self.assertIn('| 编号 | 改造结果 | 责任 | 验收 |', plan)
        self.assertIn('| 步骤 | 责任 | 交付 | 前置条件 |', plan)
        self.assertIn('```mermaid', plan)
        self.assertLess(plan.index('| TEST-001 |'), plan.index('| WORK-001 |'))
        self.assertLess(plan.index('| WORK-001 |'), plan.index('| INTEGRATE-001 |'))
        self.assertLess(plan.index('| INTEGRATE-001 |'), plan.index('| REVIEW-SEC-001 |'))
        self.assertNotIn('六要点任务合同', rendered['execution.md'])

        self.assertNotIn('## 默认版本', skill)
        self.assertNotIn('## 控制器位置与消费项目', skill)
        self.assertIn('本 SKILL 所在包', skill)
        self.assertLess(len(skill.encode()), 6000)
        self.assertIn('references/controller-guide.md', skill)
        self.assertIn('消费项目用 `--repo-root`', skill)
        self.assertNotIn('新任务默认 workflow_revision', skill)
        self.assertIn('面向用户先说明变化', skill)
        plan_guide = (legacy.REPO_ROOT / 'skills/global-task-orchestrator/references/plan-guide.md').read_text(encoding='utf-8')
        self.assertIn('默认不展示内部 revision、工具绝对路径', plan_guide)

    def test_new_initialization_derives_mirrors_from_six_point_source(self):
        payload = requirement_contract()
        mirrors = {'objective': 'do', 'scope_in': 'change_areas', 'scope_out': 'do_not',
                   'acceptance': 'acceptance', 'stop_conditions': 'risks'}
        for field in mirrors:
            del payload[field]
        implementation = payload['six_points']['implementation']
        payload['decisions'].remove(implementation)
        requirements = payload['decisions'][:]
        self.init_task(payload)
        actual = self.state()
        for field, source in mirrors.items():
            self.assertEqual(payload['six_points'][source], actual[field])
        self.assertEqual(1, actual['decisions'].count(implementation))
        self.assertEqual(requirements, [value for value in actual['decisions'] if value != implementation])

    def test_new_initialization_rejects_missing_requirement_checklist(self):
        payload = workflow.workflow_contract()
        payload['decisions'] = [value for value in payload['decisions'] if not value.startswith('REQ-')]
        self.assertTrue(payload['decisions'], '保留普通实施说明，避免空列表前置遮挡')
        rejected = self.run_ctl('init-task', contract=payload, title='缺完整要求清单', owner='coordinator', ok=False)
        self.assertTrue(rejected['errors'])
        self.assertFalse((self.repo / f'docs/ai/tasks/{legacy.TASK_ID}').exists())

    def test_generated_execution_references_current_route_instead_of_original_implementer(self):
        self.init_task(workflow.workflow_contract())
        execution = (self.repo / f'docs/tasks/{legacy.TASK_ID}/execution.md').read_text()
        self.assertNotIn('原实现者修复', execution)
        self.assertIn('workflow.md', execution, '生成入口应引用流程唯一真源，而不是维护第二份返工定义')

    def test_requirement_bodies_have_one_generated_plan_view_and_other_views_reference_ids(self):
        self.init_task(requirement_contract())
        paths = ctl._task_paths(self.repo, legacy.TASK_ID)
        plan = paths['plan.md'].read_text()
        for ident, body in [('REQ-01', '保留订单金额的精确小数'), ('REQ-02', '无效订单返回实际行号')]:
            with self.subTest(requirement=ident):
                self.assertIn(ident, plan)
                self.assertEqual(1, plan.count(body))
                self.assertIn(ident, paths['execution.md'].read_text())
                for name in ('task.md', 'execution.md', 'acceptance.md'):
                    self.assertNotIn(body, paths[name].read_text())
        self.assertIn('WORK-001', plan)
        self.assertIn('REAL-PATH-001', plan)

    def test_requirement_owner_and_acceptance_references_cannot_dangle(self):
        for label, needle, replacement in [('owner', 'WORK-001', 'MISSING-WORK'),
                                            ('acceptance', 'REAL-PATH-001', 'MISSING-AC')]:
            with self.subTest(reference=label):
                payload = requirement_contract()
                payload['decisions'][requirement_index(payload, 'REQ-01')] = payload['decisions'][requirement_index(payload, 'REQ-01')].replace(needle, replacement)
                original_repo = self.repo
                self.repo = original_repo / label
                try:
                    self.repo.mkdir()
                    rejected = self.run_ctl('init-task', contract=payload, title='悬空要求关联',
                                            owner='coordinator', ok=False)
                    self.assertTrue(rejected['errors'])
                    self.assertFalse((self.repo / f'docs/ai/tasks/{legacy.TASK_ID}/state.json').exists())
                finally:
                    self.repo = original_repo

    def test_duplicate_requirement_ids_are_rejected_before_artifact_creation(self):
        payload = requirement_contract()
        payload['decisions'][requirement_index(payload, 'REQ-02')] = payload['decisions'][requirement_index(payload, 'REQ-02')].replace('REQ-02', 'REQ-01')
        self.run_ctl('init-task', contract=payload, title='重复要求编号', owner='coordinator', ok=False)
        self.assertFalse((self.repo / f'docs/ai/tasks/{legacy.TASK_ID}/state.json').exists())

    def test_requirement_change_invalidates_approval_fingerprint(self):
        payload = requirement_contract()
        original = ctl._contract_hash(payload)
        payload['decisions'][requirement_index(payload, 'REQ-01')] = payload['decisions'][requirement_index(payload, 'REQ-01')].replace('精确小数', '两位四舍五入小数')
        self.assertNotEqual(original, ctl._contract_hash(payload), '批准不能忽略完整要求清单的实质改变')

    def test_regenerated_plan_reflects_requirement_update_from_same_contract(self):
        payload = requirement_contract()
        old = ctl._render_artifacts(legacy.TASK_ID, '订单合同', payload)['plan.md']
        payload['decisions'][requirement_index(payload, 'REQ-02')] = payload['decisions'][requirement_index(payload, 'REQ-02')].replace('实际行号', '实际行号和客户编号')
        new = ctl._render_artifacts(legacy.TASK_ID, '订单合同', payload)['plan.md']
        self.assertNotEqual(old, new)
        self.assertIn('无效订单返回实际行号和客户编号', new)

    def test_skill_only_copy_initializes_consumer_without_repository_schema(self):
        source = legacy.REPO_ROOT / 'skills/global-task-orchestrator'
        installed = self.input_dir / 'installed/global-task-orchestrator'
        shutil.copytree(source, installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.assertFalse((installed.parents[1] / 'schemas').exists())
        contract_input = self.repo / '.tmp/revision-3-contract.example.json'
        contract_input.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / 'references/revision-3-contract.example.json', contract_input)
        completed = subprocess.run([
            sys.executable, '-B', str(installed / 'scripts/orchestrator_ctl.py'),
            '--action', 'init-task', '--repo-root', str(self.repo), '--task-id', legacy.TASK_ID,
            '--contract-json-file', str(contract_input),
            '--owner', 'coordinator', '--title', '独立安装消费项目', '--json'],
            cwd=self.input_dir, text=True, capture_output=True, timeout=30)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertTrue(json.loads(completed.stdout)['ok'])
        self.assertTrue((self.repo / f'docs/ai/tasks/{legacy.TASK_ID}/state.json').is_file())
        # The copied package must also resolve its new verification/causal modules
        # from an unrelated working directory when validating and resuming.
        for script, arguments in (
            ('orchestrator_ctl.py', ['--action', 'validate']),
            ('start_session.py', []),
        ):
            checked = subprocess.run([
                sys.executable, '-B', str(installed / 'scripts' / script), *arguments,
                '--repo-root', str(self.repo), '--task-id', legacy.TASK_ID, '--json'],
                cwd=self.input_dir, text=True, capture_output=True, timeout=45)
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            self.assertTrue(json.loads(checked.stdout)['ok'])
