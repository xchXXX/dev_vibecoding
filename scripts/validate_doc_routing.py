from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from runtime_common import emit, resolve_repo_root


REQUIRED_TASK_FILES = ("plan.md", "execution.md", "acceptance.md")
REQUIRED_MODULE_DIRS = ("contract", "design", "delivery/code-map", "delivery/engineering")
BARE_NOT_APPLICABLE = re.compile(r"^\s*[-*]?\s*(?:[^:：]+[:：]\s*)?(?:不适用|N/A|n/a)\s*$")


def validate(repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    module_results: list[dict[str, Any]] = []
    task_results: list[dict[str, Any]] = []
    modules_root = repo_root / "modules"
    docs_modules = repo_root / "docs" / "modules"
    docs_tasks = repo_root / "docs" / "tasks"
    module_dirs = sorted(path for path in modules_root.iterdir() if path.is_dir()) if modules_root.is_dir() else []
    for module in module_dirs:
        target = docs_modules / module.name
        missing = [item for item in REQUIRED_MODULE_DIRS if not (target / item).is_dir()]
        if missing:
            errors.append(f"module {module.name} missing documentation skeleton: {', '.join(missing)}")
        module_results.append({"module_name": module.name, "missing_paths": missing, "ok": not missing})
    task_dirs = sorted(path for path in docs_tasks.iterdir() if path.is_dir()) if docs_tasks.is_dir() else []
    for task in task_dirs:
        missing = [name for name in REQUIRED_TASK_FILES if not (task / name).is_file()]
        if missing:
            errors.append(f"task {task.name} missing files: {', '.join(missing)}")
        task_results.append({"task_name": task.name, "missing_files": missing, "ok": not missing})
    markdown_files: list[Path] = []
    for root in (docs_modules, docs_tasks):
        if root.is_dir():
            markdown_files.extend(sorted(root.rglob("*.md")))
    not_applicable: list[dict[str, Any]] = []
    for path in markdown_files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if BARE_NOT_APPLICABLE.fullmatch(line):
                relative = path.relative_to(repo_root).as_posix()
                errors.append(f"{relative}:{line_number} bare not-applicable placeholder requires a reason")
                not_applicable.append({"path": relative, "line_number": line_number, "line": line})
    return {
        "ok": not errors, "repo_root": str(repo_root),
        "checked_module_count": len(module_dirs), "checked_task_count": len(task_dirs),
        "checked_markdown_count": len(markdown_files), "errors": errors, "warnings": [],
        "modules": module_results, "tasks": task_results, "not_applicable_checks": not_applicable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate module and task documentation routing.")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_repo_root(args.repo_root, Path(__file__))
        payload = validate(root)
    except (OSError, ValueError) as error:
        payload = {"ok": False, "errors": [str(error)]}
    return emit(payload, as_json=args.json, success_message=f"Validation passed for {payload.get('checked_module_count', 0)} modules and {payload.get('checked_task_count', 0)} task directories")


if __name__ == "__main__":
    raise SystemExit(main())
