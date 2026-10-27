"""Isolated tool performance contracts; never accesses the installed shared home."""
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from test_sync_codex_scope import SYNC, ROOT
sys.path.insert(0,str(ROOT/'scripts'))
import runtime_common
import task_workspace

class PerformanceTools(unittest.TestCase):
    def setUp(self):
        root=ROOT/'.tmp/performance-qa'; root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root); self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)
        self.source=self.repo/'source'; self.home=self.repo/'home'
        for name in SYNC.MANAGED_SKILLS:
            p=self.source/'skills'/name/'SKILL.md'; p.parent.mkdir(parents=True); p.write_text(name)

    def test_noop_sync_performs_zero_tree_replacements_and_preserves_receipt(self):
        self.assertTrue(SYNC.synchronize(self.source,self.home)['ok'])
        receipt=self.home/'.ai-harness/codex-sync.receipt.json'
        before=(receipt.read_bytes(),receipt.stat().st_mtime_ns)
        with patch.object(SYNC,'_replace_tree',wraps=SYNC._replace_tree) as replace:
            result=SYNC.synchronize(self.source,self.home)
        self.assertTrue(result['ok'])
        self.assertFalse(result['runtime_changed'])
        self.assertEqual(0,replace.call_count,'no-op sync must not copy and replace trees')
        self.assertEqual(before,(receipt.read_bytes(),receipt.stat().st_mtime_ns))

    def test_sync_source_hashes_once_and_prepares_outside_publication_lock(self):
        calls=Counter(); held=[False]
        real_hash=SYNC.sha256_file; real_lock=SYNC.fcntl.flock
        def lock(fd,operation):
            result=real_lock(fd,operation)
            held[0]=operation != SYNC.fcntl.LOCK_UN
            return result
        def digest(p):
            if Path(p).is_relative_to(self.source):
                calls[(held[0],str(p))]+=1
            return real_hash(p)
        with patch.object(SYNC.fcntl,'flock',lock),patch.object(SYNC,'sha256_file',digest):
            result=SYNC.synchronize(self.source,self.home)
        self.assertTrue(result['ok'])
        self.assertTrue(any(not locked for locked,path in calls),'source preparation must precede publication lock')
        self.assertEqual(1,max(calls.values()))

    def test_shared_ordinary_evidence_is_hashed_once(self):
        log=self.repo/'log.txt'; log.write_text('actual evidence')
        report=self.repo/'report.json'
        report.write_text(json.dumps({'actor':'qa','outcome':'pass','summary':'checked', 'evidence':['log.txt']*20}))
        real=task_workspace.digest; calls=Counter()
        def digest(p): calls[str(p)]+=1; return real(p)
        with patch.object(task_workspace,'digest',digest):
            _,manifest=task_workspace.evidence_files(self.repo,'report.json','plan')
        self.assertEqual({'report.json','log.txt'},set(manifest))
        self.assertEqual(1,max(calls.values()))

    def test_verified_stage_does_not_rehash_same_evidence(self):
        (self.repo/'log').write_text('evidence')
        (self.repo/'report.json').write_text(json.dumps({'actor':'coord','outcome':'pass','summary':'investigated','evidence':['log']}))
        _,files=task_workspace.evidence_files(self.repo,'report.json','investigation')
        state={'stages':[{'stage':'investigation','evidence':'report.json','files':files}]}
        real=task_workspace.digest; calls=Counter()
        def digest(p): calls[str(p)]+=1; return real(p)
        with patch.object(task_workspace,'digest',digest):
            task_workspace.verified_stages(self.repo,state)
        self.assertEqual(1,max(calls.values()))
        (self.repo/'log').write_text('tampered')
        with self.assertRaises(task_workspace.TaskError): task_workspace.verified_stages(self.repo,state)

    def test_probe_deadline_kills_descendants(self):
        self.assertTrue(hasattr(runtime_common,'run_probe'),'missing bounded probe executor run_probe')
        pidfile=self.repo/'child.pid'
        code="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); open(sys.argv[1],'w').write(str(p.pid)); time.sleep(30)"
        started=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            runtime_common.run_probe([sys.executable,'-c',code,str(pidfile)],timeout=0.5,capture_output=True,text=True)
        self.assertLess(time.monotonic()-started,4)
        self.assertTrue(pidfile.is_file())
        pid=int(pidfile.read_text())
        stat=Path(f'/proc/{pid}/stat')
        # A reaped process or a transient zombie cannot execute further work.
        self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z','descendant remained running')

    def test_expired_probe_deadline_does_not_launch(self):
        self.assertTrue(hasattr(runtime_common,'run_probe'),'missing bounded probe executor run_probe')
        with patch.object(subprocess,'Popen',side_effect=AssertionError('expired deadline launched a process')):
            with self.assertRaises(subprocess.TimeoutExpired):
                runtime_common.run_probe([sys.executable,'-c','pass'],deadline=time.monotonic()-1)

    def test_doctor_reuses_collected_skill_inventory(self):
        from contextlib import ExitStack
        spec=importlib.util.spec_from_file_location('performance_doctor',ROOT/'scripts/doctor-core.py')
        doctor=importlib.util.module_from_spec(spec); spec.loader.exec_module(doctor)
        SYNC.synchronize(self.source,self.home)
        calls=Counter(); original=doctor._files
        def files(root): calls[str(root)]+=1; return original(root)
        with ExitStack() as stack:
            stack.enter_context(patch.object(doctor,'_files',files))
            for name in ('_bootstrap_audit','_hook_audit','_docker_safe_start_audit','inspect_windows_external_capabilities'):
                stack.enter_context(patch.object(doctor,name,return_value={'issues':[]}))
            stack.enter_context(patch.object(doctor,'_wsl_runtime_audit',return_value=[]))
            stack.enter_context(patch.object(doctor,'_installed_gto_validation',return_value={'ok':True}))
            stack.enter_context(patch.object(doctor,'_wsl_tool_audit',return_value={'missing_tools':[],'windows_path_tools':[]}))
            stack.enter_context(patch.object(doctor,'_machine_environment_findings',return_value=[]))
            result=doctor.audit(self.source,self.home)
        self.assertTrue(result['ok'],result)
        self.assertEqual(1,max(calls.values()),'receipt comparison must reuse inventory, not rehash it')

    def test_missing_binding_index_still_discovers_active_task(self):
        common=self.repo/'git-common'; common.mkdir()
        task=self.repo/'docs/tasks/active/task.json'; task.parent.mkdir(parents=True)
        task.write_text(json.dumps({'task_id':'active','checkout_binding':task_workspace.binding(self.repo)}))
        with patch.object(task_workspace,'git',return_value=(0,f'worktree {self.repo}\n')), \
             patch.object(task_workspace,'load_record',return_value={}):
            rows=task_workspace.discover(self.repo,common)
        self.assertIn('active',rows,'missing index must not imply idle checkout')

    def test_exhausted_shared_probe_budget_never_launches(self):
        self.assertTrue(hasattr(runtime_common,'probe_budget'),'missing per-operation probe budget')
        with runtime_common.probe_budget(0),patch.object(subprocess,'Popen',side_effect=AssertionError('exhausted budget launched child')):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                runtime_common.run_probe([sys.executable,'-c','pass'],timeout=5)
        self.assertIn('probe_budget_exhausted',str(caught.exception)+str(caught.exception.stderr))

    def test_serial_probes_share_remaining_deadline(self):
        self.assertTrue(hasattr(runtime_common,'probe_budget'),'missing per-operation probe budget')
        started=time.monotonic()
        with runtime_common.probe_budget(0.6):
            first=runtime_common.run_probe([sys.executable,'-c','import time; time.sleep(0.3)'],timeout=5)
            self.assertEqual(0,first.returncode)
            with self.assertRaises(subprocess.TimeoutExpired):
                runtime_common.run_probe([sys.executable,'-c','import time; time.sleep(2)'],timeout=5)
        self.assertLess(time.monotonic()-started,1.5,'each probe restarted the shared operation budget')

    def test_venv_probe_preserves_shared_budget_classification(self):
        spec=importlib.util.spec_from_file_location('performance_project_doctor',ROOT/'scripts/project-env-doctor.py')
        doctor=importlib.util.module_from_spec(spec); spec.loader.exec_module(doctor)
        with patch.object(doctor,'run_probe',side_effect=runtime_common.ProbeBudgetExpired(['fixture'],0)):
            with self.assertRaises(runtime_common.ProbeBudgetExpired):
                doctor._is_isolated_venv(Path(sys.executable),self.repo/'venv')
    def test_project_doctor_entry_reports_exhausted_operation_budget(self):
        import io
        from contextlib import redirect_stdout
        spec=importlib.util.spec_from_file_location('performance_project_entry',ROOT/'scripts/project-env-doctor.py')
        doctor=importlib.util.module_from_spec(spec); spec.loader.exec_module(doctor)
        output=io.StringIO()
        argv=['project-env-doctor','--project-root',str(ROOT),'--environment',str(ROOT/'config/ai/environment.json'),'--json']
        with runtime_common.probe_budget(0),patch.object(sys,'argv',argv),redirect_stdout(output), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('exhausted entry launched process')):
            code=doctor.main()
        payload=json.loads(output.getvalue())
        self.assertNotEqual(0,code)
        self.assertEqual('probe_budget_exhausted',payload['error']['category'])
        self.assertNotIn('system_python_venv',str(payload['findings']))
    def test_machine_doctor_entry_reports_exhausted_operation_budget(self):
        import io
        from contextlib import redirect_stdout
        spec=importlib.util.spec_from_file_location('performance_machine_entry',ROOT/'scripts/doctor-core.py')
        doctor=importlib.util.module_from_spec(spec); spec.loader.exec_module(doctor)
        output=io.StringIO()
        def probe(*args): runtime_common.run_probe([sys.executable,'-c','pass']); return []
        argv=['doctor-core','--repo-root',str(ROOT),'--codex-home',str(self.home),'--environment-only','--json']
        with runtime_common.probe_budget(0),patch.object(sys,'argv',argv),redirect_stdout(output), \
             patch.object(doctor,'_wsl_runtime_audit',probe), \
             patch.object(subprocess,'Popen',side_effect=AssertionError('exhausted entry launched process')):
            code=doctor.main()
        self.assertNotEqual(0,code)
        self.assertIn('probe_budget_exhausted',json.loads(output.getvalue())['errors'])
if __name__=='__main__': unittest.main()
