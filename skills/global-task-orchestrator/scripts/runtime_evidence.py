"""Receipt-bound runtime snapshots and append-only, locally retained run evidence.

This is a production module shared by the controller and benchmark runner.
Manifests inventory evidence; the task state remains the only workflow ledger.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import re
import subprocess
import sys
import time
import uuid
from verification_context import scoped, cached, read_bytes, file_digest, children, operation


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _tree_paths(root):
    if any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir():
        raise ValueError('snapshot source must be a real directory')
    def walk(directory):
        for path in children(directory):
            if path.is_symlink():
                raise ValueError('snapshot must not contain symlinks')
            relative = path.relative_to(root).as_posix()
            if path.name == '__pycache__' or path.suffix in {'.pyc', '.pyo'} or relative == '.snapshot.json':
                continue
            if path.is_dir():
                yield from walk(path)
            elif path.is_file():
                yield relative, path
    return walk(root)


def _contents(root):
    files = {relative: read_bytes(path) for relative, path in _tree_paths(root)}
    if not files:
        raise ValueError('snapshot source is empty')
    return files


@scoped
@cached
def tree_manifest(root):
    files = {relative: file_digest(path) for relative, path in _tree_paths(Path(root))}
    if not files:
        raise ValueError('snapshot source is empty')
    return {'schema_version': 1, 'files': files, 'sha256': digest(files)}


@scoped
def freeze_tree(source, destination):
    source = Path(source)
    manifest = tree_manifest(source)
    destination = Path(destination)
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("snapshot destination must not contain symlinks")
    destination.mkdir(parents=True, exist_ok=False)
    for relative in manifest['files']:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Copy one stream at a time, then independently verify the published
        # bytes against the prepared inventory; never retain the entire tree.
        with (source / relative).open('rb') as reader, target.open('wb') as writer:
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
    (destination / '.snapshot.json').write_text(json.dumps(manifest, indent=2) + '\n')
    verify_tree(destination, manifest)
    return manifest


def verify_tree(root, expected):
    if tree_manifest(root) != expected:
        raise ValueError('runtime snapshot content or inventory changed')
    return expected


def _write_manifest(path, value):
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def retained_file(repo, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or '..' in path.parts or path.parts[0] == '.tmp':
        raise ValueError('evidence must be a retained repository-relative file')
    path = Path(repo) / path
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('evidence file is missing or contains symlinks: ' + str(relative))
    return path


def acceptance_evidence_paths(result):
    paths = set()
    def walk(value):
        if not isinstance(value, dict):
            if isinstance(value, list):
                for child in value: walk(child)
            return
        for key, child in value.items():
            if key == 'run_evidence':
                continue
            if key in {'evidence_refs', 'input_refs', 'trace_refs', 'business_input_refs'} and isinstance(child, list):
                paths.update(p for p in child if isinstance(p, str))
            elif key == 'evidence_by_acceptance_id' and isinstance(child, dict):
                for refs in child.values(): paths.update(refs)
            elif key == 'report_ref' and isinstance(child, str):
                paths.add(child)
            elif key == 'review_evidence' and isinstance(child, dict):
                paths.update(v for v in child.values() if isinstance(v, str))
            elif key == 'preparation' and isinstance(child, dict):
                for refs in child.get('checks', {}).values(): paths.update(refs)
                walk(child)
            else:
                walk(child)
    walk(result.get('expensive_acceptance', {}))
    walk({'review_evidence': result.get('review_evidence', {})})
    return sorted(paths)


def execution_times(manifest, *, allow_legacy_clock_reversal=False):
    """Validate the explicit evidence protocol; monotonic duration is run-local."""
    version = manifest.get('schema_version')
    if type(version) is not int or version not in {1, 2, 3}:
        raise ValueError('unsupported execution time protocol')
    started, finished = (datetime.fromisoformat(manifest[key]) for key in ('started_at', 'finished_at'))
    if started.tzinfo is None or finished.tzinfo is None:
        raise ValueError('execution time requires a timezone')
    if version == 3:
        from causal_history import validate_start
        elapsed = manifest.get('elapsed_ns')
        if type(elapsed) is not int or elapsed < 0 or 'completed_before' in manifest:
            raise ValueError('invalid execution time/causal evidence')
        validate_start(manifest.get('causal_start'), manifest.get('binding', {}).get('task_id'))
    elif version == 2:
        elapsed, before = manifest.get('elapsed_ns'), manifest.get('completed_before')
        if (type(elapsed) is not int or elapsed < 0 or not isinstance(before, list)
                or any(not isinstance(h, str) or not re.fullmatch('[0-9a-f]{64}', h) for h in before)
                or len(before) != len(set(before)) or 'causal_start' in manifest):
            raise ValueError('invalid execution time/causal evidence')
    elif ('elapsed_ns' in manifest or 'completed_before' in manifest or 'causal_start' in manifest
          or (finished < started and not allow_legacy_clock_reversal)):
        raise ValueError('original execution chronology is invalid')
    return started, finished


def _import_registered_runs(repo, state):
    """Import exact registered legacy sources; never discover unregistered history."""
    from causal_history import publish_completed
    seen = set()
    for attempt in state.get('acceptance_gate', {}).get('attempts', []):
        ref = attempt.get('run_evidence')
        if not isinstance(ref, dict) or ref.get('sha256') in seen:
            continue
        path = retained_file(repo, ref['path'])
        raw = path.read_bytes()
        if digest(raw) != ref['sha256']:
            raise ValueError('registered causal manifest hash changed')
        manifest = json.loads(raw)
        execution_times(manifest, allow_legacy_clock_reversal=True)
        if manifest['schema_version'] in {1, 2}:
            publish_completed(repo, state['task_id'], path)
        seen.add(ref['sha256'])


def run_command(retained_root, command, *, cwd, binding, timeout=None, evidence_paths=(), finalizer=None,
                metrics=None):
    monotonic_start = time.monotonic_ns()
    metrics = metrics if metrics is not None else {}
    retained_root = Path(retained_root)
    if any(p.is_symlink() for p in (retained_root, *retained_root.parents)):
        raise ValueError('retained run path must not contain symlinks')
    if '.artifacts' not in retained_root.parts:
        raise ValueError('retained runs must be inside .artifacts')
    if not command or not all(isinstance(arg, str) for arg in command):
        raise ValueError('command must be a nonempty argv list, without secrets')
    run = retained_root / ('run-' + uuid.uuid4().hex)
    run.mkdir(parents=True, exist_ok=False)
    from causal_history import capture_start, publish_completed
    task_id = binding.get('task_id')
    capturing = time.monotonic_ns()
    before = capture_start(cwd, task_id) if task_id is not None else {
        'task_id': None, 'sequence': 0, 'head': None}
    metrics['capture_ns'] = time.monotonic_ns() - capturing
    manifest = {'schema_version': 3, 'binding': binding, 'command': command,
                'causal_start': before,
                'cwd': str(Path(cwd).resolve()), 'status': 'running', 'exit_code': None,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'environment': {'host': platform.node(), 'platform': platform.platform(),
                                'python': sys.version, 'interpreter': sys.executable}}
    _write_manifest(run / 'manifest.json', manifest)
    process = None
    try:
        with (run / 'stdout.log').open('wb') as stdout, (run / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                manifest['exit_code'] = process.wait(timeout=timeout)
                manifest['status'] = 'passed' if process.returncode == 0 else 'failed'
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                finally:
                    # A terminated leader does not prove its descendants exited.
                    # Always finish cleaning our process group before sealing logs.
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                manifest['exit_code'] = process.returncode
                manifest['status'] = 'interrupted'
    except OSError as exc:
        manifest['status'] = 'failed'
        manifest['error'] = str(exc)
    finally:
        manifest['evidence_files'] = {}
        for relative in evidence_paths:
            try:
                manifest['evidence_files'][relative] = file_digest(retained_file(cwd, relative))
            except (ValueError, OSError) as exc:
                manifest['status'] = 'failed'
                manifest['error'] = str(exc)
        if finalizer is not None:
            try:
                finalizer(manifest)
            except Exception as exc:
                manifest['status'] = 'invalidated'
                manifest['error'] = 'run finalization failed: ' + str(exc)
        manifest['files'] = {name: file_digest(run / name)
                             for name in ('stdout.log', 'stderr.log') if (run / name).is_file()}
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        manifest['elapsed_ns'] = time.monotonic_ns() - monotonic_start
        publishing = time.monotonic_ns()
        _write_manifest(run / 'manifest.json', manifest)
        if task_id is not None:
            publish_completed(cwd, task_id, run / 'manifest.json')
        metrics['publication_ns'] = time.monotonic_ns() - publishing
        metrics['run_total_ns'] = time.monotonic_ns() - monotonic_start
    return run


@scoped
def verify_run(run, binding, *, repo=None):
    run = Path(run)
    if any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('run evidence path must not contain symlinks')
    manifest = json.loads(read_bytes(run / 'manifest.json'))
    if manifest.get('binding') != binding:
        raise ValueError('run binding does not match candidate/runtime')
    if manifest.get('status') not in {'passed', 'failed', 'interrupted', 'invalidated'}:
        raise ValueError('run is incomplete; retain and investigate before cleanup')
    execution_times(manifest)
    if set(manifest.get('files', {})) != {'stdout.log', 'stderr.log'}:
        raise ValueError('run evidence inventory is incomplete')
    for name, expected in manifest['files'].items():
        path = run / name
        if path.is_symlink() or not path.is_file() or file_digest(path) != expected:
            raise ValueError('run evidence hash mismatch: ' + name)
    for relative, expected in manifest.get('evidence_files', {}).items():
        path = retained_file(repo or Path(manifest['cwd']), relative)
        if file_digest(path) != expected:
            raise ValueError('business evidence hash mismatch: ' + relative)
    return manifest



def acceptance_binding(state, subtask_id):
    candidate = state['acceptance_gate']['current_candidate']
    task = next(t for t in state['subtasks'] if t['subtask_id'] == subtask_id)
    attempt = next(a for a in state['acceptance_gate']['attempts'] if a['subtask_id'] == subtask_id)
    if task['stage'] != 'expensive_acceptance' or not task.get('dispatch'):
        raise ValueError('run requires a bound acceptance attempt')
    return {'task_id': state['task_id'], 'candidate_id': candidate['candidate_id'],
            'runtime_sha256': candidate['runtime_snapshot']['sha256'],
            'candidate_fingerprint': candidate['fingerprint'], 'attempt_id': attempt['attempt_id'],
            'subtask_id': subtask_id, 'written_by': task['dispatch']['platform_agent_id']}


@scoped
def acceptance_run_errors(repo, state, subtask, result):
    try:
        acceptance = result.get('expensive_acceptance', {})
        reference = acceptance.get('run_evidence')
        if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
            raise ValueError('acceptance requires run_evidence path/sha256')
        relative = Path(reference['path'])
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != '.artifacts' or relative.name != 'manifest.json':
            raise ValueError('run manifest must be retained inside repository .artifacts')
        path = repo / relative
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('run manifest path must not contain symlinks')
        if digest(read_bytes(path)) != reference['sha256']:
            raise ValueError('run manifest hash mismatch')
        binding_subtask = subtask['subtask_id']
        preparation_id = acceptance.get('source_preparation_attempt_id')
        if preparation_id:
            source = next(a for a in state['acceptance_gate']['attempts'] if a['attempt_id'] == preparation_id)
            target = next(a for a in state['acceptance_gate']['attempts'] if a['subtask_id'] == subtask['subtask_id'])
            source_task = next(t for t in state['subtasks'] if t['subtask_id'] == source['subtask_id'])
            if (source.get('kind') != 'preparation' or source.get('outcome') != 'pass'
                    or source_task.get('status') != 'completed'
                    or source['candidate_id'] != target['candidate_id']
                    or source['runtime_sha256'] != target['runtime_sha256']
                    or source_task['dispatch']['platform_agent_id'] != subtask['dispatch']['platform_agent_id']
                    or source.get('run_evidence') != reference or acceptance.get('real_call_count') != 0):
                raise ValueError('formal observation adoption requires the original completed preparation and executor')
            for row in acceptance.get('point_results', []):
                for ref in row['evidence_refs']:
                    observation = json.loads(read_bytes(retained_file(repo, ref)))
                    if (not isinstance(observation, dict)
                            or not {'acceptance_id', 'status', 'input', 'actual', 'expected'} <= set(observation)
                            or observation['acceptance_id'] != row['acceptance_id']
                            or observation['status'] != row['status']):
                        raise ValueError('preparation output is not a formal point observation')
            if not acceptance.get('point_results'):
                raise ValueError('formal preparation adoption requires point observations')
            binding_subtask = source['subtask_id']
        manifest = verify_run(path.parent, acceptance_binding(state, binding_subtask), repo=repo)
        native_outputs = {(path.parent / name).relative_to(repo).as_posix() for name in manifest['files']}
        covered = set(manifest.get('evidence_files', {})) | native_outputs
        missing = set(acceptance_evidence_paths(result)) - covered
        if missing:
            raise ValueError('run manifest does not cover business evidence: ' + ', '.join(sorted(missing)))
        if manifest['status'] == 'invalidated' and acceptance.get('outcome') in {'pass', 'partial_pass'}:
            raise ValueError('run candidate/runtime changed during execution')
        if acceptance.get('outcome') in {'pass', 'partial_pass'} and (manifest['status'] != 'passed' or manifest.get('exit_code') != 0):
            raise ValueError('acceptance pass requires a passed run')
        return []
    except (ValueError, OSError, KeyError, TypeError, IndexError, StopIteration) as exc:
        return ['acceptance run evidence: ' + str(exc)]


def copy_installed_gto(host_codex, isolated_codex):
    """Snapshot receipt-bound installed tools, never rebuild them from a source checkout."""
    receipt_relative = '.ai-harness/codex-sync.receipt.json'
    receipt_path = host_codex / receipt_relative
    if receipt_path.is_symlink():
        raise RuntimeError('installation receipt must not be a symlink')
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    legacy_relative = 'schemas/orchestrator-task-state.schema.json'
    legacy = host_codex / legacy_relative
    if legacy.exists() or legacy.is_symlink() or any(
            item.get('source') == legacy_relative or item.get('target') == legacy_relative
            for item in receipt.get('managed_schema_files', [])):
        raise RuntimeError('legacy GTO root schema must be retired before copying the installed runtime')
    expected = {}
    skills = receipt.get('managed_skills', [])
    if 'global-task-orchestrator' not in skills:
        raise RuntimeError('installation receipt lacks global-task-orchestrator')
    for item in receipt.get('managed_files', []):
        if item.get('skill') not in skills:
            raise RuntimeError('receipt contains an unlisted managed skill')
        relative = 'skills/' + item['target']
        if not relative.startswith('skills/' + item['skill'] + '/'):
            raise RuntimeError('receipt target is outside its installed skill scope')
        expected[relative] = item['sha256']
    for item in receipt.get('managed_schema_files', []):
        relative = item['target']
        if not relative.startswith('schemas/'):
            raise RuntimeError('receipt schema target is outside installed schema scope')
        expected[relative] = item['sha256']
    required = {'skills/global-task-orchestrator/SKILL.md',
                'skills/global-task-orchestrator/scripts/orchestrator_ctl.py',
                'skills/global-task-orchestrator/scripts/start_session.py',
                'skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json'}
    if not required.issubset(expected):
        raise RuntimeError('installed GTO receipt is incomplete')
    contents = {}
    for name in skills:
        if not name or '/' in name or name in {'.', '..'}:
            raise RuntimeError('unsafe receipt skill scope')
        root = host_codex / 'skills' / name
        if root.is_symlink():
            raise RuntimeError('installed skill root must not be a symlink')
        for path in root.rglob('*'):
            if path.is_symlink():
                raise RuntimeError('installed skill contains a symlink outside receipt scope')
            if path.is_file() and path.relative_to(host_codex).as_posix() not in expected:
                if '__pycache__' not in path.parts and path.suffix != '.pyc':
                    raise RuntimeError('installed skill has unlisted receipt content')
    for relative, digest in expected.items():
        path = host_codex / relative
        if '..' in Path(relative).parts or path.is_symlink() or not path.resolve().is_relative_to(host_codex.resolve()):
            raise RuntimeError('installed receipt path is outside its scope or a symlink')
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise RuntimeError('installed file hash disagrees with receipt: ' + relative)
        contents[relative] = content
    contents[receipt_relative] = receipt_bytes
    # Validate the entire snapshot before writing, so a rejected source leaves no partial runtime.
    for relative, content in contents.items():
        target = isolated_codex / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return {'source_hashes': {p: hashlib.sha256(b).hexdigest() for p, b in contents.items()}}


def main():
    cli_started = time.monotonic_ns()
    metrics = {}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('freeze', 'run', 'verify'), required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--repo-root', type=Path)
    parser.add_argument('--task-id')
    parser.add_argument('--subtask-id')
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--timeout', type=float)
    parser.add_argument('--profile', action='store_true', help='Include diagnostic timing, outside evidence.')
    parser.add_argument('--evidence-path', action='append', default=[])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == 'freeze':
            if args.source is None or args.destination is None:
                raise ValueError('freeze requires source and destination')
            result = {'ok': True, 'snapshot': freeze_tree(args.source, args.destination)}
        else:
            if args.repo_root is None or not args.task_id:
                raise ValueError('run/verify require repo-root and task-id')
            import orchestrator_ctl as ctl
            repo = args.repo_root.resolve()
            paths = ctl._task_paths(repo, args.task_id)
            state = ctl._load_state(paths)
            errors = ctl._validate_state(paths, state)
            candidate = state.get('acceptance_gate', {}).get('current_candidate')
            if errors or not candidate:
                raise ValueError('; '.join(errors) or 'freeze a candidate before running acceptance')
            if not args.subtask_id:
                raise ValueError('run/verify require subtask-id of the bound acceptance attempt')
            subtask = ctl._find_subtask(state, args.subtask_id)
            errors = ctl._capability_errors(repo, state, subtask)
            if errors:
                raise ValueError('; '.join(errors))
            binding = acceptance_binding(state, args.subtask_id)
            if args.action == 'run':
                if subtask.get('status') != 'in_progress':
                    raise ValueError('run requires an active bound acceptance attempt')
                frozen_root = (repo / candidate['runtime_snapshot']['path']).resolve()
                if Path(__file__).resolve().parents[1] != frozen_root:
                    raise ValueError('invoke runtime_evidence.py from the frozen runtime snapshot')
            if args.action == 'verify':
                if args.run_dir is None:
                    raise ValueError('verify requires run-dir')
                manifest = verify_run(args.run_dir, binding)
                result = {'ok': True, 'status': manifest['status'], 'exit_code': manifest['exit_code']}
            else:
                command = args.command[1:] if args.command[:1] == ['--'] else args.command
                _import_registered_runs(repo, state)
                def finalize(manifest):
                    drift = ctl._candidate_staleness_errors(repo, state)
                    if drift:
                        manifest['status'] = 'invalidated'
                        manifest['invalidated_by'] = drift
                run = run_command(repo / '.artifacts/gto' / args.task_id / 'runs', command,
                                  cwd=repo, binding=binding, timeout=args.timeout,
                                  evidence_paths=args.evidence_path, finalizer=finalize, metrics=metrics)
                manifest = verify_run(run, binding)
                result = {'ok': manifest['status'] == 'passed', 'run_dir': str(run),
                          'status': manifest['status'], 'exit_code': manifest['exit_code']}
    except Exception as exc:
        result = {'ok': False, 'errors': [str(exc)]}
    if args.profile:
        metrics['cli_total_ns'] = time.monotonic_ns() - cli_started
        result['performance'] = metrics
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
