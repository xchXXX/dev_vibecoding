from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = REPO_ROOT / "skills" / "command-failure-memory" / "scripts" / "command-failure-memory.py"


def load_backend():
    spec = importlib.util.spec_from_file_location("command_failure_memory", BACKEND_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load backend: {BACKEND_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BACKEND = load_backend()


class CommandFailureMemoryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_root = REPO_ROOT / ".tmp"
        temporary_root.mkdir(exist_ok=True)
        self.tempdir = tempfile.TemporaryDirectory(prefix="cfm-contract-", dir=temporary_root)
        self.addCleanup(self.tempdir.cleanup)
        self.codex_home = Path(self.tempdir.name) / "codex-home"
        self.memory_root = self.codex_home / "memories" / "command-failure-memory"

    def invoke(self, action: str, **values: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        args = self.action_args(action, **values)
        result = subprocess.run(
            [sys.executable, str(BACKEND_PATH), *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False
        )
        payload = json.loads(result.stdout) if result.returncode == 0 else {}
        return result, payload

    def action_args(self, action: str, **values: str) -> list[str]:
        args = ["--action", action, "--codex-home", str(self.codex_home), "--json"]
        option_names = {
            "project": "--project-id",
            "command": "--command-text",
            "error": "--error-text",
            "resolution": "--resolution",
            "scope_kind": "--scope-kind",
            "scope_confidence": "--scope-confidence",
            "scope_reason": "--scope-reason",
        }
        for key, value in values.items():
            args.extend([option_names[key], str(value)])
        return args

    def invoke_with_fast_fixture_paths(self, action: str, **values: str) -> tuple[int, str, dict]:
        """Exercise the real action while skipping unrelated repeated canonical-path I/O in the 1024-case fixture."""
        stdout = io.StringIO()
        argv = [str(BACKEND_PATH), *self.action_args(action, **values)]
        direct_case_path = lambda cases_root, case_id: str(Path(cases_root) / f"{case_id}.json")
        try:
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(BACKEND, "resolve_case_file_path", side_effect=direct_case_path),
                contextlib.redirect_stdout(stdout),
            ):
                return_code = BACKEND.main()
        except BACKEND.MemoryErrorRuntime as exc:
            return 1, str(exc), {}
        output = stdout.getvalue()
        return return_code, "", json.loads(output)

    def seed_v1_case(
        self,
        ordinal: int,
        *,
        signature: str | None = None,
        command_signature: str | None = None,
        error_signature: str | None = None,
        created_at: str = "2021-01-01T00:00:00+00:00",
    ) -> dict:
        case_id = f"CASE-{ordinal:016x}"
        case = {
            "schema_version": "1.0",
            "case_id": case_id,
            "signature": signature or f"{ordinal:064x}",
            "command_signature": command_signature or f"seed command {ordinal}",
            "error_signature": error_signature or f"seed error {ordinal}",
            "command_excerpt": command_signature or f"seed command {ordinal}",
            "error_excerpt": error_signature or f"seed error {ordinal}",
            "scope_kind": "global",
            "scope_confidence": 0.9,
            "scope_reason": "seeded legacy case",
            "projects_seen": ["seed-project"],
            "solution": "seeded solution",
            "stats": {"hit_count": 0, "verify_count": 1, "incident_count": 1},
            "created_at": created_at,
            "updated_at": created_at,
            "last_verified_at": created_at,
            "last_hit_at": "",
        }
        cases_root = self.memory_root / "cases"
        cases_root.mkdir(parents=True, exist_ok=True)
        (cases_root / f"{case_id}.json").write_text(json.dumps(case), encoding="utf-8")
        return case

    def seed_v1_index(self, cases: list[dict]) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        entries = [
            {
                "case_id": case["case_id"],
                "signature": case["signature"],
                "scope_kind": case["scope_kind"],
                "scope_confidence": case["scope_confidence"],
                "scope_reason": case["scope_reason"],
                "projects_seen": case["projects_seen"],
                "stats": case["stats"],
                "created_at": case["created_at"],
                "updated_at": case["updated_at"],
                **(
                    {"storage_tier": case["storage_tier"]}
                    if "storage_tier" in case
                    else {}
                ),
            }
            for case in cases
        ]
        (self.memory_root / "index.json").write_text(
            json.dumps({"schema_version": "1.0", "updated_at": "", "cases": entries}),
            encoding="utf-8",
        )

    def test_codex_home_environment_keeps_the_windows_visible_store_identity(self) -> None:
        # Break caught: silently falling back to /home/<user>/.codex creates a second memory store.
        with mock.patch.dict(os.environ, {"CODEX_HOME": "/mnt/c/Users/Laptop/.codex"}, clear=False):
            codex_home = BACKEND.get_default_codex_home()
        memory_root = Path(codex_home) / "memories" / "command-failure-memory"
        self.assertEqual(memory_root.as_posix(), "/mnt/c/Users/Laptop/.codex/memories/command-failure-memory")
        self.assertEqual(
            memory_root.as_posix().replace("/mnt/c/", "C:/", 1),
            "C:/Users/Laptop/.codex/memories/command-failure-memory",
        )

    def test_cli_success_counts_each_verified_event_once(self) -> None:
        values = dict(project="counter-project", command="python3 check.py --mode strict", error="invalid schema")
        observed_counts = []
        case_ids = []
        for ordinal in (1, 2):
            failed, failure = self.invoke("record-failure", **values)
            self.assertEqual(failed.returncode, 0, failed.stderr)
            self.assertTrue(failure["query_should_happen_before_retry"])
            queried, query = self.invoke("query-before-retry", **values)
            self.assertEqual(queried.returncode, 0, queried.stderr)
            self.assertTrue(query["query_permitted"])
            succeeded, success = self.invoke("record-success", **values, resolution="Repair schema and verify it", scope_kind="project")
            self.assertEqual(succeeded.returncode, 0, succeeded.stderr)
            self.assertEqual(success["created_new_case"], ordinal == 1)
            case_ids.append(success["case_id"])
            body = json.loads((self.memory_root / "cases" / f"{success['case_id']}.json").read_text())
            self.assertEqual(success["stats"], body["stats"])
            observed_counts.append(body["stats"]["verify_count"])
            inspected, snapshot = self.invoke("inspect")
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(snapshot["pending_failure_count"], 0)
        self.assertEqual(case_ids[0], case_ids[1])
        self.assertEqual(observed_counts, [1, 2])

    def test_cli_new_verified_resolution_replaces_adopted_solution(self) -> None:
        values = dict(project="solution-project", command="python3 build.py", error="dependency missing")
        case_ids = []
        for resolution in ("Install dependency in system interpreter", "Install declared dependency in project interpreter"):
            for action in ("record-failure", "query-before-retry"):
                result, _ = self.invoke(action, **values)
                self.assertEqual(result.returncode, 0, result.stderr)
            result, payload = self.invoke("record-success", **values, resolution=resolution, scope_kind="project")
            self.assertEqual(result.returncode, 0, result.stderr)
            case_ids.append(payload["case_id"])
        self.assertEqual(case_ids[0], case_ids[1])
        result, _ = self.invoke("record-failure", **values)
        self.assertEqual(result.returncode, 0, result.stderr)
        result, payload = self.invoke("query-before-retry", **values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(payload["suggestions"]), 1)
        self.assertEqual(payload["suggestions"][0]["solution"], resolution)
        body = json.loads((self.memory_root / "cases" / f"{case_ids[0]}.json").read_text())
        self.assertEqual(body["solution"], resolution)

    def test_cli_temporary_directory_noise_has_one_failure_signature(self) -> None:
        signatures = []
        for directory in ("/tmp/tmpa1b2c3d4", "/tmp/tmpw9x8y7z6"):
            result, payload = self.invoke("record-failure", project="noise-project",
                command=f"python3 {directory}/check.py --mode strict",
                error=f"FileNotFoundError: {directory}/schema.json")
            self.assertEqual(result.returncode, 0, result.stderr)
            signatures.append(payload["signature"])
        self.assertEqual(signatures[0], signatures[1])

    def test_cli_semantic_parameters_paths_and_faults_remain_distinct(self) -> None:
        pairs = (
            (("tool --mode strict", "bad input"), ("tool --mode relaxed", "bad input")),
            (("tool --schema /srv/app/a.json", "bad input"), ("tool --schema /srv/app/b.json", "bad input")),
            (("tool --name Customer", "bad input"), ("tool --name customer", "bad input")),
            (("tool", "Traceback (most recent call last):\nValueError: bad field"),
             ("tool", "Traceback (most recent call last):\nPermissionError: access denied")),
            (("tool /tmp/tmpa1b2c3d4/a.json", "bad input"), ("tool /tmp/tmpw9x8y7z6/b.json", "bad input")),
        )
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                signatures = []
                for command, error in (left, right):
                    result, payload = self.invoke("record-failure", project="semantic-project", command=command, error=error)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    signatures.append(payload["signature"])
                self.assertNotEqual(signatures[0], signatures[1])

    def test_cli_unrelated_write_preserves_unique_legacy_records_and_scopes(self) -> None:
        legacy_cases = [self.seed_v1_case(index) for index in range(4)]
        before = {}
        for case, scope in zip(legacy_cases, ("global", "project", "candidate_global", "candidate_project")):
            case["scope_kind"] = scope
            case["solution"] = f"unique solution for {scope}"
            path = self.memory_root / "cases" / f"{case['case_id']}.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            before[path] = path.read_bytes()
        self.seed_v1_index(legacy_cases)
        values = dict(project="new-project", command="new independent command", error="new independent failure")
        for action in ("record-failure", "query-before-retry"):
            result, _ = self.invoke(action, **values)
            self.assertEqual(result.returncode, 0, result.stderr)
        result, _ = self.invoke("record-success", **values, resolution="new repair", scope_kind="project")
        self.assertEqual(result.returncode, 0, result.stderr)
        result, payload = self.invoke("inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["case_count"], 5)
        for path, original in before.items():
            self.assertEqual(path.read_bytes(), original)
        indexed = {case["case_id"]: case for case in payload["cases"]}
        for case in legacy_cases:
            self.assertEqual(indexed[case["case_id"]]["scope_kind"], case["scope_kind"])

    def test_cli_fixed_legacy_signature_remains_queryable_after_normalization_changes(self) -> None:
        # Frozen pre-convergence v1 signature: lowercased command + first error line.
        # Never derive this historical fixture with the current backend signature code.
        command = "python3 /tmp/tmpa1b2c3d4/check.py --name Customer"
        error = "Traceback (most recent call last):\nValueError: invalid customer"
        legacy = self.seed_v1_case(77,
            signature="d3090ab9012441b5ac0bded1440e22b8a40576d265c00ef121bf318c5e551ac4",
            command_signature="python3 /tmp/tmpa1b2c3d4/check.py --name customer",
            error_signature="traceback (most recent call last):")
        legacy["command_excerpt"] = command
        legacy["error_excerpt"] = error
        legacy["solution"] = "Repair the customer field using the legacy validated schema"
        path = self.memory_root / "cases" / f"{legacy['case_id']}.json"
        path.write_text(json.dumps(legacy), encoding="utf-8")
        self.seed_v1_index([legacy])
        values = dict(project="legacy-project", command=command, error=error)
        failed, _ = self.invoke("record-failure", **values)
        self.assertEqual(failed.returncode, 0, failed.stderr)
        queried, payload = self.invoke("query-before-retry", **values)
        self.assertEqual(queried.returncode, 0, queried.stderr)
        self.assertEqual([legacy["case_id"]], [row["case_id"] for row in payload["suggestions"]])
        self.assertEqual(legacy["solution"], payload["suggestions"][0]["solution"])
        stored = json.loads(path.read_text())
        for field in ("solution", "scope_kind", "created_at", "command_excerpt", "error_excerpt"):
            self.assertEqual(legacy[field], stored[field])

    def assert_legacy_collision_does_not_adopt_or_overwrite(self, *, signature, old_command,
                                                         old_error, command, error):
        legacy = self.seed_v1_case(88, signature=signature,
            command_signature=old_command.lower(), error_signature=old_error.split("\n", 1)[0].lower())
        legacy.update(command_excerpt=old_command, error_excerpt=old_error,
                      solution="Distinct legacy validated repair")
        path = self.memory_root / "cases" / f"{legacy['case_id']}.json"
        path.write_text(json.dumps(legacy), encoding="utf-8")
        self.seed_v1_index([legacy])
        values = dict(project="collision-project", command=command, error=error)
        failed, _ = self.invoke("record-failure", **values)
        self.assertEqual(0, failed.returncode, failed.stderr)
        queried, payload = self.invoke("query-before-retry", **values)
        self.assertEqual(0, queried.returncode, queried.stderr)
        with self.subTest(boundary="query-must-not-adopt-different-legacy-evidence"):
            self.assertNotIn(legacy["case_id"], [row["case_id"] for row in payload["suggestions"]])
        succeeded, result = self.invoke("record-success", **values,
            resolution="Verified repair for the distinct new request", scope_kind="project")
        self.assertEqual(0, succeeded.returncode, succeeded.stderr)
        with self.subTest(boundary="success-must-create-distinct-case"):
            self.assertTrue(result["created_new_case"], result)
            self.assertNotEqual(legacy["case_id"], result["case_id"])
        stored = json.loads(path.read_text())
        with self.subTest(boundary="success-must-preserve-legacy-solution-and-verifications"):
            for field in ("solution", "command_excerpt", "error_excerpt", "scope_kind", "last_verified_at"):
                self.assertEqual(legacy[field], stored[field], field)
            self.assertEqual(legacy["stats"]["verify_count"], stored["stats"]["verify_count"])

    def test_cli_legacy_lowercase_hash_collision_cannot_adopt_or_overwrite_customer_case(self) -> None:
        self.assert_legacy_collision_does_not_adopt_or_overwrite(
            signature="653d9074d83cf3fc46777565c0f04e7f81890ba673b933905bc08067d1f81b0e",
            old_command="tool --name Customer", old_error="bad input",
            command="tool --name customer", error="bad input")

    def test_cli_legacy_traceback_hash_cannot_adopt_or_overwrite_different_exception(self) -> None:
        self.assert_legacy_collision_does_not_adopt_or_overwrite(
            signature="b4122632370cea687fd17aa44eb835542fc47b7530e430a0e928fd7c3bbc1ed5",
            old_command="tool", old_error="Traceback (most recent call last):\nValueError: bad field",
            command="tool", error="Traceback (most recent call last):\nPermissionError: access denied")

    def test_cli_legacy_traceback_header_hash_cannot_adopt_or_overwrite_full_exception(self) -> None:
        self.assert_legacy_collision_does_not_adopt_or_overwrite(
            signature="b4122632370cea687fd17aa44eb835542fc47b7530e430a0e928fd7c3bbc1ed5",
            old_command="tool", old_error="Traceback (most recent call last):\nValueError: bad field",
            command="tool", error="traceback (most recent call last):")

    def test_legacy_v1_case_remains_queryable_in_place(self) -> None:
        # Break caught: an in-place format upgrade moves or stops reading the existing case files.
        command = "legacy failing command"
        error = "legacy error"
        signature = BACKEND.get_case_signature(command, error)
        legacy = self.seed_v1_case(
            1,
            signature=signature["signature"],
            command_signature=signature["command_signature"],
            error_signature=signature["error_signature"],
            created_at="2020-01-01T00:00:00+00:00",
        )
        self.seed_v1_index([legacy])

        failed, _ = self.invoke("record-failure", project="legacy-project", command=command, error=error)
        queried, payload = self.invoke("query-before-retry", project="legacy-project", command=command, error=error)

        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(queried.returncode, 0, queried.stderr)
        self.assertEqual(payload["memory_root"], str(self.memory_root))
        self.assertEqual([item["case_id"] for item in payload["suggestions"]], [legacy["case_id"]])
        self.assertTrue((self.memory_root / "cases" / f"{legacy['case_id']}.json").exists())

    def test_pending_failures_are_not_dropped_after_128(self) -> None:
        # Break caught: the pending queue trims unresolved failures to MAX_PENDING_FAILURE_EVENTS.
        runtime_root = self.memory_root / "runtime"
        runtime_root.mkdir(parents=True, exist_ok=True)
        events = [
            {
                "signature": f"{index:064x}",
                "command_signature": f"pending command {index}",
                "error_signature": f"pending error {index}",
                "project_id": "pending-project",
                "first_failed_at": f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}+00:00",
                "last_failed_at": f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}+00:00",
                "failure_count": 1,
                "last_query_at": "",
            }
            for index in range(128)
        ]
        events_path = runtime_root / "failure-events.json"
        events_path.write_text(json.dumps({"schema_version": "1.0", "updated_at": "", "events": events}), encoding="utf-8")

        result, _ = self.invoke(
            "record-failure",
            project="pending-project",
            command="the 129th pending command",
            error="the 129th pending error",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        stored = json.loads(events_path.read_text(encoding="utf-8"))["events"]
        self.assertEqual(len(stored), 129)
        self.assertEqual({entry["command_signature"] for entry in stored}, {entry["command_signature"] for entry in events} | {"the 129th pending command"})

    def test_record_success_requires_a_non_empty_resolution(self) -> None:
        result, _ = self.invoke(
            "record-success",
            project="resolution-project",
            command="resolved command",
            error="resolved error",
            resolution="   ",
            scope_kind="global",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("resolution", result.stderr.lower())
        self.assertFalse((self.memory_root / "index.json").exists())

    def test_gnu_long_options_match_the_documented_cli(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(BACKEND_PATH),
                "--action",
                "record-success",
                "--codex-home",
                str(self.codex_home),
                "--project-id",
                "gnu-project",
                "--command-text",
                "gnu command",
                "--error-text",
                "gnu error",
                "--resolution",
                "gnu resolution",
                "--scope-kind",
                "candidate_global",
                "--scope-confidence",
                "0.7",
                "--scope-reason",
                "gnu contract",
                "--project-specific",
                "--json",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "record-success")
        self.assertEqual(payload["project_id"], "gnu-project")

    def test_parser_rejects_single_dash_pascal_case_aliases(self) -> None:
        # Break caught: the retired PowerShell parameter spellings remain valid
        # alongside the documented GNU CLI and silently preserve two contracts.
        aliases = (
            "-Action", "-CodexHome", "-ProjectId", "-CommandText", "-ErrorText",
            "-Resolution", "-ScopeKind", "-ScopeConfidence", "-ScopeReason",
            "-ProjectSpecific", "-Json",
        )
        accepted: list[str] = []
        for alias in aliases:
            if alias == "-Action":
                arguments = [alias, "inspect"]
            elif alias in {"-ProjectSpecific", "-Json"}:
                arguments = ["--action", "inspect", alias]
            else:
                value = "0.5" if alias == "-ScopeConfidence" else "alias-value"
                arguments = ["--action", "inspect", alias, value]
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    BACKEND.build_parser().parse_args(arguments)
                except SystemExit:
                    continue
            accepted.append(alias)
        self.assertEqual([], accepted, f"CFM still accepts single-dash aliases: {accepted}")

    @unittest.skipUnless(os.name == "posix", "fcntl locking is a POSIX/WSL contract")
    def test_linux_processes_serialize_on_the_same_store_lock(self) -> None:
        # Break caught: the POSIX path invokes callbacks without acquiring an inter-process lock.
        lock_root = Path(self.tempdir.name) / "shared-store"
        lock_root.mkdir()
        child_code = textwrap.dedent(
            """
            import importlib.util
            import sys
            import time

            spec = importlib.util.spec_from_file_location("cfm_child", sys.argv[1])
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            def hold_lock():
                print("LOCKED", flush=True)
                time.sleep(1.0)

            module.invoke_with_memory_lock(sys.argv[2], hold_lock)
            """
        )
        child = subprocess.Popen(
            [sys.executable, "-c", child_code, str(BACKEND_PATH), str(lock_root)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(lambda: child.poll() is None and child.kill())
        self.assertEqual(child.stdout.readline().strip(), "LOCKED")

        started = time.monotonic()
        BACKEND.invoke_with_memory_lock(str(lock_root), lambda: None)
        elapsed = time.monotonic() - started
        stdout, stderr = child.communicate(timeout=3)

        self.assertEqual(child.returncode, 0, stdout + stderr)
        self.assertGreaterEqual(elapsed, 0.70)

    def test_atomic_json_replace_never_exposes_partial_json(self) -> None:
        # Break caught: direct writes expose truncated JSON when writers overlap or a process stops mid-write.
        target = Path(self.tempdir.name) / "atomic" / "state.json"
        worker_code = textwrap.dedent(
            """
            import importlib.util
            import sys

            spec = importlib.util.spec_from_file_location("cfm_writer", sys.argv[1])
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for ordinal in range(30):
                module.write_json_object(sys.argv[2], {"writer": sys.argv[3], "ordinal": ordinal, "payload": "x" * 2048})
            """
        )
        writers = [
            subprocess.Popen([sys.executable, "-c", worker_code, str(BACKEND_PATH), str(target), str(index)], cwd=REPO_ROOT)
            for index in range(4)
        ]
        for writer in writers:
            self.assertEqual(writer.wait(timeout=10), 0)

        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertIn(payload["writer"], {"0", "1", "2", "3"})
        self.assertEqual(payload["ordinal"], 29)
        self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_inspect_uses_index_without_loading_case_bodies(self) -> None:
        cases = [self.seed_v1_case(index) for index in range(32)]
        self.seed_v1_index(cases)
        original_read = BACKEND.read_json_object
        case_reads: list[str] = []

        def counted_read(path_value: str, default_value):
            if Path(path_value).parent == self.memory_root / "cases":
                case_reads.append(path_value)
            return original_read(path_value, default_value)

        with mock.patch.object(BACKEND, "read_json_object", side_effect=counted_read):
            code, error, payload = self.invoke_with_fast_fixture_paths("inspect")

        self.assertEqual(code, 0, error)
        self.assertEqual(payload["case_count"], 32)
        self.assertEqual(case_reads, [])

    def test_exact_query_reads_and_writes_only_the_matching_case_body(self) -> None:
        command = "target exact command"
        error = "target exact error"
        signature = BACKEND.get_case_signature(command, error)
        target = self.seed_v1_case(
            0,
            signature=signature["signature"],
            command_signature=signature["command_signature"],
            error_signature=signature["error_signature"],
        )
        cases = [target, *(self.seed_v1_case(index) for index in range(1, 32))]
        self.seed_v1_index(cases)
        failed, _ = self.invoke("record-failure", project="target-project", command=command, error=error)
        self.assertEqual(failed.returncode, 0, failed.stderr)

        original_read = BACKEND.read_json_object
        original_write = BACKEND.write_json_object
        case_reads: list[str] = []
        case_writes: list[str] = []

        def counted_read(path_value: str, default_value):
            if Path(path_value).parent == self.memory_root / "cases":
                case_reads.append(path_value)
            return original_read(path_value, default_value)

        def counted_write(path_value: str, data):
            if Path(path_value).parent == self.memory_root / "cases":
                case_writes.append(path_value)
            return original_write(path_value, data)

        with (
            mock.patch.object(BACKEND, "read_json_object", side_effect=counted_read),
            mock.patch.object(BACKEND, "write_json_object", side_effect=counted_write),
        ):
            code, query_error, payload = self.invoke_with_fast_fixture_paths(
                "query-before-retry", project="target-project", command=command, error=error
            )

        expected_path = str(self.memory_root / "cases" / f"{target['case_id']}.json")
        self.assertEqual(code, 0, query_error)
        self.assertEqual([item["case_id"] for item in payload["suggestions"]], [target["case_id"]])
        self.assertEqual(case_reads, [expected_path])
        self.assertEqual(case_writes, [expected_path])

    def test_full_active_set_archives_cold_case_and_archive_hit_reactivates_it(self) -> None:
        # Break caught: reaching 1024 active cases rejects a valid new verified solution.
        archived_command = "old exact command"
        archived_error = "old exact error"
        archived_signature = BACKEND.get_case_signature(archived_command, archived_error)
        cases = [
            self.seed_v1_case(
                0,
                signature=archived_signature["signature"],
                command_signature=archived_signature["command_signature"],
                error_signature=archived_signature["error_signature"],
                created_at="2020-01-01T00:00:00+00:00",
            )
        ]
        cases.extend(self.seed_v1_case(index) for index in range(1, 1028))
        for case in cases[1024:]:
            case["storage_tier"] = "archived"
            (self.memory_root / "cases" / f"{case['case_id']}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )
        self.seed_v1_index(cases)

        original_read = BACKEND.read_json_object
        original_write = BACKEND.write_json_object
        case_reads: list[str] = []
        case_writes: list[str] = []

        def counted_read(path_value: str, default_value):
            if Path(path_value).parent == self.memory_root / "cases":
                case_reads.append(path_value)
            return original_read(path_value, default_value)

        def counted_write(path_value: str, data):
            if Path(path_value).parent == self.memory_root / "cases":
                case_writes.append(path_value)
            return original_write(path_value, data)

        record_started = time.monotonic()
        with (
            mock.patch.object(BACKEND, "read_json_object", side_effect=counted_read),
            mock.patch.object(BACKEND, "write_json_object", side_effect=counted_write),
        ):
            record_code, record_error, record_payload = self.invoke_with_fast_fixture_paths(
                "record-success",
                project="new-project",
                command="new verified command",
                error="new verified error",
                resolution="new verified resolution",
                scope_kind="global",
            )
        record_elapsed = time.monotonic() - record_started
        self.assertEqual(record_code, 0, record_error)
        self.assertTrue(record_payload["created_new_case"])
        self.assertLess(record_elapsed, 5.0)
        self.assertEqual(len(case_reads), 1)
        self.assertEqual(len(case_writes), 2)

        inspect_code, inspect_error, inspect_payload = self.invoke_with_fast_fixture_paths("inspect")
        self.assertEqual(inspect_code, 0, inspect_error)
        self.assertEqual(inspect_payload["case_count"], 1029)
        self.assertLessEqual(inspect_payload["active_case_count"], 1024)
        self.assertGreaterEqual(inspect_payload["archived_case_count"], 1)

        failed_code, failed_error, _ = self.invoke_with_fast_fixture_paths(
            "record-failure", project="archive-project", command=archived_command, error=archived_error
        )
        query_code, query_error, query_payload = self.invoke_with_fast_fixture_paths(
            "query-before-retry", project="archive-project", command=archived_command, error=archived_error
        )
        self.assertEqual(failed_code, 0, failed_error)
        self.assertEqual(query_code, 0, query_error)
        self.assertEqual([item["case_id"] for item in query_payload["suggestions"]], [cases[0]["case_id"]])
        self.assertTrue(query_payload["suggestions"][0]["reactivated"])
        self.assertEqual(query_payload["suggestions"][0]["storage_tier"], "active")

    def test_full_active_set_can_archive_legacy_unsolved_cases_for_a_valid_new_solution(self) -> None:
        cases = [self.seed_v1_case(index) for index in range(2)]
        for case in cases:
            case["solution"] = ""
            (self.memory_root / "cases" / f"{case['case_id']}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )
        self.seed_v1_index(cases)

        with mock.patch.object(BACKEND, "MAX_CASE_COUNT", 2):
            code, error, payload = self.invoke_with_fast_fixture_paths(
                "record-success",
                project="new-solved-project",
                command="new solved command",
                error="new solved error",
                resolution="verified resolution",
                scope_kind="global",
            )
            inspect_code, inspect_error, inspected = self.invoke_with_fast_fixture_paths("inspect")

        self.assertEqual(code, 0, error)
        self.assertTrue(payload["created_new_case"])
        self.assertEqual(inspect_code, 0, inspect_error)
        self.assertEqual(inspected["case_count"], 3)
        self.assertEqual(inspected["active_case_count"], 2)
        self.assertEqual(inspected["archived_case_count"], 1)
        archived = [entry for entry in inspected["cases"] if entry["storage_tier"] == "archived"]
        self.assertEqual(len(archived), 1)
        archived_body = json.loads(
            (self.memory_root / "cases" / f"{archived[0]['case_id']}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(archived_body["solution"], "")
        self.assertEqual(archived_body["archive_reason"], "capacity_unresolved")


if __name__ == "__main__":
    unittest.main()
