"""Portable paths: reject aliases before resolving them."""
import hashlib
import os
from pathlib import Path
import re
import stat

from .errors import HarnessError

SKILLS = {"benchmark": "pre-dev-benchmark", "fix": "fix-closure-gate",
          "cfm": "command-failure-memory", "gto": "global-task-orchestrator"}
MODULES = {"base", *SKILLS}
RUNTIME = ".ai-harness/portable/runtime/"
META = ".ai-harness/portable/"


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise HarnessError("UNSAFE_PATH", "Expected a portable relative path")
    parts = value.split("/")
    for part in parts:
        if (part in {"", ".", ".."} or part[-1:] in {".", " "}
                or any(ord(c) < 32 for c in part) or any(c in '<>"|?*' for c in part)
                or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)):
            raise HarnessError("UNSAFE_PATH", "Unsafe path component: " + repr(part))
    return value


def checked(path: Path) -> Path:
    """Reject links/reparse points and case aliases, including existing parents."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise HarnessError("UNSAFE_PATH", "Installation paths must be absolute without '..'")
    for candidate in reversed((path, *path.parents)):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise HarnessError("UNSAFE_PATH", "Links and reparse points are not managed: " + str(candidate))
        if candidate != path and not stat.S_ISDIR(info.st_mode):
            raise HarnessError("UNSAFE_PATH", "Parent is not a directory: " + str(candidate))
        if candidate.parent != candidate and candidate.parent.is_dir():
            aliases = [p.name for p in candidate.parent.iterdir()
                       if p.name.casefold() == candidate.name.casefold()]
            if len(aliases) != 1 or aliases[0] != candidate.name:
                raise HarnessError("UNSAFE_PATH", "Ambiguous path spelling: " + str(candidate))
    # Also catch a nonexistent target whose differently cased alias exists.
    for candidate in (path, *path.parents):
        if candidate.parent != candidate and candidate.parent.is_dir():
            if any(p.name.casefold() == candidate.name.casefold() and p.name != candidate.name
                   for p in candidate.parent.iterdir()):
                raise HarnessError("UNSAFE_PATH", "Case-insensitive path collision: " + str(candidate))
    return path


def owned(module, root, target):
    relative(target)
    valid = (module == "base" and root == "home" and
             (target == "AGENTS.md" or target.startswith(RUNTIME)))
    if module in SKILLS:
        valid = root == "skills" and target.startswith(SKILLS[module] + "/")
    if not valid:
        raise HarnessError("UNSAFE_PATH", "Target is outside this module's ownership: " + target)
    return target


def file_bytes(path):
    checked(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise HarnessError("UNSAFE_PATH", "Expected a regular file: " + str(path))
    if path.stat().st_nlink != 1:
        raise HarnessError("UNSAFE_PATH", "Hard-linked files are not managed: " + str(path))
    return path.read_bytes()
