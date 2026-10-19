"""Locate public tools by installation layout; never enumerate user directories."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime_evidence import tree_manifest


def package_identity(path: Path | None) -> dict:
    """Observe package bytes, never infer session loading or repair a package."""
    result = {'path': str(path.absolute()) if path and path.is_dir() else None,
              'content_sha256': None}
    if path is not None:
        try:
            result['content_sha256'] = tree_manifest(path)['sha256']
        except (OSError, ValueError) as error:
            result['error'] = str(error)
    return result


def diagnostic(code: str, owner: str, scope: str, next_step: str) -> dict:
    return {'code': code, 'owner': owner, 'affected_scope': scope, 'next_step': next_step}


def _receipt_status(home: Path | None) -> str:
    if home is None:
        return 'unknown'
    receipt_path = home / '.ai-harness/codex-sync.receipt.json'
    if not receipt_path.exists():
        return 'missing'
    try:
        # Refuse indirect receipt paths; only inspect the explicitly selected home.
        if any(p.is_symlink() for p in (receipt_path, *receipt_path.parents)):
            return 'invalid'
        receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
        if not isinstance(receipt, dict) or not isinstance(receipt.get('managed_files'), list):
            return 'invalid'
        owner = receipt.get('codex_home')
        if not isinstance(owner, str) or not Path(owner).is_absolute() or Path(owner).resolve() != home.resolve():
            return 'mismatch'
        skill = 'global-task-orchestrator'
        managed_skills = receipt.get('managed_skills')
        if (not isinstance(managed_skills, list)
                or not all(isinstance(item, str) and item for item in managed_skills)
                or len(set(managed_skills)) != len(managed_skills)):
            return 'invalid'
        if skill not in managed_skills:
            return 'mismatch'
        recorded = {}
        for row in receipt['managed_files']:
            if not isinstance(row, dict):
                return 'invalid'
            target = row.get('target')
            if row.get('skill') != skill:
                if isinstance(target, str) and target.startswith(skill + '/'):
                    return 'mismatch'
                continue
            if not isinstance(target, str) or not target.startswith(skill + '/'):
                return 'invalid'
            relative = target[len(skill) + 1:]
            if not relative or '..' in Path(relative).parts or Path(relative).is_absolute() or '\\' in relative:
                return 'invalid'
            if relative in recorded or row.get('source') != 'skills/' + target:
                return 'invalid'
            recorded[relative] = row.get('sha256')
        actual = tree_manifest(home / 'skills' / skill)['files']
        return 'matched' if recorded == actual else 'mismatch'
    except (OSError, ValueError, TypeError):
        return 'invalid'


def resolve_tools(codex_home: Path | None = None, harness_root: Path | None = None) -> dict:
    directory = Path(__file__).resolve().parent
    paths = {
        'controller': directory / 'orchestrator_ctl.py',
        'resume': directory / 'start_session.py',
        'runtime_evidence': directory / 'runtime_evidence.py',
        'project_env_doctor': (codex_home / '.ai-harness/runtime/wsl-environment/bin/project-env-doctor.py'
                               if codex_home is not None else None),
    }
    installed = package_identity(codex_home / 'skills/global-task-orchestrator' if codex_home else None)
    installed['receipt_status'] = _receipt_status(codex_home)
    versions = {'source': package_identity(harness_root / 'skills/global-task-orchestrator' if harness_root else None),
                'loaded': package_identity(directory.parent), 'installed': installed,
                'session_load': 'unknown'}
    diagnostics = [diagnostic('tool_unavailable', 'installation', name,
        '核对该公开路径与项目实际需要；仅阻塞依赖此工具的检查，不自动安装或搜索其他目录。')
        for name, path in paths.items() if not path or not path.is_file()]
    for name in ('source', 'loaded', 'installed'):
        if versions[name].get('error'):
            diagnostics.append(diagnostic('package_unreadable', 'installation', name,
                '核对显式包路径及完整性；当前内容版本未知，不据此放行执行。'))
    if installed['receipt_status'] not in {'unknown', 'matched'}:
        diagnostics.append(diagnostic('installation_receipt_' + installed['receipt_status'], 'installation',
            'global-task-orchestrator', '核对安装归属、原回执与文件；批准的定向更新后再核验，旧任务保持原冻结版本。'))
    return {'ok': True, 'tools': {
        name: {'path': str(path) if path else None, 'available': bool(path and path.is_file())}
        for name, path in paths.items()},
        'version_summary': versions, 'diagnostics': diagnostics,
        'note': 'Exact public locations only. File presence does not prove execution capability or session loading.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path)
    parser.add_argument('--harness-root', type=Path, help='Explicit source root; never auto-discovered.')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    print(json.dumps(resolve_tools(args.codex_home, args.harness_root), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
