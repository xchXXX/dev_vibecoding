"""Content-addressed, allowlisted release bundles."""
import json
from pathlib import Path
import re
import subprocess

from .errors import HarnessError
from .paths import MODULES, SKILLS, RUNTIME, checked, digest, file_bytes, owned, relative

BASE_TOOLS = {"scripts/harness.py", "scripts/check_git_workflow.py",
              "scripts/resolve-wsl-path.py", "scripts/runtime_common.py"}
BASE_DOCS = {"docs/modules/git-workflow/contract/README.md"}
RECIPIENT_DOCS = {"docs/INSTALL.md", "docs/modules/portable-harness/contract/README.md"}
DEPENDENCIES = {"python": ">=3.11", "git": {"required_for": ["build", "git_workflow", "gto"]},
                "jsonschema": {"specifier": ">=4.10.3,<5", "required_for": ["gto"]}}
BUILD_ENTRYPOINT = "scripts/harness.py build"
SUPPORT_MATRIX = {name: {"status": "candidate", "session_verified": False}
                  for name in ("windows", "linux", "wsl")}


def _release_metadata(manifest):
    dependencies = manifest["dependencies"]
    if not isinstance(dependencies, dict) or set(dependencies) != set(DEPENDENCIES):
        raise ValueError("Invalid dependencies")
    if not isinstance(dependencies["python"], str) or not dependencies["python"]:
        raise ValueError("Invalid Python requirement")
    for name in ("git", "jsonschema"):
        record = dependencies[name]
        expected = {"required_for"} | ({"specifier"} if name == "jsonschema" else set())
        if (not isinstance(record, dict) or set(record) != expected
                or not isinstance(record["required_for"], list) or not record["required_for"]
                or any(not isinstance(item, str) or not item for item in record["required_for"])
                or (name == "jsonschema" and (not isinstance(record["specifier"], str) or not record["specifier"]))):
            raise ValueError("Invalid optional dependency")
    if manifest["build_entrypoint"] != BUILD_ENTRYPOINT:
        raise ValueError("Invalid build entrypoint")
    matrix = manifest["support_matrix"]
    if not isinstance(matrix, dict) or set(matrix) != set(SUPPORT_MATRIX):
        raise ValueError("Invalid support matrix")
    for record in matrix.values():
        if (not isinstance(record, dict) or set(record) != {"status", "session_verified"}
                or record["status"] != "candidate" or record["session_verified"] is not False):
            raise ValueError("Candidate metadata cannot claim verified platform sessions")


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)


def load_bundle(root: Path) -> dict:
    root = checked(Path(root).absolute())
    try:
        raw = file_bytes(root / "manifest.json")
        manifest = json.loads(raw.decode("utf-8"))
        if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
                or not isinstance(manifest.get("version"), str) or not manifest["version"]
                or not re.fullmatch(r"[0-9a-f]{40}", manifest.get("source_commit", ""))
                or not isinstance(manifest.get("modules"), list)
                or not manifest["modules"] or set(manifest["modules"]) - MODULES
                or len(set(manifest["modules"])) != len(manifest["modules"])):
            raise ValueError("Invalid manifest header")
        _release_metadata(manifest)
        sources, targets = set(), set()
        for field in ("files", "payload_files"):
            entries = manifest[field]
            if not isinstance(entries, list):
                raise ValueError("Invalid file list")
            for entry in entries:
                expected = {"source", "sha256"} | ({"root", "target", "module"} if field == "files" else set())
                if not isinstance(entry, dict) or set(entry) != expected or not _hash(entry["sha256"]):
                    raise ValueError("Invalid file record")
                source = relative(entry["source"])
                if source.casefold() in sources or source.casefold() == "manifest.json":
                    raise ValueError("Duplicate source")
                sources.add(source.casefold())
                content = file_bytes(root / source)
                if content is None or digest(content) != entry["sha256"]:
                    raise ValueError("File hash mismatch: " + source)
                if field == "files":
                    if entry["module"] not in manifest["modules"]:
                        raise ValueError("Undeclared module")
                    owned(entry["module"], entry["root"], entry["target"])
                    key = (entry["root"], entry["target"].casefold())
                    if key in targets:
                        raise ValueError("Duplicate target")
                    targets.add(key)
        for path in root.rglob("*"):
            checked(path)
            if path.is_file() and path != root / "manifest.json" and path.relative_to(root).as_posix().casefold() not in sources:
                raise ValueError("Unlisted bundle file")
        return manifest
    except HarnessError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise HarnessError("BUNDLE_INVALID", "Invalid bundle: " + str(error)) from error


def _git(root, *args):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HarnessError("BUILD_FAILED", "Git is required to read the fixed source commit") from error
    if result.returncode:
        raise HarnessError("BUILD_FAILED", "Cannot read fixed source commit")
    return result.stdout


