"""Read-only prerequisite check; uses only the standard library to report missing dependencies."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys


def inspect_runtime():
    root = Path(__file__).resolve().parents[1]
    issues = []
    if sys.version_info < (3, 11):
        issues.append('需要 Python 3.11 或更新版本。')
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        version = importlib.metadata.version('jsonschema')
        parts = tuple(int(part) for part in version.split('.')[:3])
        if not (parts >= (4, 10, 3) and parts < (5, 0, 0)):
            issues.append('jsonschema 版本不符合 requirements.txt：' + version)
        schema = root / 'schemas/orchestrator-task-state.schema.json'
        Draft202012Validator.check_schema(json.loads(schema.read_text(encoding='utf-8')))
        FormatChecker()
    except (ImportError, importlib.metadata.PackageNotFoundError):
        issues.append('缺少 jsonschema；使用当前解释器 -m pip install -r <skill目录>/requirements.txt 安装。')
    except Exception as error:
        issues.append('schema 或 jsonschema 检查失败：' + str(error))
    git = shutil.which('git')
    if git is None:
        issues.append('当前执行环境的 PATH 中缺少 Git；请先安装并使 git 可执行。')
    else:
        try:
            checked = subprocess.run([git, '--version'], capture_output=True, timeout=10)
            if checked.returncode:
                issues.append('git --version 执行失败。')
        except (OSError, subprocess.TimeoutExpired) as error:
            issues.append('Git 无法执行：' + str(error))
    for name in ('SKILL.md', 'requirements.txt', 'scripts/orchestrator_ctl.py',
                 'scripts/start_session.py', 'scripts/runtime_evidence.py',
                 'scripts/capability_gate.py', 'scripts/acceptance_batches.py',
                 'references/workflow.md', 'references/revision-3-contract.example.json'):
        if not (root / name).is_file():
            issues.append('技能包缺少文件：' + name)
    return {'ok': not issues, 'skill_root': str(root), 'python': sys.executable,
            'python_version': sys.version.split()[0], 'git': git, 'issues': issues,
            'requirements': str(root / 'requirements.txt'),
            'platform_capabilities_verified': False,
            'next_step': '在 Codex 新会话中核对技能加载及真实子代理能力；自检不证明平台能力。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = inspect_runtime()
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
