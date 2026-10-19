from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from runtime_common import emit


WINDOWS_DRIVE_PATH = re.compile(r"^([A-Za-z]):[\\/]+(.*)$")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert one explicit Windows drive path to its WSL path.")
    parser.add_argument("--path", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.path.startswith("\\\\"):
        payload: dict[str, Any] = {"ok": False, "exists": False, "wsl_path": "", "error": {"category": "unsupported_windows_path"}}
        return emit(payload, as_json=args.json)
    match = WINDOWS_DRIVE_PATH.fullmatch(args.path)
    if not match:
        payload: dict[str, Any] = {"ok": False, "exists": False, "wsl_path": "", "error": {"category": "malformed_windows_path"}}
        return emit(payload, as_json=args.json)
    _, remainder = match.groups()
    segments = [segment for segment in remainder.replace("\\", "/").split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        payload = {"ok": False, "exists": False, "wsl_path": "", "error": {"category": "path_traversal"}}
        return emit(payload, as_json=args.json)
    converter = shutil.which("wslpath")
    if not converter:
        payload = {"ok": False, "exists": False, "wsl_path": "", "error": {"category": "wslpath_unavailable"}}
        return emit(payload, as_json=args.json)
    try:
        converted = subprocess.run([converter, "-u", args.path], text=True, capture_output=True, check=False)
    except OSError:
        converted = None
    if converted is None or converted.returncode:
        payload = {"ok": False, "exists": False, "wsl_path": "", "error": {"category": "wslpath_failed"}}
        return emit(payload, as_json=args.json)
    output = converted.stdout.strip()
    if not output or "\n" in output or not Path(output).is_absolute():
        payload = {"ok": False, "exists": False, "wsl_path": "", "error": {"category": "wslpath_invalid_output"}}
        return emit(payload, as_json=args.json)
    candidate = Path(output)
    payload = {"ok": candidate.exists(), "exists": candidate.exists(), "wsl_path": str(candidate)}
    if not candidate.exists():
        payload["error"] = {"category": "path_not_found"}
    return emit(payload, as_json=args.json, success_message="Windows path resolved")


if __name__ == "__main__":
    raise SystemExit(main())