def _mapping(path):
    if path == "templates/codex/AGENTS.global.md":
        return "base", "home", "AGENTS.md"
    if path.startswith("rules/") and Path(path).suffix in {".md", ".json"}:
        return "base", "home", RUNTIME + path
    if path.startswith("modules/harness/") and path.endswith(".py"):
        return "base", "home", RUNTIME + path
    if path in BASE_TOOLS or path in BASE_DOCS:
        return "base", "home", RUNTIME + path
    for module, skill in SKILLS.items():
        prefix = "skills/" + skill + "/"
        if path.startswith(prefix) and Path(path).suffix in {".py", ".md", ".json", ".yaml", ".yml", ".txt"}:
            return module, "skills", path[len("skills/"):]
    return None


def build_release(source_root: Path, output_dir: Path, version: str, source_commit: str) -> dict:
    output_dir = checked(Path(output_dir).absolute())
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise HarnessError("UNMANAGED_CONFLICT", "Bundle output must be absent or empty")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version):
        raise HarnessError("CONFIG_INVALID", "Use a nonempty portable version label")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise HarnessError("CONFIG_INVALID", "source_commit must be an exact 40-character commit")
    source_root = checked(Path(source_root).absolute())
    commit = _git(source_root, "rev-parse", source_commit + "^{commit}").decode().strip()
    if commit != source_commit:
        raise HarnessError("BUILD_FAILED", "Source is not an exact commit")
    records, payloads, contents, source_files = [], [], {}, {}
    for row in _git(source_root, "ls-tree", "-rz", source_commit).split(b"\0"):
        if not row:
            continue
        header, name = row.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        path = name.decode("utf-8")
        mapping = _mapping(path)
        payload = path in RECIPIENT_DOCS
        if not mapping and not payload:
            continue
        relative(path)
        if mode not in {"100644", "100755"} or kind != "blob":
            raise HarnessError("UNSAFE_PATH", "Non-regular source in release: " + path)
        source_files[path] = _git(source_root, "cat-file", "blob", oid)
    # This is a generated global view of the fixed source registry, not a second
    # editable rule definition. Project-scoped leaves never cross the boundary.
    private_paths = {path for path, content in source_files.items()
                     if path.startswith('rules/items/') and
                     re.search(rb'(?m)^scope:\s*[\"\x27]?project[\"\x27]?\s*$', content)}
    index_path = 'rules/registry/RULES_INDEX.json'
    if index_path in source_files:
        try:
            index = json.loads(source_files[index_path].decode('utf-8'))
            original = index['rules']
            private_paths.update(row['file_path'] for row in original if row.get('scope') == 'project')
            index['rules'] = [row for row in original if row.get('scope') != 'project'
                              and row.get('file_path') not in private_paths]
            index['local_rule_count'] = len(index['rules'])
            index['repo_root'] = '<installed-rule-root>'
            index['source_fingerprint'] = digest(json.dumps(index['rules'], sort_keys=True, ensure_ascii=True).encode())
            source_files[index_path] = (json.dumps(index, sort_keys=True, ensure_ascii=True, indent=2) + '\n').encode()
            md_path = 'rules/registry/RULES_INDEX.md'
            if md_path in source_files:
                rows = ['# Exported global rules', '', 'Generated by scripts/harness.py build from the fixed source registry.', '']
                rows.extend('- `' + row['id'] + '` -> `' + row['file_path'] + '`' for row in index['rules'])
                source_files[md_path] = ('\n'.join(rows) + '\n').encode('utf-8')
        except (ValueError, KeyError, TypeError) as error:
            raise HarnessError('BUILD_FAILED', 'Invalid fixed source rule registry') from error
    for path, content in sorted(source_files.items()):
        if path in private_paths:
            continue
        mapping = _mapping(path)
        payload = path in RECIPIENT_DOCS
        if mapping:
            module, root, target = mapping
            packaged = "payload/" + path
            records.append(dict(source=packaged, root=root, target=target, module=module, sha256=digest(content)))
            contents[packaged] = content
        if payload or path.startswith("modules/harness/") or path == "scripts/harness.py":
            payloads.append(dict(source=path, sha256=digest(content)))
            contents[path] = content
    if not records:
        raise HarnessError("BUILD_FAILED", "No release files in fixed source")
    requirement = source_files.get("skills/global-task-orchestrator/requirements.txt")
    if requirement is not None and requirement.decode("utf-8").strip() != "jsonschema" + DEPENDENCIES["jsonschema"]["specifier"]:
        raise HarnessError("BUILD_FAILED", "GTO dependency declaration differs from release metadata")
    manifest = dict(schema_version=1, version=version, source_commit=source_commit,
                    dependencies=DEPENDENCIES, build_entrypoint=BUILD_ENTRYPOINT, support_matrix=SUPPORT_MATRIX,
                    modules=sorted({r["module"] for r in records}), files=records, payload_files=payloads)
    # Validate content and collisions before creating the output directory.
    folded = [name.casefold() for name in contents]
    if len(folded) != len(set(folded)):
        raise HarnessError("UNSAFE_PATH", "Case collision in release files")
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, content in sorted(contents.items()):
        target = output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return load_bundle(output_dir)
