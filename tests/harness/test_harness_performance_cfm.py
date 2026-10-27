"""CFM migration/per-signature contracts in a disposable codex home."""
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import subprocess
import sys
import test_command_failure_memory as legacy_module
from test_command_failure_memory import BACKEND

class PerformanceCfm(unittest.TestCase):
    setUp=legacy_module.CommandFailureMemoryContractTests.setUp
    action_args=legacy_module.CommandFailureMemoryContractTests.action_args
    invoke=legacy_module.CommandFailureMemoryContractTests.invoke
    invoke_with_fast_fixture_paths=legacy_module.CommandFailureMemoryContractTests.invoke_with_fast_fixture_paths
    seed_v1_case=legacy_module.CommandFailureMemoryContractTests.seed_v1_case
    seed_v1_index=legacy_module.CommandFailureMemoryContractTests.seed_v1_index

    def test_legacy_migration_preserves_archived_cases_pending_and_source_bytes(self):
        cases=[self.seed_v1_case(i+1) for i in range(5)]
        cases[-1]['storage_tier']='archived'
        (self.memory_root/'cases'/f"{cases[-1]['case_id']}.json").write_text(json.dumps(cases[-1]))
        self.seed_v1_index(cases)
        events=[{'signature':f'{i:064x}','command_signature':f'cmd {i}','error_signature':'bad',
                 'project_id':'fixture','first_failed_at':'2026-01-01T00:00:00+00:00',
                 'last_failed_at':'2026-01-01T00:00:00+00:00','failure_count':1,'last_query_at':''} for i in range(1100)]
        (self.memory_root/'runtime').mkdir(exist_ok=True)
        (self.memory_root/'runtime/failure-events.json').write_text(json.dumps({'schema_version':'1.0','events':events}))
        before={str(p.relative_to(self.memory_root)):p.read_bytes() for p in self.memory_root.rglob('*') if p.is_file()}
        result,payload=self.invoke('inspect')
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(5,payload['case_count'])
        self.assertEqual(1100,payload['pending_failure_count'],'pending history must never be truncated')
        self.assertEqual('sqlite-v2',payload.get('storage_format'),'legacy store not migrated')
        self.assertTrue((self.memory_root/'memory.sqlite3').is_file())
        self.assertEqual(before,{p:(self.memory_root/p).read_bytes() for p in before})

    def test_warm_query_never_loads_global_case_catalog(self):
        values={'project':'fixture','command':'python3 check.py','error':'bad schema'}
        self.assertEqual(0,self.invoke('record-failure',**values)[0].returncode)
        with patch.object(BACKEND,'get_case_catalog',side_effect=AssertionError('query loaded whole case catalog')):
            code,error,payload=self.invoke_with_fast_fixture_paths('query-before-retry',**values)
        self.assertEqual(0,code,error)
        self.assertTrue(payload['query_permitted'])

    def test_warm_query_uses_signature_and_project_indexed_sql(self):
        values={'project':'exact-project','command':'target command','error':'target error'}
        self.assertEqual(0,self.invoke('record-failure',**values)[0].returncode)
        traces=[]; original=BACKEND.open_store
        def opened(storage):
            connection=original(storage); connection.set_trace_callback(traces.append); return connection
        with patch.object(BACKEND,'open_store',opened):
            code,error,payload=self.invoke_with_fast_fixture_paths('query-before-retry',**values)
        self.assertEqual(0,code,error)
        reads=[sql.upper() for sql in traces if sql.lstrip().upper().startswith('SELECT') and ('FROM CASES' in sql.upper() or 'FROM PENDING' in sql.upper())]
        self.assertTrue(reads)
        self.assertTrue(all('WHERE' in sql and 'SIGNATURE' in sql for sql in reads),reads)
        self.assertTrue(any('FROM PENDING' in sql and 'PROJECT_ID' in sql for sql in reads),reads)

    def test_cross_project_concurrent_failure_records_are_not_lost(self):
        self.assertEqual(0,self.invoke('inspect')[0].returncode)
        processes=[]
        for ordinal in range(4):
            args=self.action_args('record-failure',project=f'project-{ordinal}',command='same command',error='same error')
            processes.append(subprocess.Popen([sys.executable,str(legacy_module.BACKEND_PATH),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        for process in processes:
            stdout,stderr=process.communicate(timeout=15)
            self.assertEqual(0,process.returncode,stderr)
            self.assertEqual(1,json.loads(stdout)['failure_count'])
        _,payload=self.invoke('inspect'); self.assertEqual(4,payload['pending_failure_count'])
        for ordinal in range(4):
            code,payload=self.invoke('query-before-retry',project=f'project-{ordinal}',command='same command',error='same error')
            self.assertEqual(0,code.returncode,code.stderr); self.assertTrue(payload['query_permitted'])

    def test_legacy_duplicate_case_index_is_rejected_without_destroying_sources(self):
        case=self.seed_v1_case(1); self.seed_v1_index([case,case])
        index=self.memory_root/'index.json'; before=index.read_bytes()
        result,payload=self.invoke('inspect')
        self.assertNotEqual(0,result.returncode,'duplicate legacy index must not silently collapse migration')
        self.assertEqual(before,index.read_bytes())

    def test_multiple_archive_hits_respect_capacity_during_one_query(self):
        signature=BACKEND.get_case_signature('matching command','matching error')
        active=self.seed_v1_case(1)
        archived=[self.seed_v1_case(i,signature=signature['signature'],command_signature=signature['command_signature'],error_signature=signature['error_signature']) for i in (2,3)]
        for case in archived:
            case['storage_tier']='archived'
            (self.memory_root/'cases'/(case['case_id']+'.json')).write_text(json.dumps(case))
        self.seed_v1_index([active,*archived])
        values={'project':'capacity-project','command':'matching command','error':'matching error'}
        self.assertEqual(0,self.invoke('record-failure',**values)[0].returncode)
        with patch.object(BACKEND,'MAX_CASE_COUNT',2):
            code,error,payload=self.invoke_with_fast_fixture_paths('query-before-retry',**values)
        self.assertEqual(0,code,error)
        self.assertEqual({x['case_id'] for x in archived},{x['case_id'] for x in payload['suggestions']})
        _,snapshot=self.invoke('inspect')
        self.assertEqual(3,snapshot['case_count'],'capacity handling must not drop cases')
        self.assertLessEqual(snapshot['active_case_count'],2,'pending reactivations must count against capacity')

if __name__=='__main__': unittest.main()
