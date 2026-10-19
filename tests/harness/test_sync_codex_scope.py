"""限定GTO发布的独立合同；所有安装操作仅发生在本测试临时目录。"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location('sync_codex_scoped_test_target', ROOT / 'scripts/sync-codex.py')
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)
GTO = 'global-task-orchestrator'
ENVIRONMENT_SKILL = 'command-failure-memory'
GTO_SCHEMA = f'skills/{GTO}/schemas/orchestrator-task-state.schema.json'


class ScopedCodexSyncTest(unittest.TestCase):
    def setUp(self):
        root = ROOT / '.tmp/review-acceptance-routing/test-a'
        root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name) / 'harness'
        self.installed = Path(self.temporary.name) / 'installed'
        self.source.mkdir()
        self.installed.mkdir()
        self.put(self.source, 'rules/registry/RULES_ENTRY.md', '# Fixture harness\n')
        for skill in SYNC.MANAGED_SKILLS:
            self.put(self.source, f'skills/{skill}/SKILL.md', f'old {skill}\n')
        self.put(self.source, GTO_SCHEMA, '{"version":"old"}\n')
        self.put(self.source, f'skills/{GTO}/scripts/start_session.py', '# old recovery\n')
        self.put(self.source, f'skills/{GTO}/scripts/orchestrator_ctl.py', '# old controller\n')
        # 用现有正式同步器生成初始receipt，不手拼替代发布路径。
        initial = SYNC.synchronize(self.source, self.installed)
        self.assertTrue(initial['ok'], initial)
        self.receipt_path = self.installed / '.ai-harness/codex-sync.receipt.json'
        receipt = self.receipt()
        receipt['retained_fixture_metadata'] = {'origin': 'previous-approved-publication'}
        receipt['managed_schema_files'].append({'source': 'schemas/unrelated.schema.json',
            'target': 'schemas/unrelated.schema.json', 'sha256': self.digest('unrelated-old\n')})
        self.put(self.installed, 'schemas/unrelated.schema.json', 'unrelated-old\n')
        self.receipt_path.write_text(json.dumps(receipt))
        self.before_receipt = self.receipt()
        self.before_other = self.other_files()
        # 模拟同一source工作区的未获准Windows及其他技能新内容。
        for skill in SYNC.MANAGED_SKILLS:
            self.put(self.source, f'skills/{skill}/SKILL.md', f'new {skill}\n')
        self.put(self.source, GTO_SCHEMA, '{"version":"new"}\n')
        self.put(self.source, f'skills/{GTO}/scripts/start_session.py', '# new recovery\n')
        self.put(self.source, f'skills/{GTO}/scripts/orchestrator_ctl.py', '# new controller\n')

    @staticmethod
    def digest(content):
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def put(root, relative, content):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def receipt(self):
        return json.loads(self.receipt_path.read_text())

    def other_files(self):
        paths = [p for p in self.installed.rglob('*') if p.is_file()
                 and (p.relative_to(self.installed).parts[0] == 'skills'
                      and p.relative_to(self.installed).parts[1] != GTO)]
        paths.append(self.installed / 'schemas/unrelated.schema.json')
        return {str(p.relative_to(self.installed)): (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}

    def scoped(self):
        self.assertIn('skills', inspect.signature(SYNC.synchronize).parameters,
                      'synchronize needs explicit selected skills before limited publication is possible')
        return SYNC.synchronize(self.source, self.installed, skills=[GTO])

    def assert_scoped_publication(self, result):
        self.assertTrue(result['ok'], result)
        self.assertEqual([GTO], result['changed_managed_skills'])
        self.assertEqual(self.before_other, self.other_files(), 'unselected files must not be rewritten')
        updated = self.receipt()
        self.assertEqual(self.before_receipt['retained_fixture_metadata'], updated['retained_fixture_metadata'])
        self.assertEqual(set(self.before_receipt['managed_skills']), set(updated['managed_skills']))
        others_before = [r for r in self.before_receipt['managed_files'] if r['skill'] != GTO]
        others_after = [r for r in updated['managed_files'] if r['skill'] != GTO]
        self.assertEqual(others_before, others_after)
        self.assertEqual(self.before_receipt['managed_schema_files'], updated['managed_schema_files'])
        gto_records = [r for r in updated['managed_files'] if r['skill'] == GTO]
        expected_files = {
            f'skills/{GTO}/SKILL.md': f'new {GTO}\n',
            GTO_SCHEMA: '{"version":"new"}\n',
            f'skills/{GTO}/scripts/start_session.py': '# new recovery\n',
            f'skills/{GTO}/scripts/orchestrator_ctl.py': '# new controller\n',
        }
        self.assertEqual(len(expected_files), len(gto_records), 'replacement must not duplicate stale GTO records')
        for relative, content in expected_files.items():
            self.assertEqual(content, (self.installed / relative).read_text())
            rows = [r for r in gto_records if r['target'] == relative.removeprefix('skills/')]
            self.assertEqual(1, len(rows))
            self.assertEqual(relative, rows[0]['source'])
            self.assertEqual(self.digest(content), rows[0]['sha256'])
        self.assertFalse((self.installed / 'schemas/orchestrator-task-state.schema.json').exists())

    def test_selected_gto_updates_only_gto_and_owned_schema(self):
        self.assert_scoped_publication(self.scoped())

    def test_publication_replaces_old_reference_with_complete_current_package(self):
        old = f'skills/{GTO}/references/usage-modes.md'
        self.put(self.source, old, '# Old combined entry\n')
        self.assertTrue(self.scoped()['ok'])
        self.assertTrue((self.installed / old).is_file())
        (self.source / old).unlink()
        references = ROOT / f'skills/{GTO}/references'
        for name in ('plan-guide.md', 'workflow.md'):
            self.put(self.source, f'skills/{GTO}/references/{name}', (references / name).read_text())

        result = self.scoped()

        self.assertTrue(result['ok'], result)
        self.assertFalse((self.installed / old).exists())
        rows = {row['source']: row for row in self.receipt()['managed_files'] if row['skill'] == GTO}
        self.assertNotIn(old, rows)
        for name in ('plan-guide.md', 'workflow.md'):
            relative = f'skills/{GTO}/references/{name}'
            self.assertEqual((references / name).read_bytes(), (self.installed / relative).read_bytes())
            self.assertEqual(self.digest((references / name).read_text()), rows[relative]['sha256'])
        self.assertEqual(self.before_other, self.other_files())

    def test_selected_gto_retires_receipt_owned_legacy_root_schema(self):
        legacy_relative = 'schemas/orchestrator-task-state.schema.json'
        legacy_content = '{"version":"legacy-root"}\n'
        self.put(self.installed, legacy_relative, legacy_content)
        receipt = self.receipt()
        receipt['managed_schema_files'].append({
            'source': legacy_relative,
            'target': legacy_relative,
            'sha256': self.digest(legacy_content),
        })
        self.receipt_path.write_text(json.dumps(receipt))

        result = self.scoped()

        self.assertTrue(result['ok'], result)
        self.assertFalse(
            (self.installed / legacy_relative).exists(),
            'publishing the packaged GTO schema must retire its receipt-owned legacy root copy',
        )
        self.assertNotIn(
            legacy_relative,
            {row.get('target') for row in self.receipt()['managed_schema_files']},
            'the receipt must not preserve a second editable GTO schema inventory',
        )

    def seed_legacy_schema(self):
        relative = 'schemas/orchestrator-task-state.schema.json'
        self.put(self.installed, relative, 'legacy schema\n')
        receipt = self.receipt()
        receipt['managed_schema_files'].append({'source': relative, 'target': relative,
                                               'sha256': self.digest('legacy schema\n')})
        self.receipt_path.write_text(json.dumps(receipt))
        return self.installed / relative

    def test_full_sync_retires_legacy_schema_and_preserves_unrelated_ownership(self):
        legacy = self.seed_legacy_schema()
        unrelated = self.installed / 'schemas/unrelated.schema.json'
        before = (unrelated.read_bytes(), unrelated.stat().st_mtime_ns)
        result = SYNC.synchronize(self.source, self.installed)
        self.assertTrue(result['ok'], result)
        self.assertFalse(legacy.exists())
        self.assertEqual(self.before_receipt['managed_schema_files'], self.receipt()['managed_schema_files'])
        self.assertEqual(before, (unrelated.read_bytes(), unrelated.stat().st_mtime_ns))

    def test_full_sync_rejects_retired_skill_ownership_before_writes(self):
        self.seed_legacy_schema()
        retired = 'retired-managed-skill'
        relative = f'skills/{retired}/SKILL.md'
        self.put(self.installed, relative, 'owned retired skill\n')
        original = self.receipt()
        for inventory in ('both', 'skill-only', 'file-only'):
            with self.subTest(inventory=inventory):
                receipt = json.loads(json.dumps(original))
                if inventory != 'file-only':
                    receipt['managed_skills'].append(retired)
                if inventory != 'skill-only':
                    receipt['managed_files'].append({'skill': retired, 'source': relative,
                        'target': f'{retired}/SKILL.md', 'sha256': self.digest('owned retired skill\n')})
                self.receipt_path.write_text(json.dumps(receipt))
                before = {p.relative_to(self.installed): p.read_bytes()
                          for p in self.installed.rglob('*') if p.is_file()}
                result = SYNC.synchronize(self.source, self.installed)
                self.assertFalse(result['ok'], 'full sync must not retain retired skill ownership and claim success')
                self.assertTrue(any('retired' in error for error in result['errors']), result)
                self.assertEqual(before, {p.relative_to(self.installed): p.read_bytes()
                                          for p in self.installed.rglob('*') if p.is_file()})

    def test_full_sync_replaces_allowlist_inventory_not_previous_metadata(self):
        receipt = self.receipt()
        receipt['managed_skills'].reverse()
        self.receipt_path.write_text(json.dumps(receipt))
        result = SYNC.synchronize(self.source, self.installed)
        self.assertTrue(result['ok'], result)
        updated = self.receipt()
        self.assertEqual(list(SYNC.MANAGED_SKILLS), updated['managed_skills'])
        self.assertNotIn('retained_fixture_metadata', updated)
        self.assertEqual(self.before_receipt['managed_schema_files'], updated['managed_schema_files'])
        self.assertEqual(set(SYNC.MANAGED_SKILLS), {row['skill'] for row in updated['managed_files']})

    def test_legacy_schema_drift_rejects_before_partial_or_full_writes(self):
        legacy = self.seed_legacy_schema()
        good_receipt = self.receipt()
        for selected in ([GTO], None):
            for defect in ('file', 'receipt-hash', 'receipt-source', 'unowned', 'duplicate'):
                with self.subTest(selected=selected, defect=defect):
                    receipt = json.loads(json.dumps(good_receipt))
                    legacy.write_text('changed\n' if defect == 'file' else 'legacy schema\n')
                    if defect == 'receipt-hash':
                        receipt['managed_schema_files'][-1]['sha256'] = '0' * 64
                    elif defect == 'receipt-source':
                        receipt['managed_schema_files'][-1]['source'] = 'schemas/other.json'
                    elif defect == 'unowned':
                        receipt['managed_schema_files'].pop()
                    elif defect == 'duplicate':
                        receipt['managed_schema_files'].append(dict(receipt['managed_schema_files'][-1]))
                    self.receipt_path.write_text(json.dumps(receipt))
                    before = {p.relative_to(self.installed): p.read_bytes()
                              for p in self.installed.rglob('*') if p.is_file()}
                    result = SYNC.synchronize(self.source, self.installed, skills=selected)
                    self.assertFalse(result['ok'], result)
                    self.assertEqual(before, {p.relative_to(self.installed): p.read_bytes()
                                              for p in self.installed.rglob('*') if p.is_file()})

    def test_legacy_schema_retirement_restores_file_when_receipt_commit_fails(self):
        legacy = self.seed_legacy_schema()
        before = (legacy.read_bytes(), self.receipt_path.read_bytes())
        def fail_commit(*args):
            self.assertFalse(legacy.exists(), 'fault must hit after schema retirement starts')
            raise OSError('injected receipt commit failure')
        with patch.object(SYNC, 'write_json', side_effect=fail_commit):
            with self.assertRaisesRegex(OSError, 'injected receipt'):
                self.scoped()
        self.assertEqual(before, (legacy.read_bytes(), self.receipt_path.read_bytes()))

    def test_doctor_rejects_legacy_schema_inventory_and_orphan(self):
        legacy = self.seed_legacy_schema()
        contract = f'skills/{GTO}/references/revision-3-contract.example.json'
        self.put(self.source, contract, (ROOT / contract).read_text())
        spec = importlib.util.spec_from_file_location('rar001_doctor', ROOT / 'scripts/doctor-core.py')
        doctor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doctor)
        original = self.receipt()
        for mode in ('both', 'orphan', 'inventory-only'):
            with self.subTest(mode=mode):
                if mode == 'orphan':
                    receipt = self.receipt()
                    receipt['managed_schema_files'] = self.before_receipt['managed_schema_files']
                    self.receipt_path.write_text(json.dumps(receipt))
                elif mode == 'inventory-only':
                    legacy.unlink()
                    self.receipt_path.write_text(json.dumps(original))
                result = doctor.audit(self.source, self.installed)
                issues = result['codex_audit']['runtime_issues']
                expected = 'legacy_gto_schema_inventory' if mode == 'inventory-only' else 'legacy_gto_schema_present'
                self.assertTrue(any(i['type'] == expected for i in issues), issues)
                self.assertEqual(mode != 'inventory-only', legacy.exists(), 'doctor remains read-only')

    def test_selected_gto_does_not_require_unselected_source_skills(self):
        for skill in SYNC.MANAGED_SKILLS:
            if skill != GTO:
                shutil.rmtree(self.source / 'skills' / skill)
        self.assert_scoped_publication(self.scoped())

    def test_cli_skill_flag_performs_the_same_scoped_publication(self):
        completed = subprocess.run([sys.executable, str(ROOT / 'scripts/sync-codex.py'),
            '--harness-root', str(self.source), '--codex-home', str(self.installed),
            '--skill', GTO, '--json'], capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assert_scoped_publication(json.loads(completed.stdout))

    def test_default_call_keeps_full_managed_publication(self):
        result = SYNC.synchronize(self.source, self.installed)
        self.assertTrue(result['ok'], result)
        self.assertEqual(set(SYNC.MANAGED_SKILLS), set(result['changed_managed_skills']))
        for skill in SYNC.MANAGED_SKILLS:
            self.assertEqual(f'new {skill}\n', (self.installed / f'skills/{skill}/SKILL.md').read_text())
        self.assertEqual(set(SYNC.MANAGED_SKILLS), set(self.receipt()['managed_skills']))

    def test_cli_can_publish_only_cfm_without_touching_gto_or_gto_schema(self):
        gto_path = self.installed / f'skills/{GTO}/SKILL.md'
        gto_path.write_text('installed GTO sentinel\n')
        gto_before = {path.relative_to(self.installed).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
                      for path in (self.installed / f'skills/{GTO}').rglob('*') if path.is_file()}
        receipt_before = [row for row in self.receipt()['managed_files'] if row['skill'] == GTO]
        self.assertIn(GTO_SCHEMA, gto_before)

        completed = subprocess.run([
            sys.executable, str(ROOT / 'scripts/sync-codex.py'),
            '--harness-root', str(self.source), '--codex-home', str(self.installed),
            '--skill', ENVIRONMENT_SKILL, '--json',
        ], capture_output=True, text=True)

        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual([ENVIRONMENT_SKILL], result['synchronized_skills'])
        self.assertEqual([ENVIRONMENT_SKILL], result['changed_managed_skills'])
        self.assertEqual('installed GTO sentinel\n', gto_path.read_text())
        self.assertEqual(
            gto_before,
            {path.relative_to(self.installed).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
             for path in (self.installed / f'skills/{GTO}').rglob('*') if path.is_file()},
        )
        self.assertEqual(receipt_before, [row for row in self.receipt()['managed_files'] if row['skill'] == GTO])


if __name__ == '__main__':
    unittest.main()
