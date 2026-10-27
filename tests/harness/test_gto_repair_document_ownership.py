"""Acceptance finding: historical integration scope cannot transfer discoverer docs."""
import hashlib
import unittest
import test_gto_workflow as workflow

class RepairDocumentOwnershipTest(unittest.TestCase):
    # Run only these tests; the inherited helpers exercise the actual controller CLI.
    def _open_finding(self):
        self.start()
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001',
                     result=self.review_payload(findings=[self.new_finding('DOC-OWNER')], verdict='fail'))
        self.run_ctl('dispatch-finding-fix', finding_id='DOC-OWNER')

    def test_repair_cannot_edit_formal_docs_via_prior_integration_write_scope(self):
        self._open_finding()
        doc = self.repo / 'docs/contract.md'
        doc.write_text(doc.read_text() + '\nOptional explanation written by repair implementer.\n')
        rejected = self.run_ctl('record-finding-fix', finding_id='DOC-OWNER', ok=False, result={
            'summary': 'Optional explanation during code repair', 'changed_files': ['docs/contract.md'],
            'sha256': hashlib.sha256(doc.read_bytes()).hexdigest(), 'verification': 'Red/Green and regression.',
            'checks': self.work_result()['checks'], 'written_by': 'impl-001', 'written_role': 'backend-implementer'})
        self.assertIn('document', str(rejected).lower())

    def test_code_only_repair_keeps_original_integrator_route(self):
        self.start()
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001',
                     result=self.review_payload(findings=[self.new_finding('DOC-OWNER')], verdict='fail'))
        self.fix('DOC-OWNER')
        self.assertEqual('awaiting_re_review', self.state()['findings']['DOC-OWNER']['status'])

    def _extra_path_finding(self, relative, *, reject):
        payload = workflow.workflow_contract()
        payload['acceptance_gate']['candidate_inputs']['code_paths'].append(relative)
        owner = next(t for t in payload['subtasks'] if t['subtask_id'] == 'INTEGRATE-001')
        owner['write_paths'].append(relative)
        reviewer = next(t for t in payload['subtasks'] if t['stage'] == 'pre_acceptance_review')
        reviewer['write_paths'].append(relative)
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md', relative)
        self.init_task(payload)
        self.run_ctl('prepare-workspace')
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        finding = self.new_finding('DOC-OWNER')
        finding['paths'].append(relative)
        finding['regression_proof']['scope'].append(relative)
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=self.review_payload(
            findings=[finding], verdict='fail', covered=['candidate-source.py','candidate-config.json','docs/contract.md',relative]))
        self.run_ctl('dispatch-finding-fix', finding_id='DOC-OWNER')
        path = self.repo / relative
        path.write_text(path.read_text() + 'repair edit\n')
        self.run_ctl('record-finding-fix', finding_id='DOC-OWNER', ok=not reject, result={
            'summary':'Repair change', 'changed_files':[relative],
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'verification':'Red/Green and regression.',
            'checks':self.work_result()['checks'], 'written_by':'impl-001','written_role':'backend-implementer'})

    def test_repair_cannot_rewrite_discoverer_test_even_in_finding_scope(self):
        self._extra_path_finding('tests/test_discoverer.py', reject=True)

    def test_runtime_markdown_is_product_code_not_formal_document(self):
        self._extra_path_finding('skills/example/SKILL.md', reject=False)

for helper in ('setUp','tearDown','run_ctl','init_task','state','git','init_git_checkout',
               'bind','start','integrate','work_result','review_payload','new_finding','fix'):
    setattr(RepairDocumentOwnershipTest, helper, getattr(workflow.WorkflowTest, helper))

if __name__ == '__main__':
    unittest.main()
