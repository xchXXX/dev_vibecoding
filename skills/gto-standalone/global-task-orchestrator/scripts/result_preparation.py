"""Build receipt data from sealed observations, never execute or register work."""
from __future__ import annotations

import json

from runtime_evidence import acceptance_binding, digest, execution_times, retained_file, verify_run


def base_result(subtask, summary, commands):
    dispatch = subtask.get('dispatch')
    if not dispatch or subtask.get('status') != 'in_progress':
        raise ValueError('result preparation requires an active bound dispatch')
    return {'status': 'completed', 'summary': summary, 'changed_files': [],
            'planned_files_not_changed': [], 'verification': {'commands': commands, 'result': summary},
            'deviations': [], 'blocked_by': [], 'risks': [], 'follow_up': [],
            'written_by': dispatch['platform_agent_id'], 'written_role': dispatch['agent_key']}


def acceptance_result(repo, state, subtask, manifest_relative, observation_relative):
    if subtask.get('stage') != 'expensive_acceptance':
        raise ValueError('prepare-result requires an acceptance attempt')
    if not isinstance(manifest_relative, str) or not manifest_relative.startswith('.artifacts/'):
        raise ValueError('run manifest must be retained inside repository .artifacts')
    path = retained_file(repo, manifest_relative)
    if path.name != 'manifest.json':
        raise ValueError('run manifest must name the captured manifest.json')
    manifest = verify_run(path.parent, acceptance_binding(state, subtask['subtask_id']), repo=repo)
    raw = retained_file(repo, observation_relative).read_bytes()
    if manifest.get('evidence_files', {}).get(observation_relative) != digest(raw):
        raise ValueError('observation summary must be captured by this original run')
    observation = json.loads(raw)
    required = {'outcome', 'real_call_count', 'point_results'}
    optional = {'execution_kind', 'usage_evidence', 'failed_stage', 'finding_id',
                'closed_finding_ids', 'review_evidence', 'blackbox', 'invalid_observation', 'preparation'}
    if (not isinstance(observation, dict) or not required <= observation.keys()
            or observation.keys() - required - optional):
        raise ValueError('observation summary has missing or unknown fields')
    count, rows = observation['real_call_count'], observation['point_results']
    if type(count) is not int or count < 0 or not isinstance(rows, list):
        raise ValueError('observation requires a measured nonnegative call count and point results')
    outcome = observation['outcome']
    passing = outcome in {'pass', 'partial_pass'}
    attempt = next(a for a in state['acceptance_gate']['attempts'] if a['subtask_id'] == subtask['subtask_id'])
    scope = attempt['scope_acceptance_ids']
    refs = sorted({ref for row in rows for ref in row['evidence_refs']})
    # Even a zero-business environment failure retains the captured summary.
    refs = sorted(set(refs) | {observation_relative})
    started, finished = execution_times(manifest)
    duration = (manifest['elapsed_ns'] / 1_000_000_000 if manifest['schema_version'] == 2
                else (finished - started).total_seconds())
    entry = json.dumps(manifest['command'], ensure_ascii=False)
    result = base_result(subtask, 'Captured acceptance outcome: ' + str(outcome), [entry])
    result['status'] = 'completed' if passing else 'blocked'
    usage = observation.get('usage_evidence')
    if usage is None:
        if observation.get('execution_kind') != 'cli':
            raise ValueError('original observation must declare execution_kind=cli or provide usage_evidence')
        usage = [{'written_by': result['written_by'], 'environment': 'other', 'tool': 'CLI',
                  'entry': entry, 'scope': scope, 'result': outcome, 'evidence_refs': refs,
                  'ui_applicability': 'not_applicable',
                  'ui_not_applicable_reason': 'The captured observation adapter explicitly declared execution_kind=cli.'}]
    evidence = {'outcome': outcome, 'real_call_count': count, 'duration_seconds': duration,
                'failed_stage': observation.get('failed_stage', 'none' if passing else 'check'),
                'mode': 'scoped', 'scope_acceptance_ids': scope, 'point_results': rows,
                'evidence_refs': refs,
                'evidence_by_acceptance_id': {r['acceptance_id']: r['evidence_refs'] for r in rows if r['status'] == 'pass'},
                'usage_evidence': usage,
                'run_evidence': {'path': manifest_relative, 'sha256': digest(path.read_bytes())}}
    for key in ('finding_id', 'closed_finding_ids', 'blackbox', 'invalid_observation', 'preparation'):
        if key in observation:
            evidence[key] = observation[key]
    result['expensive_acceptance'] = evidence
    if 'review_evidence' in observation:
        result['review_evidence'] = observation['review_evidence']
    return result
