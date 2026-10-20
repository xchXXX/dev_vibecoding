"""Independent batch evidence contracts; synthetic files, no model calls.

The CLI harness creates real state through existing public actions. It never
preseeds acceptance success or patches a production validation function.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from copy import deepcopy

import test_control_plane as legacy
import test_gto_workflow as workflow
import test_gto_acceptance_retest_contract as retest_contract


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class BatchHarness:
    setUp = retest_contract.AcceptanceCliContractTest.setUp
    run_ctl = retest_contract.AcceptanceCliContractTest.run_ctl
    init_task = retest_contract.AcceptanceCliContractTest.init_task
    state = retest_contract.AcceptanceCliContractTest.state
    git = retest_contract.AcceptanceCliContractTest.git
    init_git_checkout = retest_contract.AcceptanceCliContractTest.init_git_checkout
    bind = retest_contract.AcceptanceCliContractTest.bind
    work_result = retest_contract.AcceptanceCliContractTest.work_result
    integrate = retest_contract.AcceptanceCliContractTest.integrate
    review_payload = retest_contract.AcceptanceCliContractTest.review_payload
    review = retest_contract.AcceptanceCliContractTest.review

    def write_json(self, path, value):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical(value))
        return self.ref(path)

    def ref(self, path, pointer=None):
        value = {'path': path, 'sha256': hashlib.sha256((self.repo / path).read_bytes()).hexdigest()}
        if pointer is not None:
            value['pointer'] = pointer
        return value

    def read_json(self, ref):
        return json.loads((self.repo / ref['path']).read_text())

    def artifacts(self):
        folders = {'state.json': 'docs/ai/tasks', 'task.md': 'docs/ai/tasks',
                   'events.jsonl': 'docs/ai/tasks', 'plan.md': 'docs/tasks',
                   'execution.md': 'docs/tasks', 'acceptance.md': 'docs/tasks'}
        return {name: (self.repo / folder / legacy.TASK_ID / name).read_bytes()
                for name, folder in folders.items()}

    def call(self, action, result=None, **args):
        command = [sys.executable, '-B', str(legacy.CONTROLLER), '--action', action,
                   '--repo-root', str(self.repo), '--task-id', legacy.TASK_ID, '--json']
        if result is not None:
            self._json_input_index += 1
            path = self.input_dir / f'batch-{self._json_input_index}.json'
            path.write_bytes(canonical(result))
            command += ['--result-json-file', str(path)]
        for name, value in args.items():
            command += ['--' + name.replace('_', '-'), str(value)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=40)
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError:
            payload = {'ok': False, 'errors': [process.stderr or process.stdout]}
        return process, payload

    def accepted(self, action, value=None, **args):
        if action == 'record-subtask-result':
            legacy.attach_acceptance_run(self.repo, args.get('subtask_id'), value, create_fixture_files=True)
        process, response = self.call(action, value, **args)
        self.assertEqual(0, process.returncode,
                         f'Public {action} failed: {response}; stderr={process.stderr}')
        self.assertTrue(response.get('ok'), response)
        return response

    def rejected(self, action, value=None, **args):
        if action == 'record-subtask-result':
            legacy.attach_acceptance_run(self.repo, args.get('subtask_id'), value)
        before = self.artifacts()
        process, response = self.call(action, value, **args)
        self.assertNotEqual(0, process.returncode, response)
        self.assertFalse(response.get('ok'), response)
        self.assertNotIn('invalid choice', process.stderr,
                         'Missing action is only entry Red, not negative gate evidence')
        self.assertEqual(before, self.artifacts(), 'Rejected action mutated six artifacts')
        return response

    def begin(self, *, required_evidence=False, blackbox=False, extra_code_files=False):
        self.init_git_checkout('candidate-source.py', 'candidate-config.json', 'docs/contract.md')
        self.cases = [{'id': f'CASE-0{i}', 'input': f'Question {i}', 'state': {'mode': 'ready'}}
                      for i in (1, 2)]
        self.write_json('candidate-config.json', {'cases': self.cases})
        self.git('add', 'candidate-config.json')
        self.git('commit', '-m', 'Freeze complete synthetic input set')
        payload = workflow.workflow_contract()
        self.batch_kind = 'blackbox' if blackbox else 'ordinary'
        self.batch_acceptance_id = 'BBX-001' if blackbox else 'REAL-PATH-001'
        self.batch_evidence_key = 'blackbox_output_index' if blackbox else 'acceptance_output_index'
        if blackbox:
            item = deepcopy(payload['acceptance_gate']['acceptance_items'][0])
            item['acceptance_id'] = 'BBX-001'
            payload['acceptance_gate']['acceptance_items'].append(item)
            payload['acceptance_gate']['blackbox_acceptance_ids'] = ['BBX-001']
        if extra_code_files:
            self.write_json('extra-code/deleted.json', {'old': True})
            self.write_json('extra-code/modified.json', {'version': 1})
            self.git('add', 'extra-code')
            self.git('commit', '-m', 'Include complete extra code directory')
            payload['acceptance_gate']['candidate_inputs']['code_paths'].append('extra-code')
            payload['acceptance_gate']['acceptance_items'][0]['paths'].append('extra-code')
            for item in payload['subtasks']:
                if item['subtask_id'] == 'INTEGRATE-001':
                    item['write_paths'].append('extra-code')
        self.required_evidence = required_evidence
        if required_evidence:
            keys = [self.batch_evidence_key] + (['functional_output_index'] if blackbox else [])
            payload['verification_contract']['review_evidence'].extend(keys)
            template = next(t for t in payload['subtasks'] if t['stage'] == 'expensive_acceptance')
            template['assignment']['required_verification_evidence'] = {self.batch_kind: [self.batch_evidence_key]}
            if blackbox:
                template['assignment']['required_verification_evidence']['ordinary'] = ['functional_output_index']
        self.init_task(payload)
        if blackbox and required_evidence:
            # Synthetic authorization travels through the existing public
            # budget action; no state edits or budget-gate monkeypatches.
            approval = '.artifacts/synthetic-budget-approval.json'
            self.write_json(approval, {'approved_by': 'user', 'maximum': 5,
                                      'reason': 'Five isolated synthetic CLI attempts; zero model calls.'})
            self.accepted('extend-acceptance-budget', {
                'written_by': '/root', 'written_role': 'coordinator', 'approved_by': 'user',
                'reason': 'Synthetic fixture explicitly authorizes two preparations, two blackbox and one ordinary.',
                'approval_evidence_refs': [approval], 'previous_max_expensive_attempts': 4,
                'max_expensive_attempts': 5})
        self.run_ctl('prepare-workspace')
        self.integrate()
        if extra_code_files:
            self.bind('REVIEW-SEC-001', agent='review-001', role='reviewer', review=True)
            self.run_ctl('record-review-result', subtask_id='REVIEW-SEC-001', result=self.review_payload(
                covered=['candidate-source.py', 'candidate-config.json', 'docs/contract.md', 'extra-code']))
        else:
            self.review()
        self.run_ctl('freeze-candidate')
        contract = {'kind': self.batch_kind,
                    'fixture': {**self.ref('candidate-config.json'), 'collection_pointer': '/cases', 'id_pointer': '/id'},
                    'required_units': [{'unit_id': c['id'], 'acceptance_id': self.batch_acceptance_id,
                       'current_input': {'pointers': {'prompt': '/input', 'initial_state': '/state'}},
                       'raw_selectors': {'unit_id': '/id', 'execution_status': '/executed',
                                         'executed_values': [True]}}
                       for c in self.cases]}
        self.contract_ref = self.write_json('.artifacts/batch-contract.json', contract)

    def attempt(self, kind=None):
        args = {'attempt_kind': kind or self.batch_kind}
        if len(self.state()['acceptance_gate']['attempts']) >= 2:
            args.update(approval_by='user', approval_reason='Bounded synthetic local test.')
        response = self.accepted('create-subtask-attempt', subtask_id='EXPENSIVE-001', **args)
        self.bind(response['subtask_id'], agent='accept-001', role='tester')
        return response['attempt']

    def make_batch(self, attempt, index, *, terminal=False):
        prefix = f'.artifacts/{attempt["attempt_id"]}'
        raw_path = prefix + '-raw.json'
        self.write_json(raw_path, {'records': [
            {'id': c['id'], 'executed': True, 'request': {'input': c['input'], 'state': c['state']},
             'output': f'Actual synthetic output {c["id"]}'} for c in self.cases]})
        unit_id = self.cases[index]['id']
        source_path = prefix + '-score.json'
        self.write_json(source_path, {'written_by': 'accept-001', 'results': [
            {'id': c['id'], 'result': 'PASS'} for c in self.cases]})
        projection = {'prompt': self.cases[index]['input'], 'initial_state': self.cases[index]['state']}
        normalized = {'unit_id': unit_id, 'outcome': 'pass',
                      'raw_sha256': self.ref(raw_path)['sha256'], 'input_sha256': digest(projection),
                      'written_by': 'accept-001', 'source_score': self.ref(source_path, f'/results/{index}'),
                      'source_score_selectors': {'unit_id': f'/results/{index}/id',
                                                'outcome': f'/results/{index}/result', 'written_by': '/written_by'}}
        score_path = prefix + '-normalized.json'
        self.write_json(score_path, {'records': [normalized]})
        batch = {'batch_id': f'batch-{attempt["attempt_id"]}-{index}', 'source_attempt_id': attempt['attempt_id'],
                 'written_by': 'accept-001', 'written_role': 'tester', 'contract': deepcopy(self.contract_ref),
                 'units': [{'unit_id': unit_id, 'acceptance_id': self.batch_acceptance_id,
                   'raw': self.ref(raw_path, f'/records/{index}'),
                   'input': {**self.ref(raw_path), 'pointers': {'prompt': f'/records/{index}/request/input',
                                                            'initial_state': f'/records/{index}/request/state'}},
                   'score': self.ref(score_path, '/records/0')}]}
        self.review_batch(batch, attempt)
        if terminal:
            evidence = {'outcome': 'environment_failure', 'real_call_count': 2, 'duration_seconds': 3,
                        'failed_stage': 'evidence_capture', 'evidence_refs': [raw_path],
                        'evidence_by_acceptance_id': {}, 'mode': 'full', 'scope_acceptance_ids': [self.batch_acceptance_id],
                        'usage_evidence': workflow.usage('accept-001', 'acceptance')}
            if self.batch_kind == 'blackbox':
                evidence['blackbox'] = self.blackbox_refs(raw_path)
                evidence['invalid_observation'] = {'reason': 'evidence_capture',
                    'evidence_refs': [raw_path], 'summary': 'Synthetic capture stopped after archived output.'}
            result = legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance=evidence)
            if self.required_evidence:
                result['review_evidence'] = {self.batch_evidence_key: raw_path}
            self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'], result=result)
        return batch

    def review_batch(self, batch, attempt, **changes):
        snapshot = attempt['coverage_snapshot']
        proof = self.write_json(f'.artifacts/{batch["batch_id"]}-review-proof.json',
                                {'review': 'All source/current paths and complete input projection examined.'})
        review = {'written_by': 'review-001', 'written_role': 'reviewer',
                  'source_attempt_id': attempt['attempt_id'], 'source_candidate_id': attempt['candidate_id'],
                  'current_candidate_id': self.state()['acceptance_gate']['current_candidate']['candidate_id'],
                  'source_coverage_sha256': digest(snapshot), 'current_coverage_sha256': digest(snapshot),
                  'delta_sha256': digest([]), 'changed_paths': [],
                  'unit_ids': [u['unit_id'] for u in batch['units']], 'units_sha256': digest(batch['units']),
                  'input_projection_complete': True, 'compatible': True,
                  'reason': 'Synthetic source and current candidates and full input projection are identical.',
                  'evidence_refs': [proof]}
        review.update(changes)
        batch['applicability_review'] = self.write_json(f'.artifacts/{batch["batch_id"]}-review.json', review)

    def historical(self, *, required_evidence=False):
        self.begin(required_evidence=required_evidence)
        attempt = self.attempt()
        batch = self.make_batch(attempt, 0, terminal=True)
        return attempt, batch

    def blackbox_refs(self, path):
        return {'session_ids': ['synthetic-session'], 'input_refs': ['candidate-config.json'],
                'trace_refs': [path], 'report_ref': f'docs/tasks/{legacy.TASK_ID}/acceptance.md'}

    def partial_result(self, batch):
        evidence = {'outcome': 'partial_pass', 'mode': 'partial', 'real_call_count': 1,
                    'duration_seconds': 2, 'failed_stage': 'none',
                    'executed_unit_ids': [u['unit_id'] for u in batch['units']],
                    'evidence_batch_ids': [batch['batch_id']], 'scope_acceptance_ids': [self.batch_acceptance_id],
                    'evidence_refs': [u['raw']['path'] for u in batch['units']],
                    'evidence_by_acceptance_id': {self.batch_acceptance_id: [u['raw']['path'] for u in batch['units']]},
                    'usage_evidence': workflow.usage('accept-001', 'acceptance')}
        if self.batch_kind == 'blackbox':
            evidence['blackbox'] = self.blackbox_refs(batch['units'][0]['raw']['path'])
        result = legacy.result('completed', 'accept-001', 'tester', expensive_acceptance=evidence)
        if self.required_evidence:
            result['review_evidence'] = {self.batch_evidence_key: batch['units'][0]['raw']['path']}
        return result

    def finish_partial(self, attempt, batch):
        result = self.partial_result(batch)
        self.accepted('record-subtask-result', result, subtask_id=attempt['subtask_id'])

    def coverage(self, batches):
        return {'coverage_id': 'coverage-01', 'kind': self.batch_kind,
                'candidate_id': self.state()['acceptance_gate']['current_candidate']['candidate_id'],
                'contract_sha256': self.contract_ref['sha256'], 'batch_ids': [b['batch_id'] for b in batches],
                'written_by': 'accept-001', 'written_role': 'tester'}


class BatchEvidenceContractTest(BatchHarness, unittest.TestCase):
    def test_explicit_selectors_reject_wrong_types_and_cross_record_paths(self):
        attempt, batch = self.historical()
        contract = self.read_json(batch['contract'])
        variants = [('string_true', {'executed_values': ['true']}),
                    ('integer_true', {'executed_values': [1]}),
                    ('foreign_id', {'unit_id': '/records/1/id'}),
                    ('foreign_status', {'execution_status': '/records/1/executed'})]
        for name, changes in variants:
            with self.subTest(variant=name):
                altered = deepcopy(contract)
                altered['required_units'][0]['raw_selectors'].update(changes)
                value = deepcopy(batch)
                value['batch_id'] = name
                value['contract'] = self.write_json(f'.artifacts/{name}-contract.json', altered)
                self.review_batch(value, attempt)
                failure = self.rejected('record-acceptance-evidence-batch', value)
                self.assertRegex(' '.join(failure['errors']).lower(), 'status|execut|pointer|select')
        self.accepted('record-acceptance-evidence-batch', batch)

    def test_non_json_raw_and_review_evidence_are_hashed_without_rewriting(self):
        self.begin()
        attempt = self.attempt()
        batch = self.make_batch(attempt, 0)
        input_path = batch['units'][0]['input']['path']
        raw_path = '.artifacts/native-output.log'
        proof_path = '.artifacts/native-review-evidence.log'
        (self.repo / raw_path).write_bytes(b'CASE-01 actual archived output\nnot JSON\x00\xff')
        (self.repo / proof_path).write_bytes(b'Independent reviewer examined CASE-01 execution.\n')
        batch['units'][0]['raw'] = self.ref(raw_path)
        score = self.read_json(batch['units'][0]['score'])
        score['records'][0]['raw_sha256'] = self.ref(raw_path)['sha256']
        batch['units'][0]['score'] = {**self.write_json('.artifacts/text-normalized.json', score),
                                     'pointer': '/records/0'}
        contract = self.read_json(batch['contract'])
        for unit in contract['required_units']:
            unit['raw_selectors'] = None
        batch['contract'] = self.write_json('.artifacts/text-contract.json', contract)
        self.review_batch(batch, attempt)
        review = self.read_json(batch['applicability_review'])
        review['evidence_refs'] = [self.ref(proof_path)]
        batch['applicability_review'] = self.write_json('.artifacts/text-review.json', review)
        self.accepted('record-acceptance-evidence-batch', batch)
        result = self.partial_result(batch)
        result['expensive_acceptance']['evidence_refs'].append(input_path)
        self.accepted('record-subtask-result', result, subtask_id=attempt['subtask_id'])
        self.accepted('validate')
        for path in (raw_path, proof_path):
            original = (self.repo / path).read_bytes()
            try:
                (self.repo / path).write_bytes(original + b'changed')
                self.rejected('validate')
            finally:
                (self.repo / path).write_bytes(original)
        self.accepted('validate')

    def native_archived_batch(self, *, whole_file=False, second_status='OUTPUT_ARCHIVED',
                              score_outcome='PASS', raw_alias=False):
        self.begin()
        attempt = self.attempt()
        raw_path = '.artifacts/native-archived-output.json'
        # Mirrors observed business raw field names/status only; synthetic
        # values contain no business evaluator, expected answer or score rule.
        raw = {'scenarios': [{'scenario_id': c['id'], 'status': 'OUTPUT_ARCHIVED',
                 'initial_state': c['state'], 'evaluated_turn': {'input': c['input']},
                 'product_summary': f'Synthetic actual output {c["id"]}'} for c in self.cases]}
        raw['scenarios'][1]['status'] = second_status
        raw_ref = self.write_json(raw_path, raw)
        scores_path = '.artifacts/native-independent-score.json'
        self.write_json(scores_path, {'written_by': 'accept-001', 'results': [
            {'id': c['id'], 'result': score_outcome} for c in self.cases]})
        normalized = []
        for index, c in enumerate(self.cases):
            normalized.append({'unit_id': c['id'], 'outcome': 'pass',
                'raw_sha256': raw_ref['sha256'],
                'input_sha256': digest({'prompt': c['input'], 'initial_state': c['state']}),
                'written_by': 'accept-001', 'source_score': self.ref(scores_path, f'/results/{index}'),
                'source_score_selectors': {'unit_id': f'/results/{index}/id',
                    'outcome': f'/results/{index}/result', 'written_by': '/written_by'}})
        normalized_path = '.artifacts/native-normalized-score.json'
        self.write_json(normalized_path, {'records': normalized})
        units = [{'unit_id': c['id'], 'acceptance_id': 'REAL-PATH-001',
                  'raw': deepcopy(raw_ref) if whole_file else self.ref(raw_path, f'/scenarios/{index}'),
                  'input': {**raw_ref, 'pointers': {'prompt': f'/scenarios/{index}/evaluated_turn/input',
                            'initial_state': f'/scenarios/{index}/initial_state'}},
                  'score': self.ref(normalized_path, f'/records/{index}')}
                 for index, c in enumerate(self.cases)]
        if raw_alias:
            units[1]['raw']['path'] = './' + raw_path
        contract = self.read_json(self.contract_ref)
        for unit in contract['required_units']:
            unit['raw_selectors'] = None if whole_file else {
                'unit_id': '/scenario_id', 'execution_status': '/status',
                'executed_values': ['OUTPUT_ARCHIVED']}
        self.contract_ref = self.write_json('.artifacts/native-contract.json', contract)
        batch = {'batch_id': 'native-output-batch', 'source_attempt_id': attempt['attempt_id'],
                 'written_by': 'accept-001', 'written_role': 'tester',
                 'contract': deepcopy(self.contract_ref), 'units': units}
        self.review_batch(batch, attempt)
        evidence = {'outcome': 'environment_failure', 'real_call_count': 2, 'duration_seconds': 3,
                    'failed_stage': 'evidence_capture', 'evidence_refs': [raw_path],
                    'evidence_by_acceptance_id': {}, 'mode': 'full', 'scope_acceptance_ids': ['REAL-PATH-001'],
                    'usage_evidence': workflow.usage('accept-001', 'acceptance')}
        if raw_alias:
            evidence['evidence_refs'].append('./' + raw_path)
        self.run_ctl('record-subtask-result', subtask_id=attempt['subtask_id'],
                     result=legacy.result('blocked', 'accept-001', 'tester', expensive_acceptance=evidence))
        return batch

    def test_native_archived_record_does_not_require_rewriting_raw_fields(self):
        batch = self.native_archived_batch()
        original = (self.repo / batch['units'][0]['raw']['path']).read_bytes()
        self.accepted('record-acceptance-evidence-batch', batch)
        self.assertEqual(original, (self.repo / batch['units'][0]['raw']['path']).read_bytes())

    def test_whole_file_ref_cannot_replace_distinct_record_selections(self):
        batch = self.native_archived_batch(whole_file=True)
        self.assertNotEqual(batch['units'][0]['unit_id'], batch['units'][1]['unit_id'])
        self.assertEqual(batch['units'][0]['raw'], batch['units'][1]['raw'])
        response = self.rejected('record-acceptance-evidence-batch', batch)
        self.assertRegex(' '.join(response['errors']).lower(), 'repeat.*raw|raw.*repeat')

    def test_whole_file_raw_alias_cannot_bypass_duplicate_execution_guard(self):
        batch = self.native_archived_batch(whole_file=True, raw_alias=True)
        first, second = [self.repo / unit['raw']['path'] for unit in batch['units']]
        self.assertEqual(first.resolve(), second.resolve())
        self.rejected('record-acceptance-evidence-batch', batch)

    def test_native_preparation_failure_cannot_be_claimed_as_executed(self):
        batch = self.native_archived_batch(second_status='TEST_PREPARATION_FAILURE')
        response = self.rejected('record-acceptance-evidence-batch', batch)
        self.assertRegex(' '.join(response['errors']).lower(), 'status|execut|archiv')

    def test_native_output_archived_does_not_replace_independent_passing_score(self):
        batch = self.native_archived_batch(score_outcome='FAIL')
        response = self.rejected('record-acceptance-evidence-batch', batch)
        self.assertRegex(' '.join(response['errors']).lower(), 'score|pass')

    def test_historical_input_value_must_equal_current_fixture_projection(self):
        self.begin()
        attempt = self.attempt()
        # Archive an actually different execution input before recording its
        # terminal result; neither archived output nor state is edited later.
        self.cases[0]['input'] = 'Earlier execution used a different question'
        batch = self.make_batch(attempt, 0, terminal=True)
        archived = self.read_json(batch['units'][0]['input'])
        fixture = self.read_json(self.read_json(batch['contract'])['fixture'])
        self.assertNotEqual(archived['records'][0]['request']['input'],
                            fixture['cases'][0]['input'])
        self.assertTrue(self.read_json(batch['applicability_review'])['compatible'])
        self.rejected('record-acceptance-evidence-batch', batch)

    def test_historical_input_path_must_belong_to_archived_attempt(self):
        attempt, batch = self.historical()
        archived_raw = self.read_json(batch['units'][0]['raw'])
        original_raw = deepcopy(batch['units'][0]['raw'])
        # Identical values and valid hashes do not make a later copy an
        # archived input source owned by the original terminal attempt.
        replacement = self.write_json('.artifacts/later-input-copy.json', archived_raw)
        batch['units'][0]['input'].update(replacement)
        self.review_batch(batch, attempt)
        result = next(t['result'] for t in self.state()['subtasks']
                      if t['subtask_id'] == attempt['subtask_id'])
        self.assertNotIn(replacement['path'], result['expensive_acceptance']['evidence_refs'])
        self.assertEqual(original_raw, batch['units'][0]['raw'])
        self.rejected('record-acceptance-evidence-batch', batch)

    def test_public_batch_preserves_terminal_failure(self):
        attempt, batch = self.historical()
        before = self.state()
        self.accepted('record-acceptance-evidence-batch', batch)
        after = self.state()
        self.assertEqual(before['acceptance_gate']['attempts'], after['acceptance_gate']['attempts'])
        self.assertEqual(before['subtasks'], after['subtasks'])
        self.assertEqual('environment_failure', after['acceptance_gate']['attempts'][0]['outcome'])
        self.accepted('validate')

    def test_raw_sibling_pointer_cannot_reuse_review(self):
        _, batch = self.historical()
        batch['units'][0]['raw']['pointer'] = '/records/1'
        self.rejected('record-acceptance-evidence-batch', batch)

    def test_score_sibling_selectors_cannot_claim_failed_record(self):
        attempt, batch = self.historical()
        score_ref = batch['units'][0]['score']
        normalized = self.read_json(score_ref)
        record = normalized['records'][0]
        source = self.read_json(record['source_score'])
        source['results'][0]['result'] = 'FAIL'
        source_ref = self.write_json(record['source_score']['path'], source)
        record['source_score'] = {**source_ref, 'pointer': '/results/0'}
        # Both values look valid if the checker ignores the selected record boundary.
        source['results'][1]['id'] = 'CASE-01'
        source_ref = self.write_json(record['source_score']['path'], source)
        record['source_score']['sha256'] = source_ref['sha256']
        record['source_score_selectors'].update(unit_id='/results/1/id', outcome='/results/1/result')
        batch['units'][0]['score'] = {**self.write_json(score_ref['path'], normalized), 'pointer': '/records/0'}
        self.review_batch(batch, attempt)
        self.rejected('record-acceptance-evidence-batch', batch)

    def test_wrong_writer_unexecuted_or_bad_input_is_rejected(self):
        attempt, batch = self.historical()
        for variant in ('writer', 'projection', 'score_author', 'score_fail'):
            with self.subTest(variant=variant):
                value = deepcopy(batch)
                if variant == 'writer':
                    value['written_by'] = 'impl-001'
                elif variant == 'projection':
                    value['units'][0]['input']['pointers'].pop('initial_state')
                else:
                    normalized = self.read_json(value['units'][0]['score'])
                    normalized['records'][0]['written_by' if variant == 'score_author' else 'outcome'] = (
                        'impl-001' if variant == 'score_author' else 'not_executed')
                    ref = self.write_json(f'.artifacts/{variant}.json', normalized)
                    value['units'][0]['score'] = {**ref, 'pointer': '/records/0'}
                self.review_batch(value, attempt)
                self.rejected('record-acceptance-evidence-batch', value)

    def test_complete_fixture_cannot_drop_unit_or_swap_contract(self):
        attempt, batch = self.historical()
        contract = self.read_json(batch['contract'])
        contract['required_units'].pop()
        batch['contract'] = self.write_json('.artifacts/reduced-contract.json', contract)
        self.review_batch(batch, attempt)
        self.rejected('record-acceptance-evidence-batch', batch)

    def test_review_requires_real_pass_identity_and_complete_binding(self):
        attempt, batch = self.historical()
        for changes in ({'written_by': 'invented-reviewer'}, {'written_by': 'accept-001'},
                        {'written_by': 'impl-001'}, {'compatible': False},
                        {'input_projection_complete': False}, {'delta_sha256': '0' * 64},
                        {'source_candidate_id': 'candidate-fake'}, {'changed_paths': ['deleted.py']}):
            with self.subTest(changes=changes):
                self.review_batch(batch, attempt, **changes)
                self.rejected('record-acceptance-evidence-batch', batch)

    def test_idempotence_conflict_and_repeated_source_are_atomic(self):
        _, batch = self.historical()
        self.accepted('record-acceptance-evidence-batch', batch)
        before = self.artifacts()
        self.accepted('record-acceptance-evidence-batch', batch)
        self.assertEqual(before, self.artifacts())
        conflict = deepcopy(batch)
        conflict['units'][0]['raw']['pointer'] = '/records/1'
        self.rejected('record-acceptance-evidence-batch', conflict)
        duplicate = deepcopy(batch)
        duplicate['batch_id'] = 'renamed-copy'
        self.rejected('record-acceptance-evidence-batch', duplicate)

    def test_frozen_contract_and_candidate_delta_cannot_be_silently_replaced(self):
        attempt, batch = self.historical()
        self.accepted('record-acceptance-evidence-batch', batch)
        changed = deepcopy(batch)
        changed['batch_id'] = 'changed-contract'
        contract = self.read_json(batch['contract'])
        contract['required_units'][0]['current_input']['pointers'].pop('initial_state')
        changed['contract'] = self.write_json('.artifacts/changed-contract.json', contract)
        self.review_batch(changed, attempt)
        self.rejected('record-acceptance-evidence-batch', changed)
        # The previous review claims no delta; both removal and addition invalidate it.
        target = self.repo / 'candidate-source.py'
        original = target.read_bytes()
        try:
            target.unlink()
            self.rejected('validate')
        finally:
            target.write_bytes(original)
        self.write_json('candidate-config.json', {'cases': self.cases, 'new_runtime_option': True})
        self.rejected('validate')


if __name__ == '__main__':
    unittest.main()
