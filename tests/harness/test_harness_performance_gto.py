"""Task 20261027 performance contracts: real I/O counts, no timing speed claims."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_gto_plan_preflight_contract import REPO_ROOT, load_controller

class PerformanceGto(unittest.TestCase):
    def setUp(self):
        root = REPO_ROOT / '.tmp/performance-qa'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.ctl = load_controller()
        import runtime_evidence
        self.runtime = runtime_evidence

    def state(self, inputs, items=()):
        return {'task_id':'perf', 'subtasks':[], 'findings':{},
                'acceptance_gate':{'candidate_inputs':inputs, 'acceptance_items':list(items)}}

    def put(self, path, data='x'):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)
        return target

    def test_482_declarations_38_files_read_once(self):
        paths = [f'src/{i}.py' for i in range(38)]
        for p in paths: self.put(p)
        inputs = {'code_paths':[paths[i % 38] for i in range(482)]}
        original = Path.read_bytes
        reads = Counter()
        def read(path):
            if path.is_relative_to(self.repo): reads[str(path)] += 1
            return original(path)
        with patch.object(Path, 'read_bytes', read):
            records = self.ctl._candidate_records(self.repo, self.state(inputs))
        print('482/38 observed reads:', sum(reads.values()))
        self.assertEqual(38, len(records))
        self.assertEqual(38, sum(reads.values()), 'duplicate declarations must not amplify content I/O')

    def test_nested_declarations_prune_walk_and_preserve_kind_precedence(self):
        target = self.put('src/nested/a.py')
        state = self.state({'code_paths':['src','src/nested','src/nested/a.py'],
                            'document_paths':['src/nested/a.py']}, [{'paths':['src']}])
        original = Path.read_bytes
        reads=[]
        def read(p):
            if p == target: reads.append(p)
            return original(p)
        with patch.object(Path,'read_bytes',read): records=self.ctl._candidate_records(self.repo,state)
        expected=self.ctl._candidate_path_records(self.repo,'document_paths','src/nested/a.py')[0]
        self.assertEqual(self.ctl._sha(expected),records['src/nested/a.py'])
        self.assertEqual(1,len(reads))

    def test_python_cache_noise_ignored_but_real_content_changes_detected(self):
        target=self.put('src/a.py','a')
        state=self.state({'code_paths':['src']})
        before=self.ctl._candidate_records(self.repo,state)
        self.put('src/__pycache__/a.pyc','cache')
        self.put('src/loose.pyc','cache')
        self.assertEqual(before,self.ctl._candidate_records(self.repo,state))
        target.write_text('b')
        self.assertNotEqual(before,self.ctl._candidate_records(self.repo,state))

    def test_symlink_change_and_escape_never_hidden(self):
        self.put('a','a'); self.put('b','b')
        link=self.repo/'link'; link.symlink_to(self.repo/'a')
        state=self.state({'code_paths':['a','link']})
        before=self.ctl._candidate_records(self.repo,state)
        link.unlink(); link.symlink_to(self.repo/'b')
        self.assertNotEqual(before,self.ctl._candidate_records(self.repo,state))
        link.unlink(); link.symlink_to(self.repo.parent)
        with self.assertRaises(self.ctl.ControlError): self.ctl._candidate_records(self.repo,state)

    def test_missing_empty_and_cycle_stay_visible(self):
        (self.repo/'empty').mkdir()
        records=self.ctl._candidate_records(self.repo,self.state({'code_paths':['missing','empty']}))
        self.assertEqual({'missing','empty'},set(records))
        (self.repo/'empty/loop').symlink_to(self.repo/'empty')
        with self.assertRaises(self.ctl.ControlError):
            self.ctl._candidate_records(self.repo,self.state({'code_paths':['empty']}))

    def test_validate_does_not_acquire_writer_lock_or_copy_events(self):
        state={'version':3,'task_id':'perf','status':'active','current_phase':'work','next_action':'next'}
        args=argparse.Namespace(Action='validate',RepoRoot=str(self.repo),TaskId='perf')
        with patch.object(self.ctl,'_load_state',return_value=state), \
             patch.object(self.ctl,'_validate_state',return_value=[]), \
             patch.object(self.ctl,'_session_summary',return_value={}), \
             patch.object(self.ctl,'_task_lock',side_effect=AssertionError('read-only entered writer lock')), \
             patch.object(self.ctl,'_preserve_artifacts_on_io_failure',side_effect=AssertionError('read-only copied events')):
            self.assertTrue(self.ctl._run(args)['ok'])

    def test_new_run_does_not_read_unrelated_history(self):
        unrelated=self.put('.artifacts/unrelated/manifest.json',json.dumps({'binding':{'task_id':'other'},'status':'passed'}))
        original=Path.read_bytes
        def read(p):
            if p==unrelated: raise AssertionError('unrelated history read')
            return original(p)
        with patch.object(Path,'read_bytes',read):
            run=self.runtime.run_command(self.repo/'.artifacts/runs',[sys.executable,'-c','pass'],cwd=self.repo,binding={'task_id':'perf'})
        self.assertEqual('passed',json.loads((run/'manifest.json').read_text())['status'])

    def test_new_run_causal_metadata_does_not_grow_per_predecessor(self):
        manifests=[]
        for _ in range(6):
            run=self.runtime.run_command(self.repo/'.artifacts/runs',[sys.executable,'-c','pass'],cwd=self.repo,binding={'task_id':'perf'})
            manifests.append(json.loads((run/'manifest.json').read_text()))
        self.assertLessEqual(len(manifests[-1].get('completed_before',[])),1,'causal metadata must be compact')
        self.assertGreaterEqual(manifests[-1]['schema_version'],3,'new causality requires explicit protocol version')

    def test_dependency_diamond_expanded_once_and_cycles_rejected(self):
        import acceptance_points
        counts=Counter()
        class Item(dict):
            def get(self,key,default=None):
                if key=='depends_on': counts[self['acceptance_id']]+=1
                return super().get(key,default)
        items=[Item(acceptance_id='a',depends_on=[]),Item(acceptance_id='b',depends_on=['a']),
               Item(acceptance_id='c',depends_on=['a']),Item(acceptance_id='d',depends_on=['b','c'])]
        _,closure=acceptance_points.definitions({'acceptance_items':items})
        self.assertEqual({'a','b','c','d'},closure['d'])
        self.assertLessEqual(max(counts.values()),1,'shared dependency must not be recursively expanded again')
        items[0]['depends_on']=['d']
        with self.assertRaises(ValueError): acceptance_points.definitions({'acceptance_items':items})

class PerformanceEvidence(unittest.TestCase):
    def setUp(self):
        import test_gto_capability_gate as existing
        existing.CapabilityGateTest.setUp(self)
    api = lambda self, name: getattr(self.ctl,name)
    def payload(self, status='passed'):
        import test_gto_capability_gate as existing
        return existing.CapabilityGateTest.payload(self,status)

    def test_capability_json_hash_and_parse_use_one_read(self):
        payload=self.payload(); target=self.repo/'.artifacts/probe.json'
        real=Path.open; reads=[]
        def opened(p,*a,**kw):
            mode=a[0] if a else kw.get('mode','r')
            if p==target and 'r' in mode: reads.append(mode)
            return real(p,*a,**kw)
        with patch.object(Path,'open',opened):
            receipt=self.ctl._capability_receipt(self.repo,self.task,payload)
        self.assertEqual('passed',receipt['status'])
        self.assertEqual(1,len(reads),'JSON must be parsed from the same bytes verified by its hash')

    def test_capability_json_cannot_mix_executor_from_unhashed_read(self):
        payload=self.payload(); target=self.repo/'.artifacts/probe.json'
        original=Path.read_text
        def text(p,*a,**kw):
            raw=original(p,*a,**kw)
            if p==target:
                value=json.loads(raw); value['context']['executor_id']='injected-unhashed-executor'
                return json.dumps(value)
            return raw
        with patch.object(Path,'read_text',text):
            receipt=self.ctl._capability_receipt(self.repo,self.task,payload)
        self.assertNotIn('executor_id',receipt['context'])

    def test_summary_shares_dependency_and_probe_reads_across_tasks(self):
        import copy
        payload=self.payload(); receipt=self.ctl._capability_receipt(self.repo,self.task,payload)
        first=self.task; first['status']='ready'
        second=copy.deepcopy(first); second['subtask_id']='UI-002'
        other=copy.deepcopy(receipt); other['subtask_id']='UI-002'
        state={'subtasks':[first,second],'capability_receipts':[receipt,other], 'findings':{},
               'task_id':'perf','acceptance_gate':{'candidate_inputs':{},'acceptance_items':[]}}
        original=Path.read_bytes; counts=Counter()
        def read(p):
            if p.is_relative_to(self.repo): counts[str(p)]+=1
            return original(p)
        with patch.object(Path,'read_bytes',read): result=self.ctl._session_summary(self.repo,state)
        self.assertEqual({'UI-001':[],'UI-002':[]},result['capability_checks'])
        self.assertEqual(1,max(counts.values()),'summary shares one stable validation stage')

class PerformanceStableStage(unittest.TestCase):
    setUp=PerformanceGto.setUp
    put=PerformanceGto.put
    # Only the methods defined here are collected by the explicit Red invocation.
    def context(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('verification_context'),'missing operation-scoped verification context')
        import verification_context
        return verification_context

    def test_operation_shares_source_candidate_runtime_and_git_inventory(self):
        ctx=self.context(); self.put('src/a.py'); self.put('runtime/SKILL.md')
        state=PerformanceGto.state(self,{'code_paths':['src']})
        state['subtasks']=[{'write_paths':['src'],'result':{'changed_files':['src/a.py']}}]
        original=Path.read_bytes; reads=Counter()
        def read(p):
            if p.is_relative_to(self.repo): reads[str(p)]+=1
            return original(p)
        with patch.object(Path,'read_bytes',read), \
             patch.object(self.ctl,'_git_dirty_paths',return_value=[]) as git,ctx.operation():
            for _ in range(2):
                self.ctl._source_manifest(self.repo,state)
                self.ctl._candidate_records(self.repo,state)
                self.runtime.tree_manifest(self.repo/'runtime')
        self.assertEqual(1,max(reads.values()),'shared stable phase duplicated physical content reads')
        self.assertEqual(1,git.call_count,'shared stable phase duplicated Git status')

    def test_context_reads_once_but_new_operation_sees_changes(self):
        ctx=self.context(); p=self.put('source','first'); real=Path.read_bytes; seen=[]
        def read(path): seen.append(path); return real(path)
        with patch.object(Path,'read_bytes',read),ctx.operation():
            self.assertEqual(b'first',ctx.read_bytes(p)); self.assertEqual(b'first',ctx.read_bytes(p))
        self.assertEqual(1,len(seen))
        p.write_text('second')
        with ctx.operation(): self.assertEqual(b'second',ctx.read_bytes(p))

    def test_context_rejects_inflight_content_change(self):
        ctx=self.context(); p=self.put('source','first')
        with self.assertRaisesRegex(Exception, "changed|unstable|mutation|retarget|symlink"):
            with ctx.operation():
                ctx.read_bytes(p); p.write_text('changed')

    def test_context_rejects_link_retarget_after_cache_hit(self):
        ctx=self.context(); a=self.put('a'); b=self.put('b','b'); link=self.repo/'link'; link.symlink_to(a)
        with self.assertRaisesRegex(Exception, "changed|unstable|mutation|retarget|symlink"):
            with ctx.operation():
                ctx.read_bytes(link); link.unlink(); link.symlink_to(b); ctx.read_bytes(link)

    def test_commit_rehash_rejects_same_metadata_changed_bytes(self):
        ctx=self.context(); p=self.put('source','before'); stamp=ctx.identity(p)
        with patch.object(ctx,'identity',return_value=stamp),ctx.operation() as stage:
            ctx.read_bytes(p); p.write_text('after!')
            with self.assertRaisesRegex(ctx.ChangedDuringVerification,'contents changed'):
                stage.recheck_strong()

    def test_commit_reenumerates_directory_even_with_unchanged_metadata(self):
        ctx=self.context(); (self.repo/'inputs').mkdir(); directory=self.repo/'inputs'
        stamp=ctx.identity(directory)
        with patch.object(ctx,'identity',return_value=stamp),ctx.operation() as stage:
            ctx.children(directory); (directory/'new-input').write_text('new')
            with self.assertRaisesRegex(ctx.ChangedDuringVerification,'directory changed'):
                stage.recheck_strong()

    def test_large_digest_streams_without_retaining_raw_bytes(self):
        ctx=self.context(); p=self.repo/'large.log'; p.write_bytes(b'x'*(2*1024*1024))
        with ctx.operation() as stage:
            first=ctx.file_digest(p); second=ctx.file_digest(p)
            self.assertEqual(first,second)
            self.assertEqual(1,stage.metrics['read_calls'])
            self.assertEqual(0,stage.content_bytes)
            self.assertEqual({},stage.contents)
            checked=stage.recheck_strong()
            self.assertEqual(1,checked['read_calls'])

class PerformanceCausality(unittest.TestCase):
    setUp=PerformanceGto.setUp
    def history(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('causal_history'),'missing task-local causal history protocol')
        import causal_history
        return causal_history
    def run_small(self):
        path=self.runtime.run_command(self.repo/'.artifacts/runs',[sys.executable,'-c','pass'],cwd=self.repo,binding={'task_id':'perf'})/'manifest.json'
        return json.loads(path.read_bytes()),self.runtime.digest(path.read_bytes())

    def test_start_before_concurrent_completion_cannot_adopt_future_evidence(self):
        history=self.history(); start=history.capture_start(self.repo,'perf')
        _,seal=self.run_small()
        current={'schema_version':3,'binding':{'task_id':'perf'},'causal_start':start}
        self.assertFalse(history.causal_after(self.repo,current,seal))

    def test_completed_edge_survives_wall_clock_reversal_and_rejects_cross_task(self):
        history=self.history(); previous,seal=self.run_small(); current,_=self.run_small()
        current['started_at']='2000-01-01T00:00:00+00:00'
        current['finished_at']='1999-01-01T00:00:00+00:00'
        self.assertTrue(history.causal_after(self.repo,current,seal))
        current['binding']['task_id']='other'
        self.assertFalse(history.causal_after(self.repo,current,seal))

    def test_missing_causal_node_cannot_cover_prior_failure(self):
        history=self.history(); _,seal=self.run_small(); current,_=self.run_small()
        self.assertTrue(history.causal_after(self.repo,current,seal))
        nodes=self.repo/'.artifacts/gto/perf/causal/nodes'
        self.assertTrue(nodes.is_dir())
        for path in nodes.glob('*.json'): path.unlink()
        self.assertFalse(history.causal_after(self.repo,current,seal))

    def test_missing_head_with_existing_nodes_rejects_new_capture(self):
        history=self.history(); self.run_small()
        (self.repo/'.artifacts/gto/perf/causal/head.json').unlink()
        with self.assertRaisesRegex(ValueError,'head missing'): history.capture_start(self.repo,'perf')

    def test_symlink_head_and_node_are_never_trusted(self):
        history=self.history(); _,seal=self.run_small(); current,_=self.run_small()
        root=self.repo/'.artifacts/gto/perf/causal'
        head=root/'head.json'; saved=self.repo/'saved-head.json'; saved.write_bytes(head.read_bytes())
        head.unlink(); head.symlink_to(saved)
        with self.assertRaisesRegex(ValueError,'symlink'): history.capture_start(self.repo,'perf')
        head.unlink(); head.write_bytes(saved.read_bytes())
        node=root/'nodes'/(current['causal_start']['head']+'.json')
        saved_node=self.repo/'saved-node.json'; saved_node.write_bytes(node.read_bytes())
        node.unlink(); node.symlink_to(saved_node)
        self.assertFalse(history.causal_after(self.repo,current,seal))

    def test_finalizer_failure_retains_invalidated_manifest_and_child_output(self):
        def broken(manifest): raise RuntimeError('injected finalizer failure')
        run=self.runtime.run_command(self.repo/'.artifacts/runs',[sys.executable,'-c','print("kept output")'],
            cwd=self.repo,binding={'task_id':'perf'},finalizer=broken)
        manifest=json.loads((run/'manifest.json').read_bytes())
        self.assertEqual('invalidated',manifest['status'])
        self.assertIn('injected finalizer failure',manifest['error'])
        self.assertIn('kept output',(run/'stdout.log').read_text())
        self.assertEqual(manifest,self.runtime.verify_run(run,{'task_id':'perf'},repo=self.repo))

    def test_legacy_import_reads_only_registered_original_bytes(self):
        history=self.history()
        legacy={'schema_version':1,'status':'failed','binding':{'task_id':'perf'},
                'started_at':'2026-01-01T00:00:00+00:00','finished_at':'2026-01-01T00:00:01+00:00'}
        path=self.repo/'.artifacts/legacy/manifest.json'; path.parent.mkdir(parents=True)
        path.write_text(json.dumps(legacy)); original=path.read_bytes(); seal=self.runtime.digest(original)
        foreign=self.repo/'.artifacts/foreign/manifest.json'; foreign.parent.mkdir(); foreign.write_text('must not read')
        state={'task_id':'perf','acceptance_gate':{'attempts':[{'run_evidence':{'path':path.relative_to(self.repo).as_posix(),'sha256':seal}}]}}
        real=Path.read_bytes
        def read(p):
            if p==foreign: raise AssertionError('unregistered legacy source scanned')
            return real(p)
        with patch.object(Path,'read_bytes',read): self.runtime._import_registered_runs(self.repo,state)
        current,_=self.run_small()
        self.assertTrue(history.causal_after(self.repo,current,seal))
        self.assertEqual(original,path.read_bytes())
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'hash changed'): self.runtime._import_registered_runs(self.repo,state)

    def test_elapsed_includes_capture_and_log_hashing(self):
        history=self.history(); clock=[0]; real_capture=history.capture_start; real_open=Path.open
        def capture(*args): clock[0]+=2_000_000_000; return real_capture(*args)
        def opened(path,*args,**kwargs):
            mode=args[0] if args else kwargs.get('mode','r')
            if path.name in {'stdout.log','stderr.log'} and mode=='rb': clock[0]+=2_000_000_000
            return real_open(path,*args,**kwargs)
        with patch.object(history,'capture_start',capture),patch.object(Path,'open',opened), \
             patch.object(self.runtime.time,'monotonic_ns',side_effect=lambda:clock[0]):
            manifest,_=self.run_small()
        self.assertGreaterEqual(manifest['elapsed_ns'],6_000_000_000,'capture and both log hashes must be within measured elapsed')

    def test_diagnostic_total_includes_causal_publication(self):
        import inspect
        self.assertIn('metrics',inspect.signature(self.runtime.run_command).parameters,'missing total operation metrics output')
        history=self.history(); clock=[0]; real_publish=history.publish_completed; metrics={}
        def publish(*args): clock[0]+=3_000_000_000; return real_publish(*args)
        with patch.object(history,'publish_completed',publish), \
             patch.object(self.runtime.time,'monotonic_ns',side_effect=lambda:clock[0]):
            path=self.runtime.run_command(self.repo/'.artifacts/runs',[sys.executable,'-c','pass'],cwd=self.repo,binding={'task_id':'perf'},metrics=metrics)
        self.assertGreaterEqual(metrics['run_total_ns'],3_000_000_000)
        self.assertNotIn('performance',json.loads((path/'manifest.json').read_bytes()),'diagnostic timing must not change signed evidence shape')

    def test_timeout_kills_term_ignoring_child_after_leader_exits(self):
        import os
        import signal
        pidfile=self.repo/'child.pid'
        child='import os,signal,time,pathlib,sys; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)'
        leader='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]]); time.sleep(30)'
        pid=None
        try:
            run=self.runtime.run_command(self.repo/'.artifacts/runs',[sys.executable,'-c',leader,child,str(pidfile)],cwd=self.repo,binding={'task_id':'perf'},timeout=0.8)
            self.assertTrue(pidfile.exists(),'child did not reach signal-handler readiness')
            pid=int(pidfile.read_text()); stat=Path(f'/proc/{pid}/stat')
            self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z','timeout returned with live TERM-ignoring child')
            self.assertEqual('interrupted',json.loads((run/'manifest.json').read_bytes())['status'])
        finally:
            if pid is None and pidfile.exists(): pid=int(pidfile.read_text())
            if pid:
                try: os.kill(pid,signal.SIGKILL)
                except ProcessLookupError: pass
if __name__=='__main__': unittest.main()
