"""独立行为合同：初始测试作者、写入隔离和原整合者返工路由。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_control_plane as base
import test_gto_workflow as workflow

spec = importlib.util.spec_from_file_location('initial_routing_controller', base.CONTROLLER)
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)


def initial_contract(count=2):
    payload = deepcopy(base.expensive_acceptance_contract())
    payload['workflow_revision'] = 3
    payload.pop('initial_test_owner', None)
    payload['initial_test_owners'] = [f'TEST-{i:03}' for i in range(1, count + 1)]
    payload['verification_contract']['review_evidence'] = ['pass_after_fix']
    inputs = payload['acceptance_gate']['candidate_inputs']
    inputs.update(code_paths=['candidate-source.py', 'tests'], document_paths=['docs/contract.md'])
    stages = [
        *((ident, 'tester', 'work', [], [f'tests/test_{i}.py'])
          for i, ident in enumerate(payload['initial_test_owners'], 1)),
        ('WORK-001', 'backend-implementer', 'work', payload['initial_test_owners'][:], ['candidate-source.py']),
        ('INTEGRATE-001', 'backend-implementer', 'integration', ['WORK-001'], ['candidate-source.py', 'docs/contract.md']),
        ('REVIEW-001', 'reviewer', 'pre_acceptance_review', ['INTEGRATE-001'], []),
        ('ACCEPT-001', 'tester', 'expensive_acceptance', ['REVIEW-001'], []),
        ('DOC-001', 'doc-curator', 'final_documentation', ['ACCEPT-001'], [f'docs/tasks/{base.TASK_ID}']),
    ]
    payload['subtasks'] = [dict(subtask_id=ident, title=ident, role=role, stage=stage,
        planned_agent_key=ident.lower() if ident.startswith('TEST-') else ('integrator' if stage == 'integration' else role),
        status='ready', dependencies=deps, read_paths=['docs/contract.md'], write_paths=writes,
        assignment=base.assignment('按独立职责完成真实证明。'))
        for ident, role, stage, deps, writes in stages]
    workflow.add_requirement_checklist(payload, 'WORK-001')
    return payload


def check(purpose):
    exit_code = 1 if purpose == 'red' else 0
    return dict(purpose=purpose, command='python3 -m unittest tests.test_boundary',
                scope=['tests/test_1.py'], exit_code=exit_code, expected_exit_code=exit_code,
                evidence_refs=[f'.artifacts/{purpose}.log'])


class InitialTestRoutingTest(unittest.TestCase):
    run_ctl = base.ControlPlaneContractTest.run_ctl
    init_task = base.ControlPlaneContractTest.init_task
    state = base.ControlPlaneContractTest.state
    git = base.ControlPlaneContractTest.git
    init_git_checkout = base.ControlPlaneContractTest.init_git_checkout

    def setUp(self):
        root = base.REPO_ROOT / '.tmp/review-acceptance-routing/test-a'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.input_temp = tempfile.TemporaryDirectory(dir=root)
        self.repo, self.input_dir = Path(self.temp.name), Path(self.input_temp.name)
        self._json_input_index = 0

    def tearDown(self):
        self.input_temp.cleanup()
        self.temp.cleanup()

    def start(self, count=2):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(initial_contract(count))
        self.run_ctl('prepare-workspace')

    def planned_key(self, ident):
        return next(t['planned_agent_key'] for t in self.state()['subtasks'] if t['subtask_id'] == ident)

    def bind(self, ident, agent, role=None, ok=True):
        role = role or self.planned_key(ident)
        path = self.repo / '.tmp' / f'{ident}-brief.md'
        path.parent.mkdir(exist_ok=True)
        path.write_text(f'独立执行合同 {ident}\n')
        return self.run_ctl('bind-dispatch', subtask_id=ident, agent_key=role,
            platform_agent_id=agent, context_mode='isolated', brief_kind='subtask',
            brief_path=path.relative_to(self.repo).as_posix(),
            brief_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ok=ok)

    def complete_testers(self, count=2):
        for i in range(1, count + 1):
            ident, agent = f'TEST-{i:03}', f'test-agent-{i}'
            self.bind(ident, agent)
            result = base.result('completed', agent, self.planned_key(ident), checks=[check('red')])
            result['verification'] = {'commands': [check('red')['command']],
                                      'result': '预期失败已复现，测试作者不实施产品 Green。'}
            self.run_ctl('record-subtask-result', subtask_id=ident, result=result)

    def complete_work(self):
        self.bind('WORK-001', 'work-agent', 'backend-implementer')
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=base.result(
            'completed', 'work-agent', 'backend-implementer',
            checks=[check(p) for p in ('red', 'green', 'regression')],
            review_evidence={'pass_after_fix': '.artifacts/green.log'}))

    def test_one_independent_initial_tester_initializes(self):
        self.init_task(initial_contract(1))
        self.assertEqual(['TEST-001'], self.state()['initial_test_owners'])

    def test_multiple_independent_testers_complete_with_red_only(self):
        self.start()
        self.complete_testers()
        testers = [t for t in self.state()['subtasks'] if t['subtask_id'].startswith('TEST-')]
        self.assertEqual(2, len({t['dispatch']['platform_agent_id'] for t in testers}))
        self.assertTrue(all(t['status'] == 'completed' for t in testers))
        self.assertTrue(all([c['purpose'] for c in t['result']['checks']] == ['red'] for t in testers))

    def test_implementation_waits_for_every_initial_tester(self):
        self.start()
        self.complete_testers(1)
        rejected = self.bind('WORK-001', 'work-agent', 'backend-implementer', ok=False)
        self.assertIn('TEST-002', str(rejected))
        self.bind('TEST-002', 'test-agent-2')
        self.run_ctl('record-subtask-result', subtask_id='TEST-002',
                     result=base.result('completed', 'test-agent-2', self.planned_key('TEST-002'), checks=[check('red')]))
        self.bind('WORK-001', 'work-agent', 'backend-implementer')

    def test_initial_tester_cannot_be_implementation_identity(self):
        self.start(1)
        self.complete_testers(1)
        rejected = self.bind('WORK-001', 'test-agent-1', 'backend-implementer', ok=False)
        self.assertRegex(str(rejected).lower(), 'independen|initial.test|tester')

    def start_serial_testers(self):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        payload = initial_contract(2)
        payload['subtasks'][1]['dependencies'] = ['TEST-001']
        payload['subtasks'][1]['planned_agent_key'] = payload['subtasks'][0]['planned_agent_key']
        self.init_task(payload)
        self.run_ctl('prepare-workspace')

    def test_serial_initial_test_tasks_reuse_same_identity_after_dependency_completion(self):
        self.start_serial_testers()
        self.bind('TEST-001', 'same-test-agent')
        self.run_ctl('record-subtask-result', subtask_id='TEST-001', result=base.result(
            'completed', 'same-test-agent', self.planned_key('TEST-001'), checks=[check('red')]))
        self.bind('TEST-002', 'same-test-agent')
        tasks = {task['subtask_id']: task for task in self.state()['subtasks']}
        self.assertEqual('completed', tasks['TEST-001']['status'])
        self.assertEqual('in_progress', tasks['TEST-002']['status'])
        self.assertEqual(tasks['TEST-001']['dispatch']['platform_agent_id'],
                         tasks['TEST-002']['dispatch']['platform_agent_id'])

    def test_serial_initial_test_task_waits_for_unfinished_test_predecessor(self):
        self.start_serial_testers()
        self.bind('TEST-001', 'same-test-agent')
        before = self.state()
        for identity in ('same-test-agent', 'different-test-agent'):
            with self.subTest(identity=identity):
                rejected = self.bind('TEST-002', identity, ok=False)
                self.assertIn('dependencies are not completed', str(rejected))
                self.assertIn('TEST-001', str(rejected))
                self.assertEqual(before, self.state())

    def test_result_author_must_match_initial_tester_dispatch(self):
        self.start(1)
        self.bind('TEST-001', 'test-agent-1')
        rejected = self.run_ctl('record-subtask-result', subtask_id='TEST-001',
            result=base.result('completed', 'other-test-agent', self.planned_key('TEST-001'), checks=[check('red')]), ok=False)
        self.assertIn('writer', str(rejected))

    def test_integration_waits_for_work_and_preserves_original_identity(self):
        self.start(1)
        self.complete_testers(1)
        rejected = self.bind('INTEGRATE-001', 'integration-agent', 'integrator', ok=False)
        self.assertRegex(str(rejected), 'WORK-001|work')
        self.complete_work()
        self.bind('INTEGRATE-001', 'integration-agent', 'integrator')
        self.run_ctl('record-subtask-result', subtask_id='INTEGRATE-001', result=base.result(
            'completed', 'integration-agent', 'integrator', checks=[check('regression')],
            integration={'summary': '完成入口接口配置异常和文档整合。', 'document_paths': ['docs/contract.md']}))
        successor = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')['subtask_id']
        rejected = self.bind(successor, 'work-agent', 'integrator', ok=False)
        self.assertRegex(str(rejected), 'integration owner|planned agent|platform identity')
        self.bind(successor, 'integration-agent', 'integrator')

    def test_duplicate_initial_result_does_not_advance_state_or_append_success(self):
        self.start(1)
        self.bind('TEST-001', 'test-agent-1')
        receipt = base.result('completed', 'test-agent-1', self.planned_key('TEST-001'), checks=[check('red')])
        self.run_ctl('record-subtask-result', subtask_id='TEST-001', result=receipt)
        paths = ctl._task_paths(self.repo, base.TASK_ID)
        before = {name: paths[name].read_bytes() for name in ('state.json', 'task.md', 'events.jsonl')}
        input_file = self.input_dir / 'duplicate-result.json'
        input_file.write_text(json.dumps(receipt), encoding='utf-8')
        repeated = subprocess.run([sys.executable, '-B', str(base.CONTROLLER),
            '--action', 'record-subtask-result', '--repo-root', str(self.repo), '--task-id', base.TASK_ID,
            '--subtask-id', 'TEST-001', '--result-json-file', str(input_file), '--json'],
            text=True, capture_output=True, timeout=20)
        response = json.loads(repeated.stdout)
        self.assertIn(repeated.returncode, (0, 2), repeated.stderr)
        self.assertEqual(repeated.returncode == 0, response['ok'])
        self.assertEqual(before, {name: paths[name].read_bytes() for name in before},
                         '重复回执可以幂等接受或明确拒绝，但不能再次推进或追加成功事件')


class RoutingFunctionTest(unittest.TestCase):
    """直接命中生产判定函数，不让新根字段缺失遮蔽旧路由漏洞。"""

    def test_initial_tester_completed_state_does_not_require_product_green(self):
        payload = initial_contract(1)
        tester = payload['subtasks'][0]
        tester.update(status='completed', result=base.result('completed', 'test-agent', 'tester',
                                                            checks=[check('red')]))
        payload['approval']['planned_subtask_ids'] = [task['subtask_id'] for task in payload['subtasks']]
        payload['approval']['contract_sha256'] = ctl._contract_hash(payload)
        errors = ctl._subtask_state_errors(payload)
        self.assertEqual([], errors)

    def test_shared_test_file_and_fixture_have_exactly_one_writer(self):
        for scopes in ((['tests/test_shared.py'], ['tests/test_shared.py']),
                       (['tests'], ['tests/conftest.py'])):
            with self.subTest(scopes=scopes):
                payload = initial_contract()
                payload['task_id'] = base.TASK_ID
                payload['subtasks'][0]['write_paths'], payload['subtasks'][1]['write_paths'] = scopes
                errors = ctl._workflow_errors(payload)
                self.assertTrue(any(any(word in e.lower() for word in ('overlap', 'writer', 'conflict'))
                                    for e in errors), errors)

    def test_implementation_cannot_omit_initial_test_dependencies(self):
        payload = initial_contract()
        payload['task_id'] = base.TASK_ID
        next(t for t in payload['subtasks'] if t['subtask_id'] == 'WORK-001')['dependencies'] = []
        errors = ctl._workflow_errors(payload)
        self.assertTrue(any('depend' in e.lower() and ('test' in e.lower() or 'TEST-' in e)
                            for e in errors), errors)

    def test_integration_gate_counts_work_even_if_not_in_direct_dependencies(self):
        payload = initial_contract()
        for task in payload['subtasks']:
            task['status'] = 'completed'
        late = deepcopy(payload['subtasks'][2])
        late.update(subtask_id='WORK-LATE', status='in_progress')
        payload['subtasks'].append(late)
        self.assertTrue(any('WORK-LATE' in e for e in ctl._required_work_errors(payload)))

    def finding_case(self, source_stage, routed_agent):
        payload = initial_contract(1)
        identities = {'WORK-001': 'work-agent', 'INTEGRATE-001': 'integration-agent',
                      'REVIEW-001': 'review-agent', 'ACCEPT-001': 'accept-agent'}
        for task in payload['subtasks']:
            if task['subtask_id'] in identities:
                task.update(status='completed', dispatch=dict(agent_key=task['role'],
                    platform_agent_id=identities[task['subtask_id']]))
        source_id = 'REVIEW-001' if source_stage == 'review' else 'ACCEPT-001'
        discoverer = {'agent_key': 'reviewer' if source_stage == 'review' else 'tester',
                      'platform_agent_id': identities[source_id]}
        reviewer = {'agent_key': 'reviewer', 'platform_agent_id': 'review-agent'}
        finding = base.finding('F-ROUTE')
        finding.update(paths=['candidate-source.py'], root_cause='入口缺少边界判定。',
            fix_plan='在唯一整合职责内补边界判定，并保留失败断言。',
            documentation_update={'written_by': discoverer['platform_agent_id'],
                'status': 'not_applicable', 'paths': [], 'reason': '内部边界缺陷，不改变正式接口。'},
            routed_to={'agent_key': 'backend-implementer', 'platform_agent_id': routed_agent},
            regression_proof={'written_by': discoverer['platform_agent_id'],
                **{k: v for k, v in check('red').items() if k != 'purpose'}})
        return payload, finding, discoverer, source_id, reviewer

    def test_review_and_acceptance_reject_original_work_implementer_route(self):
        for stage in ('review', 'acceptance'):
            with self.subTest(stage=stage):
                with self.assertRaisesRegex(ctl.ControlError, 'integration|integrator'):
                    ctl._new_finding(*self.finding_case(stage, 'work-agent'))

    def test_review_and_acceptance_accept_original_integration_route(self):
        for stage in ('review', 'acceptance'):
            with self.subTest(stage=stage):
                finding = ctl._new_finding(*self.finding_case(stage, 'integration-agent'))
                self.assertEqual('integration-agent', finding['routed_to']['platform_agent_id'])
                self.assertEqual('open', finding['status'])


def convergence_contract():
    """使用当前合同字段表达真实职责；不借后置阶段伪装前置工作。"""
    payload = initial_contract(3)
    tasks = payload['subtasks']
    testers = tasks[:3]
    for tester in testers:
        tester['dependencies'] = ['T0']
    prototype = deepcopy(tasks[3])

    def node(ident, role, dependencies, writes):
        value = deepcopy(prototype)
        value.update(subtask_id=ident, title=ident, role=role,
                     dependencies=dependencies, write_paths=writes)
        return value

    implementations = [node(f'I{i}', 'backend-implementer', ['TJ'], ['candidate-source.py'])
                       for i in range(1, 4)]
    tasks[4]['dependencies'] = ['D2']
    payload['subtasks'] = [
        node('D1', 'doc-curator', [], ['docs/contract.md']),
        node('T0', 'tester', ['D1'], ['tests/fixtures/shared.json']),
        *testers,
        node('TJ', 'tester', payload['initial_test_owners'][:], ['tests/fixtures/shared.json']),
        *implementations,
        node('D2', 'doc-curator', ['I1', 'I2', 'I3'], ['docs/contract.md']),
        *tasks[4:],
    ]
    payload['task_id'] = base.TASK_ID
    workflow.add_requirement_checklist(payload, 'I1')
    return payload


class ConvergenceDependencyTest(unittest.TestCase):
    def test_real_dag_accepts_document_preparation_summary_and_transitive_tests(self):
        errors = ctl._workflow_errors(convergence_contract())
        self.assertEqual([], errors, '真实前置与汇总 DAG 不应被当作全部直接依赖测试的实现节点')

    def test_missing_test_branch_still_blocks_implementation(self):
        payload = convergence_contract()
        self.assertEqual([], ctl._workflow_errors(payload), '先证明完整图合法，防止泛化拒绝冒充命中')
        next(t for t in payload['subtasks'] if t['subtask_id'] == 'TJ')['dependencies'].pop()
        self.assertTrue(ctl._workflow_errors(payload), '缺失测试分支的实现依赖必须被拒绝')

    def test_document_preparation_and_summary_do_not_require_product_red_green(self):
        payload = convergence_contract()
        for ident in ('D1', 'T0', 'TJ', 'D2'):
            with self.subTest(task=ident):
                task = next(t for t in payload['subtasks'] if t['subtask_id'] == ident)
                required = ctl._required_checks(payload, task)
                self.assertFalse(required & {'red', 'green'}, (ident, required))

    def test_implementation_keeps_real_red_green_and_regression(self):
        payload = convergence_contract()
        implementation = next(t for t in payload['subtasks'] if t['subtask_id'] == 'I1')
        self.assertEqual({'red', 'green', 'regression'}, ctl._required_checks(payload, implementation))
        self.assertTrue(ctl._checks_errors([check('green')], ctl._required_checks(payload, implementation)))


class ConvergenceDispatchIdentityTest(unittest.TestCase):
    """生产绑定判定；仅隔离持久化，完整合同另由 CLI 用例验证。

    输入中的 dispatch/完成状态是身份边界夹具，不声称有真实代理或真实业务验证。
    """
    def setUp(self):
        root = base.REPO_ROOT / '.tmp/harness-minimal-convergence/T1'
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)

    def bind_pair(self, previous_id, target_id, *, same_identity=True, serial=False):
        payload = convergence_contract()
        payload['approval']['planned_subtask_ids'] = [task['subtask_id'] for task in payload['subtasks']]
        for task in payload['subtasks']:
            task['status'] = 'completed'
        previous = next(t for t in payload['subtasks'] if t['subtask_id'] == previous_id)
        target = next(t for t in payload['subtasks'] if t['subtask_id'] == target_id)
        if serial:
            target['dependencies'] = [previous_id]
        # Each case explicitly plans the identity reuse/separation being exercised.
        previous['planned_agent_key'] = previous['role']
        target['planned_agent_key'] = target['role']
        previous['dispatch'] = {'platform_agent_id': '/root/test-owner', 'agent_key': previous['role']}
        target['status'] = 'ready'
        brief = self.repo / 'brief.md'
        brief.write_text('独立身份边界测试输入，不是平台派发证据。\n', encoding='utf-8')
        args = SimpleNamespace(SubtaskId=target_id, AgentKey=target['role'],
            PlatformAgentId='/root/test-owner' if same_identity else '/root/other-owner',
            ContextMode='isolated', BriefKind='subtask', BriefPath='brief.md',
            BriefSha256=hashlib.sha256(brief.read_bytes()).hexdigest(), TaskId=base.TASK_ID)
        paths = ctl._task_paths(self.repo, base.TASK_ID)
        # 不替换身份、依赖、brief哈希或阶段门禁；只避免把局部边界夹具当完整任务落盘。
        with patch.object(ctl, '_write_state'), patch.object(ctl, '_append_event'):
            result = ctl._bind(args, paths, payload)
        self.assertTrue(result['ok'])
        self.assertEqual('in_progress', target['status'])
        self.assertEqual(args.PlatformAgentId, target['dispatch']['platform_agent_id'])
        return result

    def test_test_lead_reuses_preparation_identity_for_initial_tests(self):
        try:
            self.bind_pair('T0', 'TEST-001')
        except ctl.ControlError as error:
            self.fail(f'T0→初始测试的同一测试负责人被生产身份门禁拒绝: {error}')

    def test_test_lead_reuses_initial_identity_for_summary(self):
        try:
            self.bind_pair('TEST-001', 'TJ')
        except ctl.ControlError as error:
            self.fail(f'初始测试→TJ的同一测试负责人被生产身份门禁拒绝: {error}')

    def test_tester_and_implementation_are_independent_in_both_binding_orders(self):
        for previous, target in [('TEST-001', 'I1'), ('I1', 'TEST-001')]:
            with self.subTest(previous=previous, target=target):
                with self.assertRaisesRegex(ctl.ControlError, 'independen|tester|identity'):
                    self.bind_pair(previous, target)

    def test_serial_initial_test_owners_reuse_same_identity(self):
        try:
            self.bind_pair('TEST-001', 'TEST-002', serial=True)
        except ctl.ControlError as error:
            self.fail(f'前置测试已完成的同职责串行复用被生产身份门禁拒绝: {error}')

    def test_preparation_and_summary_test_authors_cannot_implement_product(self):
        for previous, target in [('T0', 'I1'), ('I1', 'T0'), ('TJ', 'I1'), ('I1', 'TJ')]:
            with self.subTest(previous=previous, target=target):
                self.bind_pair(previous, target, same_identity=False)
                with self.assertRaisesRegex(ctl.ControlError, 'independen|tester|identity'):
                    self.bind_pair(previous, target)


class ConvergenceCliTest(unittest.TestCase):
    setUp = InitialTestRoutingTest.setUp
    tearDown = InitialTestRoutingTest.tearDown
    run_ctl = InitialTestRoutingTest.run_ctl
    init_task = InitialTestRoutingTest.init_task
    state = InitialTestRoutingTest.state

    def test_public_init_preserves_real_dag_without_role_disguise(self):
        payload = convergence_contract()
        self.init_task(payload)
        observed = self.state()
        self.assertEqual(payload['subtasks'], observed['subtasks'])
        self.assertEqual(['TEST-001', 'TEST-002', 'TEST-003'], observed['initial_test_owners'])


if __name__ == '__main__':
    unittest.main()
