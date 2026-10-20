"""Run the portable ten-plus-two demo using public controller commands.

Governance roles/receipts below are synthetic demo fixtures. Only the business
check executions, counts, raw observations and controller decisions are real.
Run this only in a NEW disposable directory, never an existing project.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE / 'scripts'))
from runtime_evidence import run_command, acceptance_binding, digest
TASK_ID = 'point-acceptance-demo'

def result(status: str, written_by: str, written_role: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status, "summary": "Synthetic demo governance receipt; not an independent human/agent review.", "changed_files": [],
        "planned_files_not_changed": [], "verification": {"commands": ["fixture-check"], "result": "passed"},
        "deviations": [], "blocked_by": ["fixture"] if status == "blocked" else [], "risks": [], "follow_up": [],
        "written_by": written_by, "written_role": written_role,
    }
    payload.update(extra)
    return payload


def usage(writer, stage):
    return [{'written_by': writer, 'environment': 'other', 'tool': 'CLI',
             'entry': 'python3 candidate-source.py', 'scope': ['candidate-source.py'],
             'result': 'Executed command line boundary.', 'evidence_refs': [f'.artifacts/{stage}.log'],
             'ui_applicability': 'not_applicable', 'ui_not_applicable_reason': 'Only a CLI is exposed.'}]

FINDING = {'finding_id': 'POINT-FAIL', 'severity': 'high', 'paths': ['candidate-source.py'], 'summary': 'Configured value failed its check.', 'evidence': 'Raw observation contains input, actual and expected values.', 'status': 'open', 'routed_to': {'agent_key': 'backend-implementer', 'platform_agent_id': 'impl-001'}}

class Demo:
    def bind(self, subtask_id, *, agent='impl-001', role='backend-implementer', review=False, ok=True):
        if subtask_id == 'WORK-001':
            tester = next(t for t in self.state()['subtasks'] if t['subtask_id'] == 'TEST-001')
            if tester['status'] == 'ready':
                key = tester['planned_agent_key']
                self.bind('TEST-001', agent='initial-test-001', role=key)
                proof = self.work_result()['checks'][0]
                self.run_ctl('record-subtask-result', subtask_id='TEST-001',
                    result=result('completed', 'initial-test-001', key, checks=[proof]))
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
        payload = result('completed', 'impl-001', 'backend-implementer',
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

    def reintegrate(self):
        source = [t for t in self.state()['subtasks'] if t['stage'] == 'integration'][-1]['subtask_id']
        ident = self.run_ctl('create-integration-subtask', subtask_id=source)['subtask_id']
        self.bind(ident)
        self.run_ctl('record-subtask-result', subtask_id=ident, result=self.work_result('integration'))

    def new_finding(self, ident, discoverer='review-001'):
        item = deepcopy(FINDING); item["finding_id"] = ident
        item['paths'] = ['candidate-source.py']
        if discoverer == 'accept-001':
            item['acceptance_ids'] = [self.config['initial_failure']]
        item['fix_plan'] = 'Implement the existing documented boundary without weakening tests.'
        item['documentation_update'] = {'written_by': discoverer, 'status': 'not_applicable', 'paths': [], 'reason': 'Existing contract already specifies the boundary.'}
        item['root_cause'] = 'Implementation omits the input boundary check.'
        item['regression_proof'] = {'written_by': discoverer, 'command': 'python3 -m unittest test_boundary',
                                    'scope': ['candidate-source.py'], 'exit_code': 1, 'expected_exit_code': 1,
                                    'evidence_refs': ['.artifacts/repro.log']}
        return item


    def __init__(self, repo, config):
        self.repo, self.config = repo, config
        self.ids = [p['acceptance_id'] for p in config['contract']['acceptance_gate']['acceptance_items']]
        self.index = 0

    def write(self, path, value):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        return target

    def state(self):
        return json.loads((self.repo / f'docs/ai/tasks/{TASK_ID}/state.json').read_text())

    def run_ctl(self, action, **kwargs):
        command = [sys.executable, str(PACKAGE / 'scripts/orchestrator_ctl.py'),
                   '--action', action, '--repo-root', str(self.repo), '--task-id', TASK_ID, '--json']
        for key, value in kwargs.items():
            if key == 'ok':
                continue
            if key in {'result', 'contract'}:
                self.index += 1
                value = self.write(f'.tmp/receipts/{self.index}.json', value)
                key += '_json_file'
            command += ['--' + key.replace('_', '-'), str(value)]
        completed = subprocess.run(command, cwd=self.repo, text=True, capture_output=True)
        with (self.repo / '.artifacts/commands.jsonl').open('a') as log:
            log.write(json.dumps({'action': action, 'exit_code': completed.returncode,
                                  'stdout': completed.stdout, 'stderr': completed.stderr}) + '\n')
        if completed.returncode:
            raise RuntimeError(action + ': ' + completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def begin(self):
        self.repo.mkdir(parents=True, exist_ok=False)
        (self.repo / '.artifacts').mkdir()
        shutil.copyfile(Path(__file__).with_name('check_points.py'), self.repo / 'candidate-source.py')
        grouped = {}
        for ident, path in self.config['inputs'].items():
            grouped.setdefault(path, {})[ident] = ident != self.config['initial_failure']
        for path, values in grouped.items():
            self.write(path, values)
        self.write('candidate-config.json', {'inputs': self.config['inputs']})
        document = self.repo / 'docs/contract.md'
        document.parent.mkdir()
        document.write_text('Demo: each configured value must be true.\n')
        for args in [('init', '-b', 'main'), ('config', 'user.email', 'demo@example.invalid'),
                     ('config', 'user.name', 'Portable Demo'), ('add', '.'), ('commit', '-m', 'demo baseline')]:
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
        contract = deepcopy(self.config['contract'])
        # Replace the sample task identifier only in its declared documentation paths.
        contract['subtasks'][-1]['write_paths'] = [f'docs/tasks/{TASK_ID}']
        self.run_ctl('init-task', contract=contract, title='Portable point acceptance demo', owner='demo-coordinator')
        self.run_ctl('prepare-workspace')
        self.integrate()
        self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
        covered = ['candidate-source.py', 'candidate-config.json', 'docs/contract.md', *sorted(set(self.config['inputs'].values()))]
        self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=self.review_payload(covered=covered))
        self.run_ctl('freeze-candidate')

    def execute(self, close=False):
        attempt = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001')['attempt']
        scope = attempt['scope_acceptance_ids']
        self.bind(attempt['subtask_id'], agent='accept-001', role='tester')
        output = f'.artifacts/observations/{attempt["attempt_id"]}'
        refs = [f'{output}/{ident}.json' for ident in scope]
        values = {'python': sys.executable, 'scope': json.dumps(scope), 'output': output}
        command = [arg.format(**values) for arg in self.config['entry']]
        started = time.monotonic()
        run = run_command(self.repo / '.artifacts/runs', command, cwd=self.repo,
            binding=acceptance_binding(self.state(), attempt['subtask_id']), evidence_paths=refs)
        rows = [{'acceptance_id': ident, 'status': json.loads((self.repo / ref).read_text())['status'],
                 'evidence_refs': [ref]} for ident, ref in zip(scope, refs)]
        failures = [row['acceptance_id'] for row in rows if row['status'] == 'fail']
        outcome = 'product_failure' if failures else 'partial_pass' if len(scope) < len(self.ids) else 'pass'
        evidence = {'outcome': outcome, 'real_call_count': len(scope), 'duration_seconds': time.monotonic() - started,
            'failed_stage': 'check' if failures else 'none', 'mode': 'full' if len(scope) == len(self.ids) else 'scoped',
            'scope_acceptance_ids': scope, 'point_results': rows, 'evidence_refs': refs,
            'evidence_by_acceptance_id': {r['acceptance_id']: r['evidence_refs'] for r in rows if r['status'] == 'pass'},
            'usage_evidence': [{'written_by': 'accept-001', 'environment': 'other', 'tool': 'CLI',
                'entry': ' '.join(command), 'scope': scope, 'result': outcome, 'evidence_refs': refs,
                'ui_applicability': 'not_applicable', 'ui_not_applicable_reason': 'Configured CLI example.'}],
            'run_evidence': {'path': (run / 'manifest.json').relative_to(self.repo).as_posix(),
                             'sha256': digest((run / 'manifest.json').read_bytes())}}
        if failures:
            finding = self.new_finding('POINT-FAIL', 'accept-001')
            finding.update(paths=[self.config['repair_path']], acceptance_ids=failures)
            finding['regression_proof'].update(command=' '.join(command), scope=[self.config['repair_path']], evidence_refs=refs)
            self.run_ctl('record-acceptance-findings', subtask_id=attempt['subtask_id'],
                         result={'written_by': 'accept-001', 'findings': [finding]})
            evidence['finding_id'] = 'POINT-FAIL'
        if close:
            evidence['closed_finding_ids'] = ['POINT-FAIL']
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'],
            result=result('blocked' if failures else 'completed', 'accept-001', 'tester', expensive_acceptance=evidence))
        return attempt

    def demonstrate(self):
        self.begin()
        first = self.execute()
        initial = self.run_ctl('acceptance-status')
        assert sum(p['status'] == 'pass' for p in initial['points'].values()) == len(self.ids) - 1
        self.run_ctl('dispatch-finding-fix', finding_id='POINT-FAIL')
        repair = self.repo / self.config['repair_path']
        values = json.loads(repair.read_text())
        values[self.config['initial_failure']] = True
        self.write(self.config['repair_path'], values)
        self.run_ctl('record-finding-fix', finding_id='POINT-FAIL', result={
            'summary': 'Correct the configured shared input.', 'changed_files': [self.config['repair_path']],
            'sha256': digest(repair.read_bytes()), 'verification': 'Input value corrected; functional retest follows.',
            'checks': self.work_result()['checks'], 'written_by': 'impl-001', 'written_role': 'backend-implementer'})
        self.reintegrate()
        self.run_ctl('freeze-candidate')
        pending = self.run_ctl('acceptance-status')
        assert pending['rerun_acceptance_ids'] == self.config['expected_retest'], pending
        second = self.execute(close=True)
        coverage = self.run_ctl('acceptance-status')
        assert coverage['complete'], coverage
        retained = [i for i, p in coverage['points'].items() if p['source_attempt_id'] == first['attempt_id']]
        assert len(retained) == len(self.ids) - len(self.config['expected_retest'])
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        self.run_ctl('record-subtask-result', subtask_id='DOC-FINAL-001', result=result('completed', 'docs-001', 'doc-curator'))
        final = self.run_ctl('finalize-task')
        calls = len((self.repo / '.artifacts/executions.jsonl').read_text().splitlines())
        assert calls == len(self.ids) + len(self.config['expected_retest'])
        launches = list((self.repo / '.artifacts/runs').rglob('manifest.json'))
        assert len(launches) == 2, launches
        summary = {'status': final['status'], 'first_execution': len(self.ids),
                   'second_scope': second['scope_acceptance_ids'], 'retained': retained,
                   'business_calls': calls, 'process_launches': len(launches), 'third_run': len(launches) > 2,
                   'governance': 'Synthetic demo receipts; no claim of real independent review.'}
        self.write('.artifacts/demo-summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', type=Path, required=True, help='New disposable directory; must not exist.')
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('config.json'))
    args = parser.parse_args()
    Demo(args.project_dir.resolve(), json.loads(args.config.read_text())).demonstrate()
