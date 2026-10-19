"""Scoped bootstrap step: global instructions and Git checker, never other skills."""
import fcntl
import hashlib
import json
from pathlib import Path

from runtime_common import atomic_write, sha256_file


def publish(root: Path, home: Path):
    state = home / '.ai-harness'
    if (state / 'windows-native-transition.hold').exists():
        raise ValueError('WINDOWS_NATIVE_TRANSITION_HOLD')
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'codex-sync.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if (state / 'windows-native-transition.hold').exists():
            raise ValueError('WINDOWS_NATIVE_TRANSITION_HOLD')
        agents = home / 'AGENTS.md'
        bootstrap = state / 'bootstrap.receipt.json'
        receipt_file = state / 'git-workflow.receipt.json'
        checker = state / 'runtime/git-workflow/check_git_workflow.py'
        template = root / 'templates/codex/AGENTS.global.md'
        source = root / 'scripts/check_git_workflow.py'
        rule = root / 'rules/items/workflow/分支与发布管理.md'
        # All input validation precedes writes to runtime files.
        receipt = json.loads(bootstrap.read_text())
        installed = agents.read_text(encoding='utf-8-sig')
        if not installed.startswith('<!-- ai-harness:managed-global-agents:v1 -->'):
            raise ValueError('AGENTS_UNMANAGED')
        if receipt.get('target_sha256') != sha256_file(agents):
            raise ValueError('AGENTS_RECEIPT_DRIFT')
        if checker.exists():
            if not receipt_file.exists():
                raise ValueError('GIT_RUNTIME_UNMANAGED')
            old_receipt = json.loads(receipt_file.read_text())
            if old_receipt.get('checker_sha256') != sha256_file(checker):
                raise ValueError('GIT_RUNTIME_DRIFT')
        rendered = template.read_text(encoding='utf-8-sig').replace('{{HARNESS_ROOT}}', root.as_posix())
        if not rendered.startswith('<!-- ai-harness:managed-global-agents:v1 -->'):
            raise ValueError('TEMPLATE_UNMANAGED')
        content = source.read_text()
        digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
        updated = {**receipt, 'template_path': str(template), 'template_sha256': sha256_file(template),
                   'target_path': str(agents), 'target_sha256': digest(rendered)}
        own = dict(schema_version=1, harness_root=str(root), checker_path=str(checker),
                   checker_sha256=digest(content), agents_sha256=digest(rendered),
                   rule_path=str(rule), rule_sha256=sha256_file(rule), scope='git-workflow-only')
        targets = {agents: rendered, checker: content,
                   bootstrap: json.dumps(updated, ensure_ascii=False, indent=2) + '\n',
                   receipt_file: json.dumps(own, ensure_ascii=False, indent=2) + '\n'}
        before = {p: p.read_text() if p.exists() else None for p in targets}
        changed = any(before[p] != text for p, text in targets.items())
        if changed:
            backup = state / 'backups' / ('git-workflow-' + sha256_file(agents))
            for path in (agents, bootstrap, receipt_file):
                if path.exists():
                    dest = backup / path.name
                    if not dest.exists():
                        atomic_write(dest, path.read_text())
            try:
                for path, text in targets.items():
                    if before[path] != text:
                        atomic_write(path, text)
                if sha256_file(checker) != own['checker_sha256'] or sha256_file(agents) != own['agents_sha256']:
                    raise ValueError('PUBLICATION_VERIFY_FAILED')
            except BaseException:
                for path, text in before.items():
                    if text is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic_write(path, text)
                raise
        return dict(ok=True, scope='git-workflow-only', runtime_changed=changed,
                    restart_required=before[agents] != rendered, receipt_path=str(receipt_file))
