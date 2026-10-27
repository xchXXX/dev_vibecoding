"""Small bootstrap publication boundary probes without real host installation."""
import argparse
from contextlib import redirect_stdout
import fcntl
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import test_harness_performance_tools as fixtures

class PerformancePublication(unittest.TestCase):
    setUp=fixtures.PerformanceTools.setUp
    def bootstrap(self, gate=None, audit=None):
        spec=importlib.util.spec_from_file_location('qa_bootstrap',fixtures.ROOT/'scripts/bootstrap-local.py')
        boot=importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)
        entry=self.source/'rules/registry/RULES_ENTRY.md'; entry.parent.mkdir(parents=True,exist_ok=True); entry.write_text('# fixture harness')
        template=self.source/'templates/codex/AGENTS.global.md'; template.parent.mkdir(parents=True,exist_ok=True)
        template.write_text(boot.MANAGED_MARKER+'\nnew managed instructions\n')
        self.home.mkdir(exist_ok=True)
        (self.home/'AGENTS.md').write_text(boot.MANAGED_MARKER+'\nold instructions\n')
        (self.home/'hooks.json').write_text('{}')
        before={p.relative_to(self.home).as_posix():p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        doctor=SimpleNamespace(_contract_gate=gate or (lambda root:{'ok':True}),audit=audit or (lambda *a,**k:{'ok':True}))
        output=io.StringIO()
        argv=['bootstrap-local.py','--harness-root',str(self.source),'--codex-home',str(self.home),
              '--skip-rules','--skip-sync','--json']
        with patch.object(sys,'argv',argv),patch.object(boot,'_doctor_module',return_value=doctor), \
             patch.object(boot,'inspect_windows_external_capabilities',return_value={'issues':[]}),redirect_stdout(output):
            code=boot.main()
        return code,json.loads(output.getvalue()),before

    def test_source_contract_gate_runs_before_publication_lock(self):
        observed=[]
        def gate(root):
            lock=self.home/'.ai-harness/codex-sync.lock'; lock.parent.mkdir(parents=True,exist_ok=True)
            with lock.open('a+') as handle:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                observed.append(True)
                fcntl.flock(handle,fcntl.LOCK_UN)
            return {'ok':True}
        code,result,_=self.bootstrap(gate=gate)
        self.assertEqual(0,code,result)
        self.assertEqual([True],observed)

    def test_source_generation_change_during_gate_rejects_before_write(self):
        def gate(root):
            (self.source/'skills/global-task-orchestrator/SKILL.md').write_text('changed during gate')
            return {'ok':True}
        code,result,before=self.bootstrap(gate=gate)
        self.assertNotEqual(0,code)
        self.assertIn('publication_source_changed',' '.join(result['issues']))
        self.assertEqual(before,{p:(self.home/p).read_bytes() for p in before})
        self.assertFalse((self.home/'.ai-harness/bootstrap.receipt.json').exists())

    def test_final_generation_drift_rolls_back_agents_hooks_and_receipt(self):
        def audit(*a,**k):
            self.assertIn('new managed instructions',(self.home/'AGENTS.md').read_text())
            (self.source/'skills/global-task-orchestrator/SKILL.md').write_text('changed after publication')
            return {'ok':True}
        code,result,before=self.bootstrap(audit=audit)
        self.assertNotEqual(0,code)
        self.assertIn('publication_source_changed',' '.join(result['issues']))
        self.assertEqual(before,{p:(self.home/p).read_bytes() for p in before})
        self.assertFalse((self.home/'.ai-harness/bootstrap.receipt.json').exists())

if __name__=='__main__': unittest.main()
