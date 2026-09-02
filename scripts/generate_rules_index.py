from __future__ import annotations

import argparse
from pathlib import Path

from rules_index import artifacts_for_model, build_rules_model
from runtime_common import atomic_write, emit, resolve_repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic rules registry artifacts.")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--global-rules-root", action="append", default=[])
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_repo_root(args.repo_root, Path(__file__))
        model = build_rules_model(root, [Path(item) for item in args.global_rules_root])
        if model["errors"]:
            return emit({"ok": False, "repo_root": str(root), "errors": model["errors"], "warnings": model["warnings"]}, as_json=args.json)
        output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else root / "rules" / "registry"
        for name, content in artifacts_for_model(model).items():
            atomic_write(output_dir / name, content)
        payload = {
            "ok": True, "repo_root": str(root), "output_dir": str(output_dir),
            "local_rule_count": len(model["local_rules"]),
            "warnings": model["warnings"],
        }
        return emit(payload, as_json=args.json, success_message=f"Generated {payload['local_rule_count']} local rules")
    except (OSError, ValueError) as error:
        return emit({"ok": False, "errors": [str(error)]}, as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
