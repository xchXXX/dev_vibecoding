"""Independent review proofs. Agent identities below are explicit CLI test fixtures.

These tests run the source CLI in disposable consumer repositories. They do not
claim model-authored workflow behavior or Browser/Computer Use evidence.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import test_control_plane as legacy
import test_gto_workflow as workflow


class IndependentReviewTest(unittest.TestCase):
    init_task = legacy.ControlPlaneContractTest.init_task
    state = legacy.ControlPlaneContractTest.state
    git = legacy.ControlPlaneContractTest.git
    init_git_checkout = legacy.ControlPlaneContractTest.init_git_checkout
    bind = workflow.WorkflowTest.bind
    start = workflow.WorkflowTest.start
    work_result = workflow.WorkflowTest.work_result
    integrate = workflow.WorkflowTest.integrate
    review_payload = workflow.WorkflowTest.review_payload
    review = workflow.WorkflowTest.review
    fix = workflow.WorkflowTest.fix
    reintegrate = workflow.WorkflowTest.reintegrate
    new_finding = workflow.WorkflowTest.new_finding
    accept = workflow.WorkflowTest.accept

    def run_ctl(self, action, **kwargs):
        # Keep action/results and real temporary consumer paths for audit. The
        # underlying helper launches the source CLI with subprocess.run.
        entry = {'action': action, 'consumer': str(self.repo), 'arguments': kwargs}
        try:
            value = legacy.ControlPlaneContractTest.run_ctl(self, action, **kwargs)
            entry['output'] = value
            return value
        except AssertionError as error:
            entry['assertion'] = str(error)
            raise
        finally:
            path = legacy.REPO_ROOT / '.artifacts/review-acceptance-routing/review' / (self._testMethodName + '.jsonl')
            with path.open('a') as stream:
                stream.write(json.dumps(entry) + '\n')

    def setUp(self):
        root = legacy.REPO_ROOT / '.tmp/review-acceptance-routing/review'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.input_temp = tempfile.TemporaryDirectory(dir=root)
        self.repo, self.input_dir = Path(self.temp.name), Path(self.input_temp.name)
        self._json_input_index = 0

    def tearDown(self):
        self.input_temp.cleanup()
        self.temp.cleanup()

    def test_rar_001_equivalent_test_writer_paths_must_not_overlap(self):
        payload = workflow.workflow_contract()
        first = next(t for t in payload['subtasks'] if t['subtask_id'] == 'TEST-001')
        first['write_paths'] = ['tests/shared.py']
        second = deepcopy(first)
        second.update(subtask_id='TEST-002', write_paths=['tests/./shared.py'])
        payload['subtasks'].insert(-1, second)
        payload['initial_test_owners'].append('TEST-002')
        payload['subtasks'][0]['dependencies'].append('TEST-002')
        payload['acceptance_gate']['candidate_inputs']['code_paths'].append('tests')
        self.run_ctl('init-task', contract=payload, title='Equivalent writer paths',
                     owner='main-coordinator', ok=False)

    def test_rar_002_same_acceptance_finding_can_fail_retest_and_reopen(self):
        self.start()
        self.integrate()
        self.review()
        self.run_ctl('freeze-candidate')
        first = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(first, agent='accept-001', role='tester')
        finding = self.new_finding('RAR-REPEATED', 'accept-001')
        self.run_ctl('record-acceptance-findings', subtask_id=first,
                     result={'written_by': 'accept-001', 'findings': [finding]})
        evidence = {'outcome': 'product_failure', 'real_call_count': 1, 'duration_seconds': 1,
                    'failed_stage': 'boundary', 'evidence_refs': ['.artifacts/first.log'],
                    'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'],
                    'usage_evidence': workflow.usage('accept-001', 'accept'),
                    'evidence_by_acceptance_id': {}, 'finding_id': 'RAR-REPEATED'}
        self.run_ctl('record-subtask-result', subtask_id=first,
                     result=legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance=evidence))
        self.fix('RAR-REPEATED')
        self.reintegrate()
        self.run_ctl('freeze-candidate')
        second = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        self.bind(second, agent='accept-001', role='tester')
        # The same original acceptor observes the exact defect again. The stable
        # ID must reopen; creating a duplicate ID loses fix-round/history limits.
        self.run_ctl('record-acceptance-findings', subtask_id=second,
                     result={'written_by': 'accept-001', 'findings': [finding]})
        self.run_ctl('record-subtask-result', subtask_id=second,
                     result=legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance=evidence))
        self.assertEqual('open', self.state()['findings']['RAR-REPEATED']['status'])
        self.run_ctl('dispatch-finding-fix', finding_id='RAR-REPEATED')
        self.assertEqual(2, self.state()['findings']['RAR-REPEATED']['fix_round'])

    def test_rar_001_symlink_test_writer_paths_must_not_overlap(self):
        tests = self.repo / 'tests'
        tests.mkdir()
        (tests / 'shared.py').write_text('# shared test fixture\n')
        (tests / 'alias.py').symlink_to('shared.py')
        payload = workflow.workflow_contract()
        first = next(t for t in payload['subtasks'] if t['subtask_id'] == 'TEST-001')
        first['write_paths'] = ['tests/shared.py']
        second = deepcopy(first)
        second.update(subtask_id='TEST-002', write_paths=['tests/alias.py'])
        payload['subtasks'].insert(-1, second)
        payload['initial_test_owners'].append('TEST-002')
        payload['subtasks'][0]['dependencies'].append('TEST-002')
        payload['acceptance_gate']['candidate_inputs']['code_paths'].append('tests')
        self.run_ctl('init-task', contract=payload, title='Symlink writer paths',
                     owner='main-coordinator', ok=False)

    def test_rar_003_gto_documentation_keeps_native_gui_boundary(self):
        doc = (legacy.REPO_ROOT / 'docs/CODEX_COMPAT.md').read_text()
        section = doc.split('## Revision 3 行为证据与版本一致性', 1)[1]
        self.assertNotIn('computer_use_wsl', section)
        self.assertIn('Windows-native Agent environment', section)

    def test_rar_004_document_receipt_cannot_forgive_changed_code(self):
        self.start()
        self.integrate()
        self.review()
        self.accept()
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001',
                     result=legacy.result('completed', 'docs-001', 'doc-curator'))
        path = self.repo / 'candidate-source.py'
        path.write_text('unreviewed executable behavior\n')
        actual = self.run_ctl('build-review-brief', subtask_id='REVIEW-SEC-001')['brief']['candidate_fingerprint']
        state = self.state()
        gate = state['acceptance_gate']
        gate['documentation_sync'] = {
            'before_fingerprint': gate['current_candidate']['fingerprint'],
            'after_fingerprint': actual,
            'coverage_inputs_sha256': gate['attempts'][0]['coverage_inputs_sha256'],
            'written_by': 'docs-001', 'changed_paths': ['candidate-source.py'],
            'reason': 'Forged wording-only receipt; there was no documentation result for this delta.'}
        legacy.ControlPlaneContractTest.write_state(self, state)
        self.run_ctl('finalize-task', ok=False)

    def test_rar_005_acceptor_cannot_reuse_integrator_identity(self):
        self.start()
        self.integrate()
        self.review()
        self.run_ctl('freeze-candidate')
        attempt = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['subtask_id']
        relative = '.tmp/acceptor-brief.md'
        path = self.repo / relative
        path.write_text('Independent acceptance of the integrated candidate.\n')
        self.run_ctl('bind-dispatch', subtask_id=attempt, agent_key='tester',
                     platform_agent_id='impl-001', context_mode='isolated',
                     brief_kind='subtask', brief_path=relative,
                     brief_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ok=False)


if __name__ == '__main__':
    unittest.main()
