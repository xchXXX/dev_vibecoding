"""Per-point acceptance projections over the existing append-only attempts.

No command execution, persistent cache, or separate ledger lives here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import re

from runtime_evidence import digest, retained_file, execution_times


def overlap(a, b):
    return a == b or a.startswith(b.rstrip('/') + '/') or b.startswith(a.rstrip('/') + '/')


def definitions(gate):
    items = {p['acceptance_id']: p for p in gate['acceptance_items']}
    if len(items) != len(gate['acceptance_items']):
        raise ValueError('acceptance point IDs must be unique')
    def visit(ident, stack):
        if ident not in items or ident in stack:
            raise ValueError('acceptance depends_on is unknown or cyclic: ' + ident)
        result = {ident}
        for dep in items[ident].get('depends_on', []):
            result.update(visit(dep, stack | {ident}))
        return result
    return items, {ident: visit(ident, set()) for ident in items}


def snapshots(gate, records):
    items, dependencies = definitions(gate)
    fallback = [p for k in ('code_paths', 'config_paths', 'runtime_input_paths')
                for p in gate.get('candidate_inputs', {}).get(k, [])]
    result = {}
    for ident, closure in dependencies.items():
        paths = sorted({p for dep in closure for p in items[dep].get('paths', fallback)})
        # Capabilities describe execution prerequisites, not the validity of an
        # already completed observation. Changing tool availability never erases it.
        contract = {dep: {k: v for k, v in items[dep].items() if k != 'capabilities'}
                    for dep in sorted(closure)}
        result[ident] = {'definition_sha256': digest(contract), 'paths': paths,
                         'records': {p: h for p, h in records.items()
                                     if any(overlap(p, scope) for scope in paths)}}
    return result


def safe_file(repo, relative):
    if not isinstance(relative, str) or re.match(r'^[A-Za-z]:', relative) or '\\' in relative:
        raise ValueError('point evidence requires a safe relative path')
    return retained_file(repo, relative)


def normalize(gate, attempt, evidence, findings):
    required = {p['acceptance_id'] for p in gate['acceptance_items']}
    scope = evidence.get('scope_acceptance_ids', attempt.get('scope_acceptance_ids', []))
    if not isinstance(scope, list) or not scope or len(scope) != len(set(scope)) or not set(scope) <= required:
        raise ValueError('point results require a valid nonempty execution scope')
    arranged = attempt.get('scope_acceptance_ids', scope)
    if not set(scope) <= set(arranged):
        raise ValueError('point results exceed the arranged scope')
    rows = evidence.get('point_results')
    mapping = evidence.get('evidence_by_acceptance_id', {})
    if set(mapping) - set(scope) or evidence.get('retained_evidence_by_acceptance_id'):
        raise ValueError('record only actual scope; valid historical results are retained automatically')
    if rows is None:
        # Existing result writers may still submit actual passing mappings.
        # Retained mappings are references, never new executions.
        failed = {p for f in findings.values() if f.get('finding_id') == evidence.get('finding_id')
                  for p in f.get('acceptance_ids', [])}
        rows = [{'acceptance_id': ident,
                 'status': 'pass' if ident in mapping else 'fail' if ident in failed else 'not_run',
                 'evidence_refs': mapping.get(ident, evidence.get('evidence_refs', []) if ident in failed else [])}
                for ident in scope]
    if not isinstance(rows, list):
        raise ValueError('point_results must be a list')
    by_id = {}
    for row in rows:
        ident = row.get('acceptance_id')
        status = row.get('status')
        if ident in by_id or ident not in scope or status not in {'pass', 'fail', 'not_run', 'blocked'}:
            raise ValueError('point result ID/status is invalid or duplicated')
        refs = row.get('evidence_refs')
        if not isinstance(refs, list) or (status in {'pass', 'fail'} and not refs):
            raise ValueError('executed point requires original evidence')
        if status in {'not_run', 'blocked'} and refs:
            raise ValueError('unexecuted point cannot claim execution evidence')
        if not set(refs) <= set(evidence.get('evidence_refs', [])):
            raise ValueError('point evidence must be registered by the actual run')
        by_id[ident] = deepcopy(row)
    for ident in arranged:
        by_id.setdefault(ident, {'acceptance_id': ident, 'status': 'not_run', 'evidence_refs': [],
                                 'reason': 'No observation was submitted for this arranged point.'})
    passed = {i: r['evidence_refs'] for i, r in by_id.items() if r['status'] == 'pass'}
    actual_mapping = {i: refs for i, refs in mapping.items() if i in scope}
    if actual_mapping != passed:
        raise ValueError('passing mapping must exactly match actual passing point results')
    if any(r['status'] == 'fail' for r in by_id.values()) and evidence['outcome'] in {'pass', 'partial_pass'}:
        raise ValueError('failed point cannot be hidden by a passing attempt outcome')
    if evidence['outcome'] == 'pass' and any(r['status'] != 'pass' for r in by_id.values()):
        raise ValueError('passing attempt contains unexecuted or blocked points')
    evidence['point_results'] = list(by_id.values())
    evidence['evidence_by_acceptance_id'] = passed
    evidence['passed_acceptance_ids'] = sorted(passed)
    evidence['scope_acceptance_ids'] = list(arranged)


def seal(repo, attempt, evidence):
    attempt['point_evidence_hashes'] = {
        ref: digest(safe_file(repo, ref).read_bytes())
        for row in evidence['point_results'] for ref in row['evidence_refs']}


def run_manifest(repo, state, attempt, *, allow_legacy_clock_reversal=False):
    """Verify the shared execution envelope, without consuming unrelated files."""
    source = next(t for t in state['subtasks'] if t['subtask_id'] == attempt['subtask_id'])
    if source.get('status') not in {'completed', 'blocked'}:
        raise ValueError('source attempt is not honestly terminal')
    evidence_attempt = attempt
    if attempt.get('source_preparation_attempt_id'):
        evidence_attempt = next(a for a in state['acceptance_gate']['attempts']
                                if a['attempt_id'] == attempt['source_preparation_attempt_id'])
        source = next(t for t in state['subtasks'] if t['subtask_id'] == evidence_attempt['subtask_id'])
        if evidence_attempt.get('kind') != 'preparation' or evidence_attempt.get('outcome') != 'pass':
            raise ValueError('formal observation preparation source is invalid')
    reference = attempt.get('run_evidence', {})
    raw = safe_file(repo, reference['path']).read_bytes()
    if digest(raw) != reference['sha256']:
        raise ValueError('run manifest hash changed')
    manifest = json.loads(raw)
    expected = {'task_id': state['task_id'], 'candidate_id': evidence_attempt['candidate_id'],
                'runtime_sha256': evidence_attempt['runtime_sha256'], 'attempt_id': evidence_attempt['attempt_id'],
                'subtask_id': evidence_attempt['subtask_id'], 'written_by': source['dispatch']['platform_agent_id'],
                'candidate_fingerprint': digest({'records': evidence_attempt['coverage_snapshot'],
                    'inputs': evidence_attempt['coverage_inputs_sha256'], 'runtime_sha256': evidence_attempt['runtime_sha256']})}
    if manifest.get('binding') != expected or manifest.get('status') not in {'passed', 'failed', 'interrupted'}:
        raise ValueError('run source binding is invalid or execution is incomplete')
    if set(manifest.get('files', {})) != {'stdout.log', 'stderr.log'}:
        raise ValueError('run output inventory is incomplete')
    parent = reference['path'].rsplit('/', 1)[0]
    native = {parent + '/' + name: h for name, h in manifest['files'].items()}
    for ref, h in native.items():
        if digest(safe_file(repo, ref).read_bytes()) != h:
            raise ValueError('run output hash changed')
    execution_times(manifest, allow_legacy_clock_reversal=allow_legacy_clock_reversal)
    return manifest


def observed_after(repo, state, attempt, other):
    current = run_manifest(repo, state, attempt)
    previous = run_manifest(repo, state, other, allow_legacy_clock_reversal=True)
    if attempt['run_evidence']['sha256'] == other['run_evidence']['sha256']:
        return False
    if current['schema_version'] == 2:
        return other['run_evidence']['sha256'] in current['completed_before']
    if previous['schema_version'] == 1:
        execution_times(previous)  # Legacy reversal cannot prove legacy order.
        return datetime.fromisoformat(previous['finished_at']) < datetime.fromisoformat(current['finished_at'])
    return False


def failed_point(attempt, ident):
    if attempt.get('withdrawal') or attempt.get('kind') == 'preparation':
        return False
    rows = attempt.get('point_results')
    if rows is not None:
        return any(row['acceptance_id'] == ident and row['status'] == 'fail' for row in rows)
    return (attempt.get('outcome') in {'product_failure', 'effect_failure'}
            and ident in attempt.get('scope_acceptance_ids', []))


def failure_barrier(repo, state, attempt, ident, *, verified_batch_unit=False):
    for other in state['acceptance_gate'].get('attempts', []):
        if verified_batch_unit and other['attempt_id'] == attempt['attempt_id']:
            continue  # A proved PASS unit survives its own aggregate failure.
        if failed_point(other, ident):
            try:
                if observed_after(repo, state, attempt, other):
                    continue
            except (ValueError, OSError, KeyError, TypeError, StopIteration):
                pass  # Unverifiable failure must not reveal a historical pass.
            return True
    return False


def verify_observation(repo, state, attempt, row):
    source = next(t for t in state['subtasks'] if t['subtask_id'] == attempt['subtask_id'])
    if source.get('result', {}).get('expensive_acceptance', {}).get('point_results') != attempt.get('point_results'):
        raise ValueError('source point results do not match the terminal receipt')
    manifest = run_manifest(repo, state, attempt)
    parent = attempt['run_evidence']['path'].rsplit('/', 1)[0]
    native = {parent + '/' + name: h for name, h in manifest['files'].items()}
    covered = {**manifest.get('evidence_files', {}), **native}
    if not row['evidence_refs']:
        raise ValueError('executed point has no evidence')
    for ref in row['evidence_refs']:
        h = digest(safe_file(repo, ref).read_bytes())
        if h != attempt.get('point_evidence_hashes', {}).get(ref) or h != covered.get(ref):
            raise ValueError('point evidence hash changed or is absent from original run')


def coverage(repo, state, records):
    gate = state['acceptance_gate']
    current = snapshots(gate, records)
    ordered = list(reversed(gate.get('attempts', [])))
    points = {}
    for ident, snapshot in current.items():
        fallback = {'status': 'missing', 'reason': 'No completed observation.'}
        for attempt in ordered:
            if attempt.get('withdrawal') or attempt.get('kind') == 'preparation':
                continue
            row = next((p for p in attempt.get('point_results', []) if p['acceptance_id'] == ident), None)
            if row is None:
                continue
            item = {'status': row['status'], 'source_attempt_id': attempt['attempt_id'],
                    'reason': row.get('reason', '')}
            if row['status'] in {'not_run', 'blocked'}:
                if fallback['status'] == 'missing':
                    fallback = item
                continue
            try:
                verify_observation(repo, state, attempt, row)
                if row['status'] == 'pass' and failure_barrier(repo, state, attempt, ident):
                    item.update(status='invalid', invalidation_kind='later_failure',
                                reason='A later actual failure blocks this original observation.')
                elif (row['status'] == 'pass' and attempt.get('point_snapshots', {}).get(ident) != snapshot
                      and not impact_applies(repo, gate, attempt, ident, snapshot)):
                    item.update(status='invalid', invalidation_kind='inputs_changed',
                                reason='Related logic, input, dependency or point definition changed.')
            except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
                item.update(status='invalid', reason=str(exc), invalidation_kind='evidence_invalid')
            if row['status'] == 'fail':
                # Keep searching: a causally later pass may be registered earlier.
                fallback = item
                continue
            if item['status'] == 'pass':
                fallback = item
                break
            if fallback['status'] in {'missing', 'not_run', 'blocked'}:
                fallback = item
        points[ident] = fallback
    from acceptance_batches import point_coverage
    for ident in current:
        receipt = point_coverage(repo, state, ident, lambda _repo, _state: records)
        if receipt and points[ident]['status'] != 'pass':
            if receipt['status'] == 'pass' or points[ident]['status'] in {'missing', 'not_run', 'blocked'}:
                points[ident] = receipt
    items, closures = definitions(gate)
    for ident, deps in closures.items():
        failed = sorted(dep for dep in deps - {ident} if points[dep]['status'] != 'pass')
        if points[ident]['status'] == 'pass' and failed:
            points[ident] = {**points[ident], 'status': 'invalid', 'invalidation_kind': 'dependency_not_passing',
                             'reason': 'Dependency is not passing: ' + ', '.join(failed)}
    rerun = sorted(i for i, item in points.items() if item['status'] != 'pass')
    return {'ok': True, 'complete': not rerun and all(f.get('status') == 'closed' for f in state.get('findings', {}).values()),
            'points': points, 'rerun_acceptance_ids': rerun,
            'evidence_warnings': evidence_warnings(repo, state, records)}


def evidence_warnings(repo, state, records):
    """Historical retention diagnostics never rewrite receipts or launch checks."""
    warnings = []
    for attempt in state['acceptance_gate'].get('attempts', []):
        if 'outcome' not in attempt:
            continue
        try:
            manifest = run_manifest(repo, state, attempt)
            started, finished = execution_times(manifest)
            if finished < started:
                warnings.append({'source_attempt_id': attempt['attempt_id'],
                                 'reason': 'UTC clock reversed; original times retained, causal evidence used.'})
            for ref, expected in manifest.get('evidence_files', {}).items():
                try:
                    if digest(safe_file(repo, ref).read_bytes()) != expected:
                        raise ValueError('historical evidence hash changed')
                except (ValueError, OSError) as exc:
                    warnings.append({'source_attempt_id': attempt['attempt_id'], 'path': ref, 'reason': str(exc)})
        except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
            warnings.append({'source_attempt_id': attempt['attempt_id'], 'reason': str(exc)})
    from acceptance_batches import validate_all_batches
    warnings.extend({'reason': reason} for reason in validate_all_batches(repo, state, lambda _r, _s: records))
    return warnings


def impact_applies(repo, gate, attempt, ident, snapshot):
    for receipt in gate.get('impact_receipts', []):
        if (receipt['source_attempt_id'] == attempt['attempt_id']
                and receipt['point_snapshots'].get(ident) == snapshot
                and receipt['source_snapshots'].get(ident) == attempt.get('point_snapshots', {}).get(ident)):
            try:
                if all(digest(safe_file(repo, ref).read_bytes()) == h
                       for ref, h in receipt['evidence_hashes'].items()):
                    return True
            except (ValueError, OSError):
                pass
    return False


def record_impact(repo, state, payload, records):
    fields = {'written_by', 'written_role', 'source_attempt_id', 'point_ids',
              'changed_paths', 'reason', 'evidence_refs'}
    if not isinstance(payload, dict) or set(payload) != fields or not str(payload['reason']).strip():
        raise ValueError('impact judgment fields are invalid')
    gate = state['acceptance_gate']
    source = next(a for a in gate['attempts'] if a['attempt_id'] == payload['source_attempt_id'])
    task = next(t for t in state['subtasks'] if t['subtask_id'] == source['subtask_id'])
    identity = task['dispatch']
    authors = [identity] + [f.get('discovered_by', {}) for f in state.get('findings', {}).values()
                           if set(f.get('acceptance_ids', [])) & set(payload['point_ids'])]
    if not any(payload['written_by'] == author.get('platform_agent_id')
               and payload['written_role'] == author.get('agent_key') for author in authors):
        raise ValueError('impact judgment requires the original acceptance identity')
    before = source['coverage_snapshot']
    delta = sorted(p for p in set(before) | set(records) if before.get(p) != records.get(p))
    if sorted(payload['changed_paths']) != delta:
        raise ValueError('impact judgment must bind the complete actual changed paths')
    ids = payload['point_ids']
    current = snapshots(gate, records)
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or not set(ids) <= set(current):
        raise ValueError('impact judgment requires valid point IDs')
    for ident in ids:
        row = next(p for p in source.get('point_results', []) if p['acceptance_id'] == ident)
        if row['status'] != 'pass':
            raise ValueError('impact judgment cannot convert a failure into a pass')
        verify_observation(repo, state, source, row)
        if source['point_snapshots'][ident]['definition_sha256'] != current[ident]['definition_sha256']:
            raise ValueError('changed acceptance criteria require new execution')
    if not payload['evidence_refs']:
        raise ValueError('impact judgment requires evidence')
    receipt = {**deepcopy(payload), 'source_snapshots': {i: source['point_snapshots'][i] for i in ids},
               'point_snapshots': {i: current[i] for i in ids},
               'evidence_hashes': {p: digest(safe_file(repo, p).read_bytes()) for p in payload['evidence_refs']}}
    gate.setdefault('impact_receipts', []).append(receipt)
    return receipt
