#!/usr/bin/env python3
"""Read-only Git facts. Passing this check never grants merge/delete authority."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


class CheckError(Exception):
    pass


def git(root, *args, optional=False):
    result = subprocess.run(['git', '-C', str(root), *args], text=True,
                            capture_output=True, timeout=40,
                            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    if result.returncode and not optional:
        # Remote stderr may contain credential-bearing URLs; never echo it.
        raise CheckError('GIT_COMMAND_FAILED:' + args[0])
    return result.returncode, result.stdout.strip()


def read_policy(root):
    policy = json.loads((root / 'config/ai/git-policy.json').read_text())
    required = {'schema_version', 'remote', 'main_branch', 'task_prefixes',
                'reserved_branches', 'release_tag_pattern', 'merge_method', 'cleanup_mode'}
    if not required <= set(policy) or set(policy) - required - {'production_branch'} or policy['schema_version'] != 1:
        raise ValueError('policy fields/version')
    if policy['merge_method'] != 'merge' or policy['cleanup_mode'] != 'report-only':
        raise ValueError('unsupported merge/cleanup mode')
    if not isinstance(policy['remote'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', policy['remote']):
        raise ValueError('remote must be a configured alias')
    prefixes = policy['task_prefixes']
    reserved = policy['reserved_branches']
    if not isinstance(prefixes, list) or not prefixes or not isinstance(reserved, dict):
        raise ValueError('prefixes/reservations')
    for prefix in prefixes:
        if not isinstance(prefix, str) or not prefix or prefix.startswith('-') or git(root, 'check-ref-format', '--branch', prefix + 'example', optional=True)[0]:
            raise ValueError('task prefix')
    production = policy.get('production_branch')
    if production is not None and (production == policy['main_branch'] or production in reserved):
        raise ValueError('production must have a distinct role')
    for branch in [policy['main_branch'], *([production] if production is not None else []), *reserved]:
        if not isinstance(branch, str) or branch.startswith('-') or git(root, 'check-ref-format', '--branch', branch, optional=True)[0]:
            raise ValueError('branch')
    if any(not isinstance(owner, str) or not owner.strip() for owner in reserved.values()):
        raise ValueError('reserved branch owner')
    if not isinstance(policy['release_tag_pattern'], str) or not policy['release_tag_pattern']:
        raise ValueError('release tag pattern')
    re.compile(policy['release_tag_pattern'])
    return policy


def ancestor(root, older, newer):
    code, _ = git(root, 'merge-base', '--is-ancestor', older, newer, optional=True)
    if code not in (0, 1):
        raise CheckError('ANCESTRY_UNKNOWN')
    return code == 0


def exists(root, ref):
    return git(root, 'show-ref', '--verify', '--quiet', ref, optional=True)[0] == 0


def inspect(root, phase, branch_override='', release_tag='', task_id='', coordinator=''):
    root = root.resolve()
    policy = read_policy(root)
    _, head = git(root, 'rev-parse', '--verify', 'HEAD')
    _, actual_branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', optional=True)
    branch = branch_override if phase == 'ci' and branch_override else actual_branch
    _, dirty = git(root, 'status', '--porcelain=v1', '--untracked-files=normal')
    _, shallow = git(root, 'rev-parse', '--is-shallow-repository')
    main = policy['main_branch']
    production = policy.get('production_branch')
    remote = policy['remote']
    remote_main = f'refs/remotes/{remote}/{main}'
    errors, warnings = [], []
    result = dict(ok=False, phase=phase, branch=branch or None, head=head,
                  dirty=bool(dirty), errors=errors, warnings=warnings,
                  needs_task_branch=branch in (main, production),
                  reserved_owner=policy['reserved_branches'].get(branch),
                  remote_refs_freshness='cached-unverified')
    if branch_override and phase != 'ci':
        errors.append('BRANCH_OVERRIDE_CI_ONLY')
    if not branch and phase not in ('release', 'cleanup'):
        errors.append('DETACHED_HEAD')
    elif branch and branch not in (main, production) and branch not in policy['reserved_branches']:
        valid = any(branch.startswith(prefix) and len(branch) > len(prefix) for prefix in policy['task_prefixes'])
        if not valid and task_id and coordinator and branch == actual_branch and phase != 'ci':
            from task_workspace import legacy_binding_valid
            valid = legacy_binding_valid(root, task_id, coordinator)
            if valid:
                warnings.append('EXISTING_TASK_BRANCH_RETAINED')
        if not valid or branch.startswith('-') or git(root, 'check-ref-format', '--branch', branch, optional=True)[0]:
            errors.append('BRANCH_NAME')
    if result['reserved_owner']:
        warnings.append('RESERVED_OWNER_MUST_BE_VERIFIED')
    if dirty:
        warnings.append('UNCOMMITTED_CHANGES_DO_NOT_ADOPT')
    if branch == main and phase == 'push':
        errors.append('MAIN_DIRECT_PUSH')
    if production and branch == production and phase in ('push', 'merge'):
        errors.append('PRODUCTION_REQUIRES_APPROVED_RELEASE')
    if phase in ('merge', 'release', 'cleanup') and shallow == 'true':
        errors.append('SHALLOW_HISTORY')
    if phase in ('merge', 'release') and dirty:
        errors.append('DIRTY_WORKTREE')
    if phase in ('merge', 'release', 'cleanup') and not exists(root, remote_main):
        errors.append('REMOTE_MAIN_UNKNOWN')
    code, upstream = git(root, 'rev-parse', '--symbolic-full-name', '@{upstream}', optional=True)
    result['upstream'] = dict(configured=not bool(code), ref=upstream if not code else None, ahead=None, behind=None)
    if not code:
        _, counts = git(root, 'rev-list', '--left-right', '--count', 'HEAD...' + upstream)
        ahead, behind = map(int, counts.split())
        result['upstream'].update(ahead=ahead, behind=behind)
    if phase == 'merge' and exists(root, remote_main) and shallow != 'true':
        result['main_is_ancestor'] = ancestor(root, remote_main, head)
        if not result['main_is_ancestor']:
            errors.append('MAIN_NOT_INTEGRATED')
        warnings.append('REVIEW_ACCEPTANCE_AND_LIVE_REMOTE_CHECK_REQUIRED')
    if phase == 'cleanup':
        _, worktrees = git(root, 'worktree', 'list', '--porcelain')
        occupied = {line[7:] for line in worktrees.splitlines() if line.startswith('branch ')}
        _, names = git(root, 'for-each-ref', '--format=%(refname:short)', 'refs/heads/')
        rows = []
        for name in names.splitlines():
            ref = 'refs/heads/' + name
            other = f'refs/remotes/{remote}/{name}'
            reasons = []
            if name == main:
                reasons.append('MAIN')
            if name == production:
                reasons.append('PRODUCTION')
            if name in policy['reserved_branches']:
                reasons.append('RESERVED')
            if ref in occupied:
                reasons.append('WORKTREE_IN_USE')
            if shallow == 'true' or not exists(root, remote_main):
                reasons.append('MERGE_STATUS_UNKNOWN')
            elif not ancestor(root, ref, remote_main):
                reasons.append('NOT_MERGED')
            if not exists(root, other):
                reasons.append('REMOTE_BRANCH_UNKNOWN')
            elif shallow == 'true' or not ancestor(root, ref, other):
                reasons.append('UNPUSHED_COMMITS')
            elif exists(root, remote_main) and not ancestor(root, other, remote_main):
                reasons.append('REMOTE_NOT_MERGED')
            rows.append(dict(branch=name, reasons=reasons, git_candidate=not reasons,
                             delete_authorized=False))
        result['branches'] = rows
        warnings.append('REPORT_ONLY_VERIFY_FRESH_REFS_TASK_USAGE_ACCEPTANCE_AND_AUTHORIZATION')
    if phase == 'release':
        result['remote_verified'] = False
        if not re.fullmatch(policy['release_tag_pattern'], release_tag) or git(root, 'check-ref-format', 'refs/tags/' + release_tag, optional=True)[0]:
            errors.append('RELEASE_TAG_NAME')
        else:
            tagref = 'refs/tags/' + release_tag
            code, target = git(root, 'rev-parse', '--verify', tagref + '^{commit}', optional=True)
            if code or target != head:
                errors.append('TAG_HEAD_MISMATCH')
            _, listing = git(root, 'ls-remote', '--refs', remote, tagref, 'refs/heads/' + main)
            live = {line.split('\t')[1]: line.split('\t')[0] for line in listing.splitlines() if '\t' in line}
            _, local_object = git(root, 'rev-parse', '--verify', tagref, optional=True)
            if tagref not in live:
                errors.append('TAG_NOT_ON_REMOTE')
            elif live[tagref] != local_object:
                errors.append('REMOTE_TAG_MISMATCH')
            if exists(root, remote_main):
                _, cached = git(root, 'rev-parse', remote_main)
                if live.get('refs/heads/' + main) != cached:
                    errors.append('REMOTE_MAIN_STALE')
                elif shallow != 'true' and not ancestor(root, head, remote_main):
                    errors.append('SOURCE_NOT_ON_MAIN')
            result['remote_verified'] = not errors
            result['remote_refs_freshness'] = 'queried-selected-refs'
    result['ok'] = not errors
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--phase', choices=['start', 'push', 'merge', 'release', 'cleanup', 'ci'], required=True)
    parser.add_argument('--branch', default='')
    parser.add_argument('--release-tag', default='')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--coordinator', default='')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        result = inspect(args.repo_root, args.phase, args.branch, args.release_tag, args.task_id, args.coordinator)
        code = 0 if result['ok'] else 1
    except (ValueError, KeyError, TypeError, OSError, re.error) as error:
        result = dict(ok=False, errors=['CONFIG_INVALID'], detail=type(error).__name__)
        code = 2
    except (CheckError, subprocess.TimeoutExpired) as error:
        result = dict(ok=False, errors=['GIT_UNAVAILABLE'], detail=str(error) if isinstance(error, CheckError) else 'TIMEOUT')
        code = 2
    print(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
