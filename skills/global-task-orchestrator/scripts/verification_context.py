"""Bounded, operation-local reads; never a persistent trust cache.

Consumers still check path policy and expected hashes. Every observed identity is
checked again before leaving a stable stage. Separate commit checks use a fresh
stage, so neither state changes nor a second command inherit cached trust.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
from pathlib import Path
import time


_current = ContextVar('verification_context', default=None)


def identity(path):
    path = Path(path)
    try:
        resolved = path.resolve(strict=True)
        st = path.stat()
        return (str(resolved), st.st_dev, st.st_ino, st.st_mode,
                st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    except FileNotFoundError:
        return (str(path.resolve(strict=False)), 'missing')


class ChangedDuringVerification(OSError):
    pass


class VerificationContext:
    def __init__(self):
        self.observed = {}
        self.contents = {}
        self.content_bytes = 0
        self.content_limit = 16 * 1024 * 1024
        self.digests = {}
        self.directories = {}
        self.results = {}
        self.metrics = dict(read_calls=0, read_bytes=0, hash_calls=0,
                            cache_hits=0, directory_scans=0)
        self.started = time.monotonic_ns()

    def watch(self, path):
        path = Path(path).absolute()
        stamp = identity(path)
        previous = self.observed.setdefault(path, stamp)
        if previous != stamp:
            raise ChangedDuringVerification('input changed during verification: ' + str(path))
        return stamp

    def validate(self):
        for path, expected in self.observed.items():
            if identity(path) != expected:
                raise ChangedDuringVerification('input changed during verification: ' + str(path))

    def recheck_strong(self):
        """Independent commit check: identity is a rejection hint, never trust.

        Rehash every consumed file and enumerate each consumed directory, even
        when its metadata stayed unchanged. The caller supplies writer locking
        and independently checks control state and external (for example Git)
        inputs which are not filesystem reads in this context.
        """
        self.validate()
        with operation(fresh=True) as check:
            for path, stamp in self.observed.items():
                if stamp in self.digests and file_digest(path) != self.digests[stamp]:
                    raise ChangedDuringVerification('input contents changed before commit: ' + str(path))
            for path, expected in self.directories.items():
                if tuple(p.name for p in children(path)) != expected:
                    raise ChangedDuringVerification('input directory changed before commit: ' + str(path))
            self.validate()
        return check.metrics

    def read(self, path):
        path = Path(path)
        stamp = self.watch(path)
        if stamp not in self.contents:
            raw = path.read_bytes()
            self.watch(path)
            self.metrics['read_calls'] += 1
            self.metrics['read_bytes'] += len(raw)
            if stamp not in self.digests:
                self.digests[stamp] = hashlib.sha256(raw).hexdigest()
                self.metrics['hash_calls'] += 1
            # Large logs use file_digest's streaming path. JSON callers still
            # need their bytes, but must not retain unbounded input across files.
            if self.content_bytes + len(raw) <= self.content_limit:
                self.contents[stamp] = raw
                self.content_bytes += len(raw)
            return raw
        else:
            self.metrics['cache_hits'] += 1
        return self.contents[stamp]


@contextmanager
def operation(*, fresh=False):
    existing = _current.get()
    if existing is not None and not fresh:
        yield existing
        return
    context = VerificationContext()
    token = _current.set(context)
    try:
        yield context
        context.validate()
    finally:
        context.metrics['elapsed_ns'] = time.monotonic_ns() - context.started
        _current.reset(token)


def scoped(function):
    @wraps(function)
    def invoke(*args, **kwargs):
        with operation():
            return function(*args, **kwargs)
    return invoke


def memo(namespace, key, calculate):
    context = _current.get()
    if context is None:
        return calculate()
    raw = json.dumps(key, sort_keys=True, separators=(',', ':'), default=str).encode()
    key = (namespace, hashlib.sha256(raw).digest())
    if key not in context.results:
        context.results[key] = calculate()
    else:
        context.metrics['cache_hits'] += 1
    return context.results[key]


def cached(function):
    @wraps(function)
    def invoke(*args, **kwargs):
        return memo(function.__module__ + '.' + function.__name__, [args, kwargs],
                    lambda: function(*args, **kwargs))
    return invoke


def read_bytes(path):
    context = _current.get()
    return context.read(path) if context is not None else Path(path).read_bytes()


def read_text(path, encoding='utf-8'):
    return read_bytes(path).decode(encoding)


def watch(path):
    context = _current.get()
    return context.watch(path) if context is not None else identity(path)


def children(path):
    context = _current.get()
    watch(path)
    def collect():
        if context:
            context.metrics['directory_scans'] += 1
        result = tuple(sorted(Path(path).iterdir(), key=lambda p: p.name))
        if context:
            context.directories[Path(path).absolute()] = tuple(p.name for p in result)
        return result
    return memo('directory', str(Path(path).absolute()), collect)


def file_digest(path):
    """Hash large evidence without retaining its complete contents in memory."""
    context = _current.get()
    stamp = watch(path)
    if context and stamp in context.digests:
        context.metrics['cache_hits'] += 1
        return context.digests[stamp]
    if context and (stamp in context.contents or (len(stamp) > 2 and stamp[4] <= 1024 * 1024)):
        context.read(path)
        return context.digests[stamp]
    else:
        hasher = hashlib.sha256()
        size = 0
        with Path(path).open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                hasher.update(chunk)
        watch(path)
        result = hasher.hexdigest()
        if context:
            context.metrics['read_calls'] += 1
            context.metrics['read_bytes'] += size
    if context:
        context.digests[stamp] = result
        context.metrics['hash_calls'] += 1
    return result
