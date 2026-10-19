"""Independent B contracts: discovery evidence, acceptance retest and document closeout.

Receipts below are controlled test inputs, not claims of actual agent/browser use.
No production behavior is mocked. Function tests isolate gates from the separate
initial-test-owner migration; CLI tests additionally cover persisted transitions.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import test_control_plane as legacy
import test_gto_workflow as workflow
from test_gto_point_acceptance import PointHarness

SPEC = importlib.util.spec_from_file_location("gto_acceptance_contract_controller", legacy.CONTROLLER)
ctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ctl)


def usage(writer, stage):
    return [{"written_by": writer, "environment": "wsl", "tool": "CLI",
             "entry": "python3 candidate-source.py --check-boundary",
             "scope": ["candidate-source.py"], "result": "Boundary rejects invalid input.",
             "evidence_refs": [f".artifacts/{stage}-use.log"],
             "ui_applicability": "not_applicable",
             "ui_not_applicable_reason": "This fixture exposes only a command line interface."}]


def identity(agent, role):
    return {"platform_agent_id": agent, "agent_key": role}


INTEGRATOR = identity("impl-001", "backend-implementer")
REVIEWER = identity("review-001", "reviewer")
ACCEPTOR = identity("accept-001", "tester")


def finding_state():
    return {"workflow_revision": 3, "findings": {}, "subtasks": [
        {"subtask_id": "INTEGRATE-001", "role": "backend-implementer", "stage": "integration",
         "status": "completed", "dispatch": INTEGRATOR},
        {"subtask_id": "REVIEW-001", "role": "reviewer", "stage": "pre_acceptance_review",
         "status": "completed", "dispatch": REVIEWER},
        {"subtask_id": "ACCEPT-001", "role": "tester", "stage": "expensive_acceptance",
         "status": "in_progress", "dispatch": ACCEPTOR}]}


def complete_finding(writer="review-001"):
    value = workflow.WorkflowTest.new_finding(None, "F-CONTRACT", writer)
    value["fix_plan"] = "Reject invalid boundary input before invoking the downstream operation."
    value["documentation_update"] = {
        "written_by": writer, "status": "not_applicable", "paths": [],
        "reason": "The existing documented input boundary is correct; implementation violates it."}
    return value


class DiscovererContractTest(unittest.TestCase):
    def normalize(self, value, *, acceptance=False):
        writer = ACCEPTOR if acceptance else REVIEWER
        return ctl._new_finding(finding_state(), value, writer,
                                "ACCEPT-001" if acceptance else "REVIEW-001", writer)

    def test_discoverer_must_supply_a_repair_plan(self):
        value = complete_finding()
        del value["fix_plan"]
        with self.assertRaises(ctl.ControlError):
            self.normalize(value)

    def test_discoverer_must_sync_documents_or_explain_not_applicable(self):
        value = complete_finding()
        del value["documentation_update"]
        with self.assertRaises(ctl.ControlError):
            self.normalize(value)

    def test_document_not_applicable_cannot_be_an_empty_excuse(self):
        value = complete_finding()
        value["documentation_update"]["reason"] = ""
        with self.assertRaises(ctl.ControlError):
            self.normalize(value)

    def test_document_update_must_be_authored_by_the_discoverer(self):
        value = complete_finding()
        value["documentation_update"]["written_by"] = "impl-001"
        with self.assertRaises(ctl.ControlError):
            self.normalize(value)

    def test_a_passing_command_is_not_failure_proof(self):
        value = complete_finding()
        value["regression_proof"].update(exit_code=0, expected_exit_code=0)
        with self.assertRaises(ctl.ControlError):
            self.normalize(value)

    def test_acceptance_discoverer_owns_retest_without_becoming_reviewer(self):
        try:
            result = self.normalize(complete_finding("accept-001"), acceptance=True)
        except ctl.ControlError as exc:
            self.fail(f"Acceptance finding must retain its acceptance owner without a reviewer hop: {exc}")
        self.assertEqual(ACCEPTOR, result["discovered_by"])
        self.assertEqual(INTEGRATOR, result["routed_to"])


def acceptance_state():
    state = finding_state()
    state["acceptance_gate"] = {
        "current_candidate": {"candidate_id": "candidate-new", "status": "frozen"},
        "acceptance_items": [{"acceptance_id": "PATH-A"}, {"acceptance_id": "PATH-B"}],
        "attempts": [{"attempt_id": "attempt-1", "subtask_id": "ACCEPT-001",
                      "candidate_id": "candidate-new"}]}
    return state


def acceptance_result():
    return {"status": "completed", "written_by": "accept-001", "expensive_acceptance": {
        "outcome": "pass", "real_call_count": 1, "duration_seconds": 1, "failed_stage": "none",
        "evidence_refs": [".artifacts/accept-use.log"],
        "evidence_by_acceptance_id": {"PATH-A": [".artifacts/accept-use.log"],
                                      "PATH-B": [".artifacts/accept-use.log"]},
        "usage_evidence": usage("accept-001", "accept"), "mode": "full",
        "scope_acceptance_ids": ["PATH-A", "PATH-B"]}}


class AcceptanceEvidenceContractTest(PointHarness, unittest.TestCase):
    def record(self, state, receipt):
        ctl._record_expensive_attempt(state, state["subtasks"][-1], receipt)

    def test_acceptance_requires_its_own_actual_use_evidence(self):
        result = acceptance_result()
        del result["expensive_acceptance"]["usage_evidence"]
        with self.assertRaises(ctl.ControlError):
            self.record(acceptance_state(), result)

    def test_acceptance_cannot_reuse_reviewers_operation_as_its_own(self):
        result = acceptance_result()
        result["expensive_acceptance"]["usage_evidence"] = usage("review-001", "review")
        with self.assertRaises(ctl.ControlError):
            self.record(acceptance_state(), result)

    def test_non_ui_use_must_explain_ui_inapplicability(self):
        result = acceptance_result()
        result["expensive_acceptance"]["usage_evidence"][0]["ui_not_applicable_reason"] = ""
        with self.assertRaises(ctl.ControlError):
            self.record(acceptance_state(), result)

    def test_wsl_ui_cannot_claim_windows_computer_use(self):
        result = acceptance_result()
        result["expensive_acceptance"]["usage_evidence"][0].update(
            tool="Computer Use", environment="wsl", ui_applicability="required",
            entry="http://localhost:8000/form", ui_not_applicable_reason="")
        with self.assertRaises(ctl.ControlError):
            self.record(acceptance_state(), result)

    def test_first_acceptance_can_register_its_executed_scope_without_extra_review(self):
        self.begin()
        attempt = self.attempt(['CHECK-01'])
        result = self.observe(attempt, ['CHECK-01'])
        result['expensive_acceptance'].pop('point_results')  # Existing mapping input is still public.
        self.register(attempt, result)
        status = self.coverage()
        self.assertEqual('pass', status['points']['CHECK-01']['status'])
        self.assertFalse(status['complete'])
        self.assertEqual(['CHECK-02'], status['rerun_acceptance_ids'])

    def repaired_failure(self):
        self.begin(10, failing=True)
        source = self.attempt()
        self.register(source, self.observe(source, self.ids, failed='POINT-FAIL'))
        self.run_ctl('dispatch-finding-fix', finding_id='POINT-FAIL')
        path = self.repo / 'inputs/shared.json'
        path.write_text(json.dumps({'CHECK-09': True, 'CHECK-10': True}))
        self.run_ctl('record-finding-fix', finding_id='POINT-FAIL', result={
            'summary': 'Correct shared input.', 'changed_files': ['inputs/shared.json'],
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'verification': 'Targeted input correction.',
            'checks': self.work_result()['checks'], 'written_by': 'impl-001', 'written_role': 'backend-implementer'})
        self.reintegrate()
        self.run_ctl('freeze-candidate')
        return self.attempt(bind=False)

    def test_scoped_retest_cannot_inherit_a_failed_item(self):
        self.begin(10, failing=True)
        attempt = self.attempt()
        result = self.observe(attempt, self.ids)
        falsely_passed = deepcopy(result)
        failed_point = falsely_passed['expensive_acceptance']['point_results'][-1]
        failed_point['status'] = 'pass'
        falsely_passed['expensive_acceptance']['evidence_by_acceptance_id']['CHECK-10'] = failed_point['evidence_refs']
        self.register(attempt, falsely_passed, ok=False)
        self.register(attempt, result)
        status = self.coverage()
        self.assertEqual('fail', status['points']['CHECK-10']['status'])
        self.assertEqual(9, sum(point['status'] == 'pass' for point in status['points'].values()))
        self.assertFalse(status['complete'])
        self.run_ctl('finalize-task', ok=False)

    def test_scoped_retest_cannot_inherit_an_unexecuted_item(self):
        self.begin()
        attempt = self.attempt()
        self.register(attempt, self.observe(attempt, self.ids, unexecuted={'CHECK-02': 'not_run'}))
        status = self.coverage()
        self.assertEqual('not_run', status['points']['CHECK-02']['status'])
        self.assertFalse(status['complete'])
        self.run_ctl('finalize-task', ok=False)

    def test_changed_impact_cannot_be_hidden_behind_old_passing_evidence(self):
        self.begin()
        attempt = self.attempt()
        self.register(attempt, self.observe(attempt, self.ids))
        (self.repo / 'inputs/CHECK-01.json').write_text('{"CHECK-01": false}')
        proof = self.repo / '.artifacts/impact.json'
        proof.write_text('{"claim": "no change"}')
        before = self.state()
        rejected = self.run_ctl('record-acceptance-impact', result={
            'written_by': 'accept-001', 'written_role': 'tester', 'source_attempt_id': attempt['attempt_id'],
            'point_ids': ['CHECK-01'], 'changed_paths': [], 'reason': 'Attempt to hide the input change.',
            'evidence_refs': ['.artifacts/impact.json']}, ok=False)
        self.assertNotIn('invalid choice', str(rejected))
        self.assertEqual(before, self.state())
        self.assertEqual('invalid', self.coverage()['points']['CHECK-01']['status'])

    def test_unchanged_historical_points_need_no_self_reported_impact_or_mapping_copy(self):
        self.begin(3)
        sources = []
        for ident in self.ids:
            attempt = self.attempt([ident])
            result = self.observe(attempt, [ident])
            result['expensive_acceptance'].pop('point_results')
            self.assertNotIn('impact', result['expensive_acceptance'])
            self.assertEqual({ident}, set(result['expensive_acceptance']['evidence_by_acceptance_id']))
            self.register(attempt, result)
            sources.append(attempt['attempt_id'])
        status = self.coverage()
        self.assertTrue(status['complete'])
        self.assertEqual(sources, [status['points'][ident]['source_attempt_id'] for ident in self.ids])
        self.assertEqual(3, self.count())

    def test_product_fix_can_proceed_to_acceptance_without_re_review(self):
        state = finding_state()
        state["findings"]["F-ACCEPT"] = {
            "status": "awaiting_re_review", "source_subtask_id": "ACCEPT-001",
            "discovered_by": ACCEPTOR, "routed_to": INTEGRATOR,
            "fix_delta": {"changed_files": ["candidate-source.py"], "sha256": "a" * 64},
            "lineage": {"original_implementer": INTEGRATOR, "original_reviewer": REVIEWER}}
        errors = ctl._product_failure_retry_errors(state, {"finding_id": "F-ACCEPT"})
        self.assertEqual([], errors, "Fixed acceptance finding must be closed by the retest, not a reviewer prerequisite.")

    def test_successful_retest_closes_the_stable_acceptance_finding(self):
        attempt = self.repaired_failure()
        self.bind(attempt['subtask_id'], agent='accept-001', role='tester')
        result = self.observe(attempt, ['CHECK-09', 'CHECK-10'])
        result['expensive_acceptance'].pop('point_results')
        result['expensive_acceptance']['closed_finding_ids'] = ['POINT-FAIL']
        self.register(attempt, result)
        finding = self.state()['findings']['POINT-FAIL']
        self.assertEqual('closed', finding['status'])
        self.assertEqual('accept-001', finding['discovered_by']['platform_agent_id'])
        self.assertEqual(attempt['attempt_id'], finding['closed_by_attempt_id'])

    def test_a_different_acceptor_cannot_close_the_original_finding(self):
        attempt = self.repaired_failure()
        before = self.state()
        rejected = self.bind(attempt['subtask_id'], agent='other-acceptor', role='tester', ok=False)
        self.assertRegex(str(rejected).lower(), 'identity|acceptor|owner|same|original')
        self.assertEqual(before, self.state())
        self.assertEqual('awaiting_retest', self.state()['findings']['POINT-FAIL']['status'])

    def test_full_acceptance_with_current_use_maps_both_items(self):
        self.begin()
        attempt = self.attempt()
        result = self.observe(attempt, self.ids)
        result['expensive_acceptance'].pop('point_results')
        self.register(attempt, result)
        self.assertTrue(self.coverage()['complete'])
        self.assertEqual({'CHECK-01', 'CHECK-02'},
                         set(self.state()['acceptance_gate']['attempts'][-1]['evidence_by_acceptance_id']))

    def test_scoped_retest_can_retain_proven_unchanged_passing_item(self):
        self.begin()
        first = self.attempt(['CHECK-01'])
        first_result = self.observe(first, ['CHECK-01'])
        first_result['expensive_acceptance'].pop('point_results')
        self.register(first, first_result)
        second = self.attempt(['CHECK-02'])
        result = self.observe(second, ['CHECK-02'])
        result['expensive_acceptance'].pop('point_results')
        self.register(second, result)
        status = self.coverage()
        self.assertTrue(status['complete'])
        self.assertEqual(first['attempt_id'], status['points']['CHECK-01']['source_attempt_id'])
        self.assertEqual({'CHECK-02'}, set(self.state()['acceptance_gate']['attempts'][-1]['evidence_by_acceptance_id']))


class AcceptanceCliContractTest(unittest.TestCase):
    run_ctl = legacy.ControlPlaneContractTest.run_ctl
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state
    git = legacy.ControlPlaneContractTest.git
    init_git_checkout = legacy.ControlPlaneContractTest.init_git_checkout
    bind = workflow.WorkflowTest.bind
    work_result = workflow.WorkflowTest.work_result
    integrate = workflow.WorkflowTest.integrate
    review_payload = workflow.WorkflowTest.review_payload
    review = workflow.WorkflowTest.review
    accept = workflow.WorkflowTest.accept

    def setUp(self):
        base = legacy.REPO_ROOT / ".tmp/review-acceptance-routing/test-b"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.input_temp = tempfile.TemporaryDirectory(dir=base)
        self.repo, self.input_dir = Path(self.temp.name), Path(self.input_temp.name)
        self._json_input_index = 0
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.input_temp.cleanup)

    def start(self, *, documents=False):
        payload = workflow.workflow_contract()
        if documents:
            payload["subtasks"][-1]["write_paths"] = ["docs"]
        self.init_git_checkout("candidate-source.py", "candidate-config.json", "docs/contract.md")
        self.init_task(payload)
        self.run_ctl("prepare-workspace")
        self.integrate()

    def test_review_cannot_pass_without_actual_use_evidence(self):
        self.start()
        self.bind("REVIEW-SEC-001", agent="review-001", role="reviewer", review=True)
        payload = self.review_payload()
        payload["review"].pop("usage_evidence", None)
        self.run_ctl("record-review-result", subtask_id="REVIEW-SEC-001", result=payload, ok=False)

    def test_document_agent_can_sync_non_whitespace_wording_after_acceptance(self):
        self.start(documents=True)
        self.review()
        accepted_subtask = self.accept()
        source_attempt = next(attempt for attempt in self.state()['acceptance_gate']['attempts']
                              if attempt['subtask_id'] == accepted_subtask)
        original_attempts = deepcopy(self.state()['acceptance_gate']['attempts'])
        original_runs = {path.relative_to(self.repo).as_posix(): path.read_bytes()
                         for path in (self.repo / '.artifacts/synthetic-runs').rglob('manifest.json')}
        self.bind("DOC-FINAL-001", agent="docs-001", role="doc-curator")
        document = self.repo / "docs/contract.md"
        before_document = document.read_bytes()
        document.write_text(document.read_text() + "\nThe command line entry is described above.\n")
        receipt = legacy.result("completed", "docs-001", "doc-curator", changed_files=["docs/contract.md"])
        receipt["documentation_sync"] = {
            "checked_paths": ["docs/contract.md"], "changed_paths": ["docs/contract.md"],
            "behavior_changed": False, "contract_changed": False, "configuration_changed": False,
            "reason": "Clarifies an existing entry without changing commands, inputs, outputs or requirements."}
        self.assertEqual('invalid', self.run_ctl('acceptance-status')['points']['REAL-PATH-001']['status'])
        before_rejection = self.state()
        self.run_ctl("record-subtask-result", subtask_id="DOC-FINAL-001", result=receipt, ok=False)
        self.assertEqual(before_rejection, self.state(), 'Document author cannot silently authorize point reuse.')
        proof = self.repo / '.artifacts/document-impact.json'
        proof.write_text(json.dumps({'source_attempt_id': source_attempt['attempt_id'],
            'changed_paths': ['docs/contract.md'],
            'before_sha256': hashlib.sha256(before_document).hexdigest(),
            'after_sha256': hashlib.sha256(document.read_bytes()).hexdigest(),
            'judgment': 'Only an explanatory sentence was appended; acceptance criteria remain unchanged.'}))
        self.run_ctl('record-acceptance-impact', result={
            'written_by': 'accept-001', 'written_role': 'tester',
            'source_attempt_id': source_attempt['attempt_id'], 'point_ids': ['REAL-PATH-001'],
            'changed_paths': ['docs/contract.md'],
            'reason': 'Original acceptor checked the full document delta; no input, output or criterion changed.',
            'evidence_refs': ['.artifacts/document-impact.json']})
        self.run_ctl("record-subtask-result", subtask_id="DOC-FINAL-001", result=receipt)
        self.assertIn("The command line entry", document.read_text())
        self.assertEqual("completed", self.run_ctl("finalize-task")["status"])
        self.assertEqual(original_attempts, self.state()['acceptance_gate']['attempts'])
        self.assertEqual(original_runs, {path.relative_to(self.repo).as_posix(): path.read_bytes()
                         for path in (self.repo / '.artifacts/synthetic-runs').rglob('manifest.json')},
                         'Scope judgment and document closeout must not execute another acceptance run.')

    def test_document_wording_receipt_cannot_hide_changed_executable_content(self):
        self.start(documents=True)
        self.review()
        self.accept()
        self.bind("DOC-FINAL-001", agent="docs-001", role="doc-curator")
        document = self.repo / "docs/contract.md"
        document.write_text(document.read_text() + "\nClarified wording.\n")
        code = self.repo / "candidate-source.py"
        code.write_text(code.read_text() + "\nraise RuntimeError('changed behavior')\n")
        receipt = legacy.result("completed", "docs-001", "doc-curator", changed_files=["docs/contract.md"])
        receipt["documentation_sync"] = {
            "checked_paths": ["docs/contract.md"], "changed_paths": ["docs/contract.md"],
            "behavior_changed": False, "contract_changed": False, "configuration_changed": False,
            "reason": "Claims wording only, but executable content actually changed."}
        self.run_ctl("record-subtask-result", subtask_id="DOC-FINAL-001", result=receipt, ok=False)


class BlackboxMachineEntryTest(unittest.TestCase):
    """已确认公开接口的最小入口证明；不把入口Red算成后置停止门禁命中。"""
    setUp = AcceptanceCliContractTest.setUp
    start = AcceptanceCliContractTest.start
    run_ctl = AcceptanceCliContractTest.run_ctl
    init_task = AcceptanceCliContractTest.init_task
    state = AcceptanceCliContractTest.state
    git = AcceptanceCliContractTest.git
    init_git_checkout = AcceptanceCliContractTest.init_git_checkout
    bind = AcceptanceCliContractTest.bind
    work_result = AcceptanceCliContractTest.work_result
    integrate = AcceptanceCliContractTest.integrate
    review_payload = AcceptanceCliContractTest.review_payload
    review = AcceptanceCliContractTest.review
    accept = AcceptanceCliContractTest.accept

    def public_call(self, action, **arguments):
        command = [sys.executable, '-B', str(legacy.CONTROLLER), '--action', action,
                   '--repo-root', str(self.repo), '--task-id', legacy.TASK_ID, '--json']
        for name, value in arguments.items():
            if name == 'result':
                self._json_input_index += 1
                path = self.input_dir / f'blackbox-input-{self._json_input_index}.json'
                path.write_text(json.dumps(value), encoding='utf-8')
                command.extend(['--result-json-file', str(path)])
            else:
                command.extend(['--' + name.replace('_', '-'), str(value)])
        completed = subprocess.run(command, cwd=self.input_dir, capture_output=True,
                                   text=True, timeout=30)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            self.fail(f'已确认的新公开入口尚无结构化响应: exit={completed.returncode}; '
                      f'stdout={completed.stdout}; stderr={completed.stderr}')
        return completed, payload

    def test_new_ordinary_contract_with_requirements_reaches_acceptance_without_blackbox_fields(self):
        self.start()
        self.review()
        self.accept()
        attempts = self.state()['acceptance_gate']['attempts']
        self.assertEqual(1, len(attempts))
        self.assertEqual('pass', attempts[0]['outcome'])
        self.assertEqual('ordinary', attempts[0].get('kind', 'ordinary'))

    def test_contract_accepts_blackbox_ids_as_existing_acceptance_subset(self):
        payload = workflow.workflow_contract()
        payload['acceptance_gate']['blackbox_acceptance_ids'] = ['REAL-PATH-001']
        self.init_task(payload)
        self.assertEqual(['REAL-PATH-001'], self.state()['acceptance_gate']['blackbox_acceptance_ids'])

    def test_attempt_kind_is_recognized_before_existing_stage_gate(self):
        self.init_task(workflow.workflow_contract())
        before = self.state()
        completed, payload = self.public_call('create-subtask-attempt',
            subtask_id='EXPENSIVE-001', attempt_kind='preparation')
        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(payload['ok'])
        self.assertRegex(' '.join(payload['errors']).lower(), 'candidate|review|integration')
        self.assertEqual(before, self.state())

    def test_decision_action_rejects_unknown_attempt_without_changing_history(self):
        self.init_task(workflow.workflow_contract())
        paths = ctl._task_paths(self.repo, legacy.TASK_ID)
        before = {name: paths[name].read_bytes() for name in ('state.json', 'events.jsonl')}
        completed, payload = self.public_call('record-blackbox-decision', result={
            'attempt_id': 'unknown-attempt', 'approved_by': 'user',
            'reason': '隔离接口反例：不存在的attempt不能被授权。',
            'evidence_refs': ['.artifacts/user-decision.log'], 'allow': ['repair']})
        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(payload['ok'])
        self.assertRegex(' '.join(payload['errors']).lower(), 'attempt|effect.failure')
        self.assertEqual(before, {name: paths[name].read_bytes() for name in before})

    def test_effect_failure_schema_preserves_trace_and_existing_report_reference(self):
        evidence = acceptance_result()['expensive_acceptance']
        # Shape-only input, deliberately not a claim of a real captured run.
        evidence['run_evidence'] = {'path': '.artifacts/schema-only/manifest.json', 'sha256': '0' * 64}
        receipt = legacy.result('completed', 'accept-001', 'tester', expensive_acceptance=evidence)
        self.assertEqual([], ctl._canonical_schema_errors(receipt, definition='result'),
                         '先证明既有回执结构合法，不拿缺通用字段冒充效果入口Red')
        failure = deepcopy(receipt)
        failure.update(status='blocked', blocked_by=['正式首轮效果未达预期，待用户决定。'])
        failure['expensive_acceptance'].update(outcome='effect_failure', failed_stage='effect',
            evidence_by_acceptance_id={}, blackbox={
                'session_ids': ['fixture-top-level-session'],
                'input_refs': ['candidate-config.json'],
                'trace_refs': ['.artifacts/blackbox-trace.log'],
                'report_ref': f'docs/tasks/{legacy.TASK_ID}/acceptance.md'})
        self.assertEqual([], ctl._canonical_schema_errors(failure, definition='result'),
                         '正式效果失败应保留输入/轨迹及既有acceptance.md报告引用')



class BlackboxLifecycleTest(unittest.TestCase):
    """只在隔离合成项目走真实 CLI；阶段前置失败不冒充后置门禁命中。"""
    setUp = AcceptanceCliContractTest.setUp
    run_ctl = AcceptanceCliContractTest.run_ctl
    init_task = AcceptanceCliContractTest.init_task
    state = AcceptanceCliContractTest.state
    git = AcceptanceCliContractTest.git
    init_git_checkout = AcceptanceCliContractTest.init_git_checkout
    bind = AcceptanceCliContractTest.bind
    work_result = AcceptanceCliContractTest.work_result
    integrate = AcceptanceCliContractTest.integrate
    review_payload = AcceptanceCliContractTest.review_payload
    review = AcceptanceCliContractTest.review
    public_call = BlackboxMachineEntryTest.public_call

    def start_flow(self):
        payload = workflow.workflow_contract()
        gate = payload['acceptance_gate']
        blackbox_item = deepcopy(gate['acceptance_items'][0])
        blackbox_item['acceptance_id'] = 'BBX-001'
        gate['acceptance_items'].append(blackbox_item)
        gate['blackbox_acceptance_ids'] = ['BBX-001']
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(payload)
        self.run_ctl('prepare-workspace')
        self.integrate()
        self.review()
        self.run_ctl('freeze-candidate')

    def create_attempt(self, kind, *, approve_budget=False):
        arguments = {'subtask_id': 'EXPENSIVE-001', 'attempt_kind': kind}
        if approve_budget:
            arguments.update(approval_by='user', approval_reason='合成测试明确批准既有命令预算；不是效果停止授权。')
        completed, payload = self.public_call('create-subtask-attempt', **arguments)
        self.assertEqual(0, completed.returncode, f'{kind}创建前置未通过: {payload}')
        self.assertTrue(payload['ok'], payload)
        attempt = payload['attempt']
        self.assertEqual(kind, attempt['kind'])
        self.bind(payload['subtask_id'], agent='accept-001', role='tester')
        return attempt

    def receipt(self, kind, outcome='pass'):
        ids = [] if kind == 'preparation' else (['BBX-001'] if kind == 'blackbox' else ['REAL-PATH-001'])
        evidence = {'outcome': outcome, 'real_call_count': 1, 'duration_seconds': 2,
            'failed_stage': 'none' if outcome == 'pass' else 'effect',
            'evidence_refs': ['.artifacts/observation.log'],
            'evidence_by_acceptance_id': {ident: ['.artifacts/observation.log'] for ident in ids} if outcome == 'pass' else {},
            'mode': 'full', 'scope_acceptance_ids': ids,
            'usage_evidence': workflow.usage('accept-001', kind)}
        if kind == 'preparation':
            evidence['preparation'] = {'checks': {key: [f'.artifacts/{key}.log'] for key in
                ('deployment', 'version', 'environment', 'input_and_session', 'evidence_capture')},
                'business_input_refs': ['candidate-config.json']}
        if kind == 'blackbox':
            evidence['blackbox'] = {'session_ids': ['synthetic-isolated-session'],
                'input_refs': ['candidate-config.json'], 'trace_refs': ['.artifacts/observation.log'],
                'report_ref': f'docs/tasks/{legacy.TASK_ID}/acceptance.md'}
        return legacy.result('completed' if outcome == 'pass' else 'blocked', 'accept-001', 'tester',
                             expensive_acceptance=evidence)

    def finish_attempt(self, kind, outcome='pass', *, approve_budget=False):
        attempt = self.create_attempt(kind, approve_budget=approve_budget)
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=self.receipt(kind, outcome))
        return self.state()['acceptance_gate']['attempts'][-1]

    def test_ordinary_preparation_blackbox_chain_keeps_separate_evidence(self):
        self.start_flow()
        ordinary = self.finish_attempt('ordinary')
        preparation = self.finish_attempt('preparation')
        brief = self.repo / '.tmp/closeout-brief.md'
        brief.write_text('Finalize documented facts after all current-candidate business evidence passes.\n')
        before = self.state()
        rejected = self.run_ctl('bind-dispatch', subtask_id='DOC-FINAL-001', agent_key='doc-curator',
            platform_agent_id='docs-001', context_mode='isolated', brief_kind='subtask',
            brief_path='.tmp/closeout-brief.md', brief_sha256=hashlib.sha256(brief.read_bytes()).hexdigest(), ok=False)
        self.assertRegex(' '.join(rejected['errors']).lower(), 'acceptance|evidence|blackbox')
        self.assertEqual(before, self.state(), '准备通过不能代替缺失的黑盒业务证据')
        blackbox = self.finish_attempt('blackbox', approve_budget=True)
        self.assertEqual(preparation['attempt_id'], blackbox['preparation_attempt_id'])
        self.assertEqual(ordinary['candidate_id'], blackbox['candidate_id'])
        attempts = self.state()['acceptance_gate']['attempts']
        self.assertEqual(['ordinary', 'preparation', 'blackbox'], [item['kind'] for item in attempts])
        self.assertEqual([{'REAL-PATH-001'}, set(), {'BBX-001'}],
                         [set(item['evidence_by_acceptance_id']) for item in attempts])
        self.assertEqual(3, sum(item['real_call_count'] for item in attempts))
        self.assertEqual(6, sum(item['duration_seconds'] for item in attempts))
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.assertEqual('completed', self.run_ctl('finalize-task')['status'])

    def test_valid_effect_failure_persists_before_rejecting_second_round(self):
        self.start_flow()
        preparation = self.finish_attempt('preparation')
        failure = self.finish_attempt('blackbox', 'effect_failure')
        self.assertEqual('effect_failure', failure['outcome'])
        self.assertEqual(preparation['attempt_id'], failure['preparation_attempt_id'])
        self.assertEqual(f'docs/tasks/{legacy.TASK_ID}/acceptance.md', failure['blackbox']['report_ref'])
        before = self.state()
        completed, rejected = self.public_call('create-subtask-attempt', subtask_id='EXPENSIVE-001',
            attempt_kind='blackbox', approval_by='user', approval_reason='仅批准已有总预算，不授权第二轮效果。')
        self.assertNotEqual(0, completed.returncode, rejected)
        self.assertRegex(' '.join(rejected['errors']).lower(), 'effect|decision|stop')
        self.assertEqual(before, self.state())

    def start_effect_failure(self):
        self.start_flow()
        self.finish_attempt('preparation')
        return self.finish_attempt('blackbox', 'effect_failure')

    def assert_effect_stop(self, action, **arguments):
        before = self.state()
        completed, rejected = self.public_call(action, **arguments)
        self.assertNotEqual(0, completed.returncode, rejected)
        self.assertRegex(' '.join(rejected['errors']).lower(), 'effect|decision|stop')
        self.assertEqual(before, self.state())

    def decision(self, failure, allow):
        return {'attempt_id': failure['attempt_id'], 'approved_by': 'user',
            'reason': '合成任务明确选择的处理范围。',
            'evidence_refs': ['.artifacts/user-decision.log'], 'allow': allow}

    def test_effect_stop_survives_resume_ordinary_and_preparation_pass(self):
        failure = self.start_effect_failure()
        self.assert_effect_stop('create-integration-subtask', subtask_id='INTEGRATE-001')
        original_phase = self.state()['current_phase']
        blocked = legacy.result('blocked', 'coordinator-001', 'coordinator')
        recovered = legacy.result('completed', 'coordinator-001', 'coordinator', checks=[{
            'purpose': 'regression', 'command': 'python3 candidate-source.py',
            'scope': ['candidate-source.py'], 'exit_code': 0, 'expected_exit_code': 0,
            'evidence_refs': ['.artifacts/recovery.log']}])
        self.run_ctl('set-phase', phase='blocked', result=blocked)
        self.run_ctl('set-phase', phase=original_phase, result=recovered)
        self.assert_effect_stop('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.finish_attempt('ordinary', approve_budget=True)
        self.finish_attempt('preparation', approve_budget=True)
        self.assertEqual(failure, self.state()['acceptance_gate']['attempts'][1])
        self.assert_effect_stop('create-integration-subtask', subtask_id='INTEGRATE-001')
        # Separate public process reloads state on every call; no in-memory stop flag is sufficient.
        self.run_ctl('validate')
        self.assert_effect_stop('finalize-task')

    def test_effect_result_cannot_be_reclassified_or_overwritten(self):
        failure = self.start_effect_failure()
        before = self.state()
        changed = self.receipt('blackbox', 'environment_failure')
        changed['expensive_acceptance']['invalid_observation'] = {
            'reason': 'environment', 'evidence_refs': ['.artifacts/late-claim.log'],
            'summary': '事后改写已经有效的效果观察。'}
        rejected = self.run_ctl('record-subtask-result', subtask_id=failure['subtask_id'], result=changed, ok=False)
        self.assertTrue(rejected['errors'], rejected)
        self.assertEqual(before, self.state())

    def test_repair_decision_is_idempotent_and_does_not_authorize_next_round(self):
        failure = self.start_effect_failure()
        invalid = self.decision(self.state()['acceptance_gate']['attempts'][0], ['repair'])
        before = self.state()
        completed, rejected = self.public_call('record-blackbox-decision', result=invalid)
        self.assertNotEqual(0, completed.returncode, rejected)
        self.assertEqual(before, self.state(), '准备通过不是有效效果失败，不能授权产品修复')
        decision = self.decision(failure, ['repair'])
        completed, accepted = self.public_call('record-blackbox-decision', result=decision)
        self.assertEqual(0, completed.returncode, accepted)
        paths = ctl._task_paths(self.repo, legacy.TASK_ID)
        before = {name: paths[name].read_bytes() for name in ('state.json', 'events.jsonl')}
        completed, duplicate = self.public_call('record-blackbox-decision', result=decision)
        self.assertEqual(0, completed.returncode, duplicate)
        self.assertEqual(before, {name: paths[name].read_bytes() for name in before})
        with self.subTest(boundary='repair_navigation'):
            self.assertNotEqual('human_adjudication', self.state()['next_action']['kind'],
                                'repair授权后应能继续修复/质量检查，不等待next_round决定')
        saved = self.state()['acceptance_gate']['attempts'][1]
        self.assertEqual(1, len(saved['decisions']))
        self.assertEqual(failure, {key: value for key, value in saved.items() if key != 'decisions'})
        self.assert_effect_stop('create-subtask-attempt', subtask_id='EXPENSIVE-001', attempt_kind='blackbox',
            approval_by='user', approval_reason='仅批准既有预算。')
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')

    def test_ordinary_finding_cannot_dispatch_product_fix_during_effect_stop(self):
        failure = self.start_effect_failure()
        ordinary = self.create_attempt('ordinary', approve_budget=True)
        finding = workflow.WorkflowTest.new_finding(self, 'ORDINARY-BYPASS', 'accept-001')
        finding['review_owner'] = legacy.REVIEWER
        self.run_ctl('record-acceptance-findings', subtask_id=ordinary['subtask_id'],
                     result={'written_by': 'accept-001', 'findings': [finding]})
        self.assertIn('ORDINARY-BYPASS', self.state()['findings'])
        self.assertEqual(failure, self.state()['acceptance_gate']['attempts'][1])
        self.assert_effect_stop('dispatch-finding-fix', finding_id='ORDINARY-BYPASS')

    def test_next_round_permission_requires_new_candidate_and_does_not_grant_repair(self):
        failure = self.start_effect_failure()
        completed, approved = self.public_call('record-blackbox-decision', result=self.decision(failure, ['next_round']))
        self.assertEqual(0, completed.returncode, approved)
        self.assert_effect_stop('create-integration-subtask', subtask_id='INTEGRATE-001')
        before = self.state()
        completed, rejected = self.public_call('create-subtask-attempt', subtask_id='EXPENSIVE-001',
            attempt_kind='blackbox', approval_by='user', approval_reason='明确批准既有命令预算。')
        self.assertNotEqual(0, completed.returncode, rejected)
        self.assertRegex(' '.join(rejected['errors']).lower(), 'candidate|prepar')
        self.assertEqual(before, self.state())
        completed, approved = self.public_call('record-blackbox-decision', result=self.decision(failure, ['repair']))
        self.assertEqual(0, completed.returncode, approved)
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')
        source = self.repo / 'candidate-source.py'
        source.write_text(source.read_text() + '\n# Synthetic authorized candidate change.\n')
        result = self.work_result('integration')
        result['changed_files'] = ['candidate-source.py']
        self.run_ctl('record-subtask-result', subtask_id=integration['subtask_id'], result=result)
        self.run_ctl('freeze-candidate')
        self.assertNotEqual(failure['candidate_id'], self.state()['acceptance_gate']['current_candidate']['candidate_id'])
        self.finish_attempt('preparation', approve_budget=True)
        new = self.finish_attempt('blackbox', approve_budget=True)
        self.assertEqual('pass', new['outcome'])
        self.assertEqual(failure['attempt_id'], new['authorization_attempt_id'])
        self.assertEqual(self.state()['acceptance_gate']['attempts'][-2]['attempt_id'], new['preparation_attempt_id'])
        old = self.state()['acceptance_gate']['attempts'][1]
        self.assertEqual('effect_failure', old['outcome'])
        self.assertEqual([['next_round'], ['repair']], [d['allow'] for d in old['decisions']])

    def test_invalid_observation_requires_evidence_then_allows_reprepared_first_round(self):
        self.start_flow()
        self.finish_attempt('preparation')
        attempt = self.create_attempt('blackbox')
        invalid = self.receipt('blackbox', 'environment_failure')
        # Capture every original reference once, before testing the malformed
        # registration. Repairing its classification must reuse this exact run.
        invalid['expensive_acceptance']['evidence_refs'].append('.artifacts/capture-failure.log')
        legacy.attach_acceptance_run(self.repo, attempt['subtask_id'], invalid, create_fixture_files=True)
        run_reference = deepcopy(invalid['expensive_acceptance']['run_evidence'])
        run_manifest = (self.repo / run_reference['path']).read_bytes()
        run_inventory = {path.relative_to(self.repo).as_posix()
                         for path in (self.repo / '.artifacts/synthetic-runs').rglob('manifest.json')}
        before = self.state()
        rejected = self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=invalid, ok=False)
        self.assertRegex(' '.join(rejected['errors']).lower(), 'invalid.observation|evidence|reason')
        self.assertEqual(before, self.state())
        invalid['expensive_acceptance']['invalid_observation'] = {
            'reason': 'evidence_capture', 'evidence_refs': ['.artifacts/capture-failure.log'],
            'summary': '合成观察证据采集失败，不能得出产品效果结论。'}
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=invalid)
        self.assertEqual(run_reference, invalid['expensive_acceptance']['run_evidence'])
        self.assertEqual(run_manifest, (self.repo / run_reference['path']).read_bytes())
        self.assertEqual(run_inventory, {path.relative_to(self.repo).as_posix()
                         for path in (self.repo / '.artifacts/synthetic-runs').rglob('manifest.json')},
                         'Registration correction must not launch a replacement run.')
        preparation = self.finish_attempt('preparation', approve_budget=True)
        valid = self.finish_attempt('blackbox', approve_budget=True)
        self.assertEqual(preparation['attempt_id'], valid['preparation_attempt_id'])
        attempts = self.state()['acceptance_gate']['attempts']
        self.assertEqual(['pass', 'environment_failure', 'pass', 'pass'], [a['outcome'] for a in attempts])
        self.assertEqual(4, sum(a['real_call_count'] for a in attempts))
        self.assertEqual(8, sum(a['duration_seconds'] for a in attempts))
        self.assertNotIn('decisions', attempts[1], '无效观察不是有效效果失败，不需要伪造用户第二轮授权')

    def test_blackbox_creation_without_preparation_is_rejected(self):
        self.start_flow()
        before = self.state()
        completed, payload = self.public_call('create-subtask-attempt',
            subtask_id='EXPENSIVE-001', attempt_kind='blackbox')
        self.assertNotEqual(0, completed.returncode, '没有同候选准备回执却创建了正式黑盒attempt')
        self.assertFalse(payload['ok'], payload)
        self.assertRegex(' '.join(payload['errors']).lower(), 'prepar')
        self.assertEqual(before, self.state())

    def test_preparation_pass_preserves_checks_without_claiming_business_acceptance(self):
        self.start_flow()
        attempt = self.create_attempt('preparation')
        receipt = self.receipt('preparation')
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=receipt)
        saved = self.state()['acceptance_gate']['attempts'][-1]
        self.assertEqual('preparation', saved['kind'])
        self.assertEqual({}, saved['evidence_by_acceptance_id'])
        self.assertEqual(receipt['expensive_acceptance']['preparation'], saved['preparation'])
        self.assertEqual((1, 2), (saved['real_call_count'], saved['duration_seconds']))

    def test_ordinary_pass_covers_only_non_blackbox_acceptance_items(self):
        self.start_flow()
        attempt = self.create_attempt('ordinary')
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=self.receipt('ordinary'))
        saved = self.state()['acceptance_gate']['attempts'][-1]
        self.assertEqual({'REAL-PATH-001'}, set(saved['evidence_by_acceptance_id']))
        self.assertEqual('pass', saved['outcome'])

    def effect_finding(self):
        finding = workflow.WorkflowTest.new_finding(self, 'BBX-EFFECT-REPAIR', 'accept-001')
        finding['acceptance_ids'] = ['BBX-001']
        return {'written_by': 'accept-001', 'findings': [finding]}

    def effect_artifact_snapshot(self):
        paths = ctl._task_paths(self.repo, legacy.TASK_ID)
        return {name: paths[name].read_bytes() for name in
                ('state.json', 'task.md', 'events.jsonl', 'plan.md', 'execution.md', 'acceptance.md')}

    def assert_effect_finding_rejected(self, attempt, receipt=None):
        before = self.effect_artifact_snapshot()
        completed, rejected = self.public_call('record-acceptance-findings',
            subtask_id=attempt['subtask_id'], result=receipt or self.effect_finding())
        self.assertNotEqual(0, completed.returncode, rejected)
        self.assertFalse(rejected['ok'], rejected)
        self.assertEqual(before, self.effect_artifact_snapshot(),
                         'rejected finding must leave all six artifacts unchanged')

    def test_authorized_effect_failure_accepts_original_acceptor_finding_without_rewriting_history(self):
        """L4 repair entry: actual CLI terminal failure plus user repair decision."""
        failure = self.start_effect_failure()
        self.run_ctl('record-blackbox-decision', result=self.decision(failure, ['repair']))
        before = self.state()
        prior_events = (self.repo / f'docs/ai/tasks/{legacy.TASK_ID}/events.jsonl').read_bytes()
        source = next(t for t in before['subtasks'] if t['subtask_id'] == failure['subtask_id'])
        self.assertEqual('blocked', source['status'])
        self.assertEqual('effect_failure', source['result']['expensive_acceptance']['outcome'])
        self.assertEqual(['repair'], before['acceptance_gate']['attempts'][-1]['decisions'][-1]['allow'])
        completed, accepted = self.public_call('record-acceptance-findings',
            subtask_id=failure['subtask_id'], result=self.effect_finding())
        self.assertEqual(0, completed.returncode, accepted)
        self.assertEqual(['BBX-EFFECT-REPAIR'], accepted['finding_ids'])
        after = self.state()
        self.assertEqual(before['acceptance_gate'], after['acceptance_gate'])
        self.assertEqual(before['subtasks'], after['subtasks'])
        self.assertEqual(before['approval'], after['approval'])
        finding = after['findings']['BBX-EFFECT-REPAIR']
        self.assertEqual(ACCEPTOR, finding['discovered_by'])
        self.assertEqual(INTEGRATOR, finding['routed_to'])
        self.assertEqual(failure['candidate_id'], finding['source_candidate_id'])
        self.assertEqual(failure['subtask_id'], finding['source_subtask_id'])
        self.assertEqual('open', finding['status'])
        self.assertTrue((self.repo / f'docs/ai/tasks/{legacy.TASK_ID}/events.jsonl').read_bytes().startswith(prior_events))
        self.run_ctl('validate')
        # Repair alone must never imply permission to start another effect round.
        self.assert_effect_stop('create-subtask-attempt', subtask_id='EXPENSIVE-001',
            attempt_kind='blackbox', approval_by='user', approval_reason='Budget approval only.')

    def test_effect_finding_requires_repair_not_just_next_round_permission(self):
        failure = self.start_effect_failure()
        self.assert_effect_finding_rejected(failure)
        self.run_ctl('record-blackbox-decision', result=self.decision(failure, ['next_round']))
        self.assert_effect_finding_rejected(failure)

    def test_terminal_blackbox_pass_cannot_receive_effect_repair_finding(self):
        self.start_flow()
        self.finish_attempt('preparation')
        passed = self.finish_attempt('blackbox')
        self.assert_effect_finding_rejected(passed)

    def test_terminal_environment_failure_cannot_receive_effect_repair_finding(self):
        self.start_flow()
        self.finish_attempt('preparation')
        attempt = self.create_attempt('blackbox')
        receipt = self.receipt('blackbox', 'environment_failure')
        receipt['expensive_acceptance']['invalid_observation'] = {
            'reason': 'environment', 'evidence_refs': ['.artifacts/environment.log'],
            'summary': 'Synthetic environment failure is not a valid effect observation.'}
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=receipt)
        self.assert_effect_finding_rejected(attempt)

    def test_authorized_effect_finding_rejects_historical_candidate(self):
        failure = self.start_effect_failure()
        self.run_ctl('record-blackbox-decision', result=self.decision(failure, ['repair']))
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')
        source = self.repo / 'candidate-source.py'
        source.write_text(source.read_text() + '\n# Synthetic new candidate, old finding replay forbidden.\n')
        result = self.work_result('integration')
        result['changed_files'] = ['candidate-source.py']
        self.run_ctl('record-subtask-result', subtask_id=integration['subtask_id'], result=result)
        self.run_ctl('freeze-candidate')
        self.assertNotEqual(failure['candidate_id'], self.state()['acceptance_gate']['current_candidate']['candidate_id'])
        self.assert_effect_finding_rejected(failure)

    def test_authorized_effect_finding_rejects_forged_writer_and_proof_author(self):
        failure = self.start_effect_failure()
        self.run_ctl('record-blackbox-decision', result=self.decision(failure, ['repair']))
        receipt = self.effect_finding()
        receipt['written_by'] = 'impl-001'
        self.assert_effect_finding_rejected(failure, receipt)
        receipt = self.effect_finding()
        receipt['findings'][0]['regression_proof']['written_by'] = 'impl-001'
        self.assert_effect_finding_rejected(failure, receipt)

    def test_pending_blackbox_finding_entry_remains_available(self):
        self.start_flow()
        self.finish_attempt('preparation')
        attempt = self.create_attempt('blackbox')
        before = self.state()
        self.run_ctl('record-acceptance-findings', subtask_id=attempt['subtask_id'], result=self.effect_finding())
        after = self.state()
        self.assertEqual(before['acceptance_gate'], after['acceptance_gate'])
        self.assertEqual(before['subtasks'], after['subtasks'])
        self.assertIn('BBX-EFFECT-REPAIR', after['findings'])
        self.run_ctl('validate')


if __name__ == "__main__":
    unittest.main()
