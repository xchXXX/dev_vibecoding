#!/usr/bin/env python3
"""Generate a portable project copy; refuse to overwrite unowned or edited files."""
import argparse
import hashlib
from pathlib import Path
import re


FILES = ('check_git_workflow.py', 'task_workspace.py')


def generated(source, name='check_git_workflow.py'):
    digest = hashlib.sha256(source).hexdigest()
    return f'# Generated from ai-harness/scripts/{name}; DO NOT EDIT.\n# source-sha256: {digest}\n'.encode() + source


def verify_owned(data, name='check_git_workflow.py'):
    lines = data.split(b'\n', 2)
    if len(lines) != 3 or lines[0] != f'# Generated from ai-harness/scripts/{name}; DO NOT EDIT.'.encode():
        raise ValueError('TARGET_UNMANAGED')
    digest = lines[1].removeprefix(b'# source-sha256: ').decode()
    if not re.fullmatch('[0-9a-f]{64}', digest) or hashlib.sha256(lines[2]).hexdigest() != digest:
        raise ValueError('GENERATED_TARGET_DRIFT')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.project_root.resolve(strict=True)
    try:
        updates = {}
        for name in FILES:
            target = root / 'modules/tooling' / name
            expected = generated(Path(__file__).with_name(name).read_bytes(), name)
            if not target.resolve().is_relative_to(root):
                raise ValueError('TARGET_OUTSIDE_PROJECT')
            current = target.read_bytes() if target.exists() else None
            if current is not None:
                verify_owned(current, name)
            if args.check and current != expected:
                raise ValueError('GENERATED_TARGET_STALE')
            if not args.check and current != expected:
                updates[target] = expected
        # Check ownership of the entire pair before writing either entry.
        for target, expected in updates.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
        print('PASS ' + str(root / 'modules/tooling'))
        return 0
    except (ValueError, OSError) as error:
        print(str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
