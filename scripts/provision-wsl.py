from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from runtime_common import command_available, emit, load_wsl_baseline, select_wsl_profile


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or explicitly apply the declared WSL tool baseline.")
    runtime_baseline = Path(__file__).parents[1] / "config/wsl-tool-baseline.json"
    source_baseline = Path(__file__).parents[1] / "config/ai/wsl-tool-baseline.json"
    parser.add_argument("--baseline", default=str(runtime_baseline if runtime_baseline.is_file() else source_baseline))
    parser.add_argument("--profile", default="developer")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload: dict[str, Any] = {
        "ok": False, "mode": "apply" if args.apply else "plan", "profile": args.profile,
        "dry_run": bool(args.dry_run), "mutated": False, "missing_packages": [],
        "planned_commands": [], "executed_commands": [], "errors": [],
    }
    baseline, validation_errors = load_wsl_baseline(Path(args.baseline))
    if validation_errors:
        payload.update(error={"category": "invalid_baseline"}, validation_errors=validation_errors)
        return emit(payload, as_json=args.json)
    profile = select_wsl_profile(baseline, args.profile)
    if profile is None:
        payload.update(error={"category": "unknown_profile"}, validation_errors=[])
        return emit(payload, as_json=args.json)
    missing = [package for package in profile["packages"] if not command_available(package)]
    payload["missing_packages"] = sorted(package["name"] for package in missing)
    apt_missing = [package["name"] for package in missing if package["source"] == "apt"]
    external_missing = [package["name"] for package in missing if package["source"] != "apt"]
    if apt_missing:
        payload["planned_commands"] = [["apt-get", "install", "-y", "--", *apt_missing]]
    if external_missing:
        payload["handoff"] = {
            "owner": "machine_external",
            "prerequisite": "Provide a Linux-native pnpm executable in the current WSL distribution.",
            "next_action": "Use the approved external runtime or package source to install pnpm, then rerun this read-only plan.",
        }
    if args.apply and not args.dry_run:
        if external_missing:
            payload.update(error={"category": "unprovisionable_baseline", "packages": external_missing})
            return emit(payload, as_json=args.json)
        if apt_missing:
            command = payload["planned_commands"][0]
            try:
                completed = subprocess.run(command, text=True, capture_output=True, check=False)
            except OSError as error:
                payload.update(error={"category": "provision_failed", "message": str(error)})
                return emit(payload, as_json=args.json)
            if completed.returncode:
                payload.update(error={"category": "provision_failed", "returncode": completed.returncode})
                return emit(payload, as_json=args.json)
            payload["executed_commands"].append(command)
            payload["mutated"] = True
            still_missing = [package["name"] for package in profile["packages"] if not command_available(package)]
            if still_missing:
                payload.update(missing_packages=sorted(still_missing), error={"category": "provision_failed", "message": "post_install_probe_failed"})
                return emit(payload, as_json=args.json)
    payload["ok"] = True
    return emit(payload, as_json=args.json, success_message="WSL baseline plan completed")


if __name__ == "__main__":
    raise SystemExit(main())
