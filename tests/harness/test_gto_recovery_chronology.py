"""Recovery and execution chronology contracts; no external model/Browser calls."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

import test_control_plane as legacy
from test_gto_plan_preflight_contract import load_controller
from test_gto_point_acceptance import PointHarness


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / '.artifacts/scoped-acceptance/followup/testing'


def retain(test):
    destination = OUTPUT / 'consumers' / (test.id() + '-' + uuid.uuid4().hex)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(test.repo, destination)
    print('Retained recovery/chronology consumer: ' + str(destination), file=sys.stderr)


class EnvironmentRecoveryTest(PointHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: retain(self))

    def interrupted(self, attempt):
        receipt = self.observe(attempt, ['CHECK-02'], unexecuted={'CHECK-02': 'blocked'})
        evidence = receipt['expensive_acceptance']
        stdout = str(Path(evidence['run_evidence']['path']).parent / 'stdout.log')
        evidence.update(outcome='environment_failure', failed_stage='environment', evidence_refs=[stdout])
        evidence['usage_evidence'][0]['evidence_refs'] = [stdout]
        receipt.update(status='blocked', blocked_by=['Synthetic environment interruption before business execution.'])
        self.register(attempt, receipt)

    def test_explicit_scope_authorization_allows_recovery_but_not_budget_bypass(self):
        self.begin(2)
        first = self.attempt(['CHECK-01'])
        self.register(first, self.observe(first, ['CHECK-01']))
        for _ in range(2):
            self.interrupted(self.attempt(['CHECK-02']))
        history = deepcopy(self.state()['acceptance_gate']['attempts'])
        candidate = deepcopy(self.state()['acceptance_gate']['current_candidate'])
        for authorization in ({}, {'approval_by': 'coordinator', 'approval_reason': 'Not user authorization.'},
                              {'approval_by': 'user', 'approval_reason': '   '}):
            with self.subTest(authorization=authorization):
                before = self.state()
                rejected = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001',
                    result={'scope_acceptance_ids': ['CHECK-02']}, ok=False, **authorization)
                self.assertRegex(str(rejected).lower(), 'environment|approval|authoriz')
                self.assertEqual(before, self.state())
        approved = self.attempt(['CHECK-02'])
        self.assertEqual(['CHECK-02'], approved['scope_acceptance_ids'])
        self.interrupted(approved)  # A third real environment failure must remain recordable.
        self.run_ctl('validate')
        self.assertEqual(history, self.state()['acceptance_gate']['attempts'][:3])
        self.assertEqual(candidate, self.state()['acceptance_gate']['current_candidate'])
        self.assertEqual(1, self.count())
        before = self.state()
        rejected = self.run_ctl('create-subtask-attempt', subtask_id='EXPENSIVE-001',
            result={'scope_acceptance_ids': ['CHECK-02']}, approval_by='user',
            approval_reason='Scope permission is not total-budget extension.', ok=False)
        self.assertRegex(str(rejected), 'max_expensive_attempts')
        self.assertEqual(before, self.state())
        approval = '.artifacts/synthetic-budget-approval.json'
        (self.repo / approval).write_text(json.dumps({'approved_by': 'user', 'maximum': 5}))
        self.run_ctl('extend-acceptance-budget', result={
            'written_by': '/root', 'written_role': 'coordinator', 'approved_by': 'user',
            'reason': 'One separately authorized recovery after three retained interruptions.',
            'approval_evidence_refs': [approval], 'previous_max_expensive_attempts': 4, 'max_expensive_attempts': 5})
        recovered = self.attempt(['CHECK-02'])
        self.register(recovered, self.observe(recovered, ['CHECK-02']))
        status = self.coverage()
        self.assertTrue(status['complete'], status)
        self.assertEqual(first['attempt_id'], status['points']['CHECK-01']['source_attempt_id'])
        self.assertEqual([1, 0, 0, 0, 1], [a['real_call_count'] for a in self.state()['acceptance_gate']['attempts']])
        self.assertEqual(2, self.count())


class ChronologyFixture(unittest.TestCase):
    def setUp(self):
        load_controller()
        self.runtime = importlib.import_module('runtime_evidence')
        self.points = importlib.import_module('acceptance_points')
        temporary = ROOT / '.tmp/scoped-acceptance-testing'
        temporary.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary)
        self.repo = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(lambda: retain(self))
        self.state = {'task_id': 'synthetic-chronology', 'subtasks': [], 'findings': {},
            'acceptance_gate': {'acceptance_items': [{'acceptance_id': 'POINT', 'paths': ['logic.py']}],
                                'attempts': []}}

    def observation(self, status, *, version=2, before=(), wall=('2030-01-01T00:00:00+00:00',
                    '2030-01-01T00:00:01+00:00'), kind='ordinary', malformed=None):
        """Sealed synthetic records isolate projection; not a claimed business run."""
        index = len(self.state['acceptance_gate']['attempts']) + 1
        ident = f'attempt-{index}'
        folder = self.repo / '.artifacts' / ident
        folder.mkdir(parents=True)
        for name in ('stdout.log', 'stderr.log'):
            (folder / name).write_text('Synthetic projection fixture.\n' if name == 'stdout.log' else '')
        raw = folder / 'observation.json'
        raw.write_text(json.dumps({'acceptance_id': 'POINT', 'status': status,
                                  'input': 'synthetic', 'actual': status, 'expected': 'pass'}))
        ref = raw.relative_to(self.repo).as_posix()
        rows = [{'acceptance_id': 'POINT', 'status': status, 'evidence_refs': [ref]}]
        attempt = {'attempt_id': ident, 'subtask_id': ident, 'kind': kind, 'candidate_id': 'candidate',
            'runtime_sha256': 'a' * 64, 'coverage_snapshot': {}, 'coverage_inputs_sha256': self.runtime.digest({}),
            'scope_acceptance_ids': ['POINT'], 'outcome': 'pass' if status == 'pass' else 'product_failure',
            'point_results': rows, 'real_call_count': 1}
        attempt['point_snapshots'] = self.points.snapshots(self.state['acceptance_gate'], {})
        binding = {'task_id': self.state['task_id'], 'candidate_id': 'candidate', 'runtime_sha256': 'a' * 64,
            'attempt_id': ident, 'subtask_id': ident, 'written_by': 'observer',
            'candidate_fingerprint': self.runtime.digest({'records': {}, 'inputs': attempt['coverage_inputs_sha256'],
                                                        'runtime_sha256': 'a' * 64})}
        manifest = {'schema_version': version, 'binding': binding, 'status': 'passed' if status == 'pass' else 'failed',
            'exit_code': 0 if status == 'pass' else 1, 'started_at': wall[0], 'finished_at': wall[1],
            'files': {name: self.runtime.digest((folder / name).read_bytes()) for name in ('stdout.log', 'stderr.log')},
            'evidence_files': {ref: self.runtime.digest(raw.read_bytes())}}
        if version == 2:
            manifest.update(elapsed_ns=1000, completed_before=list(before))
        if malformed:
            for key, value in malformed.items():
                if value is None:
                    manifest.pop(key, None)
                else:
                    manifest[key] = value
        path = folder / 'manifest.json'
        path.write_text(json.dumps(manifest))
        attempt['run_evidence'] = {'path': path.relative_to(self.repo).as_posix(), 'sha256': self.runtime.digest(path.read_bytes())}
        self.points.seal(self.repo, attempt, {'point_results': rows})
        self.state['acceptance_gate']['attempts'].append(attempt)
        self.state['subtasks'].append({'subtask_id': ident, 'status': 'completed' if status == 'pass' else 'blocked',
            'dispatch': {'platform_agent_id': 'observer'}, 'result': {'expensive_acceptance': {'point_results': rows}}})
        return attempt

    def coverage(self):
        return self.points.coverage(self.repo, self.state, {})


class RunCaptureChronologyTest(ChronologyFixture):
    def test_real_runs_capture_monotonic_elapsed_and_prestart_same_task_hashes(self):
        binding = {'task_id': self.state['task_id'], 'candidate_id': 'candidate-A'}
        times = [datetime(2030, 1, 2, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc),
                 datetime(2029, 1, 2, tzinfo=timezone.utc), datetime(2029, 1, 1, tzinfo=timezone.utc)]
        foreign = self.repo / '.artifacts/foreign'
        foreign.mkdir(parents=True)
        other = {'schema_version': 2, 'status': 'passed', 'binding': {'task_id': 'other-task'}}
        (foreign / 'manifest.json').write_text(json.dumps(other))
        pending = self.repo / '.artifacts/pending'
        pending.mkdir()
        (pending / 'manifest.json').write_text(json.dumps({'status': 'running', 'binding': binding}))
        with patch.object(self.runtime, 'datetime') as clock:
            clock.now.side_effect = times
            first = self.runtime.run_command(self.repo / '.artifacts/preparation-runs',
                [sys.executable, '-c', 'print("real preparation microprocess")'], cwd=self.repo, binding=binding)
            first_raw = (first / 'manifest.json').read_bytes()
            first_hash = self.runtime.digest(first_raw)
            (self.repo / '.artifacts/linked-run').symlink_to(first, target_is_directory=True)
            # This synthetic terminal record appears during the process: it must
            # never be retroactively included in the pre-start observation set.
            late = '.artifacts/during-run/manifest.json'
            script = ('import json; from pathlib import Path; '
                f'value=json.loads(Path({str(first / "manifest.json")!r}).read_text()); '
                'value["binding"]["attempt_id"]="during-run"; '
                f'path=Path({late!r}); path.parent.mkdir(); path.write_text(json.dumps(value)); print("real second microprocess")')
            second = self.runtime.run_command(self.repo / '.artifacts/formal-runs',
                [sys.executable, '-c', script], cwd=self.repo, binding={**binding, 'candidate_id': 'candidate-B'})
        old, new = json.loads(first_raw), json.loads((second / 'manifest.json').read_bytes())
        self.assertEqual(2, old['schema_version'], old)
        for manifest in (old, new):
            self.assertIs(type(manifest['elapsed_ns']), int)
            self.assertGreaterEqual(manifest['elapsed_ns'], 0)
            self.assertLess(manifest['finished_at'], manifest['started_at'])
        self.assertEqual([first_hash], new['completed_before'])
        self.assertNotIn(self.runtime.digest((self.repo / late).read_bytes()), new['completed_before'])
        self.assertEqual(first_raw, (first / 'manifest.json').read_bytes())


class CausalFailureBarrierTest(ChronologyFixture):
    def test_later_failure_blocks_old_pass_despite_earlier_wall_clock_for_point_and_batch(self):
        old = self.observation('pass')
        failure = self.observation('fail', before=[old['run_evidence']['sha256']],
            wall=('2029-01-01T00:00:00+00:00', '2029-01-01T00:00:01+00:00'))
        for batch in (False, True):
            with self.subTest(verified_batch_unit=batch):
                self.assertTrue(self.points.failure_barrier(self.repo, self.state, old, 'POINT', verified_batch_unit=batch))
        status = self.coverage()
        self.assertFalse(status['complete'], status)
        self.assertEqual(failure['attempt_id'], status['points']['POINT']['source_attempt_id'])

    def test_new_pass_after_failure_is_usable_despite_reversed_wall_clock(self):
        failure = self.observation('fail')
        good = self.observation('pass', before=[failure['run_evidence']['sha256']],
            wall=('2029-01-02T00:00:00+00:00', '2029-01-01T00:00:00+00:00'))
        status = self.coverage()
        self.assertTrue(status['complete'], status)
        self.assertEqual(good['attempt_id'], status['points']['POINT']['source_attempt_id'])

    def test_adopting_preparation_keeps_original_hash_order(self):
        source = self.observation('pass', kind='preparation')
        failure = self.observation('fail', before=[source['run_evidence']['sha256']],
            wall=('2029-01-01T00:00:00+00:00', '2029-01-01T00:00:01+00:00'))
        adopted = deepcopy(source)
        adopted.update(attempt_id='adopted', subtask_id='adopted', kind='ordinary', real_call_count=0,
                       source_preparation_attempt_id=source['attempt_id'])
        self.state['acceptance_gate']['attempts'].append(adopted)
        self.state['subtasks'].append({'subtask_id': 'adopted', 'status': 'completed',
            'dispatch': {'platform_agent_id': 'observer'},
            'result': {'expensive_acceptance': {'point_results': adopted['point_results']}}})
        status = self.coverage()
        self.assertFalse(status['complete'], status)
        self.assertEqual(failure['attempt_id'], status['points']['POINT']['source_attempt_id'])

    def test_missing_new_or_mixed_causal_edge_cannot_use_utc_to_hide_failure(self):
        original_repo = self.repo
        for version in (1, 2):
            with self.subTest(failure_version=version):
                self.state['acceptance_gate']['attempts'].clear()
                self.state['subtasks'].clear()
                # Unique fixture folders across the two independent examples.
                self.repo = original_repo / f'version-{version}'
                self.repo.mkdir()
                self.observation('fail', version=version)
                good = self.observation('pass', wall=('2031-01-01T00:00:00+00:00', '2031-01-01T00:00:01+00:00'))
                try:
                    self.assertTrue(self.points.failure_barrier(self.repo, self.state, good, 'POINT'))
                finally:
                    self.repo = original_repo

    def test_new_proven_success_can_follow_invalid_old_failure_without_rewriting_it(self):
        old = self.observation('fail', version=1,
            wall=('2030-01-02T00:00:00+00:00', '2030-01-01T00:00:00+00:00'))
        path = self.repo / old['run_evidence']['path']
        original = path.read_bytes()
        self.observation('pass', before=[old['run_evidence']['sha256']])
        status = self.coverage()
        self.assertTrue(status['complete'], status)
        self.assertEqual(original, path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'chronology|time'):
            self.points.run_manifest(self.repo, self.state, old)

    def test_old_backward_pass_and_malformed_new_protocol_never_downgrade_to_valid(self):
        old = self.observation('pass', version=1,
            wall=('2030-01-02T00:00:00+00:00', '2030-01-01T00:00:00+00:00'))
        with self.assertRaises(ValueError):
            self.points.run_manifest(self.repo, self.state, old)
        for malformed in ({'elapsed_ns': None}, {'elapsed_ns': True}, {'elapsed_ns': -1},
                          {'completed_before': None}, {'completed_before': ['invalid-digest']}):
            with self.subTest(malformed=malformed):
                bad = self.observation('pass', malformed=malformed)
                with self.assertRaises(ValueError):
                    self.points.run_manifest(self.repo, self.state, bad)


if __name__ == '__main__':
    unittest.main()
