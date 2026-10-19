"""Windows native host policy and scoped environment publication regressions."""
from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from runtime_common import validate_windows_external_capabilities, inspect_windows_external_capabilities


class NativeEnvironmentTests(unittest.TestCase):
    def test_legacy_gui_prohibition_is_not_a_positive_dependency(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('t3_retired_policy', ROOT / 'tests/harness/test_pure_codex_cleanup.py')
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        prohibited = (
            '当前使用 Windows 官方 Browser；禁止调用 computer_use_wsl。',
            '不调用 computer_use_wsl，当前使用 Windows 原生能力。',
            '当前不再调用 browser_use_wsl，项目继续使用 WSL 命令。',
        )
        for line in prohibited:
            with self.subTest(line=line):
                self.assertEqual([], policy.affirmative_contract_names(line))
        self.assertEqual(['windows-gui-bridge'], policy.affirmative_contract_names('当前使用 computer_use_wsl。'))

    def setUp(self):
        base = ROOT / '.tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'codex'
        self.home.mkdir()
        self.config = self.home / 'config.toml'
        self.config.write_text('''model = "sentinel"
[plugins."browser@openai-bundled"]
enabled = true
[plugins."computer-use@openai-bundled"]
enabled = true
[plugins."unified-computer-use@openai-bundled"]
enabled = true
[mcp_servers.computer_use_wsl]
enabled = false
[mcp_servers.node_repl]
command = "app-owned-command"
args = ["app-owned-arg"]
''')
        self.declaration = ROOT / 'config/ai/windows-external-capabilities.json'

    def test_repository_declares_native_windows_plugins(self):
        declaration = json.loads(self.declaration.read_text())
        self.assertEqual(3, declaration['schema_version'])
        self.assertEqual({'windows_native'}, {x['kind'] for x in declaration['capabilities']})
        self.assertEqual([], validate_windows_external_capabilities(declaration))

    def test_old_bridge_contract_is_rejected(self):
        self.assertTrue(validate_windows_external_capabilities({'schema_version': 3, 'capabilities': [
            {'id':'old','kind':'wsl_windows_bridge','provider':'old'}]}))

    def test_diagnostic_is_readonly_and_does_not_claim_gui_proof(self):
        before = (self.config.read_bytes(), self.config.stat().st_mtime_ns)
        result = inspect_windows_external_capabilities(self.home, self.declaration)
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['runtime_verified'])
        self.assertEqual({'configured_on_disk'}, {x['status'] for x in result['capabilities']})
        self.assertEqual(before, (self.config.read_bytes(), self.config.stat().st_mtime_ns))

    def test_missing_or_disabled_plugin_is_not_automatically_repaired(self):
        for config in ['', '[plugins."browser@openai-bundled"]\nenabled=false\n']:
            with self.subTest(config=config):
                self.config.write_text(config)
                result = inspect_windows_external_capabilities(self.home, self.declaration)
                self.assertFalse(result['ok'])
                self.assertEqual(config, self.config.read_text())
                self.assertTrue(all(x['action']=='check_desktop_plugin' for x in result['capabilities']))

    def cli(self, *args):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/bootstrap-local.py'),
            '--harness-root', str(ROOT), '--codex-home', str(self.home), *args, '--json'],
            text=True, capture_output=True)
        return result, json.loads(result.stdout)

    def test_environment_only_repeat_preserves_config_and_unrelated_files(self):
        sentinel = self.home / 'AGENTS.md'
        sentinel.write_text('user active instructions')
        before = (self.config.read_bytes(), self.config.stat().st_mtime_ns)
        for attempt in range(2):
            completed, result = self.cli('--environment-only')
            self.assertEqual(0, completed.returncode, result)
            self.assertTrue(result['ok'])
            self.assertEqual(before, (self.config.read_bytes(), self.config.stat().st_mtime_ns))
            self.assertEqual('user active instructions', sentinel.read_text())
            self.assertFalse((self.home / 'skills').exists())
            self.assertFalse((self.home / 'schemas').exists())
            runtime = self.home / '.ai-harness/runtime/wsl-environment'
            self.assertFalse((runtime / 'bin/node-repl-wsl-compat.py').exists())
            receipt = json.loads((self.home / '.ai-harness/bootstrap.receipt.json').read_text())
            self.assertTrue(receipt['managed_runtime_files'])
            if attempt:
                self.assertFalse(result['runtime_changed'])

    def test_environment_only_respects_hold_before_writes(self):
        directory = self.home / '.ai-harness'
        directory.mkdir()
        (directory / 'windows-native-transition.hold').write_text('pending')
        before = sorted(str(x.relative_to(self.home)) for x in self.home.rglob('*'))
        completed, result = self.cli('--environment-only')
        self.assertNotEqual(0, completed.returncode)
        self.assertIn('WINDOWS_NATIVE_TRANSITION_HOLD', str(result))
        self.assertEqual(before, sorted(str(x.relative_to(self.home)) for x in self.home.rglob('*')))

    def test_regular_bootstrap_no_longer_changes_plugin_config(self):
        before = self.config.read_bytes()
        completed, result = self.cli('--skip-sync', '--skip-rules', '--skip-doctor')
        self.assertEqual(0, completed.returncode, result)
        self.assertEqual(before, self.config.read_bytes())

    def test_environment_doctor_uses_only_runtime_inventory(self):
        completed, payload = self.cli('--environment-only')
        self.assertEqual(0, completed.returncode, payload)
        baseline = self.home / 'baseline.json'
        baseline.write_text(json.dumps({'schema_version':1,'profiles':[{'id':'developer','packages':[]}]}))
        env = dict(os.environ)
        for name in ('TEMP','TMP','TMPDIR'):
            env.pop(name, None)
        result = subprocess.run([sys.executable, str(ROOT/'scripts/doctor-core.py'),
            '--root',str(ROOT),'--codex-home',str(self.home),'--environment-only',
            '--baseline',str(baseline),'--json'],capture_output=True,text=True,env=env)
        report = json.loads(result.stdout)
        self.assertEqual(0,result.returncode,report)
        self.assertEqual('environment-only',report['scope'])
        self.assertNotIn('installed_gto_validation',report)

    def legacy_fixture(self):
        name = 'windows-computer-use-wsl'
        target = self.home/'skills'/name/'SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text('old bridge skill')
        receipt = {'schema_version':'3.0','harness_root':str(ROOT),'codex_home':str(self.home),
            'managed_skills':['unrelated',name],
            'managed_files':[{'skill':'unrelated','target':'unrelated/SKILL.md','sha256':'sentinel'},
                {'skill':name,'source':'skills/'+name+'/SKILL.md','target':name+'/SKILL.md',
                 'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}],
            'managed_schema_files':[{'target':'unrelated.schema.json','sha256':'unchanged'}],
            'custom_field':'preserve'}
        receipt_path=self.home/'.ai-harness/codex-sync.receipt.json'
        receipt_path.parent.mkdir(parents=True,exist_ok=True)
        receipt_path.write_text(json.dumps(receipt))
        return target, receipt_path, receipt

    def retire(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/sync-codex.py'),
            '--harness-root',str(ROOT),'--codex-home',str(self.home),'--retire-legacy-gui','--json'],
            capture_output=True,text=True)
        return result,json.loads(result.stdout)

    def test_legacy_retirement_preserves_other_receipt_records_and_config(self):
        target,receipt_path,before=self.legacy_fixture()
        raw=self.config.read_bytes()
        completed,result=self.retire()
        self.assertEqual(0,completed.returncode,result)
        self.assertFalse(target.exists())
        self.assertEqual('old bridge skill',(Path(result['backup_path'])/'SKILL.md').read_text())
        after=json.loads(receipt_path.read_text())
        self.assertEqual([before['managed_files'][0]],after['managed_files'])
        self.assertEqual(before['managed_schema_files'],after['managed_schema_files'])
        self.assertEqual('preserve',after['custom_field'])
        self.assertEqual(raw,self.config.read_bytes())
        completed,result=self.retire()
        self.assertEqual(0,completed.returncode,result)
        self.assertFalse(result['changed'])

    def test_legacy_retirement_rejects_drift_or_active_bridge(self):
        target,receipt_path,_=self.legacy_fixture()
        before=receipt_path.read_bytes()
        target.write_text('someone else changed it')
        completed,result=self.retire()
        self.assertNotEqual(0,completed.returncode)
        self.assertEqual(before,receipt_path.read_bytes())
        self.assertEqual('someone else changed it',target.read_text())
        target.write_text('old bridge skill')
        self.config.write_text(chr(10).join(['[mcp_servers.computer_use_wsl]', 'enabled=true', '']))
        completed,result=self.retire()
        self.assertNotEqual(0,completed.returncode)
        self.assertEqual(before,receipt_path.read_bytes())
        self.assertTrue(target.exists())

    def test_legacy_retirement_respects_hold(self):
        target,receipt_path,_=self.legacy_fixture()
        before=receipt_path.read_bytes()
        (self.home/'.ai-harness/windows-native-transition.hold').write_text('pending')
        completed,result=self.retire()
        self.assertNotEqual(0,completed.returncode)
        self.assertIn('WINDOWS_NATIVE_TRANSITION_HOLD',str(result))
        self.assertEqual(before,receipt_path.read_bytes())
        self.assertTrue(target.exists())

    def module(self, name):
        import importlib.util
        spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_review_runtime_retirement_and_failure_restore(self):
        from unittest.mock import patch
        import io
        from contextlib import redirect_stdout
        module=self.module('bootstrap-local')
        completed,result=self.cli('--environment-only');self.assertEqual(0,completed.returncode,result)
        receipt_path=self.home/'.ai-harness/bootstrap.receipt.json'
        retired=self.home/'.ai-harness/runtime/wsl-environment/bin/node-repl-wsl-compat.py'
        retired.write_text('installed legacy')
        receipt=json.loads(receipt_path.read_text());receipt['managed_runtime_files'].append({'target_path':str(retired),'target_sha256':hashlib.sha256(retired.read_bytes()).hexdigest(),'source_path':str(ROOT/'modules/wsl-environment/tooling/node-repl-wsl-compat.py'),'source_sha256':hashlib.sha256(retired.read_bytes()).hexdigest()})
        # Create a receipt-owned older managed target so copy failure exercises a write.
        target=self.home/'.ai-harness/runtime/wsl-environment/bin/runtime_common.py'
        target.write_text('installed older runtime')
        for row in receipt['managed_runtime_files']:
            if row['target_path']==str(target):row['target_sha256']=row['source_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt));before={p:p.read_bytes() for p in [retired,target,receipt_path]}
        config=self.config.read_bytes();self.config.write_text('[mcp_servers.computer_use_wsl]'+chr(10)+'enabled=true')
        completed,result=self.cli('--environment-only');self.assertNotEqual(0,completed.returncode)
        self.assertEqual(before,{p:p.read_bytes() for p in before});self.config.write_bytes(config)
        for fault in ('copy','receipt'):
            original_copy=module.shutil.copy2;original_write=module.write_json
            def copy(source,destination,*args,**kwargs):
                if fault=='copy' and Path(source)==ROOT/'scripts/runtime_common.py':raise OSError('injected copy failure')
                return original_copy(source,destination,*args,**kwargs)
            def write(path,payload):
                if fault=='receipt' and Path(path)==receipt_path:raise OSError('injected receipt failure')
                return original_write(path,payload)
            with patch.object(module.shutil,'copy2',side_effect=copy),patch.object(module,'write_json',side_effect=write),patch.object(sys,'argv',['bootstrap','--harness-root',str(ROOT),'--codex-home',str(self.home),'--environment-only','--json']),redirect_stdout(io.StringIO()):
                self.assertNotEqual(0,module.main())
            self.assertEqual(before,{p:p.read_bytes() for p in before},fault)
        completed,result=self.cli('--environment-only');self.assertEqual(0,completed.returncode,result)
        self.assertFalse(retired.exists())
        self.assertTrue(list((self.home/'.ai-harness/backups/environment-publication').glob('*/manifest.json')))

    def test_review_sync_rechecks_hold_after_acquiring_lock(self):
        from unittest.mock import patch
        module=self.module('sync-codex')
        def lock(*args):
            (self.home/'.ai-harness/windows-native-transition.hold').write_text('appeared while waiting')
        with patch.object(module.fcntl,'flock',side_effect=lock):
            with self.assertRaisesRegex(ValueError,'WINDOWS_NATIVE_TRANSITION_HOLD'):
                module.synchronize(ROOT,self.home,skills=['command-failure-memory'])
        self.assertFalse((self.home/'skills/command-failure-memory').exists())

    def test_review_doctor_reports_windows_path_outside_subset(self):
        from unittest.mock import patch
        module=self.module('doctor-core')
        audit={'ok':False,'tools':[],'missing_tools':[],'windows_path_tools':['git'],'errors':[]}
        with patch.object(module,'_wsl_tool_audit',return_value=audit),patch.object(module,'_machine_environment_findings',return_value=[]),patch.object(module,'_wsl_runtime_audit',return_value=[]),patch.object(module,'_read_json_object',return_value=({},None)),patch.object(module,'inspect_windows_external_capabilities',return_value={'issues':[]}):
            report=module.audit_environment(ROOT,self.home)
        self.assertFalse(report['ok']);self.assertIn('wsl_tool_windows_path',report['errors'])

    def test_review_malformed_receipts_return_json(self):
        target,path,receipt=self.legacy_fixture()
        receipt['managed_files'].append('invalid');path.write_text(json.dumps(receipt))
        completed,result=self.retire();self.assertNotEqual(0,completed.returncode);self.assertFalse(result['ok'])
        path=self.home/'.ai-harness/bootstrap.receipt.json';path.write_text(json.dumps({'managed_runtime_files':[{'target_path':[],'target_sha256':'x'}]}))
        completed,result=self.cli('--environment-only');self.assertNotEqual(0,completed.returncode);self.assertFalse(result['ok'])

    def test_review_existing_receipt_requires_ownership(self):
        completed,result=self.cli('--environment-only');self.assertEqual(0,completed.returncode,result)
        rp=self.home/'.ai-harness/bootstrap.receipt.json';base=json.loads(rp.read_text())
        for field in ('harness_root','codex_home'):
            receipt=dict(base);receipt.pop(field,None);rp.write_text(json.dumps(receipt))
            completed,result=self.cli('--environment-only');self.assertNotEqual(0,completed.returncode,field)
        for field in ('source_path','source_sha256'):
            receipt=json.loads(json.dumps(base));receipt['managed_runtime_files'][0].pop(field,None);rp.write_text(json.dumps(receipt))
            completed,result=self.cli('--environment-only');self.assertNotEqual(0,completed.returncode,field)

    def test_review_extra_records_and_unknown_runtime_audit(self):
        completed,result=self.cli('--environment-only');self.assertEqual(0,completed.returncode,result)
        rp=self.home/'.ai-harness/bootstrap.receipt.json';receipt=json.loads(rp.read_text())
        receipt['managed_runtime_files'].append({'target_path':str(self.home/'other'),'source_path':'other','source_sha256':'extra','target_sha256':'extra'})
        module=self.module('doctor-core')
        self.assertEqual([],module._wsl_runtime_audit(ROOT,self.home,receipt))
        unknown=self.home/'.ai-harness/runtime/wsl-environment/bin/unknown.py';unknown.write_text('unknown')
        self.assertIn('managed_runtime_unexpected',{x['type'] for x in module._wsl_runtime_audit(ROOT,self.home,receipt)})

    def test_review_default_interrupt_restores_and_reports_restore_failure(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout
        import io
        module=self.module('bootstrap-local')
        completed,result=self.cli('--environment-only');self.assertEqual(0,completed.returncode,result)
        target=self.home/'.ai-harness/runtime/wsl-environment/bin/runtime_common.py';before=target.read_bytes()
        def interrupted(*args):
            target.write_text('partial publication')
            raise KeyboardInterrupt('injected interrupt')
        argv=['bootstrap','--harness-root',str(ROOT),'--codex-home',str(self.home),'--skip-rules','--skip-doctor','--json']
        for restore_failure in (False,True):
            original_copy=module.shutil.copyfile
            def copy(source,destination,*args,**kwargs):
                if restore_failure and Path(destination)==target:raise OSError('injected restore failure')
                return original_copy(source,destination,*args,**kwargs)
            output=io.StringIO()
            with patch.object(sys,'argv',argv),patch.object(module,'_run',return_value={'ok':True}),patch.object(module,'_sync_wsl_environment_runtime',side_effect=interrupted),patch.object(module.shutil,'copyfile',side_effect=copy),redirect_stdout(output):
                self.assertNotEqual(0,module.main())
            report=json.loads(output.getvalue());self.assertFalse(report['ok'])
            if restore_failure:
                self.assertIn('environment_restore_failed',str(report));self.assertIn('backup_path',str(report));self.assertIn('unrestored',str(report))
                target.write_bytes(before)
            else:self.assertEqual(before,target.read_bytes())

    def test_explicit_codex_home_required(self):
        from unittest.mock import patch
        from runtime_common import resolve_codex_home
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'codex_home_required'):
                resolve_codex_home()
            self.assertEqual(self.home.resolve(), resolve_codex_home(str(self.home)))

    def test_cfm_missing_home_rejects_before_storage(self):
        env=dict(os.environ);env.pop('CODEX_HOME',None);env['HOME']=str(self.home)
        completed=subprocess.run([sys.executable,str(ROOT/'skills/command-failure-memory/scripts/command-failure-memory.py'),'--action','inspect','--json'],env=env,capture_output=True,text=True)
        self.assertNotEqual(0,completed.returncode)
        self.assertIn('codex_home_required',completed.stderr)
        self.assertFalse((self.home/'.codex').exists())

    def test_native_shell_is_allowed_but_legacy_bridge_is_rejected(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('retired_policy',ROOT/'tests/harness/test_pure_codex_cleanup.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual([],module.affirmative_contract_names('Windows 原生文件操作使用 PowerShell；项目命令通过 wsl.exe --exec 调用。'))
        self.assertEqual(['windows-gui-bridge'],module.affirmative_contract_names('当前启用 computer_use_wsl 作为 GUI 运行入口。'))

    def test_fixtures_leave_no_task_parent_directory(self):
        from unittest.mock import patch
        import importlib.util
        for name,klass in [('test_windows_native_environment','NativeEnvironmentTests'),('test_windows_native_transition','NativeTransitionGuardTests')]:
            spec=importlib.util.spec_from_file_location(name,ROOT/'tests/harness'/f'{name}.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            fake=self.home/name; (fake/'.tmp').mkdir(parents=True)
            test=getattr(module,klass)()
            with patch.object(module,'ROOT',fake):
                test.setUp();test.doCleanups()
            self.assertEqual([],list((fake/'.tmp').iterdir()),name)

    def test_health_fixture_preserves_notify_and_declares_plugins(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('health_fixture',ROOT/'tests/harness/test_wsl_runtime.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.config.write_text('notify = ["python3", "/opt/user-notify.py"]'+chr(10)+'[features]'+chr(10)+'multi_agent=true'+chr(10))
        module.configure_native_plugins(self.home)
        self.assertTrue(inspect_windows_external_capabilities(self.home,self.declaration)['ok'])
        self.assertIn('notify = ["python3", "/opt/user-notify.py"]',self.config.read_text())

    def test_current_environment_documents_allow_native_host(self):
        import importlib.util
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('current_contract',ROOT/'tests/harness/test_pure_codex_cleanup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        paths=[ROOT/x for x in ['docs/CODEX_COMPAT.md','docs/ARCHITECTURE.md','docs/INSTALL.md','tests/README.md','docs/modules/wsl-environment/design/windows-attachment-path-bridge.md']]
        # The strict helper is exercised only on this migration's authorized documents.
        with patch.object(module,'active_truth_paths',return_value=paths):
            self.assertEqual([],module.affirmative_retired_contract_hits())

    def test_review_schema_metadata(self):
        schema=json.loads((ROOT/'schemas/windows-external-capabilities.schema.json').read_text())
        self.assertEqual('https://json-schema.org/draft/2020-12/schema',schema.get('$schema'))
        self.assertTrue(schema.get('$id','').endswith('windows-external-capabilities.schema.json'))

    def test_review_environment_rejects_unowned_and_drift(self):
        target=self.home/'.ai-harness/runtime/wsl-environment/bin/runtime_common.py'
        target.parent.mkdir(parents=True)
        target.write_text('unowned')
        completed,result=self.cli('--environment-only')
        self.assertNotEqual(0,completed.returncode,result)
        self.assertEqual('unowned',target.read_text())

    def test_review_environment_preserves_extra_records(self):
        completed,result=self.cli('--environment-only')
        self.assertEqual(0,completed.returncode,result)
        rp=self.home/'.ai-harness/bootstrap.receipt.json'
        receipt=json.loads(rp.read_text());extra={'target_path':str(self.home/'other'),'target_sha256':'extra','source_path':'other','source_sha256':'extra'}
        receipt['managed_runtime_files'].append(extra);rp.write_text(json.dumps(receipt))
        completed,result=self.cli('--environment-only')
        self.assertEqual(0,completed.returncode,result)
        self.assertIn(extra,json.loads(rp.read_text())['managed_runtime_files'])

    def test_native_schema_and_validator_reject_malformed_declarations(self):
        from jsonschema import Draft202012Validator
        schema=json.loads((ROOT/'schemas/windows-external-capabilities.schema.json').read_text())
        validator=Draft202012Validator(schema)
        valid=json.loads(self.declaration.read_text())
        self.assertFalse(list(validator.iter_errors(valid)))
        for invalid in [[],{'schema_version':2,'capabilities':valid['capabilities']},
                {'schema_version':3,'capabilities':[]},
                {'schema_version':3,'capabilities':[{'id':'bad','kind':'windows_native','provider':'x','required_plugins':[True]}]},
                {'schema_version':3,'capabilities':[{'id':'bad','kind':'windows_native','provider':'x','required_plugins':['x','x']}]}]:
            with self.subTest(invalid=invalid):
                self.assertTrue(validate_windows_external_capabilities(invalid))
                self.assertTrue(list(validator.iter_errors(invalid)))

if __name__ == '__main__':
    unittest.main()
