"""Owned-file lifecycle. No recursive deletes and no implicit environment repair."""
import base64
from contextlib import ExitStack, contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from .bundle import load_bundle
from .config import current_environment
from .errors import HarnessError
from .paths import META, MODULES, RUNTIME, SKILLS, checked, digest, file_bytes, owned, relative

START = b"<!-- ai-harness:portable:start -->"
END = b"<!-- ai-harness:portable:end -->"
RECEIPT = META + "receipt.json"
JOURNAL = META + "journal.json"


def _json(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def _decode(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid backup encoding")
    return base64.b64decode(value, validate=True)


def _encode(value):
    return base64.b64encode(value).decode("ascii") if value is not None else None


def _hash(value):
    return digest(value) if value is not None else None


def _roots(config):
    try:
        roots = {"home": checked(Path(config["codex_home"])),
                 "skills": checked(Path(config["skills_dir"]))}
        if roots["home"] == roots["skills"] or roots["home"].is_relative_to(roots["skills"]):
            raise HarnessError("CONFIG_INVALID", "home and skills must not overlap in this direction")
        if roots["skills"].is_relative_to(roots["home"] / ".ai-harness"):
            raise HarnessError("CONFIG_INVALID", "skills cannot overlap installation metadata")
        environment = config.get("environment", "auto")
        if environment not in {"auto", "windows", "linux", "wsl"}:
            raise ValueError("Invalid environment")
        if environment != "auto" and ((environment == "windows") != (os.name == "nt")):
            raise ValueError("Use an interpreter matching the requested environment")
        return roots
    except (KeyError, ValueError, TypeError) as error:
        raise HarnessError("CONFIG_INVALID", str(error)) from error


def _root_names(roots):
    return {key: str(value) for key, value in roots.items()}


def _path(roots, root, target):
    if root not in roots:
        raise HarnessError("UNSAFE_PATH", "Unknown installation root")
    return checked(roots[root] / relative(target))


def _block(content):
    if content is None:
        return None
    if content.count(START) != content.count(END) or content.count(START) > 1:
        raise HarnessError("MANAGED_DRIFT", "Ambiguous AGENTS management markers")
    if START not in content:
        return None
    start, end = content.index(START), content.index(END) + len(END)
    if end <= start:
        raise HarnessError("MANAGED_DRIFT", "Malformed AGENTS management block")
    return content[start:end]


def _records(items):
    if not isinstance(items, list):
        raise ValueError("Invalid receipt files")
    result = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {"root", "target", "module", "sha256"}:
            raise ValueError("Invalid ownership record")
        owned(item["module"], item["root"], item["target"])
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Invalid ownership hash")
        key = item["root"], item["target"]
        if any((r, t.casefold()) == (key[0], key[1].casefold()) for r, t in result):
            raise ValueError("Duplicate ownership record")
        result[key] = item
    return result


def _receipt(raw, roots):
    if raw is None:
        return dict(schema_version=1, roots=_root_names(roots), modules={}, files=[], agents_block=None,
                    environment=current_environment())
    try:
        value = json.loads(raw.decode("utf-8"))
        if (not isinstance(value, dict) or value.get("schema_version") != 1
                or value.get("roots") != _root_names(roots)
                or not isinstance(value.get("modules"), dict) or set(value["modules"]) - MODULES
                or any(not isinstance(v, str) or not v for v in value["modules"].values())):
            raise ValueError("Invalid receipt header or installation roots")
        records = _records(value["files"])
        if any(item["module"] not in value["modules"] for item in records.values()):
            raise ValueError("Receipt references an uninstalled module")
        agents = records.get(("home", "AGENTS.md"))
        if value.get("agents_block") != (agents["sha256"] if agents else None):
            raise ValueError("Inconsistent AGENTS ownership")
        if value.get("environment", current_environment()) != current_environment():
            raise ValueError("Manage this installation using its original execution environment")
        return value
    except HarnessError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise HarnessError("RECEIPT_INVALID", str(error)) from error


def _verify(receipt, roots):
    for item in receipt["files"]:
        content = file_bytes(_path(roots, item["root"], item["target"]))
        value = _block(content) if item["target"] == "AGENTS.md" else content
        if _hash(value) != item["sha256"]:
            raise HarnessError("MANAGED_DRIFT", "Preserve modified/missing managed file: " + item["target"])


def _pending(roots):
    if file_bytes(roots["home"] / JOURNAL) is not None:
        raise HarnessError("RECOVERY_REQUIRED", "An unfinished transaction exists; run recover first")


def _atomic(path, content):
    checked(path)
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    checked(path)
    fd, temporary = tempfile.mkstemp(prefix=".portable-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        checked(path)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def _lock(path):
    checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    checked(path)
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise HarnessError("UNSAFE_PATH", "Lock must be an unaliased regular file")
    # Never truncate an existing lock inode: all processes lock the same file.
    with path.open("a+b") as stream:
        if os.fstat(stream.fileno()).st_nlink != 1:
            raise HarnessError("UNSAFE_PATH", "Hard-linked lock files are not managed")
        try:
            if os.name == "nt":
                import msvcrt
                if stream.seek(0, 2) == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise HarnessError("LOCKED", "Another process holds the installation lock") from error
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def _locks(roots):
    paths = sorted({roots["home"] / (META + "install.lock"), roots["skills"] / ".ai-harness-portable.lock"}, key=str)
    with ExitStack() as stack:
        for path in paths:
            stack.enter_context(_lock(path))
        yield


def _selected(selected, available):
    selected = list(available) if selected is None else selected
    if (not isinstance(selected, list) or not selected or any(not isinstance(x, str) for x in selected)
            or len(set(selected)) != len(selected) or set(selected) - set(available)):
        raise HarnessError("CONFIG_INVALID", "Select unique modules present in this bundle/installation")
    return set(selected)


def _plan(roots, manifest=None, bundle_root=None, selected=None):
    _pending(roots)
    raw = file_bytes(roots["home"] / RECEIPT)
    old = _receipt(raw, roots)
    _verify(old, roots)
    modules = _selected(selected, manifest["modules"] if manifest else old["modules"])
    old_files = _records(old["files"])
    desired = {key: value for key, value in old_files.items() if value["module"] not in modules}
    contents = {}
    if manifest:
        for module in modules - set(old["modules"]):
            if module in SKILLS:
                folder = _path(roots, "skills", SKILLS[module])
                if folder.exists() and (not folder.is_dir() or any(not p.is_dir() or p.is_symlink() for p in folder.rglob("*"))):
                    raise HarnessError("UNMANAGED_CONFLICT", "Unknown skill directory already exists: " + str(folder))
        for entry in manifest["files"]:
            if entry["module"] not in modules:
                continue
            key = entry["root"], entry["target"]
            content = file_bytes(Path(bundle_root).absolute() / entry["source"])
            if _hash(content) != entry["sha256"]:
                raise HarnessError("BUNDLE_INVALID", "Bundle changed during installation")
            if key == ("home", "AGENTS.md"):
                if START in content or END in content:
                    raise HarnessError("BUNDLE_INVALID", "AGENTS source must not contain management markers")
                runtime = roots["home"] / RUNTIME
                content = content.replace(b"{{HARNESS_ROOT}}", str(runtime).encode("utf-8"))
                content = content.replace(b"{{SKILLS_DIR}}", str(roots["skills"]).encode("utf-8"))
                content = START + b"\n" + content.rstrip(b"\r\n") + b"\n" + END
            desired[key] = {field: entry[field] for field in ("root", "target", "module", "sha256")}
            desired[key]["sha256"] = digest(content)
            contents[key] = content
    changes = []
    for key in sorted(set(old_files) | set(desired)):
        before = file_bytes(_path(roots, *key))
        if key not in contents and key in desired:
            continue
        after = contents.get(key)
        if key == ("home", "AGENTS.md"):
            block = _block(before)
            if key not in old_files and block is not None:
                raise HarnessError("UNMANAGED_CONFLICT", "AGENTS already contains an unowned management block")
            if block is not None:
                after = before.replace(block, after or b"", 1)
            elif after is not None:
                after = (before or b"") + after
            if after == b"" and before == block:
                after = None
        elif key not in old_files and before is not None:
            raise HarnessError("UNMANAGED_CONFLICT", "Unknown file already exists: " + key[1])
        if before != after:
            changes.append(dict(root=key[0], target=key[1], before=_encode(before), after=_hash(after), content=after))
    versions = {key: value for key, value in old["modules"].items() if key not in modules}
    if manifest:
        versions.update({module: manifest["version"] for module in modules})
    agents = desired.get(("home", "AGENTS.md"))
    result = dict(schema_version=1, roots=_root_names(roots), environment=current_environment(),
                  modules=versions, files=[desired[k] for k in sorted(desired)],
                  agents_block=agents["sha256"] if agents else None)
    receipt_content = _json(result)
    if receipt_content != raw:
        changes.append(dict(root="home", target=RECEIPT, before=_encode(raw), after=digest(receipt_content), content=receipt_content))
    return changes, result, raw


def _journal_valid(value, roots):
    try:
        if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("roots") != _root_names(roots):
            raise ValueError("Invalid journal roots/header")
        old_raw = _decode(value["before_receipt"])
        old = _receipt(old_raw, roots)
        before_files = _records(old["files"])
        after_files = _records(value["transaction_files"])
        changes = value["changes"]
        if not isinstance(changes, list) or not changes:
            raise ValueError("Empty transaction")
        seen = set()
        for index, change in enumerate(changes):
            if not isinstance(change, dict) or set(change) != {"root", "target", "before", "after"}:
                raise ValueError("Invalid journal change")
            key = change["root"], change["target"]
            _path(roots, *key)
            folded = key[0], key[1].casefold()
            if folded in seen:
                raise ValueError("Duplicate journal change")
            seen.add(folded)
            before = _decode(change["before"])
            after = change["after"]
            if after is not None and (not isinstance(after, str) or not re.fullmatch(r"[0-9a-f]{64}", after)):
                raise ValueError("Invalid after hash")
            if key == ("home", RECEIPT):
                if index != len(changes) - 1 or before != old_raw or after is None:
                    raise ValueError("Receipt must commit last")
                continue
            old_item, new_item = before_files.get(key), after_files.get(key)
            if old_item is None and new_item is None:
                raise ValueError("Journal claims an unowned target")
            content_hash = _hash(_block(before)) if key == ("home", "AGENTS.md") else _hash(before)
            if content_hash != (old_item["sha256"] if old_item else None):
                raise ValueError("Backup does not match prior ownership")
            if key == ("home", "AGENTS.md"):
                current = file_bytes(_path(roots, *key))
                # The receipt owns only the block, so its hash alone cannot
                # authenticate the user's surrounding text in a full backup.
                # A matching after-image supplies an independent copy of those
                # unchanged bytes; check every backup before restoring any file.
                if _hash(current) == after:
                    current_block = _block(current)
                    if _hash(current_block) != (new_item["sha256"] if new_item else None):
                        raise ValueError("AGENTS after block does not match ownership")
                    old_block = _block(before)
                    before_user = (before or b"").replace(old_block, b"", 1) if old_block else (before or b"")
                    after_user = (current or b"").replace(current_block, b"", 1) if current_block else (current or b"")
                    if before_user != after_user:
                        raise ValueError("AGENTS backup changes unowned user bytes")
            if key != ("home", "AGENTS.md") and after != (new_item["sha256"] if new_item else None):
                raise ValueError("After state does not match transaction ownership")
        if changes[-1]["target"] != RECEIPT or changes[-1]["root"] != "home":
            raise ValueError("Missing final receipt")
        return changes
    except HarnessError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise HarnessError("JOURNAL_INVALID", str(error)) from error


def _restore(roots, journal):
    changes = _journal_valid(journal, roots)
    blocked = []
    for change in reversed(changes):
        path = _path(roots, change["root"], change["target"])
        before = _decode(change["before"])
        try:
            current = file_bytes(path)
            if current == before:
                continue
            if _hash(current) != change["after"]:
                blocked.append(change["target"])
                continue
            _atomic(path, before)
        except OSError:
            blocked.append(change["target"])
    if blocked:
        raise HarnessError("RECOVERY_INCOMPLETE", "External changes or I/O failures preserved: " + ", ".join(blocked))
    (roots["home"] / JOURNAL).unlink()


def _execute(roots, changes, result, raw):
    if not changes:
        return
    journal = dict(schema_version=1, roots=_root_names(roots), before_receipt=_encode(raw),
                   transaction_files=result["files"], changes=[{k: v for k, v in c.items() if k != "content"} for c in changes])
    _journal_valid(journal, roots)
    _atomic(roots["home"] / JOURNAL, _json(journal))
    try:
        for change in changes:
            path = _path(roots, change["root"], change["target"])
            if file_bytes(path) != _decode(change["before"]):
                raise HarnessError("MANAGED_DRIFT", "File changed after preflight: " + change["target"])
            _atomic(path, change["content"])
            if _hash(file_bytes(path)) != change["after"]:
                raise OSError("Post-write verification failed")
        (roots["home"] / JOURNAL).unlink()
    except (OSError, HarnessError) as error:
        _restore(roots, journal)
        raise HarnessError("ROLLED_BACK", "Operation failed; managed bytes restored: " + str(error)) from error


def _operation(config, manifest=None, bundle_root=None, selected=None, dry_run=False):
    roots = _roots(config)
    changes, result, raw = _plan(roots, manifest, bundle_root, selected)
    if not dry_run:
        with _locks(roots):
            changes, result, raw = _plan(roots, manifest, bundle_root, selected)
            _execute(roots, changes, result, raw)
    return dict(ok=True, dry_run=dry_run, modules=result["modules"],
                changes=[dict(root=c["root"], target=c["target"], action="remove" if c["after"] is None else "write") for c in changes],
                session_verified=False)


def install(bundle_root: Path, config: dict, selected=None, dry_run=False) -> dict:
    return _operation(config, load_bundle(bundle_root), bundle_root, selected, dry_run)


def uninstall(config: dict, selected=None, dry_run=False) -> dict:
    return _operation(config, selected=selected, dry_run=dry_run)


def recover(config: dict) -> dict:
    roots = _roots(config)
    raw = file_bytes(roots["home"] / JOURNAL)
    if raw is None:
        return dict(ok=True, recovered=False, session_verified=False)
    try:
        journal = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise HarnessError("JOURNAL_INVALID", "Cannot decode pending journal") from error
    _journal_valid(journal, roots)
    with _locks(roots):
        if file_bytes(roots["home"] / JOURNAL) != raw:
            raise HarnessError("RECOVERY_REQUIRED", "Transaction changed; inspect again")
        changes = journal["changes"]
        if all(_hash(file_bytes(_path(roots, c["root"], c["target"]))) == c["after"] for c in changes):
            current = _receipt(file_bytes(roots["home"] / RECEIPT), roots)
            if current["files"] != journal["transaction_files"]:
                raise HarnessError("JOURNAL_INVALID", "Committed receipt does not match transaction")
            _verify(current, roots)
            (roots["home"] / JOURNAL).unlink()
        else:
            _restore(roots, journal)
    return dict(ok=True, recovered=True, session_verified=False)


def doctor(config: dict) -> dict:
    roots = _roots(config)
    _pending(roots)
    raw = file_bytes(roots["home"] / RECEIPT)
    receipt = _receipt(raw, roots)
    _verify(receipt, roots)
    dependencies = {"python": sys.version.split()[0], "git": shutil.which("git") is not None,
                    "jsonschema": importlib.util.find_spec("jsonschema") is not None}
    blocked = []
    next_steps = []
    if not dependencies["git"]:
        blocked.append("git_workflow")
        next_steps.append("Install Git for this environment and make git available on PATH")
    if "gto" in receipt["modules"]:
        if not dependencies["git"] or not dependencies["jsonschema"]:
            blocked.append("gto")
        if not dependencies["jsonschema"]:
            requirements = roots["skills"] / "global-task-orchestrator" / "requirements.txt"
            next_steps.append(f"Prepare jsonschema with this interpreter ({sys.executable}) using {requirements}")
    next_steps.append("Open a new Codex session to verify actual rule and skill loading")
    return dict(ok=True, installed=bool(receipt["modules"]), modules=receipt["modules"],
                environment=current_environment(), session_verified=False,
                dependencies=dependencies, blocked_capabilities=blocked,
                next_step="; ".join(next_steps))
