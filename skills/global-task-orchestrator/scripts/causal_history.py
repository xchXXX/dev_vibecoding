"""Task-local immutable completion proofs; indexes never establish chronology."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import uuid

from verification_context import read_bytes


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _safe(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('causal evidence must not contain symlinks')
    return path


def _root(repo, task_id):
    if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', task_id):
        raise ValueError('invalid causal task id')
    return _safe(Path(repo) / '.artifacts' / 'gto' / task_id / 'causal')


def _write(path, value):
    _safe(path)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.writing')
    try:
        temporary.write_bytes(raw)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _locked(root):
    root.mkdir(parents=True, exist_ok=True)
    with _safe(root / 'lock').open('a+b') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate_start(start, task_id):
    if task_id is None and start == {'task_id': None, 'sequence': 0, 'head': None} and type(start['sequence']) is int:
        return start  # Generic unbound command runner; this carries no causal proof.
    if (not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', task_id)
            or not isinstance(start, dict) or set(start) != {'task_id', 'sequence', 'head'}
            or start['task_id'] != task_id or type(start['sequence']) is not int
            or start['sequence'] < 0
            or (start['sequence'] == 0 and start['head'] is not None)
            or (start['sequence'] > 0 and (not isinstance(start['head'], str)
                or not re.fullmatch('[0-9a-f]{64}', start['head'])))):
        raise ValueError('invalid causal start watermark')
    return start


def _node(root, sha, task_id, sequence=None):
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('invalid causal node digest')
    raw = read_bytes(_safe(root / 'nodes' / (sha + '.json')))
    value = json.loads(raw)
    if (_hash(raw) != sha or not isinstance(value, dict)
            or set(value) != {'task_id', 'sequence', 'prev', 'manifest'}
            or value['task_id'] != task_id or type(value['sequence']) is not int
            or value['sequence'] < 1 or (sequence is not None and value['sequence'] != sequence)):
        raise ValueError('invalid causal chain node')
    validate_start({'task_id': task_id, 'sequence': value['sequence'] - 1,
                    'head': value['prev']}, task_id)
    reference = value['manifest']
    if (not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}
            or not isinstance(reference['sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', reference['sha256'])):
        raise ValueError('invalid causal manifest reference')
    _relative(reference['path'])
    return value


def _relative(value):
    if not isinstance(value, str):
        raise ValueError('invalid causal manifest path')
    path = Path(value)
    if (path.is_absolute() or '..' in path.parts or not path.parts
            or path.parts[0] != '.artifacts' or path.name != 'manifest.json'):
        raise ValueError('causal manifest must be retained in .artifacts')
    return path


def _head(root, task_id):
    path = _safe(root / 'head.json')
    if not path.exists():
        nodes = _safe(root / 'nodes')
        if nodes.exists() and any(nodes.iterdir()):
            raise ValueError('causal head missing while nodes exist')
        return {'task_id': task_id, 'sequence': 0, 'head': None}
    # Mutable head is never served from a verification-stage cache.
    head = validate_start(json.loads(path.read_bytes()), task_id)
    if head['head']:
        _node(root, head['head'], task_id, head['sequence'])
    return head


def capture_start(repo, task_id):
    root = _root(repo, task_id)
    with _locked(root):
        return _head(root, task_id)


def publish_completed(repo, task_id, manifest_path):
    repo = Path(repo)
    path = Path(manifest_path)
    if not path.is_absolute():
        path = repo / path
    relative = _relative(path.relative_to(repo).as_posix())
    raw = _safe(path).read_bytes()
    manifest = json.loads(raw)
    if (manifest.get('binding', {}).get('task_id') != task_id
            or manifest.get('status') not in {'passed', 'failed', 'interrupted', 'invalidated'}):
        raise ValueError('causal publication requires same-task terminal manifest')
    sha = _hash(raw)
    root = _root(repo, task_id)
    with _locked(root):
        head = _head(root, task_id)
        index = _safe(root / 'by-manifest' / (sha + '.json'))
        if index.exists():
            hint = json.loads(index.read_bytes())
            node = _node(root, hint['head'], task_id)
            if node['manifest'] != {'path': relative.as_posix(), 'sha256': sha}:
                raise ValueError('causal manifest index mismatch')
            return head  # Hint can only omit a redundant import, never prove order.
        node = {'task_id': task_id, 'sequence': head['sequence'] + 1,
                'prev': head['head'], 'manifest': {'path': relative.as_posix(), 'sha256': sha}}
        node_sha = _hash(json.dumps(node, sort_keys=True, separators=(',', ':')).encode())
        _safe(root / 'nodes').mkdir(exist_ok=True)
        node_path = _safe(root / 'nodes' / (node_sha + '.json'))
        if node_path.exists():
            if _hash(node_path.read_bytes()) != node_sha:
                raise ValueError('immutable causal node was changed')
        else:
            _write(node_path, node)
        new_head = {'task_id': task_id, 'sequence': node['sequence'], 'head': node_sha}
        _write(root / 'head.json', new_head)
        _safe(root / 'by-manifest').mkdir(exist_ok=True)
        _write(index, {'head': node_sha})
        return new_head


def causal_after(repo, current_manifest, previous_manifest_sha):
    """Missing proof is false, including damaged or concurrently incomplete indexes."""
    try:
        if current_manifest.get('schema_version') != 3:
            return False
        task_id = current_manifest['binding']['task_id']
        if task_id is None:
            return False
        start = validate_start(current_manifest['causal_start'], task_id)
        root = _root(repo, task_id)
        sha, sequence = start['head'], start['sequence']
        while sequence:
            node = _node(root, sha, task_id, sequence)
            if node['manifest']['sha256'] == previous_manifest_sha:
                raw = read_bytes(_safe(Path(repo) / _relative(node['manifest']['path'])))
                manifest = json.loads(raw)
                return (_hash(raw) == previous_manifest_sha
                        and manifest.get('binding', {}).get('task_id') == task_id
                        and manifest.get('status') in {'passed', 'failed', 'interrupted', 'invalidated'})
            sha, sequence = node['prev'], sequence - 1
        return False
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False
