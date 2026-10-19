#!/usr/bin/env python3
"""Generate a portable project copy; refuse to overwrite unowned or edited files."""
import argparse
import hashlib
from pathlib import Path
import re


def generated(source):
    digest = hashlib.sha256(source).hexdigest()
    return f'# Generated from ai-harness/scripts/check_git_workflow.py; DO NOT EDIT.\n# source-sha256: {digest}\n'.encode() + source


def verify_owned(data):
    lines = data.split(b'\n', 2)
    if len(lines) != 3 or lines[0] != b'# Generated from ai-harness/scripts/check_git_workflow.py; DO NOT EDIT.':
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
    target = root / 'modules/tooling/check_git_workflow.py'
    expected = generated(Path(__file__).with_name('check_git_workflow.py').read_bytes())
    try:
        if not target.resolve().is_relative_to(root):
            raise ValueError('TARGET_OUTSIDE_PROJECT')
        current = target.read_bytes() if target.exists() else None
        if current is not None:
            verify_owned(current)
        if args.check:
            if current != expected:
                raise ValueError('GENERATED_TARGET_STALE')
        elif current != expected:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
        print('PASS ' + str(target))
        return 0
    except (ValueError, OSError) as error:
        print(str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
