from __future__ import annotations

import argparse
from pathlib import Path

from rules_index import build_rules_model
from runtime_common import emit, resolve_repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rules frontmatter and metadata conflicts.")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--global-rules-root", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_repo_root(args.repo_root, Path(__file__))
        model = build_rules_model(root, [Path(item) for item in args.global_rules_root])
        payload = {
            "ok": not model["errors"], "repo_root": str(root),
            "local_rule_count": len(model["local_rules"]),
            "global_rule_count": len(model["global_rules"]),
            "errors": model["errors"], "warnings": model["warnings"],
        }
        return emit(payload, as_json=args.json, success_message=f"Validation passed for {payload['local_rule_count']} local rules")
    except (OSError, ValueError) as error:
        return emit({"ok": False, "errors": [str(error)]}, as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
