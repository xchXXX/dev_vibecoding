"""Consume actual probe evidence without launching tools during preflight."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys

from runtime_evidence import digest


def _file(repo, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('capability path must be repository relative')
    target = repo / path
    if any(p.is_symlink() for p in (target, *target.parents) if p != repo.parent) or not target.resolve().is_relative_to(repo.resolve()) or not target.is_file():
        raise ValueError('capability binding/evidence file is missing or outside repository')
    return target


def _context(repo, declaration):
    session = os.environ.get('GTO_SESSION_ID', '')
    if not session.strip():
        raise ValueError('capability requires GTO_SESSION_ID from the actual host/tool session')
    return {'host': platform.node(), 'session_id': session,
            'interpreter': str(Path(sys.executable).resolve()), 'python': sys.version,
            'tool': declaration['tool'],
            'dependencies': {p: digest(_file(repo, p).read_bytes())
                             for p in declaration['binding_paths']}}


def capture_context(repo, declaration, executor_id=None):
    context = _context(repo, declaration)
    if executor_id:
        context['executor_id'] = executor_id
    return {'context': context, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'declaration_sha256': digest(declaration)}


def _proof(repo, declaration, reference, context):
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
        raise ValueError('capability evidence must be a path/sha256 file reference')
    if not reference['path'].startswith('.artifacts/'):
        raise ValueError('capability evidence must be retained in .artifacts')
    raw = _file(repo, reference['path']).read_bytes()
    if digest(raw) != reference['sha256']:
        raise ValueError('capability evidence hash changed')
    proof = json.loads(raw)
    if not isinstance(proof, dict) or any(proof.get(k) != v for k, v in {
        'tool': declaration['tool'], 'probe': declaration['probe'], 'session_id': context['session_id']}.items()):
        raise ValueError('capability proof tool/probe/session binding mismatch')
    if proof.get('status') not in {'passed', 'failed'} or not all(
        isinstance(proof.get(k), str) and proof[k].strip() for k in ('operation', 'observed')):
        raise ValueError('capability proof requires actual operation, observation and outcome')
    if proof.get('context') != context or proof.get('declaration_sha256') != digest(declaration):
        raise ValueError('probe capture-time environment/declaration binding mismatch')
    observed = datetime.fromisoformat(proof['observed_at'])
    age = (datetime.now(timezone.utc) - observed).total_seconds()
    if age < 0 or age > declaration['max_age_seconds']:
        raise ValueError('probe evidence expired')
    return proof


def capability_receipt(repo, task, payload):
    if not isinstance(payload, dict):
        raise ValueError('capability receipt payload must be an object')
    declarations = task.get('assignment', {}).get('required_capabilities', [])
    declaration = next((d for d in declarations if d['capability_id'] == payload.get('capability_id')), None)
    if declaration is None:
        raise ValueError('capability is not declared in the approved assignment')
    context = _context(repo, declaration)
    proof_data = json.loads(_file(repo, payload.get('evidence', {}).get('path', '')).read_text())
    executor = proof_data.get('context', {}).get('executor_id')
    if executor:
        context['executor_id'] = executor
    proof = _proof(repo, declaration, payload.get('evidence'), context)
    return {'subtask_id': task['subtask_id'], 'capability_id': declaration['capability_id'],
            'declaration_sha256': digest(declaration), 'context': context,
            'status': proof['status'], 'evidence': payload['evidence'],
            'recorded_at': proof['observed_at']}


def scoped_declarations(state, task):
    declarations = task.get('assignment', {}).get('required_capabilities', [])
    gate = state.get('acceptance_gate', {})
    attempt = next((a for a in gate.get('attempts', []) if a['subtask_id'] == task['subtask_id']), None)
    if attempt is None or attempt.get('kind') == 'preparation':
        return declarations
    from acceptance_points import definitions
    items, closures = definitions(gate)
    selected = {dep for ident in attempt.get('scope_acceptance_ids', []) for dep in closures[ident]}
    declared = {d['capability_id'] for d in declarations}
    needed = {cap for ident in selected for cap in items[ident].get('capabilities', declared)}
    if needed - declared:
        raise ValueError('point capability has no execution declaration: ' + ', '.join(sorted(needed - declared)))
    return [d for d in declarations if d['capability_id'] in needed]


def capability_errors(repo, state, task, executor_id=None):
    errors = []
    try:
        declarations = scoped_declarations(state, task)
    except (ValueError, KeyError) as exc:
        return [str(exc)]
    for declaration in declarations:
        ident = declaration['capability_id']
        try:
            receipt = next((r for r in reversed(state.get('capability_receipts', []))
                            if r['subtask_id'] == task['subtask_id'] and r['capability_id'] == ident), None)
            if receipt is None:
                raise ValueError('probe evidence missing')
            context = _context(repo, declaration)
            expected_executor = executor_id or task.get('dispatch', {}).get('platform_agent_id')
            recorded_executor = receipt.get('context', {}).get('executor_id')
            if expected_executor and expected_executor != recorded_executor:
                raise ValueError('probe executor identity does not match the actual bound agent')
            if recorded_executor:
                context['executor_id'] = recorded_executor
            if receipt['declaration_sha256'] != digest(declaration) or receipt['context'] != context:
                raise ValueError('host/session/tool/interpreter/dependency binding changed')
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(receipt['recorded_at'])).total_seconds()
            if age < 0 or age > declaration['max_age_seconds']:
                raise ValueError('probe evidence expired')
            proof = _proof(repo, declaration, receipt['evidence'], context)
            if receipt['recorded_at'] != proof['observed_at']:
                raise ValueError('probe observation time changed')
            if receipt['status'] != 'passed' or proof['status'] != 'passed':
                raise ValueError('latest probe failed')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(f'capability {ident}: {exc}')
    return errors
