"""Generate an exact standalone copy of the canonical GTO skill; --check is read-only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'SKILL.md', 'README.md', 'requirements.txt'}
DIRECTORIES = {'agents', 'references', 'schemas', 'scripts'}


def _inventory(root):
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError('package path must not contain symlinks')
    result = {}
    folded = set()
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('package must not contain symlinks: ' + str(path))
        relative = path.relative_to(root)
        if '__pycache__' in relative.parts or path.suffix == '.pyc':
            continue
        if not path.is_file():
            continue
        name = relative.as_posix()
        if name.casefold() in folded:
            raise ValueError('case-colliding package path: ' + name)
        folded.add(name.casefold())
        result[name] = path.read_bytes()
    return result


def generate(source, output, *, check=False):
    source, output = Path(source).absolute(), Path(output).absolute()
    if source.resolve().is_relative_to(output.resolve()) or output.resolve().is_relative_to(source.resolve()):
        raise ValueError('source and output must not overlap')
    contents = _inventory(source)
    if not ROOT_FILES.issubset(contents):
        raise ValueError('canonical package is missing required root files')
    for name in contents:
        if name not in ROOT_FILES and Path(name).parts[0] not in DIRECTORIES:
            raise ValueError('unexpected canonical package file: ' + name)
    manifest = {'schema_version': 1, 'source': 'skills/global-task-orchestrator',
                'generated_by': 'scripts/generate-gto-standalone.py',
                'files': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(contents.items())]}
    contents['SOURCE.json'] = (json.dumps(manifest, ensure_ascii=True, indent=2) + '\n').encode('utf-8')
    current = _inventory(output)
    missing = sorted(contents.keys() - current.keys())
    extra = sorted(current.keys() - contents.keys())
    changed = sorted(name for name in current.keys() & contents.keys() if current[name] != contents[name])
    if check:
        return {'ok': not (missing or extra or changed), 'missing': missing, 'extra': extra,
                'changed': changed, 'files': len(contents)}
    if extra:
        raise ValueError('unexpected output files; preserve and inspect before generation: ' + ', '.join(extra))
    for name, content in contents.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if current.get(name) != content:
            target.write_bytes(content)
    return {'ok': True, 'files': len(contents), 'changed': missing + changed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'skills/global-task-orchestrator')
    parser.add_argument('--output', type=Path, default=ROOT / 'skills/gto-standalone/global-task-orchestrator')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        result = generate(args.source, args.output, check=args.check)
    except (OSError, ValueError) as error:
        result = {'ok': False, 'errors': [str(error)]}
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
