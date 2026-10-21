"""Real CLI recovery tests: release occupancy without claiming task completion.

Fixtures and raw invocation logs stay under this task's QA evidence directory.
No production repositories, credentials, or business services are involved.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "scripts/task_workspace.py"
QA = ROOT / ".artifacts/20261021-task-binding-release/qa"
POLICY = {"schema_version": 1, "remote": "origin", "main_branch": "main",
          "task_prefixes": ["codex/fix-"], "reserved_branches": {},
          "release_tag_pattern": "release/[0-9]+", "merge_method": "merge",
          "cleanup_mode": "report-only"}


class RecoveryCliTests(unittest.TestCase):
    def setUp(self):
        self.base = QA / "runs" / (self._testMethodName + "-" + uuid.uuid4().hex)
        self.repo = self.base / "consumer"
        self.repo.mkdir(parents=True)
        self.seq = 0
        self.task_id = "fixture-history"
        self.owner = "synthetic-recovery-coordinator"
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Synthetic Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("config/ai/git-policy.json", POLICY)
        self.write(".gitignore", ".tmp/\n.artifacts/\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("switch", "-c", "codex/fix-fixture")

    def write(self, path, value, repo=None):
        target = (repo or self.repo) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value if isinstance(value, str) else
                          json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def run_command(self, args):
        run = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                             timeout=60, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                              "GIT_TERMINAL_PROMPT": "0"})
        self.seq += 1
        (self.base / f"{self.seq:03d}.json").write_text(json.dumps({
            "command": [str(a) for a in args], "returncode": run.returncode,
            "stdout": run.stdout, "stderr": run.stderr}, indent=2), encoding="utf-8")
        return run

    def git(self, *args, repo=None):
        run = self.run_command(["git", "-C", repo or self.repo, *args])
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return run.stdout.strip()

    def cli(self, action, *extra, repo=None, success=True):
        args = [sys.executable, ENTRY, "--repo-root", repo or self.repo,
                "--action", action, "--json"]
        if action != "inspect":
            args += ["--task-id", self.task_id, "--coordinator", self.owner]
        run = self.run_command(args + list(extra))
        if success:
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        else:
            self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        return json.loads(run.stdout)

    @property
    def index_path(self):
        return self.repo / ".git/ai-harness/task-bindings.json"

    def index(self):
        return json.loads(self.index_path.read_text())

    def controls(self):
        paths = [*self.repo.glob("docs/**/*"), *self.repo.glob(".git/ai-harness/**/*")]
        return {str(p.relative_to(self.repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in paths if p.is_file()}

    def setup_history(self, *, archived=False, gto=False):
        origin = self.repo
        if archived:
            origin = self.base / "old-checkout"
            self.git("worktree", "add", "-b", "codex/fix-old", origin)
        if gto:
            from test_gto_workflow import workflow_contract
            self.task_id = "20310102-030405-gto-history"
            contract = self.write(".tmp/contract.json", workflow_contract(), repo=origin)
            run = self.run_command([sys.executable,
                ROOT / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py",
                "--repo-root", origin, "--task-id", self.task_id, "--action", "init-task",
                "--title", "Synthetic historical task", "--owner", self.owner,
                "--contract-json-file", contract, "--json"])
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.cli("register-gto", repo=origin)
            self.record_relative = f"docs/ai/tasks/{self.task_id}/state.json"
        else:
            self.cli("begin", "--title", "Synthetic historical task", repo=origin)
            self.record_relative = f"docs/tasks/{self.task_id}/task.json"
        self.git("add", ".", repo=origin)
        self.git("commit", "-m", "preserved historical task", repo=origin)
        self.origin = origin
        self.original_binding = copy.deepcopy(self.index()["bindings"][self.task_id])
        if archived:
            self.git("merge", "--ff-only", self.git("rev-parse", "HEAD", repo=origin))
            self.git("worktree", "remove", origin)
        self.record_path = self.repo / self.record_relative
        self.original_record = self.record_path.read_bytes()
        self.write(".artifacts/recovery/authorization.txt", "Synthetic user explicitly authorizes release only.")
        self.write(".artifacts/recovery/original-evidence.txt", "Synthetic work stopped; not a completion claim.")
        self.evidence = {
            "actor": self.owner, "summary": "Release historical occupancy, retain unfinished state",
            "authorization": ".artifacts/recovery/authorization.txt",
            "evidence": [".artifacts/recovery/original-evidence.txt"],
            "original_binding": self.original_binding,
            "preserved_record": self.record_relative,
            "record_sha256": hashlib.sha256(self.original_record).hexdigest(),
        }
        self.save_evidence()

    def save_evidence(self):
        self.write(".artifacts/recovery/release.json", self.evidence)

    def release(self, *, success=True, omit=None):
        args = {"basis": ["--basis", "Synthetic explicit authorization to release"],
                "stopped": ["--writes-stopped"],
                "evidence": ["--evidence", ".artifacts/recovery/release.json"]}
        return self.cli("recover-release", *(a for k, values in args.items()
                         if k != omit for a in values), success=success)

    def assert_available_preserved(self):
        result = self.cli("inspect")
        self.assertEqual(result["decision"], "available")
        self.assertIn(self.task_id, json.dumps(result["released_tasks"]))
        self.assertIn("active", json.dumps(result["released_tasks"]))
        self.assertEqual(self.record_path.read_bytes(), self.original_record)
        row = self.index()["bindings"][self.task_id]
        self.assertEqual({k: row[k] for k in self.original_binding}, self.original_binding)
        self.assertTrue(list((self.repo / ".git/ai-harness/task-releases").glob("*.json")))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_archived_ordinary_release_preserves_record_and_git_refs(self):
        self.setup_history(archived=True)
        before = self.cli("inspect", success=False)
        self.assertIn("BINDING_INVALID", before["errors"])
        refs = self.git("show-ref")
        self.release()
        self.assert_available_preserved()
        self.assertEqual(self.git("show-ref"), refs)

    def test_current_gto_release_preserves_frozen_state_and_reports_active(self):
        self.setup_history(gto=True)
        self.assertEqual(self.cli("inspect")["decision"], "occupied")
        frozen = self.controls()
        self.release()
        self.assert_available_preserved()
        for path, sha in frozen.items():
            if path.startswith("docs/"):
                self.assertEqual(self.controls()[path], sha)
        self.assertFalse((self.repo / f"docs/tasks/{self.task_id}/task.json").exists())

    def test_released_task_cannot_resume_or_mutate_or_release_twice(self):
        self.setup_history()
        self.release()
        snapshot = self.controls()
        for action in ("resume", "check", "complete", "register-gto"):
            with self.subTest(action=action):
                self.cli(action, success=False)
                self.assertEqual(self.controls(), snapshot)
        self.cli("adopt", "--basis", "Must not revive", success=False)
        self.cli("record-stage", "--stage", "investigation", "--evidence",
                 ".artifacts/recovery/release.json", success=False)
        self.release(success=False)
        self.assertEqual(self.controls(), snapshot)

    def test_release_requires_explicit_authorization_and_matching_evidence(self):
        self.setup_history()
        snapshot = self.controls()
        for omit in ("basis", "stopped", "evidence"):
            with self.subTest(omit=omit):
                self.release(success=False, omit=omit)
                self.assertEqual(self.controls(), snapshot)
        original = copy.deepcopy(self.evidence)
        variants = [(key, None) for key in ("authorization", "evidence", "record_sha256")]
        variants += [("actor", "another-owner"), ("record_sha256", "0" * 64),
                     ("original_binding", {}), ("authorization", "../../outside"),
                     ("preserved_record", ".artifacts/recovery/untracked.json")]
        self.write(".artifacts/recovery/untracked.json", self.original_record.decode())
        for key, value in variants:
            with self.subTest(key=key, value=value):
                self.evidence = copy.deepcopy(original)
                if value is None:
                    self.evidence.pop(key)
                else:
                    self.evidence[key] = value
                self.save_evidence()
                self.release(success=False)
                self.assertEqual(self.controls(), snapshot)

    def test_dirty_workspace_or_lock_does_not_release(self):
        self.setup_history()
        snapshot = self.controls()
        dirty = self.write("unknown.txt", "must preserve")
        self.release(success=False)
        self.assertEqual(dirty.read_text(), "must preserve")
        self.assertEqual(self.controls(), snapshot)
        dirty.unlink()
        lock = self.repo / ".git/ai-harness/task-bindings.lock"
        lock.mkdir()
        self.release(success=False)
        self.assertTrue(lock.is_dir())
        self.assertEqual(self.controls(), snapshot)
        lock.rmdir()

    def test_other_live_checkout_cannot_be_released(self):
        self.setup_history(archived=True)
        self.git("worktree", "add", self.origin, "codex/fix-old")
        snapshot = self.controls()
        self.release(success=False)
        self.assertEqual(self.controls(), snapshot)

    def test_changed_or_missing_evidence_and_record_block_inspect(self):
        self.setup_history()
        self.release()
        for relative in (self.record_relative, ".artifacts/recovery/release.json",
                         ".artifacts/recovery/authorization.txt",
                         ".artifacts/recovery/original-evidence.txt"):
            path = self.repo / relative
            saved = path.read_bytes()
            with self.subTest(path=relative, change="changed"):
                path.write_bytes(saved + b"\n ")
                self.cli("inspect", success=False)
            path.write_bytes(saved)
            with self.subTest(path=relative, change="missing"):
                path.unlink()
                self.cli("inspect", success=False)
            path.write_bytes(saved)
        self.assert_available_preserved()

    def test_reappearing_archived_workspace_blocks_release_receipt(self):
        self.setup_history(archived=True)
        self.release()
        self.git("worktree", "add", self.origin, "codex/fix-old")
        self.cli("inspect", success=False)

    def test_same_task_id_in_another_binding_is_not_hidden_by_release(self):
        self.setup_history()
        self.release()
        other = self.base / "duplicate-checkout"
        self.git("worktree", "add", "-b", "codex/fix-duplicate", other)
        record = json.loads((other / self.record_relative).read_text())
        record["checkout_binding"] = hashlib.sha256(json.dumps(str(other.resolve()),
            ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        record["branch"] = "codex/fix-duplicate"
        self.write(self.record_relative, record, repo=other)
        self.cli("inspect", success=False)

    def test_tampered_receipt_or_missing_receipt_is_not_available(self):
        self.setup_history()
        self.release()
        receipt = next((self.repo / ".git/ai-harness/task-releases").glob("*.json"))
        saved = receipt.read_bytes()
        receipt.write_bytes(saved + b"\n ")
        self.cli("inspect", success=False)
        receipt.unlink()
        self.cli("inspect", success=False)


if __name__ == "__main__":
    unittest.main()
