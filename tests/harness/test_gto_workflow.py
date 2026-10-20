"""Revision 3 gates exercised through the real controller CLI."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import test_control_plane as legacy


def workflow_contract():
    payload = legacy.expensive_acceptance_contract()
    payload['workflow_revision'] = 3
    payload['initial_test_owners'] = ['TEST-001']
    payload['verification_contract']['review_evidence'] = ['pass_after_fix']
    payload['acceptance_gate']['candidate_inputs']['document_paths'] = ['docs/contract.md']
    tasks = payload['subtasks']
    tasks[0]['write_paths'] = ['candidate-source.py']
    tasks[0]['dependencies'] = ['TEST-001']
    tasks[1].update(subtask_id='INTEGRATE-001', role='backend-implementer', stage='integration',
                    write_paths=['candidate-source.py', 'docs/contract.md'])
    tasks[2]['dependencies'] = ['INTEGRATE-001']
    tasks[-1]['write_paths'] = [f'docs/tasks/{legacy.TASK_ID}']
    tester = deepcopy(tasks[0])
    tester.update(subtask_id='TEST-001', role='tester', dependencies=[], write_paths=[])
    tasks.insert(-1, tester)
    for task in tasks:
        task['planned_agent_key'] = 'initial-tester' if task['subtask_id'] == 'TEST-001' else task['role']
    payload['acceptance_gate']['acceptance_items'][0]['paths'] = ['candidate-source.py', 'candidate-config.json', 'docs/contract.md']
    add_requirement_checklist(payload, 'WORK-001')
    return payload


def add_requirement_checklist(payload, owner):
    acceptance_id = payload['acceptance_gate']['acceptance_items'][0]['acceptance_id']
    payload['decisions'] = [value for value in payload['decisions'] if not value.startswith('REQ-')]
    payload['decisions'].append(f'REQ-01｜完成合成任务的既定业务行为｜落实：{owner}｜验收：{acceptance_id}')


def usage(writer, stage):
    return [{'written_by': writer, 'environment': 'wsl', 'tool': 'CLI',
             'entry': 'python3 candidate-source.py', 'scope': ['candidate-source.py'],
             'result': 'Executed command line boundary.', 'evidence_refs': [f'.artifacts/{stage}.log'],
             'ui_applicability': 'not_applicable', 'ui_not_applicable_reason': 'Only a CLI is exposed.'}]


class WorkflowTest(unittest.TestCase):
    run_ctl = legacy.ControlPlaneContractTest.run_ctl
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state
    item = staticmethod(legacy.ControlPlaneContractTest.item)
    write_state = legacy.ControlPlaneContractTest.write_state
    git = legacy.ControlPlaneContractTest.git
    init_git_checkout = legacy.ControlPlaneContractTest.init_git_checkout

    def setUp(self):
        root = legacy.REPO_ROOT / '.tmp/gto-workflow/implementation'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.input_temp = tempfile.TemporaryDirectory(dir=root)
        self.repo, self.input_dir = Path(self.temp.name), Path(self.input_temp.name)
        self._json_input_index = 0

    def tearDown(self):
        self.input_temp.cleanup()
        self.temp.cleanup()

    def test_revision_three_initializes_without_redundant_stages(self):
        self.init_task(workflow_contract())
        state = self.state()
        self.assertEqual(3, state['workflow_revision'])
        self.assertNotIn('require_independent_final_review', state['review_policy'])
        self.assertEqual(['work', 'integration', 'pre_acceptance_review', 'expensive_acceptance',
                          'work', 'final_documentation'], [t['stage'] for t in state['subtasks']])

    def start(self):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(workflow_contract())
        self.run_ctl('prepare-workspace')

    def published_result(self, key):
        path = legacy.REPO_ROOT / 'skills/global-task-orchestrator/references/revision-3-results.example.json'
        text = json.dumps(json.loads(path.read_text())[key])
        replacements = {
            'tests/fixtures/example/business-input.json': 'candidate-config.json',
            'tests/fixtures/example/cases.json': 'candidate-config.json',
            'docs/tasks/ACTUAL_TASK_ID/acceptance.md': f'docs/tasks/{legacy.TASK_ID}/acceptance.md',
            'modules/example/entry.py': 'candidate-source.py',
            'docs/modules/example/contract/entry.md': 'docs/contract.md',
            'docs/modules/example': 'docs/contract.md',
            'modules/example': 'candidate-source.py',
            'tests/fixtures/example': 'candidate-config.json',
            'BUSINESS-001': 'REAL-PATH-001',
            'ACTUAL_IMPLEMENTER_ID': 'impl-001', 'ACTUAL_REVIEWER_ID': 'review-001',
            'ACTUAL_ACCEPTANCE_ID': 'accept-001', 'ACTUAL_CLOSEOUT_ID': 'docs-001',
            'ACTUAL_COORDINATOR_ID': 'coordinator-001',
        }
        for original, actual in replacements.items():
            text = text.replace(original, actual)
        payload = json.loads(text)
        if isinstance(payload.get("expensive_acceptance"), dict):
            payload["expensive_acceptance"].pop("run_evidence", None)
        return payload

    def test_blackbox_published_results_complete_cli_sequence(self):
        # Exercise the public payloads as controller contracts, not as real business/CFM evidence.
        self.start()
        absolute_brief = self.repo / '.tmp/absolute-brief.md'
        absolute_brief.parent.mkdir(exist_ok=True)
        absolute_brief.write_text('Explicit work assignment\n')
        rejected = self.run_ctl('bind-dispatch', subtask_id='WORK-001', agent_key='backend-implementer',
                                platform_agent_id='impl-001', context_mode='isolated', brief_kind='subtask',
                                brief_path=str(absolute_brief), brief_sha256=hashlib.sha256(absolute_brief.read_bytes()).hexdigest(), ok=False)
        self.assertIn('relative to --repo-root', str(rejected))
        self.assertNotIn('revision=2', str(rejected))
        for ident, key in [('WORK-001', 'work'), ('INTEGRATE-001', 'integration')]:
            self.bind(ident)
            self.run_ctl('record-subtask-result', subtask_id=ident, result=self.published_result(key))
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        brief = self.run_ctl('build-review-brief', subtask_id='REVIEW-SEC-001')['brief']
        file_hash = hashlib.sha256((self.repo / 'candidate-source.py').read_bytes()).hexdigest()
        self.assertEqual(file_hash, next(item['sha256'] for item in brief['source_manifest'] if item['path'] == 'candidate-source.py'))
        self.assertNotEqual(file_hash, brief['candidate_manifest']['candidate-source.py'])
        review = self.published_result('review')
        review['review']['reviewed_candidate_fingerprint'] = brief['candidate_fingerprint']
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=review)
        self.run_ctl('freeze-candidate')
        attempt = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(attempt, agent='accept-001', role='tester')
        acceptance = self.published_result('acceptance_pass')
        evidence_ref = acceptance['review_evidence'].pop('COPY_DECLARED_GENERIC_EVIDENCE_KEY')
        acceptance['review_evidence']['pass_after_fix'] = evidence_ref
        evidence = self.repo / evidence_ref
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text('Synthetic published-payload evidence; not real product acceptance.\n')
        invalid = deepcopy(acceptance)
        invalid['expensive_acceptance']['failed_stage'] = ''
        rejected = self.run_ctl('record-subtask-result', subtask_id=attempt, result=invalid, ok=False)
        self.assertIn('use "none"', ' '.join(rejected['errors']))
        self.run_ctl('record-subtask-result', subtask_id=attempt, result=acceptance)
        path = self.repo / f'docs/tasks/{legacy.TASK_ID}/acceptance.md'
        current = path.read_text()
        marker = '任务尚未完成；需最新候选审查、验收和事实回执。'
        self.assertIn(marker, current)
        path.write_text(current.replace(marker, '业务测试已通过。'))
        rejected = self.run_ctl('accept-artifact-update', ok=False)
        self.assertIn(marker, ' '.join(rejected['errors']))
        path.write_text(current + '\n## 补充事实\n已登记验收证据，等待机械收尾。\n')
        self.run_ctl('accept-artifact-update')
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001', result=self.published_result('final_documentation'))
        self.assertEqual('completed', self.run_ctl('finalize-task')['status'])

    def test_blackbox_block_preserves_inflight_receipt_without_rescheduling(self):
        self.start()
        self.bind('WORK-001')
        blocked = self.published_result('coordinator_blocked')
        self.run_ctl('set-phase', phase='blocked', result=blocked)
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=self.work_result())
        state = self.state()
        self.assertEqual('blocked', state['status'])
        self.assertEqual('human_adjudication', state['next_action']['kind'])
        self.assertEqual(blocked, state['coordinator_blocker']['result'])
        self.run_ctl('validate')
        self.run_ctl('set-phase', phase='planning', result=self.published_result('coordinator_resumed'))
        self.assertEqual('active', self.state()['status'])
        self.bind('INTEGRATE-001')

    def bind(self, subtask_id, *, agent='impl-001', role='backend-implementer', review=False, ok=True):
        if subtask_id == 'WORK-001':
            tester = next(t for t in self.state()['subtasks'] if t['subtask_id'] == 'TEST-001')
            if tester['status'] == 'ready':
                key = tester['planned_agent_key']
                WorkflowTest.bind(self, 'TEST-001', agent='initial-test-001', role=key)
                proof = self.work_result()['checks'][0]
                self.run_ctl('record-subtask-result', subtask_id='TEST-001',
                    result=legacy.result('completed', 'initial-test-001', key, checks=[proof]))
        relative = f'.tmp/brief-{subtask_id}.md'
        path = self.repo / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text(f'Explicit assignment: {subtask_id}\n')
        return self.run_ctl('bind-dispatch', subtask_id=subtask_id, agent_key=role,
                            platform_agent_id=agent, context_mode='isolated',
                            brief_kind='review' if review else 'subtask', brief_path=relative,
                            brief_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ok=ok)

    def work_result(self, stage='work'):
        checks = []
        for purpose in (['red', 'green', 'regression'] if stage == 'work' else ['regression']):
            checks.append({'purpose': purpose, 'command': 'python3 -m unittest test_boundary',
                           'scope': ['candidate-source.py'], 'exit_code': 1 if purpose == 'red' else 0,
                           'expected_exit_code': 1 if purpose == 'red' else 0,
                           'evidence_refs': [f'.artifacts/{purpose}.log']})
        payload = legacy.result('completed', 'impl-001', 'backend-implementer',
                                checks=checks, review_evidence={'pass_after_fix': 'green.log'})
        if stage == 'integration':
            payload['integration'] = {'summary': 'Entry, interfaces, config and failure paths connected.',
                                      'document_paths': ['docs/contract.md']}
        return payload

    def integrate(self):
        self.bind('WORK-001')
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=self.work_result())
        self.bind('INTEGRATE-001')
        self.run_ctl('record-subtask-result', subtask_id='INTEGRATE-001', result=self.work_result('integration'))

    def review_payload(self, subtask_id='REVIEW-SEC-001', *, findings=None, kind='task', verdict='pass', covered=None):
        brief = self.run_ctl('build-review-brief', subtask_id=subtask_id)['brief']
        return {'review': {'kind': kind, 'verdict': verdict, 'reviewer_platform_agent_id': 'review-001',
                           'findings': findings or [], 'reviewed_candidate_fingerprint': brief['candidate_fingerprint'],
                           'covered_paths': covered or ['candidate-source.py', 'candidate-config.json', 'docs/contract.md'],
                           'evidence_refs': ['.artifacts/review.log'],
                           'checks_completed': ['requirements', 'tests', 'boundaries', 'documentation'],
                           'checks_not_run': [], 'usage_evidence': usage('review-001', 'review')}}

    def review(self):
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=self.review_payload())

    def accept(self):
        self.run_ctl('freeze-candidate')
        attempt = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')
        ident = attempt['subtask_id']
        self.bind(ident, agent='accept-001', role='tester')
        payload = legacy.result('completed', 'accept-001', 'tester', expensive_acceptance={
            'outcome': 'pass', 'real_call_count': 1, 'duration_seconds': 1, 'failed_stage': 'none',
            'evidence_refs': ['.artifacts/accept.log'],
            'evidence_by_acceptance_id': {'REAL-PATH-001': ['.artifacts/accept.log']},
            'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'], 'usage_evidence': usage('accept-001', 'accept'),
            'closed_finding_ids': [f['finding_id'] for f in self.state()['findings'].values() if f['status'] == 'awaiting_retest']})
        self.run_ctl('record-subtask-result', subtask_id=ident, result=payload)
        return ident

    def test_work_result_rejects_prose_only_and_empty_checks(self):
        self.start()
        self.bind('WORK-001')
        for checks in (None, []):
            payload = self.work_result()
            if checks is None:
                payload.pop('checks')
            else:
                payload['checks'] = checks
            rejected = self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=payload, ok=False)
            self.assertIn('checks', str(rejected))
        self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=self.work_result())

    def test_latest_candidate_completes_without_post_acceptance_review(self):
        self.start()
        self.integrate()
        self.review()
        self.accept()
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        completed = self.run_ctl('finalize-task')
        self.assertEqual('completed', completed['status'])
        self.assertNotIn('final_review', self.state())

    def test_formal_document_change_invalidates_review_before_freeze(self):
        self.start()
        self.integrate()
        self.review()
        (self.repo / 'docs/contract.md').write_text('Changed substantive contract\n')
        rejected = self.run_ctl('freeze-candidate', ok=False)
        self.assertIn('coverage', str(rejected))

    def test_pre_acceptance_reviewer_cannot_be_implementer(self):
        self.start()
        self.integrate()
        before = self.state()
        rejected = self.bind('REVIEW-SEC-001', role='reviewer', review=True, ok=False)
        self.assertIn('platform identity', str(rejected))
        self.assertEqual(before, self.state(), 'Wrong planned reviewer must be refused before dispatch.')

    def new_finding(self, ident, discoverer='review-001'):
        item = legacy.finding(ident)
        item['paths'] = ['candidate-source.py']
        if discoverer == 'accept-001':
            item['acceptance_ids'] = ['REAL-PATH-001']
        item['fix_plan'] = 'Implement the existing documented boundary without weakening tests.'
        item['documentation_update'] = {'written_by': discoverer, 'status': 'not_applicable', 'paths': [], 'reason': 'Existing contract already specifies the boundary.'}
        item['root_cause'] = 'Implementation omits the input boundary check.'
        item['regression_proof'] = {'written_by': discoverer, 'command': 'python3 -m unittest test_boundary',
                                    'scope': ['candidate-source.py'], 'exit_code': 1, 'expected_exit_code': 1,
                                    'evidence_refs': ['.artifacts/repro.log']}
        return item

    def fix(self, ident):
        self.run_ctl('dispatch-finding-fix', finding_id=ident)
        source = self.repo / 'candidate-source.py'
        source.write_text(source.read_text() + f'fix {ident}\n')
        self.run_ctl('record-finding-fix', finding_id=ident, result={
            'summary': f'Fix root cause {ident}', 'changed_files': ['candidate-source.py'],
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'verification': 'Focused Red/Green and regression.',
            'checks': self.work_result()['checks'], 'written_by': 'impl-001', 'written_role': 'backend-implementer'})

    def reintegrate(self):
        source = [t for t in self.state()['subtasks'] if t['stage'] == 'integration'][-1]['subtask_id']
        ident = self.run_ctl('create-integration-subtask', subtask_id=source)['subtask_id']
        self.bind(ident)
        self.run_ctl('record-subtask-result', subtask_id=ident, result=self.work_result('integration'))

    def rereview(self, source, closed, new=None):
        ident = self.run_ctl('create-re-review-subtask', subtask_id=source)['subtask_id']
        self.bind(ident, agent='review-001', role='reviewer', review=True)
        findings = [{'finding_id': name, 'status': 'closed'} for name in closed]
        findings.extend(new or [])
        self.run_ctl('record-review-result', subtask_id=ident,
                     result=self.review_payload(ident, kind='re_review', verdict='fail' if new else 'pass', findings=findings))
        return ident

    def test_batch_review_new_finding_and_acceptance_failure_reach_completion(self):
        self.start()
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=self.review_payload(
            verdict='fail', findings=[self.new_finding('F-1'), self.new_finding('F-2')]))
        self.fix('F-1')
        self.fix('F-2')
        self.reintegrate()
        review2 = self.rereview('REVIEW-SEC-001', ['F-1', 'F-2'], [self.new_finding('F-3')])
        self.fix('F-3')
        self.reintegrate()
        self.rereview(review2, ['F-3'])
        self.run_ctl('freeze-candidate')
        first = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(first, agent='accept-001', role='tester')
        finding = self.new_finding('A-1', 'accept-001')
        finding['review_owner'] = legacy.REVIEWER
        self.run_ctl('record-acceptance-findings', subtask_id=first,
                     result={'written_by': 'accept-001', 'findings': [finding]})
        self.run_ctl('record-subtask-result', subtask_id=first, result=legacy.result('blocked', 'accept-001', 'tester',
            expensive_acceptance={'outcome': 'product_failure', 'real_call_count': 1, 'duration_seconds': 1,
                                 'failed_stage': 'boundary', 'evidence_refs': ['.artifacts/failure.log'],
                                 'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'], 'usage_evidence': usage('accept-001', 'accept'),
                                 'evidence_by_acceptance_id': {}, 'finding_id': 'A-1'}))
        self.fix('A-1')
        self.reintegrate()
        self.run_ctl('create-re-review-subtask', subtask_id=first, ok=False)
        self.accept()
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001', result=legacy.result('completed', 'docs-001', 'doc-curator'))
        self.run_ctl('finalize-task')
        state = self.state()
        self.assertEqual(4, len(state['findings']))
        self.assertTrue(all(f['status'] == 'closed' for f in state['findings'].values()))
        self.assertEqual(['product_failure', 'pass'], [a['outcome'] for a in state['acceptance_gate']['attempts']])
        self.assertEqual('accept-001', state['findings']['A-1']['discovered_by']['platform_agent_id'])
        self.assertEqual('accept-001', state['findings']['A-1']['lineage']['original_reviewer']['platform_agent_id'])

    def test_new_integration_preserves_responsible_identity(self):
        self.start()
        self.integrate()
        ident = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')['subtask_id']
        relative = '.tmp/other-integrator.md'
        path = self.repo / relative
        path.write_text('Different identity cannot silently replace integration owner.')
        rejected = self.run_ctl('bind-dispatch', subtask_id=ident, agent_key='backend-implementer',
            platform_agent_id='other-impl', context_mode='isolated', brief_kind='subtask',
            brief_path=relative, brief_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ok=False)
        self.assertIn('integration owner', str(rejected))

    def test_scoped_acceptance_repair_and_wording_closeout_cli(self):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        contract = workflow_contract()
        contract['acceptance_gate']['acceptance_items'] = [
            {'acceptance_id': 'REAL-PATH-001', 'evidence_refs': [], 'paths': ['candidate-source.py', 'docs/contract.md']},
            {'acceptance_id': 'UNCHANGED-002', 'evidence_refs': [], 'paths': ['candidate-config.json']}]
        contract['subtasks'][-1]['write_paths'] = ['docs']
        self.init_task(contract)
        self.run_ctl('prepare-workspace')
        self.integrate()
        self.review()
        self.run_ctl('freeze-candidate')
        first = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(first, agent='accept-001', role='tester')
        self.run_ctl('record-acceptance-findings', subtask_id=first,
            result={'written_by': 'accept-001', 'findings': [self.new_finding('SCOPED-1', 'accept-001')]})
        self.run_ctl('record-subtask-result', subtask_id=first,
            result=legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance={
                'outcome': 'product_failure', 'real_call_count': 2, 'duration_seconds': 1,
                'failed_stage': 'boundary', 'evidence_refs': ['.artifacts/first.log'],
                'finding_id': 'SCOPED-1', 'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001', 'UNCHANGED-002'],
                'usage_evidence': usage('accept-001', 'first'),
                'evidence_by_acceptance_id': {'UNCHANGED-002': ['.artifacts/unchanged.log']}}))
        self.fix('SCOPED-1')
        self.run_ctl('freeze-candidate', ok=False)  # New integration is mandatory even after repair.
        self.reintegrate()
        self.run_ctl('create-re-review-subtask', subtask_id=first, ok=False)
        self.run_ctl('freeze-candidate')
        second = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(second, agent='accept-001', role='tester')
        evidence = {'outcome': 'pass', 'real_call_count': 1, 'duration_seconds': 1, 'failed_stage': 'none',
            'evidence_refs': ['.artifacts/retest.log'], 'mode': 'scoped', 'scope_acceptance_ids': ['REAL-PATH-001'],
            'usage_evidence': usage('accept-001', 'retest'), 'closed_finding_ids': ['SCOPED-1'],
            'impact': {'changed_paths': ['candidate-source.py'], 'affected_acceptance_ids': ['REAL-PATH-001'], 'reason': 'Only the boundary adapter changed.'},
            'retained_evidence_by_acceptance_id': {'UNCHANGED-002': {'source_attempt_id': 'attempt-1', 'evidence_refs': ['.artifacts/unchanged.log'], 'reason': 'Configuration dependency is byte-identical.'}},
            'evidence_by_acceptance_id': {'REAL-PATH-001': ['.artifacts/retest.log'], 'UNCHANGED-002': ['.artifacts/unchanged.log']}}
        hidden = deepcopy(evidence)
        hidden['impact']['changed_paths'] = []
        self.run_ctl('record-subtask-result', subtask_id=second,
            result=legacy.result('completed', 'accept-001', 'tester', expensive_acceptance=hidden), ok=False)
        self.run_ctl('record-subtask-result', subtask_id=second,
            result=legacy.result('completed', 'accept-001', 'tester', expensive_acceptance=evidence))
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        document = self.repo / 'docs/contract.md'
        document.write_text(document.read_text() + '\nClarifies the existing command line entry.\n')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
            result=legacy.result('completed', 'docs-001', 'doc-curator', changed_files=['docs/contract.md'],
                documentation_sync={'checked_paths': ['docs/contract.md'], 'changed_paths': ['docs/contract.md'],
                    'behavior_changed': False, 'contract_changed': False, 'configuration_changed': False,
                    'reason': 'Wording only; commands, inputs, outputs and requirements are unchanged.'}))
        self.run_ctl('finalize-task')
        state = self.state()
        self.assertEqual('closed', state['findings']['SCOPED-1']['status'])
        self.assertEqual('attempt-2', state['findings']['SCOPED-1']['closed_by_attempt_id'])
        self.assertEqual(1, len([t for t in state['subtasks'] if t['stage'] == 'pre_acceptance_review']))

    def test_normal_result_cannot_bypass_independent_review_action(self):
        self.start()
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        rejected = self.run_ctl('record-subtask-result', subtask_id='REVIEW-SEC-001',
            result=legacy.result('completed', 'review-001', 'reviewer'), ok=False)
        self.assertIn('record-review-result', str(rejected))

    def test_scope_re_review_covers_new_configuration_without_reopening_terminal_subtasks(self):
        self.start()
        self.integrate()
        self.review()
        (self.repo / 'candidate-config.json').write_text('{"new_input": true}\n')
        self.reintegrate()
        self.rereview('REVIEW-SEC-001', [])
        self.run_ctl('freeze-candidate')

    def test_checks_with_failed_green_cannot_complete_work(self):
        self.start()
        self.bind('WORK-001')
        payload = self.work_result()
        payload['checks'][1].update(exit_code=1, expected_exit_code=1)
        rejected = self.run_ctl('record-subtask-result', subtask_id='WORK-001', result=payload, ok=False)
        self.assertIn('zero', str(rejected))

    def test_finding_proof_must_come_from_discoverer(self):
        self.start()
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        finding = self.new_finding('F-wrong', 'impl-001')
        rejected = self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001',
            result=self.review_payload(verdict='fail', findings=[finding]), ok=False)
        self.assertIn('discoverer', str(rejected))

    def test_closeout_cannot_write_substantive_formal_documents(self):
        payload = workflow_contract()
        payload['subtasks'][-1]['write_paths'] = ['docs']
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(payload)
        self.run_ctl('prepare-workspace')
        self.integrate()
        self.review()
        self.accept()
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        result = legacy.result('completed', 'docs-001', 'doc-curator', changed_files=['docs/contract.md'])
        (self.repo / 'docs/contract.md').write_text('New behavior: accepts inputs previously rejected.\n')
        result['documentation_sync'] = {'checked_paths': ['docs/contract.md'], 'changed_paths': ['docs/contract.md'],
            'behavior_changed': True, 'contract_changed': True, 'configuration_changed': False,
            'reason': 'Changes the documented accepted inputs; requires actual re-acceptance.'}
        rejected = self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001', result=result, ok=False)
        self.assertIn('return to acceptance', str(rejected))

    def start_with_discoverer_test_scope(self):
        payload = workflow_contract()
        payload['acceptance_gate']['candidate_inputs']['code_paths'].append('tests')
        payload['subtasks'][2]['write_paths'] = ['tests']
        payload['subtasks'][3]['write_paths'] = ['tests']
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.init_task(payload)
        self.run_ctl('prepare-workspace')
        self.integrate()

    def add_regression_test(self, name):
        path = self.repo / 'tests' / name
        path.parent.mkdir(exist_ok=True)
        path.write_text('assert False, "reproduces boundary defect"\n')

    def test_reviewer_can_record_failure_after_adding_its_regression_test(self):
        self.start_with_discoverer_test_scope()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.add_regression_test('test_review_boundary.py')
        payload = self.review_payload(verdict='fail', findings=[self.new_finding('F-proof')],
                                      covered=['candidate-source.py', 'candidate-config.json', 'docs/contract.md', 'tests'])
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=payload)
        self.assertEqual('open', self.state()['findings']['F-proof']['status'])
        self.run_ctl('freeze-candidate', ok=False)

    def test_acceptance_failure_can_be_recorded_after_discoverer_adds_test(self):
        self.start_with_discoverer_test_scope()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=self.review_payload(
            covered=['candidate-source.py', 'candidate-config.json', 'docs/contract.md', 'tests']))
        self.run_ctl('freeze-candidate')
        attempt = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')
        ident = attempt['subtask_id']
        self.bind(ident, agent='accept-001', role='tester')
        self.add_regression_test('test_acceptance_boundary.py')
        finding = self.new_finding('A-proof', 'accept-001')
        finding['review_owner'] = legacy.REVIEWER
        self.run_ctl('record-acceptance-findings', subtask_id=ident,
                     result={'written_by': 'accept-001', 'findings': [finding]})
        self.run_ctl('record-subtask-result', subtask_id=ident, result=legacy.result('blocked', 'accept-001', 'tester',
            expensive_acceptance={'outcome': 'product_failure', 'real_call_count': 1, 'duration_seconds': 1,
                                 'failed_stage': 'boundary', 'evidence_refs': ['.artifacts/failure.log'],
                                 'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'], 'usage_evidence': usage('accept-001', 'accept'),
                                 'evidence_by_acceptance_id': {}, 'finding_id': 'A-proof'}))
        state = self.state()
        self.assertEqual(attempt['attempt']['candidate_id'], state['acceptance_gate']['attempts'][0]['candidate_id'])
        self.assertEqual('product_failure', state['acceptance_gate']['attempts'][0]['outcome'])
        self.run_ctl('finalize-task', ok=False)

    def test_rework_required_work_cannot_be_omitted_from_later_gate(self):
        self.start()
        self.integrate()
        state = self.state()
        missing = deepcopy(state['subtasks'][0])
        missing.update(subtask_id='WORK-LATE', status='ready')
        missing.pop('dispatch')
        missing.pop('result')
        state['subtasks'].append(missing)
        self.write_state(state)  # Malformed test data must not bypass the downstream gate.
        rejected = self.run_ctl('freeze-candidate', ok=False)
        self.assertIn('work', str(rejected).lower())

    def test_rework_acceptance_test_scope_and_evidence_log_boundary(self):
        base_repo = self.repo
        for scope, accepted in [('tests/acceptance-regression', False),
                                ('.tmp/proof.py', False), ('.artifacts/folder.log', False),
                                ('.artifacts/acceptance.log', True)]:
            with self.subTest(scope=scope), tempfile.TemporaryDirectory(dir=base_repo) as directory:
                self.repo = Path(directory)
                (self.repo / '.artifacts/folder.log').mkdir(parents=True)
                payload = workflow_contract()
                payload['subtasks'][3]['write_paths'] = [scope]
                self.run_ctl('init-task', contract=payload, title='Acceptance proof scope',
                             owner='coordinator', ok=accepted)
        self.repo = base_repo

    def test_rework_documented_cli_uses_loaded_skill_outside_consumer_project(self):
        import os
        import shutil
        import subprocess
        skill = self.input_dir / 'loaded-runtime/skills/global-task-orchestrator'
        shutil.copytree(legacy.REPO_ROOT / 'skills/global-task-orchestrator', skill,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.assertTrue((skill / 'schemas/orchestrator-task-state.schema.json').is_file())
        self.assertFalse((skill.parents[1] / 'schemas').exists())
        contract_input = self.repo / '.tmp/revision-3-contract.example.json'
        contract_input.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(skill / 'references/revision-3-contract.example.json', contract_input)
        documentation = (legacy.REPO_ROOT / 'skills/global-task-orchestrator/references/controller-guide.md').read_text().replace('\\\n', ' ')
        env = dict(os.environ, GTO_SKILL_DIR=str(skill), GTO_CONTROLLER=str(skill / 'scripts/orchestrator_ctl.py'),
                   CODEX_HOME=str(self.input_dir / 'different-codex-home'), repo_root=str(self.repo),
                   task_id='20300102-030405-example-task', title='Portable CLI proof', owner='coordinator',
                   contract_json_file=str(contract_input))
        for action in ('new-task', 'init-task'):
            command = next(line for line in documentation.splitlines()
                           if line.startswith('python3 ') and f'--action {action}' in line)
            completed = subprocess.run(['bash', '-c', command], cwd=self.repo, env=env, text=True, capture_output=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertFalse((self.repo / 'skills').exists())
        self.assertTrue((self.repo / 'docs/ai/tasks/20300102-030405-example-task/state.json').is_file())
