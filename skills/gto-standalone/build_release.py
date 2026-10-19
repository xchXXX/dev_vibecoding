"""Export the standalone skill without installing or touching the original GTO."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def refresh(source, package):
    """Regenerate the distributable from an explicit canonical skill directory."""
    source, package = Path(source).resolve(), Path(package).resolve()
    if source.is_relative_to(package) or package.is_relative_to(source) or not (source / 'scripts/orchestrator_ctl.py').is_file():
        raise ValueError('refresh requires a separate canonical GTO skill directory')
    contents = {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('canonical skill must not contain symlinks')
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            contents[path.relative_to(source).as_posix()] = path.read_bytes()
    package.mkdir(parents=True, exist_ok=True)
    # These publication wrappers are maintained here, not duplicate controller
    # implementations. Keep them when pruning the previous generated inventory.
    wrappers = {'README.md', 'references/governance.md'}
    previous = package / 'SOURCE.json'
    if previous.is_file():
        for item in json.loads(previous.read_text()).get('files', []):
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('unsafe generated inventory path')
            target = package / relative
            if not target.resolve().is_relative_to(package) or target.is_symlink():
                raise ValueError('unsafe generated inventory target')
            if relative.as_posix() not in contents and relative.as_posix() not in wrappers and target.is_file():
                target.unlink()
    for relative, raw in contents.items():
        target = package / relative
        if target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('distribution must not contain symlinks')
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith('.md'):
            text = raw.decode('utf-8').replace('../../../docs/SUBAGENT_GOVERNANCE.md#黑盒验收归因和清理', 'governance.md#环境与证据')
            text = text.replace('../../../docs/SUBAGENT_GOVERNANCE.md', 'governance.md')
            text = text.replace('../../command-failure-memory/SKILL.md#触发边界', 'governance.md#命令失败与重试')
            text = text.replace('../../command-failure-memory/SKILL.md', 'governance.md#命令失败与重试')
            if relative == 'SKILL.md':
                text = text.replace('全局 AGENTS 决定是否启用 GTO；本入口负责按阶段指向唯一正文。',
                    '仅在用户显式选择 GTO 或继续已批准任务时启用；消费项目自身权限与约束仍适用。'
                    '本包独立运行，不要求全局 AGENTS、ai-harness 或其他 skill。')
                text = text.replace('## 先定位任务',
                    '安装与依赖见 [使用说明](README.md)。使用实际环境的 Python 3.10+ 运行 '
                    '`scripts/doctor.py --json`；脚本自检不证明宿主工具可用。'
                    '治理与命令失败边界见 [包内治理](references/governance.md)。\n\n## 先定位任务')
            raw = text.encode('utf-8')
        target.write_bytes(raw)
    (package / 'SOURCE.json').write_text(json.dumps({'generated': True,
        'source': 'canonical global-task-orchestrator skill',
        'files': [{'path': p, 'sha256': hashlib.sha256(raw).hexdigest()} for p, raw in contents.items()]},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.is_relative_to(source):
        raise ValueError('release output must be outside the skill')
    required = {'SKILL.md', 'README.md', 'SOURCE.json', 'requirements.txt'}
    directories = {'agents', 'references', 'schemas', 'scripts'}
    contents = {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('release must not contain symlinks: ' + str(path))
        relative = path.relative_to(source)
        if '__pycache__' in relative.parts or path.suffix == '.pyc':
            continue
        if not path.is_file():
            continue
        if relative.as_posix() not in required and relative.parts[0] not in directories:
            raise ValueError('unexpected package content: ' + str(relative))
        contents[relative.as_posix()] = path.read_bytes()
    if not required.issubset(contents):
        raise ValueError('incomplete skill: missing required root files')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'global-task-orchestrator.zip'
    temporary = output / 'global-task-orchestrator.zip.writing'
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for path, data in contents.items():
            entry = zipfile.ZipInfo('global-task-orchestrator/' + path, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            zipped.writestr(entry, data)
    temporary.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = output / 'manifest.json'
    manifest.write_text(json.dumps({'archive': archive.name, 'archive_sha256': digest,
        'files': {p: hashlib.sha256(b).hexdigest() for p, b in contents.items()}}, indent=2) + '\n', encoding='utf-8')
    (output / 'global-task-orchestrator.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    return {'archive': str(archive), 'manifest': str(manifest), 'sha256': digest, 'files': len(contents)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent / 'global-task-orchestrator')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--refresh-source', type=Path, help='Refresh the distributable from this canonical skill before export.')
    args = parser.parse_args()
    if args.refresh_source:
        refresh(args.refresh_source, args.source)
    print(json.dumps(build(args.source, args.output_dir)))


if __name__ == '__main__':
    main()
