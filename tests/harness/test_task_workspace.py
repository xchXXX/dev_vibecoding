"""Public task ownership contract; synthetic roles do not prove model identity.

Every invocation and consumer is retained under the current task's evidence roots.
No production workspace, branch, model, or GTO orchestration is changed.
"""
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
CHECKER = ROOT / "scripts/check_git_workflow.py"
SYNC = ROOT / "scripts/sync_git_workflow.py"
POLICY = {
    "schema_version": 1, "remote": "origin", "main_branch": "main",
    "task_prefixes": ["codex/feat-", "codex/fix-", "codex/ops-"],
    "reserved_branches": {}, "release_tag_pattern": r"release/\d{4}",
    "merge_method": "merge", "cleanup_mode": "report-only",
}


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


class TaskWorkspaceCliTests(unittest.TestCase):
    def setUp(self):
        self.run_id = self._testMethodName + "-" + uuid.uuid4().hex
        self.base = ROOT / ".tmp/task-workspace-governance" / self.run_id
        self.repo = self.base / "consumer"
        self.repo.mkdir(parents=True)
        self.logs = ROOT / ".artifacts/task-workspace-governance/cli" / self.run_id
        self.logs.mkdir(parents=True)
        self.seq = 0
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Synthetic Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("config/ai/git-policy.json", POLICY)
        self.write(".gitignore", ".tmp/\n.artifacts/\n")
        self.git("add", ".")
        self.git("commit", "-m", "synthetic fixture")
        self.git("switch", "-c", "codex/fix-fixture")
        self.task_id = "fixture-task"
        self.owner = "synthetic-coordinator"

    def git(self, *args, repo=None):
        run = subprocess.run(["git", "-C", str(repo or self.repo), *args],
                             text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return run.stdout.strip()

    def write(self, relative, value, repo=None):
        path = (repo or self.repo) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)
                        if not isinstance(value, str) else value, encoding="utf-8")
        return path

    def execute(self, command, code=0, cwd=None):
        run = subprocess.run([str(x) for x in command], cwd=cwd or self.base,
                             capture_output=True, text=True, timeout=60,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                  "PYTHONPATH": "", "GIT_TERMINAL_PROMPT": "0"})
        self.seq += 1
        record = dict(command=[str(x) for x in command], cwd=str(cwd or self.base),
                      returncode=run.returncode, stdout=run.stdout, stderr=run.stderr,
                      consumer=str(self.repo))
        (self.logs / f"{self.seq:03d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        if code is not None:
            self.assertEqual(run.returncode, code, json.dumps(record, ensure_ascii=False))
        return run

    def command(self, action, *extra, repo=None, task=None, owner=None, entry=None):
        args = [sys.executable, str(entry or ENTRY), "--repo-root", str(repo or self.repo),
                "--action", action, "--json"]
        if action != "inspect" or task:
            args += ["--task-id", task or self.task_id]
        if action not in ("inspect", "register-gto"):
            args += ["--coordinator", owner or self.owner]
        return args + list(extra)

    def cli(self, action, *extra, code=0, **kwargs):
        run = self.execute(self.command(action, *extra, **kwargs), code=code)
        try:
            return json.loads(run.stdout)
        except ValueError:
            self.fail("Public CLI must return JSON: " + run.stdout + run.stderr)

    def begin(self):
        return self.cli("begin", "--title", "Synthetic contract fixture",
                        "--point", "P1", "--point", "P2")

    @property
    def task_path(self):
        return self.repo / f"docs/tasks/{self.task_id}/task.json"

    @property
    def index_dir(self):
        return self.repo / ".git/ai-harness"

    def state(self):
        return json.loads(self.task_path.read_text())

    def controls(self):
        return {"tasks": hashes(self.repo / "docs/tasks"),
                "index": hashes(self.index_dir)}

    def stage(self, name, *, actor=None, outcome="pass", checks=None, code=0, **fields):
        actor = actor or {
            "tests": "synthetic-tester", "review": "synthetic-reviewer",
            "acceptance": "synthetic-tester",
        }.get(name, self.owner)
        token = uuid.uuid4().hex
        raw = f".artifacts/fixture/{token}.log"
        self.write(raw, "Synthetic CLI contract evidence; no actual independent agent claimed.\n")
        evidence = dict(actor=actor, outcome=outcome, summary="Synthetic contract check",
                        evidence=[raw], **fields)
        if name == "tests":
            evidence.setdefault("red_observed", True)
        if name in ("review", "acceptance"):
            dispatch = f".artifacts/fixture/{token}-dispatch.json"
            self.write(dispatch, {"synthetic_fixture": True, "actor": actor})
            evidence["dispatch_evidence"] = dispatch
        if name == "acceptance":
            evidence["checks"] = checks if checks is not None else [
                {"id": p, "status": "pass", "evidence": [raw]} for p in ("P1", "P2")]
            evidence.setdefault("open_issues", [])
        relative = f".artifacts/fixture/{token}.json"
        self.write(relative, evidence)
        result = self.cli("record-stage", "--stage", name, "--evidence", relative, code=code)
        return relative, raw, result

    def through(self, last="implementation"):
        for name in ("investigation", "plan", "documentation", "tests",
                     "implementation", "review", "acceptance"):
            self.stage(name)
            if name == last:
                break

    def test_inspect_is_read_only_and_reports_available(self):
        before = hashes(self.repo)
        payload = self.cli("inspect")
        self.assertEqual(payload["decision"], "available")
        self.assertEqual(before, hashes(self.repo))
        self.assertFalse(self.index_dir.exists())

    def test_configured_hyphen_prefix_is_accepted(self):
        run = self.execute([sys.executable, CHECKER, "--repo-root", self.repo,
                            "--phase", "start", "--json"])
        self.assertTrue(json.loads(run.stdout)["ok"])

    def test_same_task_dirty_reuses_and_clean_occupied_cannot_be_claimed(self):
        self.begin()
        self.write("owned-change.txt", "preserve exactly")
        before = self.controls()
        self.cli("resume")
        self.cli("check")
        self.assertEqual(before, self.controls())
        self.git("add", ".")
        self.git("commit", "-m", "synthetic task checkpoint")
        self.assertEqual(self.git("status", "--porcelain"), "")
        before = hashes(self.repo)
        self.cli("begin", task="different-task", code=1)
        self.assertEqual(before, hashes(self.repo))
        self.assertEqual((self.repo / "owned-change.txt").read_text(), "preserve exactly")

    def test_unknown_dirty_requires_adopt_and_binding_scopes_legacy_prefix(self):
        self.git("switch", "-c", "legacy-existing")
        self.write("old-dirty.txt", "already present")
        self.cli("begin", code=1)
        self.cli("adopt", code=1)
        self.cli("adopt", "--basis", "User explicitly confirmed this existing synthetic task")
        self.cli("check")
        args = [sys.executable, CHECKER, "--repo-root", self.repo, "--phase", "start", "--json"]
        self.execute(args, code=1)
        self.execute(args + ["--task-id", self.task_id, "--coordinator", self.owner])
        self.execute(args + ["--task-id", "unbound-task", "--coordinator", self.owner], code=1)
        self.assertEqual((self.repo / "old-dirty.txt").read_text(), "already present")

    def test_handoff_requires_stopped_writes_then_revokes_old_coordinator(self):
        self.begin()
        before = self.controls()
        self.cli("resume", owner="next-coordinator", code=1)
        self.cli("handoff", "--next-coordinator", "next-coordinator",
                 "--basis", "Explicit transfer", code=1)
        self.assertEqual(before, self.controls())
        self.cli("handoff", "--next-coordinator", "next-coordinator",
                 "--basis", "Explicit transfer", "--writes-stopped")
        transferred = self.controls()
        self.cli("check", code=1)
        self.cli("resume", owner="next-coordinator")
        self.cli("check", owner="next-coordinator")
        self.assertEqual(transferred, self.controls())

    def test_resume_locates_original_worktree_but_check_rejects_wrong_checkout(self):
        other = self.base / "other"
        self.git("worktree", "add", "-b", "codex/feat-other", str(other))
        self.begin()
        before = self.controls()
        result = self.cli("resume", repo=other)
        self.assertIn(str(self.repo), json.dumps(result))
        self.cli("check", repo=other, code=1)
        self.cli("begin", repo=other, code=1)
        self.assertEqual(before, self.controls())
        self.assertFalse((other / "docs/tasks" / self.task_id).exists())

    def test_corrupt_index_missing_task_and_stale_lock_never_become_available(self):
        self.begin()
        index = self.index_dir / "task-bindings.json"
        saved = index.read_bytes()
        index.write_text("{broken")
        before = self.controls()
        self.cli("inspect", code=2)
        self.cli("begin", task="new-task", code=2)
        self.assertEqual(before, self.controls())
        index.write_bytes(saved)
        task = self.task_path.read_bytes()
        self.task_path.unlink()
        before = self.controls()
        self.cli("inspect", code=2)
        self.assertEqual(before, self.controls())
        self.task_path.write_bytes(task)
        lock = self.index_dir / "task-bindings.lock"
        lock.mkdir()
        os.utime(lock, (1, 1))
        before = self.controls()
        self.cli("handoff", "--next-coordinator", "next", "--writes-stopped",
                 "--basis", "Explicit transfer", code=1)
        self.assertTrue(lock.exists())
        self.assertEqual(before, self.controls())

    def test_two_process_claims_have_at_most_one_winner(self):
        self.assertTrue(ENTRY.is_file(), "task_workspace public entry is required")
        commands = [self.command("begin", task=f"race-{n}", owner=f"coordinator-{n}")
                    for n in range(2)]
        processes = [subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True) for c in commands]
        results = []
        for command, process in zip(commands, processes):
            stdout, stderr = process.communicate(timeout=60)
            results.append(dict(command=command, returncode=process.returncode,
                                stdout=stdout, stderr=stderr))
        (self.logs / "race.json").write_text(json.dumps(results, indent=2))
        self.assertEqual(sum(r["returncode"] == 0 for r in results), 1, results)
        self.assertEqual(len(list((self.repo / "docs/tasks").glob("*/task.json"))), 1)

    def test_missing_policy_does_not_create_task(self):
        (self.repo / "config/ai/git-policy.json").unlink()
        before = hashes(self.repo)
        self.cli("begin", code=2)
        self.assertEqual(before, hashes(self.repo))

    def test_stage_order_identity_and_complete_fail_atomically(self):
        self.begin()
        before = self.controls()
        self.stage("implementation", code=1)
        self.cli("complete", code=1)
        self.assertEqual(before, self.controls())
        self.through()
        before = self.controls()
        self.stage("review", actor=self.owner, code=1)
        self.assertEqual(before, self.controls())
        self.stage("review")
        before = self.controls()
        self.stage("acceptance", actor="synthetic-reviewer", code=1)
        self.assertEqual(before, self.controls())
        self.stage("acceptance")
        self.cli("complete")
        self.assertEqual(self.state()["status"], "completed")

    def test_failed_history_retained_and_later_failure_blocks_completion(self):
        self.begin()
        self.through("review")
        _, raw, _ = self.stage("acceptance", outcome="fail", checks=[
            {"id": "P1", "status": "pass", "evidence": [".gitignore"]},
            {"id": "P2", "status": "fail", "evidence": [".gitignore"]}])
        failed = json.dumps(self.state())
        self.cli("complete", code=1)
        self.stage("acceptance", checks=[
            {"id": "P1", "status": "pass", "evidence": [raw]},
            {"id": "P2", "status": "pass", "evidence": [".gitignore"]}])
        self.assertGreater(len(json.dumps(self.state())), len(failed))
        self.stage("acceptance", outcome="fail")
        before = self.controls()
        self.cli("complete", code=1)
        self.assertEqual(before, self.controls())
        self.stage("acceptance")
        self.cli("complete")
        self.assertEqual(self.state()["status"], "completed")

    def test_evidence_bytes_missing_points_and_open_issues_block_completion(self):
        self.begin()
        self.through("review")
        self.stage("acceptance", checks=[{"id": "P1", "status": "pass",
                                        "evidence": [".gitignore"]}])
        self.cli("complete", code=1)
        self.stage("acceptance", open_issues=["unresolved"])
        self.cli("complete", code=1)
        relative, raw, _ = self.stage("acceptance")
        original = (self.repo / raw).read_bytes()
        (self.repo / raw).write_text("tampered original evidence")
        before = self.controls()
        self.cli("complete", code=1)
        self.assertEqual(before, self.controls())
        (self.repo / raw).write_bytes(original)
        (self.repo / relative).write_text("{}")
        self.cli("complete", code=1)

    def test_stage_evidence_must_stay_inside_consumer(self):
        self.begin()
        before = self.controls()
        outside = self.base / "outside.json"
        outside.write_text(json.dumps(dict(actor=self.owner, outcome="pass",
                                           summary="escape", evidence=["../outside.json"])))
        self.cli("record-stage", "--stage", "investigation",
                 "--evidence", "../outside.json", code=1)
        self.assertEqual(before, self.controls())

    def test_generated_relative_entry_is_independent_and_preserves_drift(self):
        self.execute([sys.executable, SYNC, "--project-root", self.repo])
        entry = self.repo / "modules/tooling/task_workspace.py"
        checker = entry.with_name("check_git_workflow.py")
        for target, source in ((entry, ENTRY), (checker, CHECKER)):
            header, fingerprint, payload = target.read_bytes().split(b"\n", 2)
            self.assertEqual(header, (
                f"# Generated from ai-harness/scripts/{source.name}; DO NOT EDIT.").encode())
            self.assertEqual(fingerprint, b"# source-sha256: " +
                             hashlib.sha256(source.read_bytes()).hexdigest().encode())
            self.assertEqual(payload, source.read_bytes())
        self.execute([sys.executable, SYNC, "--project-root", self.repo, "--check"])
        before = hashes(self.repo)
        self.execute([sys.executable, "-I", "modules/tooling/task_workspace.py",
                      "--repo-root", ".", "--action", "inspect", "--json"], cwd=self.repo)
        self.assertEqual(before, hashes(self.repo))
        entry.write_bytes(entry.read_bytes() + b"\n# independent local change\n")
        drift = entry.read_bytes()
        self.execute([sys.executable, SYNC, "--project-root", self.repo], code=1)
        self.assertEqual(entry.read_bytes(), drift)

    def test_missing_index_discovers_existing_task_without_taking_ownership(self):
        self.begin()
        index = self.index_dir / "task-bindings.json"
        index.unlink()
        before = self.controls()
        result = self.cli("inspect", task=self.task_id)
        self.assertEqual(result["decision"], "reuse")
        self.assertEqual(before, self.controls())
        self.cli("begin", task="other-task", code=1)
        self.assertEqual(before, self.controls())

    def test_gto_registration_only_indexes_original_control_plane(self):
        # Use real init-task, not handwritten state; no delivery/business execution.
        from test_gto_workflow import workflow_contract
        self.task_id = "20310102-030405-gto-readonly"
        self.write(".tmp/contract.json", workflow_contract())
        controller = ROOT / "skills/global-task-orchestrator/scripts/orchestrator_ctl.py"
        self.execute([sys.executable, controller, "--repo-root", self.repo,
                      "--task-id", self.task_id, "--action", "init-task",
                      "--title", "Synthetic GTO registration",
                      "--owner", self.owner, "--contract-json-file",
                      self.repo / ".tmp/contract.json", "--json"])
        before = {"docs": hashes(self.repo / "docs"), "artifacts": hashes(self.repo / ".artifacts")}
        self.cli("register-gto")
        self.assertEqual(before, {"docs": hashes(self.repo / "docs"),
                                  "artifacts": hashes(self.repo / ".artifacts")})
        self.assertFalse(self.task_path.exists())
        self.cli("adopt", "--basis", "Cannot replace GTO with ordinary state", code=1)
        self.assertEqual(before, {"docs": hashes(self.repo / "docs"),
                                  "artifacts": hashes(self.repo / ".artifacts")})

    def doc_contract(self, script):
        task = f"docs/tasks/{self.task_id}"
        self.write(task + "/task.json", {
            "schema_version": 1, "mode": "ordinary", "task_id": self.task_id,
            "status": "active", "phase": "documentation",
            "branch": "codex/fix-fixture", "workspace": "<repo-root>",
            "coordinator": self.owner, "task_document": "task.md",
            "acceptance_points": ["P1"], "stages": [],
        })
        document_text = "# 普通任务\n\n## 目标\n验证任务归属。\n\n## 范围\n仅合成夹具。\n\n## 验收\nP1：公开入口返回正确定位。\n"
        self.write(task + "/task.md", document_text)
        command = [sys.executable, ROOT / "scripts" / script,
                   "--repo-root", self.repo, "--json"]
        self.execute(command)
        ordinary = self.task_path.read_bytes()
        self.task_path.unlink()
        self.execute(command, code=1)
        self.task_path.write_bytes(ordinary)
        document = self.repo / task / "task.md"
        document.unlink()
        self.execute(command, code=1)
        document.write_text(document_text)
        self.task_path.write_text("{broken")
        self.execute(command, code=1)
        self.task_path.write_text(json.dumps({"mode": "gto"}))
        self.execute(command, code=1)
        self.task_path.unlink()
        headings = {
            "plan.md": ["任务目标", "背景与问题", "范围", "非目标", "约束与依赖", "方案摘要",
                        "风险与回退", "验收标准", "阶段划分", "需先同步的核心文档与测试"],
            "execution.md": ["施工目标", "前置条件", "执行顺序", "文档先行清单", "测试同步清单",
                             "实施批次", "每批写入范围", "验证命令", "回退方案", "审查与返工路径"],
            "acceptance.md": ["验收目标", "验收标准", "必备证据", "未决项", "最终结论"],
        }
        for name, sections in headings.items():
            self.write(task + "/" + name, "\n".join(
                f"## {heading}\n合成夹具已有真实合同内容。\n" for heading in sections))
        self.execute(command)

    def test_ordinary_two_artifact_doc_routing_and_legacy_requirements(self):
        self.doc_contract("validate_doc_routing.py")

    def test_ordinary_two_artifact_plan_validation_and_legacy_requirements(self):
        self.doc_contract("validate_plan_docs.py")

    def test_directed_publication_installs_both_tools_without_touching_other_runtime(self):
        home = self.base / "synthetic-home"
        home.mkdir()
        old = "<!-- ai-harness:managed-global-agents:v1 -->\nPrevious managed instructions\n"
        self.write("AGENTS.md", old, repo=home)
        self.write(".ai-harness/bootstrap.receipt.json", {
            "schema_version": "2.0",
            "target_sha256": hashlib.sha256(old.encode()).hexdigest(),
            "managed_runtime_files": [{"sentinel": "keep"}],
            "unrelated": {"keep": True},
        }, repo=home)
        protected = ("config.toml", "skills/other/SKILL.md",
                     ".ai-harness/codex-sync.receipt.json", "frozen/old-controller.py")
        for name in protected:
            self.write(name, "retained exact original bytes", repo=home)
        command = [sys.executable, ROOT / "scripts/bootstrap-local.py",
                   "--codex-home", home, "--git-workflow-only", "--json"]
        self.execute(command)
        installed = home / ".ai-harness/runtime/git-workflow"
        for name in ("task_workspace.py", "check_git_workflow.py"):
            self.assertEqual((installed / name).read_bytes(), (ROOT / "scripts" / name).read_bytes())
        before = hashes(home)
        self.execute(command)
        for name in protected:
            self.assertEqual((home / name).read_text(), "retained exact original bytes")
        receipt = json.loads((home / ".ai-harness/bootstrap.receipt.json").read_text())
        self.assertEqual(receipt["managed_runtime_files"], [{"sentinel": "keep"}])
        self.assertEqual(receipt["unrelated"], {"keep": True})
        # Timestamps may change; runtime bytes must be stable.
        self.assertEqual(before[".ai-harness/runtime/git-workflow/task_workspace.py"],
                         hashes(home)[".ai-harness/runtime/git-workflow/task_workspace.py"])

    def test_revision_new_implementation_needs_latest_coverage_without_rerunning_old_points(self):
        self.begin()
        self.through("acceptance")
        old_history = self.state()["stages"]
        old_review = [r for r in old_history if r["stage"] == "review"]
        old_acceptance = next(r for r in reversed(old_history) if r["stage"] == "acceptance")
        old_report = json.loads((self.repo / old_acceptance["evidence"]).read_text())
        counter = self.write(".artifacts/fixture/business-count.txt", "0")
        self.stage("implementation")
        before = self.controls()
        self.cli("complete", code=1)
        self.assertEqual(before, self.controls())
        self.stage("acceptance", checks=old_report["checks"])
        self.assertEqual([r for r in self.state()["stages"] if r["stage"] == "review"], old_review)
        self.assertEqual(self.state()["stages"][:len(old_history)], old_history)
        self.cli("complete")
        self.assertEqual(self.state()["status"], "completed")
        self.assertEqual(counter.read_text(), "0")

    def test_revision_original_reviewer_must_close_own_failed_review(self):
        self.begin()
        self.through()
        self.stage("review", actor="synthetic-reviewer", outcome="fail")
        failed_history = self.state()["stages"]
        before = self.controls()
        self.stage("review", actor="replacement-reviewer", code=1)
        self.assertEqual(before, self.controls())
        self.stage("review", actor="synthetic-reviewer")
        self.assertEqual(self.state()["stages"][:len(failed_history)], failed_history)
        self.stage("acceptance")
        self.cli("complete")
        self.assertEqual(self.state()["status"], "completed")

    def test_revision_original_tester_cannot_be_replaced(self):
        self.begin()
        self.through("tests")
        before = self.controls()
        self.stage("tests", actor="replacement-tester", code=1)
        self.assertEqual(before, self.controls())
        self.stage("tests", actor="synthetic-tester")
        self.stage("implementation")
        self.stage("review")
        self.stage("acceptance", actor="synthetic-tester")
        self.cli("complete")

    def test_revision_prior_implementer_cannot_review_after_coordinator_handoff(self):
        self.begin()
        self.through()
        original = self.owner
        replacement = "synthetic-second-implementer"
        self.cli("handoff", "--next-coordinator", replacement, "--writes-stopped",
                 "--basis", "Synthetic explicit handoff between implementation owners")
        self.owner = replacement
        self.stage("implementation")
        before = self.controls()
        self.stage("review", actor=original, code=1)
        self.assertEqual(before, self.controls())
        self.stage("review", actor="synthetic-reviewer")
        self.stage("acceptance")
        self.cli("complete")

    def test_revision_independent_roles_cannot_later_become_implementers(self):
        self.begin()
        self.through("review")
        for actor in ("synthetic-reviewer", "synthetic-tester"):
            with self.subTest(actor=actor):
                before = self.controls()
                self.stage("implementation", actor=actor, code=1)
                self.assertEqual(before, self.controls())


if __name__ == "__main__":
    unittest.main()
