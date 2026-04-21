#!/usr/bin/env python3
"""Scaffold a benchmark planning bundle from the skill templates."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys


TEMPLATE_TO_OUTPUT = {
    "benchmark-plan.template.md": "benchmark-plan.md",
    "fixture-matrix.template.md": "fixture-matrix.md",
    "runbook.template.md": "runbook.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a pre-implementation benchmark bundle from the skill templates."
    )
    parser.add_argument("--output", required=True, help="Output directory for the benchmark bundle")
    parser.add_argument("--slug", required=True, help="Stable slug used in file contents and case ids")
    parser.add_argument("--title", help="Human-readable benchmark title")
    parser.add_argument(
        "--change-type",
        default="feature-or-fix",
        help="Short label such as feature, refactor, migration, skill, or workflow",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files if they already exist",
    )
    return parser.parse_args()


def title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def render_template(template_text: str, mapping: dict[str, str]) -> str:
    rendered = template_text
    for key, value in mapping.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file without --force: {path}")
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    skill_dir = Path(__file__).resolve().parent.parent
    assets_dir = skill_dir / "assets"
    output_dir = Path(args.output).resolve()
    title = args.title or title_from_slug(args.slug)
    mapping = {
        "TITLE": title,
        "SLUG": args.slug,
        "CHANGE_TYPE": args.change_type,
        "DATE": date.today().isoformat(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    created_paths: list[Path] = []
    try:
        for template_name, output_name in TEMPLATE_TO_OUTPUT.items():
            template_path = assets_dir / template_name
            template_text = template_path.read_text(encoding="utf-8")
            rendered = render_template(template_text, mapping)
            destination = output_dir / output_name
            write_file(destination, rendered, args.force)
            created_paths.append(destination)
    except FileExistsError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[ERROR] Failed to scaffold benchmark bundle: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Created benchmark bundle at {output_dir}")
    for created_path in created_paths:
        print(f"[OK] {created_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
