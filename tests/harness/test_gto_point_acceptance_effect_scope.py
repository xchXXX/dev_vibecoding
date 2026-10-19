"""Effect-stop authority applies to failed/dependent scopes, not independent first runs."""
from copy import deepcopy
import unittest

import test_control_plane as legacy
import test_gto_acceptance_retest_contract as lifecycle
from test_gto_acceptance_batches import BatchHarness
from test_gto_point_acceptance import PointHarness


class ScopedEffectStopTest(PointHarness, unittest.TestCase):
    call = BatchHarness.call
    public_call = lifecycle.BlackboxMachineEntryTest.public_call
    start_flow = lifecycle.BlackboxLifecycleTest.start_flow
    create_attempt = lifecycle.BlackboxLifecycleTest.create_attempt
    finish_attempt = lifecycle.BlackboxLifecycleTest.finish_attempt
    receipt = lifecycle.BlackboxLifecycleTest.receipt

    def init_task(self, payload):
        gate = payload['acceptance_gate']
        gate['acceptance_items'][-1]['paths'] = ['candidate-source.py']
        for ident, paths, dependencies in (
                ('BBX-002', ['docs/contract.md'], []),
                ('BBX-003', ['candidate-config.json'], ['BBX-001'])):
            item = deepcopy(gate['acceptance_items'][-1])
            item.update(acceptance_id=ident, paths=paths, depends_on=dependencies)
            gate['acceptance_items'].append(item)
            gate['blackbox_acceptance_ids'].append(ident)
        return legacy.ControlPlaneContractTest.init_task(self, payload)

    def arrange(self, scope, *, expected=True):
        process, response = self.call('create-subtask-attempt', {'scope_acceptance_ids': scope},
            subtask_id='EXPENSIVE-001', attempt_kind='blackbox', approval_by='user',
            approval_reason='Synthetic budget permission only; no failed scope next_round permission.')
        if expected:
            self.assertEqual(0, process.returncode, response)
            return response['attempt']
        self.assertNotEqual(0, process.returncode, response)
        self.assertRegex(str(response).lower(), 'effect|stop|decision|depend')

    def test_independent_blackbox_can_complete_without_releasing_failed_or_dependent_scope(self):
        self.start_flow()
        self.finish_attempt('preparation')
        failed = self.arrange(['BBX-001'])
        self.bind(failed['subtask_id'], agent='accept-001', role='tester')
        receipt = self.receipt('blackbox', 'effect_failure')
        receipt['expensive_acceptance']['point_results'] = [
            {'acceptance_id': 'BBX-001', 'status': 'fail', 'evidence_refs': ['.artifacts/observation.log']}]
        self.run_ctl('record-subtask-result', subtask_id=failed['subtask_id'], result=receipt)
        original = deepcopy(self.state()['acceptance_gate']['attempts'][-1])
        independent = self.arrange(['BBX-002'])
        self.bind(independent['subtask_id'], agent='accept-001', role='tester')
        success = self.receipt('blackbox')
        success['expensive_acceptance'].update(mode='scoped', scope_acceptance_ids=['BBX-002'],
            evidence_by_acceptance_id={'BBX-002': ['.artifacts/independent-observation.log']},
            point_results=[{'acceptance_id': 'BBX-002', 'status': 'pass',
                            'evidence_refs': ['.artifacts/independent-observation.log']}])
        success['expensive_acceptance']['evidence_refs'].append('.artifacts/independent-observation.log')
        self.run_ctl('record-subtask-result', subtask_id=independent['subtask_id'], result=success)
        status = self.run_ctl('acceptance-status')
        self.assertEqual('fail', status['points']['BBX-001']['status'])
        self.assertEqual('pass', status['points']['BBX-002']['status'])
        self.assertFalse(status['complete'])
        for scope in (['BBX-001'], ['BBX-003']):
            with self.subTest(scope=scope):
                before = self.state()
                self.arrange(scope, expected=False)
                self.assertEqual(before, self.state())
        self.assertEqual(original, self.state()['acceptance_gate']['attempts'][1])
        self.assertNotIn('decisions', original)


class EffectStopAuthorizationChainTest(unittest.TestCase):
    def test_authorized_real_pass_resolves_all_prior_failures_in_its_scope(self):
        from test_gto_plan_preflight_contract import load_controller
        controller = load_controller()
        # Pure projection fixture: upstream CLI evidence validation is covered
        # separately. These rows represent already validated real observations.
        def observation(ident, point, outcome, authorization=None):
            value = {'attempt_id': ident, 'kind': 'blackbox', 'outcome': outcome,
                'real_call_count': 1, 'scope_acceptance_ids': [point],
                'point_results': [{'acceptance_id': point,
                    'status': 'fail' if outcome == 'effect_failure' else 'pass'}]}
            if authorization:
                value['authorization_attempt_id'] = authorization
            if outcome == 'effect_failure':
                value['decisions'] = [{'allow': ['next_round'], 'written_by': 'user'}]
            return value

        first = observation('attempt-1', 'BBX-001', 'effect_failure')
        second = observation('attempt-2', 'BBX-001', 'effect_failure', 'attempt-1')
        state = {'acceptance_gate': {
            'acceptance_items': [{'acceptance_id': 'BBX-001'}, {'acceptance_id': 'BBX-002'}],
            'blackbox_acceptance_ids': ['BBX-001', 'BBX-002'],
            'attempts': [first, second]}}
        history = deepcopy(state['acceptance_gate']['attempts'])
        state['acceptance_gate']['attempts'].append(observation('independent', 'BBX-002', 'pass'))
        self.assertEqual(['attempt-1', 'attempt-2'],
                         [a['attempt_id'] for a in controller._effect_failures(state, ['BBX-001'])])
        self.assertEqual([], controller._effect_failures(state, ['BBX-002']))
        state['acceptance_gate']['attempts'].append(
            observation('attempt-3', 'BBX-001', 'pass', 'attempt-2'))
        self.assertEqual([], controller._effect_failures(state, ['BBX-001']),
                         'A newer authorized real pass resolves both failures of the same point.')
        self.assertEqual([], controller._effect_failures(state))
        self.assertEqual(history, state['acceptance_gate']['attempts'][:2])


if __name__ == '__main__':
    unittest.main()
