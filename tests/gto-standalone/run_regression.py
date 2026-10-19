"""Run existing GTO behavior suites against a copied standalone candidate, not the original."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=ROOT / 'skills/gto-standalone/global-task-orchestrator')
    parser.add_argument('--log', type=Path, default=ROOT / '.artifacts/gto-standalone/regression.log')
    parser.add_argument('--suite', action='append', help='Optional targeted unittest module or test name')
    args = parser.parse_args()
    base = ROOT / '.tmp/gto-standalone/regression'
    base.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as temporary:
        isolated = Path(temporary)
        candidate = isolated / 'skills/global-task-orchestrator'
        shutil.copytree(args.package, candidate,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(ROOT / 'tests/harness', isolated / 'tests/harness',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        # The inherited blocker fixture predates the consumer/.tmp contract.
        # Use the independently repaired fixture without changing the source suite.
        blocker = ROOT / 'tests/gto-standalone/test_coordinator_blocking.py'
        if blocker.is_file():
            shutil.copyfile(blocker, isolated / 'tests/harness/test_gto_coordinator_blocking.py')
        (isolated / '.tmp').mkdir()
        env = dict(os.environ, PYTHONPATH=str(isolated / 'tests/harness'), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                   GTO_TEST_PACKAGE=str(isolated / 'skills/global-task-orchestrator'), GTO_TEST_REPO=str(isolated))
        suites = args.suite or ['test_gto_workflow', 'test_gto_runtime_hardening', 'test_gto_capability_gate',
                  'test_gto_acceptance_batches', 'test_gto_coordinator_blocking']
        with args.log.open('w', encoding='utf-8') as log:
            result = subprocess.run([sys.executable, '-B', '-m', 'unittest', *suites, '-v'],
                cwd=isolated, env=env, stdout=log, stderr=subprocess.STDOUT)
        args.log.with_suffix('.json').write_text(json.dumps({
            'exit_code': result.returncode, 'suites': suites,
            'blocker_fixture_adapter': blocker.is_file(),
            'package_files': {str(p.relative_to(candidate)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(candidate.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
        }, indent=2) + '\n', encoding='utf-8')
        print(args.log.read_text(encoding='utf-8')[-12000:])
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
