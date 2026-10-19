"""Apply explicit path-based skill switches, preserving unrelated TOML settings.

Never modify plugin cache contents. Re-run after a plugin version/path change;
--check audits disk configuration, not the skills actually loaded by a session.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib


def host_path(path):
    path = path.resolve()
    if re.match(r'^/mnt/[a-z]/', str(path)):
        return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip().replace('\\', '/')
    return str(path)


def render_policy(text, policy, skills_root):
    current = tomllib.loads(text)
    disabled = set(policy['disabled'])
    for name in disabled | set(policy['retained_methods']):
        if not (skills_root / name / 'SKILL.md').is_file():
            raise ValueError('plugin skill missing; inspect plugin upgrade before applying: ' + name)
    prefix = host_path(skills_root)
    expected = {prefix + '/' + name + '/SKILL.md' for name in disabled}
    # Remove only the policy-owned switches; preserve comments and unrelated tables.
    pattern = re.compile(r'^\[\[skills\.config\]\][^\n]*\n.*?(?=^\[|\Z)', re.M | re.S)
    def replace(match):
        rows = tomllib.loads(match.group())['skills']['config']
        row = rows[0]
        name = row.get('name', '')
        path = row.get('path', '').replace('\\', '/')
        owned = name in {'superpowers:' + n for n in disabled} or any(
            '/superpowers/' in path and path.endswith('/skills/' + n + '/SKILL.md') for n in disabled)
        owned = owned or path in expected
        return '' if owned else match.group()
    rendered = pattern.sub(replace, text).rstrip() + '\n'
    for path in sorted(expected):
        rendered += '\n[[skills.config]]\npath = ' + json.dumps(path) + '\nenabled = false\n'
    parsed = tomllib.loads(rendered)
    original = dict(current); original.pop('skills', None)
    after = dict(parsed); after.pop('skills', None)
    if original != after:
        raise ValueError('refusing to change unrelated configuration')
    return rendered, expected


def apply_policy(codex_home, skills_root, policy_path, *, check=False):
    policy = json.loads(policy_path.read_text())
    if policy.get('schema_version') != 1 or policy.get('plugin') != 'superpowers':
        raise ValueError('unsupported skill policy')
    lock_path = codex_home / '.ai-harness/codex-sync.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if (codex_home / '.ai-harness/windows-native-transition.hold').exists():
            raise ValueError('WINDOWS_NATIVE_TRANSITION_HOLD')
        config = codex_home / 'config.toml'
        before = config.read_text()
        rendered, expected = render_policy(before, policy, skills_root)
        rows = tomllib.loads(before).get('skills', {}).get('config', [])
        actual = {r.get('path', '').replace('\\', '/') for r in rows if r.get('enabled') is False}
        valid = expected.issubset(actual)
        if check:
            return {'ok': valid, 'configured_on_disk': valid, 'runtime_verified': False,
                    'missing_paths': sorted(expected - actual)}
        if before != rendered:
            temporary = config.with_name('config.toml.skill-policy-writing')
            temporary.write_text(rendered)
            temporary.replace(config)
        receipt = {'schema_version': 1, 'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(),
                   'plugin_skills_root': host_path(skills_root), 'disabled_paths': sorted(expected),
                   'runtime_verified': False}
        target = codex_home / '.ai-harness/skill-policy.receipt.json'
        temporary = target.with_suffix('.writing')
        temporary.write_text(json.dumps(receipt, indent=2) + '\n')
        temporary.replace(target)
        return {'ok': True, 'changed': before != rendered, 'configured_on_disk': True,
                'runtime_verified': False, 'disabled_count': len(expected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, required=True)
    parser.add_argument('--plugin-skills-root', type=Path, required=True)
    parser.add_argument('--policy', type=Path, default=Path(__file__).resolve().parents[1] / 'config/ai/skill-policy.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        result = apply_policy(args.codex_home, args.plugin_skills_root, args.policy, check=args.check)
    except (OSError, ValueError) as exc:
        result = {'ok': False, 'errors': [str(exc)]}
    print(json.dumps(result))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
