"""Deterministic transaction race injection at the real commit boundary."""
import argparse
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import unittest
import test_harness_performance_gto as gto

class PerformanceTransactions(unittest.TestCase):
    setUp=gto.PerformanceGto.setUp
    put=gto.PerformanceGto.put
    def prepare(self):
        self.paths=self.ctl._task_paths(self.repo,'perf')
        for name,path in self.paths.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('original '+name+'\n')
        self.before={name:p.read_bytes() for name,p in self.paths.items()}
        self.args=argparse.Namespace(Action='set-phase',RepoRoot=str(self.repo),TaskId='perf')
    def dispatch(self,args):
        self.ctl._atomic_write(self.paths['state.json'],'new state')
        self.ctl._append_event(self.paths['events.jsonl'],'perf','committed')
        return {'ok':True}

    def test_state_conflict_rejects_staged_writes_and_preserves_concurrent_state(self):
        self.prepare()
        @contextmanager
        def race(*args):
            self.assertEqual(self.before,{n:p.read_bytes() for n,p in self.paths.items()},'writes escaped preparation')
            self.paths['state.json'].write_text('concurrent state')
            yield
        with patch.object(self.ctl,'_run_dispatch',self.dispatch),patch.object(self.ctl,'_task_lock',race), \
             patch.object(self.ctl,'_transaction_git_snapshot',return_value=None):
            with self.assertRaisesRegex(self.ctl.ControlError,'control input changed'): self.ctl._run(self.args)
        self.assertEqual('concurrent state',self.paths['state.json'].read_text())
        self.assertEqual(self.before['events.jsonl'],self.paths['events.jsonl'].read_bytes())

    def test_business_input_drift_rejected_before_any_commit(self):
        self.prepare(); source=self.put('business.py','initial')
        import verification_context as context
        def dispatch(args): context.read_bytes(source); return self.dispatch(args)
        @contextmanager
        def race(*args): source.write_text('mutated'); yield
        with patch.object(self.ctl,'_run_dispatch',dispatch),patch.object(self.ctl,'_task_lock',race), \
             patch.object(self.ctl,'_transaction_git_snapshot',return_value=None):
            with self.assertRaisesRegex(OSError,'changed'): self.ctl._run(self.args)
        self.assertEqual(self.before,{n:p.read_bytes() for n,p in self.paths.items()})

    def test_git_change_rejects_commit(self):
        self.prepare()
        with patch.object(self.ctl,'_run_dispatch',self.dispatch), \
             patch.object(self.ctl,'_transaction_git_snapshot',side_effect=[('before',),('after',)]):
            with self.assertRaisesRegex(self.ctl.ControlError,'Git inputs changed'): self.ctl._run(self.args)
        self.assertEqual(self.before,{n:p.read_bytes() for n,p in self.paths.items()})

    def test_partial_event_append_rolls_back_without_reading_event_history(self):
        self.prepare(); real=Path.read_bytes
        def read(p):
            if p==self.paths['events.jsonl']: raise AssertionError('transaction read full event history')
            return real(p)
        def fail(path,record):
            with path.open('a') as stream: stream.write('partial new event')
            raise OSError('injected append failure')
        with patch.object(self.ctl,'_run_dispatch',self.dispatch),patch.object(Path,'read_bytes',read), \
             patch.object(self.ctl,'_append_event_record',fail), \
             patch.object(self.ctl,'_transaction_git_snapshot',return_value=None):
            with self.assertRaisesRegex(self.ctl.ControlError,'restored'): self.ctl._run(self.args)
        self.assertEqual(self.before,{n:p.read_bytes() for n,p in self.paths.items()})

    def test_init_failure_restores_preexisting_event_bytes_not_just_length(self):
        self.prepare(); self.paths['state.json'].unlink()
        original_events=b'original retained event history\xff\x00\n'
        self.paths['events.jsonl'].write_bytes(original_events)
        contract=self.put('.tmp/contract.json','{}')
        args=argparse.Namespace(Action='init-task',RepoRoot=str(self.repo),TaskId='perf',ContractJsonFile=str(contract))
        with patch.object(self.ctl,'_initial_state',return_value=({'task_id':'perf'},{'task.md':'new task'})), \
             patch.object(self.ctl,'_write_state',side_effect=OSError('injected init state failure')):
            with self.assertRaises(self.ctl.ControlError): self.ctl._run(args)
        self.assertFalse(self.paths['state.json'].exists())
        self.assertEqual(original_events,self.paths['events.jsonl'].read_bytes(),'init truncates events and needs full original bytes for rollback')
        self.assertEqual(self.before['task.md'],self.paths['task.md'].read_bytes())

    def test_freeze_capture_is_prepared_outside_writer_lock(self):
        self.prepare(); self.args.Action='freeze-candidate'; locked=[False]
        @contextmanager
        def lock(*args):
            locked[0]=True
            try: yield
            finally: locked[0]=False
        def capture(*args):
            self.assertFalse(locked[0],'freeze capture entered writer lock')
            self.ctl._atomic_write(self.paths['state.json'],'frozen state')
            return {'ok':True}
        state={'version':3,'task_id':'perf'}
        with patch.object(self.ctl,'_task_lock',lock),patch.object(self.ctl,'_load_state',return_value=state), \
             patch.object(self.ctl,'_state_model_errors',return_value=[]), \
             patch.object(self.ctl,'_latest_effect_failure',return_value=None), \
             patch.object(self.ctl,'_freeze_candidate',capture), \
             patch.object(self.ctl,'_transaction_git_snapshot',return_value=None):
            self.assertTrue(self.ctl._run(self.args)['ok'])
        self.assertEqual('frozen state',self.paths['state.json'].read_text())

    def test_frozen_tree_publisher_refuses_changed_existing_archive(self):
        self.assertTrue(hasattr(self.ctl,'_publish_frozen_tree'),'missing staged frozen tree publisher')
        source=self.repo/'source'; source.mkdir(); (source/'a').write_text('expected')
        expected=self.runtime.tree_manifest(source)
        staged=self.repo/'staged'; self.runtime.freeze_tree(source,staged)
        destination=self.repo/'published'; destination.mkdir(); (destination/'a').write_text('do not overwrite')
        with self.assertRaises((ValueError,self.ctl.ControlError)):
            self.ctl._publish_frozen_tree(staged,destination,expected)
        self.assertEqual('do not overwrite',(destination/'a').read_text())

    def staged_freeze(self):
        self.prepare(); self.args.Action='freeze-candidate'
        self.source=self.repo/'runtime-source'; self.source.mkdir(); (self.source/'SKILL.md').write_text('runtime')
        self.destination=self.repo/'.artifacts/frozen/runtime'; self.expected=self.runtime.tree_manifest(self.source)
        def dispatch(args):
            self.ctl._prepare_frozen_tree(self.source,self.destination,self.repo/'.tmp/staging',self.expected)
            self.ctl._atomic_write(self.paths['state.json'],'frozen state')
            return {'ok':True}
        return dispatch

    def test_freeze_source_drift_prevents_state_and_archive_commit(self):
        self.assertTrue(hasattr(self.ctl,'_prepare_frozen_tree'),'missing staged freeze preparation')
        dispatch=self.staged_freeze()
        @contextmanager
        def lock(*args): (self.source/'SKILL.md').write_text('changed'); yield
        with patch.object(self.ctl,'_run_dispatch',dispatch),patch.object(self.ctl,'_task_lock',lock), \
             patch.object(self.ctl,'_transaction_git_snapshot',return_value=None):
            with self.assertRaisesRegex((OSError,self.ctl.ControlError),'changed'): self.ctl._run(self.args)
        self.assertEqual(self.before['state.json'],self.paths['state.json'].read_bytes())
        self.assertFalse(self.destination.exists())

    def test_freeze_publication_failure_never_commits_new_state(self):
        self.assertTrue(hasattr(self.ctl,'_prepare_frozen_tree'),'missing staged freeze preparation')
        dispatch=self.staged_freeze()
        with patch.object(self.ctl,'_run_dispatch',dispatch), \
             patch.object(self.ctl,'_publish_frozen_tree',side_effect=OSError('injected tree publication failure')), \
             patch.object(self.ctl,'_transaction_git_snapshot',return_value=None):
            with self.assertRaisesRegex((OSError,self.ctl.ControlError),'publication failure'): self.ctl._run(self.args)
        self.assertEqual(self.before['state.json'],self.paths['state.json'].read_bytes())
        self.assertFalse(self.destination.exists())

    def test_freeze_concurrent_state_winner_is_not_overwritten(self):
        self.assertTrue(hasattr(self.ctl,'_prepare_frozen_tree'),'missing staged freeze preparation')
        dispatch=self.staged_freeze()
        @contextmanager
        def lock(*args): self.paths['state.json'].write_text('other freeze committed'); yield
        with patch.object(self.ctl,'_run_dispatch',dispatch),patch.object(self.ctl,'_task_lock',lock), \
             patch.object(self.ctl,'_transaction_git_snapshot',return_value=None):
            with self.assertRaisesRegex(self.ctl.ControlError,'control input changed'): self.ctl._run(self.args)
        self.assertEqual('other freeze committed',self.paths['state.json'].read_text())
        self.assertFalse(self.destination.exists())

    def test_git_status_failure_in_real_repository_is_not_missing_git(self):
        import subprocess
        (self.repo/'.git').mkdir()
        failed=subprocess.CompletedProcess(['git'],128,'','fatal: cannot read index: Permission denied')
        with patch.object(self.ctl.subprocess,'run',return_value=failed):
            with self.assertRaises(self.ctl.ControlError):
                self.ctl._transaction_git_snapshot(self.repo)
if __name__=='__main__': unittest.main()
