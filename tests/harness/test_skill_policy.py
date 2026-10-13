import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('skill_policy', ROOT / 'scripts/configure-skill-policy.py')
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class SkillPolicyTest(unittest.TestCase):
    def test_path_switches_preserve_unrelated_settings_and_are_idempotent(self):
        data = json.loads((ROOT / 'config/ai/skill-policy.json').read_text())
        with tempfile.TemporaryDirectory(dir=ROOT / '.tmp') as folder:
            root = Path(folder)
            for name in data['disabled'] + data['retained_methods']:
                path = root / name / 'SKILL.md'
                path.parent.mkdir()
                path.write_text('fixture')
            before = 'model = "configured-model"\n[unrelated]\nvalue = "preserve"\n\n[[skills.config]]\nname = "superpowers:subagent-driven-development"\nenabled = false\n\n[[skills.config]]\npath = "/custom/SKILL.md"\nenabled = true\n'
            rendered, expected = POLICY.render_policy(before, data, root)
            parsed = tomllib.loads(rendered)
            self.assertEqual('configured-model', parsed['model'])
            self.assertEqual({'value': 'preserve'}, parsed['unrelated'])
            rows = parsed['skills']['config']
            self.assertEqual(10, len(rows))
            self.assertTrue(all('name' not in row for row in rows))
            self.assertEqual(expected, {r['path'] for r in rows if r['enabled'] is False})
            again, _ = POLICY.render_policy(rendered, data, root)
            self.assertEqual(rendered, again)
            for name in data['retained_methods']:
                self.assertFalse(any('/' + name + '/' in path for path in expected))
            (root / data['disabled'][0] / 'SKILL.md').unlink()
            with self.assertRaisesRegex(ValueError, 'plugin skill missing'):
                POLICY.render_policy(rendered, data, root)
