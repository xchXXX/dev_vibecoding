from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from runtime_common import emit, resolve_repo_root


DOC_RULES = {
    "plan.md": {
        "kind": "plan",
        "headings": ["任务目标", "背景与问题", "范围", "非目标", "约束与依赖", "方案摘要", "风险与回退", "验收标准", "阶段划分", "需先同步的核心文档与测试"],
        "non_empty": ["需先同步的核心文档与测试"],
    },
    "execution.md": {
        "kind": "implementation",
        "headings": ["施工目标", "前置条件", "执行顺序", "文档先行清单", "测试同步清单", "实施批次", "每批写入范围", "验证命令", "回退方案", "审查与返工路径"],
        "non_empty": ["文档先行清单", "测试同步清单", "审查与返工路径"],
    },
    "acceptance.md": {
        "kind": "acceptance",
        "headings": ["验收目标", "验收标准", "必备证据", "未决项", "最终结论"],
        "non_empty": ["验收标准", "必备证据", "最终结论"],
    },
}


def _sections(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8-sig")
    matches = list(re.finditer(r"(?m)^#{1,2}\s+(.+?)\s*$", content))
    return {
        match.group(1).strip(): content[match.end(): matches[number + 1].start() if number + 1 < len(matches) else len(content)]
        for number, match in enumerate(matches)
    }


def _meaningful(body: str) -> bool:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    placeholders = {"TODO", "TBD", "待补", "占位", "待填写", "- TODO", "- TBD", "- 待补", "- 占位", "- 待填写"}
    return bool(lines) and any(line not in placeholders for line in lines)


def validate(repo_root: Path) -> dict[str, Any]:
    tasks_root = repo_root / "docs" / "tasks"
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    task_dirs = sorted(path for path in tasks_root.iterdir() if path.is_dir()) if tasks_root.is_dir() else []
    if not task_dirs:
        errors.append("未发现 docs/tasks/<task-id> 长任务文档目录。")
    for task_dir in task_dirs:
        for file_name, rule in DOC_RULES.items():
            path = task_dir / file_name
            result: dict[str, Any] = {"task_id": task_dir.name, "path": path.relative_to(repo_root).as_posix(), "kind": rule["kind"], "exists": path.is_file()}
            if not path.is_file():
                result.update(ok=False, missing_headings=[], invalid_content_headings=[])
                errors.append(f"{task_dir.relative_to(repo_root).as_posix()}: missing {file_name}")
                results.append(result)
                continue
            sections = _sections(path)
            missing = [heading for heading in rule["headings"] if heading not in sections]
            invalid = [heading for heading in rule["non_empty"] if heading in sections and not _meaningful(sections[heading])]
            result.update(ok=not missing and not invalid, missing_headings=missing, invalid_content_headings=invalid)
            errors.extend(f"{result['path']}: missing heading {heading}" for heading in missing)
            errors.extend(f"{result['path']}: empty or placeholder heading {heading}" for heading in invalid)
            results.append(result)
    return {"ok": not errors, "repo_root": str(repo_root), "checked_task_count": len(task_dirs), "errors": errors, "warnings": [], "documents": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate long-task plan, execution and acceptance documents.")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(None, Path(__file__))
        if not root.is_dir():
            raise ValueError(f"consumer_repo_root_invalid: expected an existing directory: {root}")
        payload = validate(root)
    except (OSError, ValueError) as error:
        payload = {"ok": False, "errors": [str(error)]}
    return emit(payload, as_json=args.json, success_message=f"Validation passed for {payload.get('checked_task_count', 0)} task directories")


if __name__ == "__main__":
    raise SystemExit(main())
