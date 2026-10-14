#!/usr/bin/env python3
"""Portable harness command entry point; standard library only."""
import argparse
import json
from pathlib import Path
import sys

# Imports must not add unlisted files to the immutable release or managed runtime.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.harness import bundle, lifecycle
from modules.harness.config import resolve_config
from modules.harness.errors import HarnessError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    build = commands.add_parser("build")
    build.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    for name in ("output", "version", "source-commit"):
        build.add_argument("--" + name, required=True)
    build.add_argument("--json", action="store_true")
    for name in ("install", "update", "uninstall", "recover", "doctor"):
        command = commands.add_parser(name)
        for field in ("codex-home", "skills-dir", "environment", "config"):
            command.add_argument("--" + field, action="append")
        command.add_argument("--json", action="store_true")
        if name in {"install", "update"}:
            command.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parents[1],
                                 help="Release bundle root; defaults to this script's package")
        if name in {"install", "update", "uninstall"}:
            command.add_argument("--modules")
            command.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            manifest = bundle.build_release(args.source_root, Path(args.output), args.version, args.source_commit)
            result = dict(ok=True, version=manifest["version"], source_commit=manifest["source_commit"],
                          output=str(Path(args.output).absolute()), modules=manifest["modules"])
        else:
            for name in ("codex_home", "skills_dir", "environment", "config"):
                supplied = getattr(args, name)
                if supplied is not None and len(supplied) != 1:
                    raise HarnessError("CONFIG_INVALID", "Configuration option must appear once: --" + name.replace("_", "-"))
                setattr(args, name, supplied[0] if supplied else None)
            values = {name: getattr(args, name) for name in ("codex_home", "skills_dir", "environment")
                      if getattr(args, name) is not None}
            config = resolve_config(values, Path(args.config) if args.config else None)
            options = {}
            if args.action in {"install", "update", "uninstall"}:
                options = dict(selected=args.modules.split(",") if args.modules is not None else None,
                               dry_run=args.dry_run)
            if args.action in {"install", "update"}:
                result = lifecycle.install(args.bundle, config, **options)
            else:
                result = getattr(lifecycle, args.action)(config, **options)
    except HarnessError as error:
        result = dict(ok=False, code=error.code, message=str(error))
    except OSError as error:
        result = dict(ok=False, code="IO_ERROR", message=type(error).__name__ + ": " + str(error))
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        print(("OK " if result["ok"] else "ERROR ") + json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
