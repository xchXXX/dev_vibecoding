"""Export the standalone skill without installing or touching the original GTO."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


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
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output_dir)))


if __name__ == '__main__':
    main()
