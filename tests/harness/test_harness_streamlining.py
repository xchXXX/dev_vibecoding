"""Public-entry contract tests; synthetic roles, real captured subprocesses."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

import test_control_plane as legacy
import test_gto_point_acceptance_boundaries as boundaries
import test_gto_point_acceptance_batch_isolation as batch_isolation
from test_gto_point_acceptance import PointHarness


SKILL = legacy.REPO_ROOT / 'skills/global-task-orchestrator'


class StreamliningHarness(PointHarness):
    def setUp(self):
        root = legacy.REPO_ROOT / '.tmp/harness-streamlining'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.repo = Path(self.temp.name)
        self.input_dir = self.repo / '.tmp/receipts'
        self.input_dir.mkdir(parents=True)
        self._json_input_index = 0
        self.addCleanup(self.preserve_and_cleanup)

    def preserve_and_cleanup(self):
        # Keep all evidence for this small contract suite, including expected Red.
        dest = (legacy.REPO_ROOT / '.artifacts/harness-streamlining/testing/consumers'
                / (self.id() + '-' + uuid.uuid4().hex))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.repo, dest)
        print('Consumer evidence: ' + str(dest), file=sys.stderr)
        self.temp.cleanup()

    def public(self, *arguments, script='orchestrator_ctl.py', ok=True):
        command = [sys.executable, str(SKILL / 'scripts' / script), *arguments]
        completed = subprocess.run(command, cwd=self.repo, text=True, capture_output=True)
        logs = self.repo / '.artifacts/cli'
        logs.mkdir(parents=True, exist_ok=True)
        (logs / (uuid.uuid4().hex + '.json')).write_text(json.dumps({
            'command': command, 'exit_code': completed.returncode,
            'stdout': completed.stdout, 'stderr': completed.stderr}, indent=2))
        if ok:
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        else:
            self.assertNotEqual(0, completed.returncode, completed.stdout + completed.stderr)
        return json.loads(completed.stdout) if completed.stdout.strip().startswith('{') else {}

    def action(self, action, *arguments, ok=True):
        return self.public('--action', action, '--repo-root', str(self.repo),
                           '--task-id', legacy.TASK_ID, '--json', *arguments, ok=ok)

    def resume(self, ok=True):
        return self.public('--repo-root', str(self.repo), '--task-id', legacy.TASK_ID,
                           '--json', script='start_session.py', ok=ok)

    def controls(self):
        return {str(p.relative_to(self.repo)): p.read_bytes()
                for p in (self.repo / 'docs').rglob('*') if p.is_file()}

    def captured_summary(self, attempt, *, execution_kind='cli'):
        from test_gto_plan_preflight_contract import load_controller
        load_controller()
        from runtime_evidence import run_command, acceptance_binding
        output = '.artifacts/observations/' + attempt['attempt_id']
        summary = output + '/summary.json'
        scope = attempt['scope_acceptance_ids']
        # The real child checks inputs, counts calls, and writes its own summary
        # before run_command seals all files. No post-run manifest editing.
        code = '''import json,runpy,sys
from pathlib import Path
scope,output,kind=json.loads(sys.argv[1]),sys.argv[2],sys.argv[3]
sys.argv=['candidate-source.py',json.dumps(scope),output]
try: runpy.run_path('candidate-source.py',run_name='__main__')
except SystemExit as e:
    if e.code: raise
points=[{'acceptance_id':i,'status':json.loads(Path(output,i+'.json').read_text())['status'],'evidence_refs':[output+'/'+i+'.json']} for i in scope]
summary={'outcome':'pass','real_call_count':len(scope),'point_results':points}
if kind: summary['execution_kind']=kind
Path(output,'summary.json').write_text(json.dumps(summary))
'''
        run = run_command(self.repo / '.artifacts/runs',
            [sys.executable, '-c', code, json.dumps(scope), output, execution_kind], cwd=self.repo,
            binding=acceptance_binding(self.state(), attempt['subtask_id']),
            evidence_paths=[summary, *[output + '/' + ident + '.json' for ident in scope]])
        return (run / 'manifest.json').relative_to(self.repo).as_posix(), summary

    def prepare(self, attempt, manifest, summary, *, ok=True):
        return self.action('prepare-result', '--subtask-id', attempt['subtask_id'],
            '--run-manifest', manifest, '--observation-file', summary,
            '--output-file', '.tmp/generated-result.json', ok=ok)


class StreamliningCliTest(StreamliningHarness, unittest.TestCase):
    def test_resume_accepts_refrozen_dependency_change_but_rejects_corruption(self):
        self.begin(2)
        attempt = self.attempt()
        receipt = self.observe(attempt, self.ids)
        self.register(attempt, receipt)
        (self.repo / 'inputs/CHECK-01.json').write_text('{"CHECK-01":true,"revision":2}')
        self.reintegrate()
        self.run_ctl('freeze-candidate')
        before = self.controls()
        for result in (self.action('validate'), self.resume()):
            self.assertTrue(result['ok'])
            self.assertEqual(['CHECK-01'], result['acceptance']['rerun_acceptance_ids'])
            self.assertEqual('pass', result['acceptance']['points']['CHECK-02']['status'])
            self.assertIn('capability_checks', result)
            self.assertTrue(result['summary'])
        self.assertEqual(before, self.controls())
        self.assertEqual(2, self.count())
        # Damage a still-consumed observation: legal staleness is not an excuse
        # to ignore broken original evidence.
        ref = receipt['expensive_acceptance']['point_results'][1]['evidence_refs'][0]
        (self.repo / ref).write_text('tampered original observation')
        self.resume(ok=False)
        self.assertEqual(before, self.controls())
        self.assertEqual(2, self.count())

    def test_tool_paths_checks_fixed_locations_without_directory_enumeration(self):
        home = self.repo / '.tmp/codex-home'
        doctor = home / '.ai-harness/runtime/wsl-environment/bin/project-env-doctor.py'
        doctor.parent.mkdir(parents=True)
        doctor.write_text('# synthetic installed public entry\n')
        installed = home / 'skills/global-task-orchestrator'
        shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        # Permit only the explicit package subtree needed for content identity.
        # Home root, other skills, sessions, and memories must not be enumerated.
        # Python may also enumerate its own standard-library import directories.
        guard = self.repo / '.tmp/audit-tool-paths.py'
        guard.write_text("import runpy,sys\nfrom pathlib import Path\n"
            "home=Path(sys.argv[sys.argv.index('--codex-home')+1]).resolve()\n"
            "package=home/'skills/global-task-orchestrator'\n"
            "def guard(event,args):\n"
            "    if event in ('os.scandir','os.listdir'):\n"
            "        if isinstance(args[0],int): raise RuntimeError('Unresolved directory enumeration forbidden')\n"
            "        path=Path(args[0]).resolve()\n"
            "        if path.is_relative_to(home) and not path.is_relative_to(package): raise RuntimeError('Codex home directory enumeration forbidden outside fixed GTO package')\n"
            "sys.addaudithook(guard)\n"
            "script=sys.argv.pop(1)\nsys.path.insert(0,str(Path(script).resolve().parent))\nrunpy.run_path(script,run_name='__main__')\n")
        target = SKILL / 'scripts/tool_paths.py'
        self.assertTrue(target.is_file(), 'TDD target tool_paths.py does not exist')
        result = subprocess.run([sys.executable, str(guard), str(target), '--codex-home',
            str(home), '--json'], cwd=self.repo, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        tools = json.loads(result.stdout)['tools']
        self.assertEqual(str(doctor), tools['project_env_doctor']['path'])
        self.assertTrue(tools['project_env_doctor']['available'])
        for key in ('controller', 'resume', 'runtime_evidence'):
            self.assertTrue(tools[key]['available'])
            self.assertTrue(Path(tools[key]['path']).is_relative_to(SKILL))
        absent = self.public('--json', script='tool_paths.py')['tools']
        self.assertFalse(absent['project_env_doctor']['available'])

    def test_prepare_result_reuses_original_captured_summary_without_execution(self):
        self.begin()
        attempt = self.attempt()
        manifest, summary = self.captured_summary(attempt)
        before = self.controls()
        original = {p: (self.repo / p).read_bytes() for p in (manifest, summary)}
        self.prepare(attempt, manifest, summary)
        draft = self.repo / '.tmp/generated-result.json'
        first = json.loads(draft.read_text())
        self.assertEqual(before, self.controls())
        self.assertEqual(2, self.count())
        draft.write_text('{"incorrect_manual_edit":true}')
        self.prepare(attempt, manifest, summary)
        self.assertEqual(first, json.loads(draft.read_text()))
        self.register(attempt, first)
        self.assertTrue(self.coverage()['complete'])
        self.assertEqual(original, {p: (self.repo / p).read_bytes() for p in original})
        self.assertEqual(2, self.count())

    def test_prepare_result_rejects_uncaptured_or_modified_summary_atomically(self):
        self.begin()
        attempt = self.attempt()
        manifest, summary = self.captured_summary(attempt)
        self.prepare(attempt, manifest, summary)
        draft = self.repo / '.tmp/generated-result.json'
        before, original_draft = self.controls(), draft.read_bytes()
        uncaptured = '.artifacts/uncaptured-summary.json'
        (self.repo / uncaptured).write_bytes((self.repo / summary).read_bytes())
        self.prepare(attempt, manifest, uncaptured, ok=False)
        (self.repo / summary).write_text('{"outcome":"pass","point_results":[]}')
        self.prepare(attempt, manifest, summary, ok=False)
        self.assertEqual(before, self.controls())
        self.assertEqual(original_draft, draft.read_bytes())
        self.assertEqual(2, self.count())

    def test_complete_task_records_brief_facts_without_new_business_or_review(self):
        self.begin()
        attempt = self.attempt()
        self.register(attempt, self.observe(attempt, self.ids))
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        before = self.state()
        result = self.action('complete-task', '--subtask-id', 'DOC-FINAL-001')
        self.assertEqual('completed', result['status'])
        self.assertTrue(result['summary'])
        self.assertEqual('completed', self.state()['status'])
        self.assertEqual(before['acceptance_gate']['attempts'], self.state()['acceptance_gate']['attempts'])
        self.assertEqual([t for t in before['subtasks'] if t['stage'] == 'pre_acceptance_review'],
                         [t for t in self.state()['subtasks'] if t['stage'] == 'pre_acceptance_review'])
        self.assertEqual(2, self.count())

    def test_prepare_result_does_not_infer_cli_applicability_from_process_launch(self):
        self.begin()
        attempt = self.attempt()
        manifest, summary = self.captured_summary(attempt, execution_kind='')
        before = self.controls()
        rejection = self.prepare(attempt, manifest, summary, ok=False)
        self.assertRegex(str(rejection).lower(), 'execution_kind|usage_evidence|cli')
        self.assertFalse((self.repo / '.tmp/generated-result.json').exists())
        self.assertEqual(before, self.controls())
        self.assertEqual(2, self.count())

    def test_complete_task_rejects_document_delta_without_partial_receipt(self):
        self.begin()
        attempt = self.attempt()
        self.register(attempt, self.observe(attempt, self.ids))
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        (self.repo / 'docs/contract.md').write_text('Changed formal documentation.')
        before = self.controls()
        self.action('complete-task', '--subtask-id', 'DOC-FINAL-001', ok=False)
        self.assertEqual(before, self.controls())
        self.assertEqual(2, self.count())

    def test_prepare_result_rejects_wrong_binding_and_corrupt_run_without_state_changes(self):
        self.begin()
        attempt = self.attempt()
        manifest, summary = self.captured_summary(attempt)
        self.prepare(attempt, manifest, summary)
        draft = self.repo / '.tmp/generated-result.json'
        before, draft_bytes = self.controls(), draft.read_bytes()
        for field in ('task_id', 'attempt_id', 'written_by', 'candidate_id', 'runtime_sha256'):
            with self.subTest(binding=field):
                copied = self.repo / '.artifacts/foreign-run' / field
                shutil.copytree((self.repo / manifest).parent, copied)
                payload = json.loads((copied / 'manifest.json').read_text())
                payload['binding'][field] = 'unrelated-source'
                (copied / 'manifest.json').write_text(json.dumps(payload))
                rejected = self.prepare(attempt, (copied / 'manifest.json').relative_to(self.repo).as_posix(), summary, ok=False)
                self.assertRegex(str(rejected).lower(), 'binding|task|attempt|candidate|runtime|writer|written_by')
                self.assertEqual(before, self.controls())
                self.assertEqual(draft_bytes, draft.read_bytes())
        stdout = (self.repo / manifest).with_name('stdout.log')
        stdout.write_bytes(stdout.read_bytes() + b'corrupt captured stdout')
        rejected = self.prepare(attempt, manifest, summary, ok=False)
        self.assertRegex(str(rejected).lower(), 'hash|integrity|stdout|content')
        self.assertEqual(before, self.controls())
        self.assertEqual(draft_bytes, draft.read_bytes())
        self.assertEqual(2, self.count())

    def test_complete_task_keeps_consumed_evidence_and_integration_gates_atomic(self):
        self.begin()
        attempt = self.attempt()
        receipt = self.observe(attempt, self.ids)
        self.register(attempt, receipt)
        self.bind('DOC-FINAL-001', agent='docs-001', role='doc-curator')
        ref = receipt['expensive_acceptance']['point_results'][0]['evidence_refs'][0]
        original = (self.repo / ref).read_bytes()
        (self.repo / ref).write_text('corrupt adopted observation')
        before = self.controls()
        rejected = self.action('complete-task', '--subtask-id', 'DOC-FINAL-001', ok=False)
        self.assertRegex(str(rejected).lower(), 'evidence|hash|invalid|integrity')
        self.assertEqual(before, self.controls())
        (self.repo / ref).write_bytes(original)
        self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        before = self.controls()
        rejected = self.action('complete-task', '--subtask-id', 'DOC-FINAL-001', ok=False)
        self.assertRegex(str(rejected).lower(), 'integration|unfinished|completed|coverage')
        self.assertEqual(before, self.controls())
        self.assertEqual(2, self.count())


class MultiModuleStreamliningTest(StreamliningHarness, unittest.TestCase):
    def init_task(self, contract):
        for item in contract['acceptance_gate']['acceptance_items']:
            relative = 'modules/' + item['acceptance_id'] + '/rule.json'
            path = self.repo / relative
            path.parent.mkdir(parents=True)
            path.write_text('{"enabled":true}')
            item['paths'].append(relative)
            self.paths.append(relative)
        items = contract['acceptance_gate']['acceptance_items']
        items[1]['depends_on'] = ['CHECK-01']
        items[2]['depends_on'] = ['CHECK-02']
        contract['acceptance_gate']['candidate_inputs']['code_paths'].append('modules')
        for task in contract['subtasks']:
            if task['stage'] in ('work', 'integration') and task['write_paths']:
                task['write_paths'].append('modules')
        source = self.repo / 'candidate-source.py'
        source.write_text(source.read_text().replace(
            'value = json.loads(source.read_text())[ident]',
            "value = json.loads(source.read_text())[ident] and json.loads(Path('modules', ident, 'rule.json').read_text())['enabled']"))
        self.git('add', 'candidate-source.py', 'modules')
        self.git('commit', '-m', 'Freeze synthetic multi-module fixture before task creation')
        return legacy.ControlPlaneContractTest.init_task(self, contract)

    def test_transitive_module_change_preserves_independent_scope_and_resumes(self):
        self.begin(4)
        attempt = self.attempt()
        self.register(attempt, self.observe(attempt, self.ids))
        (self.repo / 'modules/CHECK-01/rule.json').write_text('{"enabled":true,"revision":2}')
        self.reintegrate()
        self.run_ctl('freeze-candidate')
        coverage = self.coverage()
        self.assertEqual(['CHECK-01', 'CHECK-02', 'CHECK-03'], coverage['rerun_acceptance_ids'])
        self.assertEqual('pass', coverage['points']['CHECK-04']['status'])
        self.assertEqual(attempt['attempt_id'], coverage['points']['CHECK-04']['source_attempt_id'])
        before = self.controls()
        resumed = self.resume()
        self.assertEqual(coverage, resumed['acceptance'])
        self.assertEqual(before, self.controls())
        self.assertEqual(4, self.count())


class ScopedCapabilityStreamliningTest(StreamliningHarness, unittest.TestCase):
    init_task = boundaries.PointScopedCapabilityTest.init_task

    def test_missing_page_probe_does_not_block_ordinary_pass_or_resume(self):
        # Reuse the established actual-executor/independent-scope CLI fixture;
        # do not represent synthetic dispatch capability as a browser test.
        boundaries.PointScopedCapabilityTest.test_missing_page_capability_blocks_only_page_scope_and_preserves_ordinary_pass(self)
        before = self.controls()
        resumed = self.resume()
        self.assertEqual('pass', resumed['acceptance']['points']['CHECK-01']['status'])
        self.assertTrue(resumed['capability_checks'])
        self.assertEqual(before, self.controls())
        self.assertEqual(1, self.count())


class BatchResumeStreamliningTest(batch_isolation.MultiPointBatchHarness, StreamliningHarness, unittest.TestCase):
    setUp = StreamliningHarness.setUp

    def test_refrozen_batch_dependency_change_allows_resume_but_bad_raw_does_not(self):
        source, batch = self.complete_batches()
        source_file = self.repo / 'candidate-source.py'
        source_file.write_text(source_file.read_text() + '\n# Changed first-point dependency.\n')
        integration = self.run_ctl('create-integration-subtask', subtask_id='INTEGRATE-001')
        self.bind(integration['subtask_id'], agent='impl-001', role='backend-implementer')
        integrated = self.work_result('integration')
        integrated['changed_files'] = ['candidate-source.py']
        self.run_ctl('record-subtask-result', subtask_id=integration['subtask_id'], result=integrated)
        self.run_ctl('freeze-candidate')
        before = self.controls()
        resumed = self.resume()
        self.assertEqual([self.batch_acceptance_id], resumed['acceptance']['rerun_acceptance_ids'])
        self.assertEqual('pass', resumed['acceptance']['points']['SECOND-POINT']['status'])
        self.assertEqual(before, self.controls())
        self.assertEqual(2, sum(a['real_call_count'] for a in self.state()['acceptance_gate']['attempts']))
        # Damage the independent still-consumed second point, not just the
        # intentionally stale first point. Resume must retain integrity checks.
        raw = self.repo / batch['units'][1]['raw']['path']
        raw.write_bytes(raw.read_bytes() + b'corrupt adopted raw')
        self.resume(ok=False)
        self.assertEqual(before, self.controls())


if __name__ == '__main__':
    unittest.main()
