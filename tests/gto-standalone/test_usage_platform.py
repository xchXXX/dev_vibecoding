"""External UI capability evidence is independent of the host operating system."""
import importlib.util
import json
import os
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(os.environ.get('GTO_TEST_PACKAGE', ROOT / 'skills/gto-standalone/global-task-orchestrator'))
spec = importlib.util.spec_from_file_location('gto_usage_platform', PACKAGE / 'scripts/orchestrator_ctl.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
schema = json.loads((PACKAGE / 'schemas/orchestrator-task-state.schema.json').read_text(encoding='utf-8'))
validator = Draft202012Validator({'$ref': '#/$defs/usageEvidence', '$defs': schema['$defs']})


def usage(environment='macos', tool='Computer Use'):
    return {'written_by': 'reviewer', 'environment': environment, 'tool': tool,
            'entry': 'external desktop capability', 'scope': ['open target window'],
            'result': 'target window observed', 'evidence_refs': ['.artifacts/ui/result.json'],
            'ui_applicability': 'required', 'ui_not_applicable_reason': ''}


class UsagePlatformTest(unittest.TestCase):
    def test_ui_evidence_accepts_actual_environment_without_os_allowlist(self):
        for environment in ('macos', 'linux', 'windows_native', 'wsl', 'other', 'remote-desktop'):
            for tool in ('Computer Use', 'Browser'):
                with self.subTest(environment=environment, tool=tool):
                    evidence = [usage(environment, tool)]
                    self.assertEqual(list(validator.iter_errors(evidence)), [])
                    self.assertEqual(controller._usage_errors(evidence, 'reviewer'), [])

    def test_environment_remains_required_and_nonempty(self):
        for environment in ('', '   ', None, 123):
            with self.subTest(environment=environment):
                self.assertTrue(list(validator.iter_errors([usage(environment)])))
        evidence = usage()
        del evidence['environment']
        self.assertTrue(list(validator.iter_errors([evidence])))

    def test_ui_still_requires_ui_tool(self):
        for tool in ('CLI', 'API'):
            self.assertTrue(controller._usage_errors([usage(tool=tool)], 'reviewer'))

    def test_real_stage_writer_and_evidence_fields_remain_required(self):
        self.assertTrue(controller._usage_errors([usage()], 'acceptor'))
        for field in ('entry', 'scope', 'result', 'evidence_refs', 'environment'):
            with self.subTest(field=field):
                evidence = usage()
                del evidence[field]
                self.assertTrue(controller._usage_errors([evidence], 'reviewer'))

    def test_non_ui_keeps_applicability_reason(self):
        evidence = usage(tool='CLI')
        evidence['ui_applicability'] = 'not_applicable'
        self.assertTrue(controller._usage_errors([evidence], 'reviewer'))
        evidence['ui_not_applicable_reason'] = 'Command-line only target'
        self.assertEqual(controller._usage_errors([evidence], 'reviewer'), [])


if __name__ == '__main__':
    unittest.main()
