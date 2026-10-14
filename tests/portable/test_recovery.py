"""Damaged transaction metadata must never expand filesystem authority."""
import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
from support import PortableCase


class RecoveryTests(PortableCase):
    def test_hardlinked_empty_locks_are_rejected_without_mutating_external_files(self):
        install = self.api("lifecycle", "install")
        error_type = self.api("errors", "HarnessError")
        directory, _ = self.bundle()
        for name, relative in (("home", ".ai-harness/portable/install.lock"),
                               ("skills", ".ai-harness-portable.lock")):
            with self.subTest(lock_root=name):
                scope = self.root / (name + "-hardlink-case")
                config = {"codex_home": scope / "home", "skills_dir": scope / "skills",
                          "environment": "auto"}
                roots = {"home": config["codex_home"], "skills": config["skills_dir"]}
                lock = roots[name] / relative
                lock.parent.mkdir(parents=True)
                external = scope / "outside-install-roots" / "empty-sentinel"
                external.parent.mkdir()
                external.write_bytes(b"")
                os.link(external, lock)
                self.assertEqual(external.stat().st_nlink, 2)
                rejected = None
                try:
                    install(directory, config)
                except error_type as error:
                    rejected = error
                self.assertEqual(external.read_bytes(), b"", "locking must not initialize a hardlinked user file")
                self.assertIsNotNone(rejected, "a hardlinked lock must be rejected")
                self.assertEqual(rejected.code, "UNSAFE_PATH")
                self.assertFalse((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").exists())
                self.assertFalse((config["skills_dir"] / "fix-closure-gate/SKILL.md").exists())

    def interrupted_agents_update(self):
        """Real v1/v2 installs produce valid receipts; the interruption journal is hand-built."""
        install = self.api("lifecycle", "install")
        config = self.config()
        config["codex_home"].mkdir()
        agents = config["codex_home"] / "AGENTS.md"
        agents.write_bytes(b"USER outside the managed block\r\n")
        target = ".ai-harness/portable/runtime/rules/example.md"
        directory, _ = self.bundle(entries=[("base", "home", "AGENTS.md", b"# Rules v1\n"),
                                            ("base", "home", target, b"base-v1\n")])
        install(directory, config)
        agents.write_bytes(agents.read_bytes() + b"USER suffix after managed block\r\n")
        receipt = config["codex_home"] / ".ai-harness/portable/receipt.json"
        managed = config["codex_home"] / target
        originals = {path: path.read_bytes() for path in (agents, managed, receipt)}
        new, _ = self.bundle("new", "2.0.0", [("base", "home", "AGENTS.md", b"# Rules v2\n"),
                                             ("base", "home", target, b"base-v2\n")])
        install(new, config)
        after = {path: path.read_bytes() for path in (agents, managed, receipt)}
        proposed = json.loads(after[receipt])
        old_receipt = json.loads(originals[receipt])
        receipt.write_bytes(originals[receipt])
        changes = [{"root": "home", "target": str(path.relative_to(config["codex_home"])).replace("\\", "/"),
                    "before": base64.b64encode(originals[path]).decode("ascii"),
                    "after": hashlib.sha256(after[path]).hexdigest()}
                   for path in (agents, managed, receipt)]
        journal = {"schema_version": 1, "roots": old_receipt["roots"], "changes": changes,
                   "transaction_files": proposed["files"],
                   "before_receipt": base64.b64encode(originals[receipt]).decode("ascii")}
        self.journal_path(config).write_text(json.dumps(journal))
        return config, originals, journal

    def test_agents_backup_external_text_tamper_rejected_before_any_restore(self):
        recover = self.api("lifecycle", "recover")
        config, originals, journal = self.interrupted_agents_update()
        agents_change = next(row for row in journal["changes"] if row["target"] == "AGENTS.md")
        before = base64.b64decode(agents_change["before"])
        self.assertIn(b"USER", before)
        agents_change["before"] = base64.b64encode(before.replace(b"USER", b"CORRUPT")).decode("ascii")
        path = self.journal_path(config)
        path.write_text(json.dumps(journal))
        journal_bytes = path.read_bytes()
        current = {file: file.read_bytes() for file in originals}
        error = self.assertRejected(lambda: recover(config))
        self.assertEqual(error.code, "JOURNAL_INVALID")
        self.assertEqual({file: file.read_bytes() for file in originals}, current)
        self.assertEqual(path.read_bytes(), journal_bytes)

    def test_agents_interrupted_update_restores_original_user_text(self):
        recover = self.api("lifecycle", "recover")
        config, originals, _ = self.interrupted_agents_update()
        recover(config)
        self.assertEqual({file: file.read_bytes() for file in originals}, originals)
        agents = (config["codex_home"] / "AGENTS.md").read_bytes()
        self.assertTrue(agents.startswith(b"USER outside the managed block\r\n"))
        self.assertTrue(agents.endswith(b"USER suffix after managed block\r\n"))
        self.assertNotIn(b"CORRUPT", agents)
        self.assertFalse(self.journal_path(config).exists())

    def interrupted_update(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        receipt_path = config["codex_home"] / ".ai-harness/portable/receipt.json"
        original_receipt = receipt_path.read_bytes()
        previous = json.loads(original_receipt)
        proposed = copy.deepcopy(previous)
        changes = []
        originals = {}
        roots = {"home": config["codex_home"], "skills": config["skills_dir"]}
        for entry in proposed["files"]:
            path = roots[entry["root"]] / entry["target"]
            original = path.read_bytes()
            originals[path] = original
            updated = b"version-two:" + original
            entry["sha256"] = hashlib.sha256(updated).hexdigest()
            changes.append({"root": entry["root"], "target": entry["target"],
                            "before": base64.b64encode(original).decode("ascii"),
                            "after": entry["sha256"]})
            path.write_bytes(updated)
        proposed["modules"] = {module: "2.0.0" for module in proposed["modules"]}
        proposed_bytes = json.dumps(proposed).encode("utf-8")
        changes.append({"root": "home", "target": ".ai-harness/portable/receipt.json",
                        "before": base64.b64encode(original_receipt).decode("ascii"),
                        "after": hashlib.sha256(proposed_bytes).hexdigest()})
        journal = {"schema_version": 1, "roots": previous["roots"], "changes": changes,
                   "transaction_files": proposed["files"],
                   "before_receipt": base64.b64encode(original_receipt).decode("ascii")}
        self.journal_path(config).write_text(json.dumps(journal))
        return config, originals, original_receipt, journal

    def test_interrupted_update_restores_old_bytes_and_receipt(self):
        recover = self.api("lifecycle", "recover")
        config, originals, original_receipt, _ = self.interrupted_update()
        recover(config)
        for path, expected in originals.items():
            self.assertEqual(path.read_bytes(), expected)
        receipt = config["codex_home"] / ".ai-harness/portable/receipt.json"
        self.assertEqual(receipt.read_bytes(), original_receipt)
        self.assertFalse(self.journal_path(config).exists())

    def test_external_edit_reports_incomplete_and_restores_other_safe_files(self):
        recover = self.api("lifecycle", "recover")
        config, originals, _, _ = self.interrupted_update()
        changed = config["skills_dir"] / "fix-closure-gate/SKILL.md"
        changed.write_bytes(b"external update after crash")
        error = self.assertRejected(lambda: recover(config))
        self.assertEqual(error.code, "RECOVERY_INCOMPLETE")
        self.assertEqual(changed.read_bytes(), b"external update after crash")
        for path, expected in originals.items():
            if path != changed:
                self.assertEqual(path.read_bytes(), expected)
        self.assertTrue(self.journal_path(config).is_file())

    def test_corrupt_backup_is_rejected_before_any_restore(self):
        recover = self.api("lifecycle", "recover")
        config, originals, _, journal = self.interrupted_update()
        journal["changes"][0]["before"] = base64.b64encode(b"forged old bytes").decode("ascii")
        self.journal_path(config).write_text(json.dumps(journal))
        before = {path: path.read_bytes() for path in originals}
        self.assertRejected(lambda: recover(config))
        self.assertEqual({path: path.read_bytes() for path in originals}, before)
        self.assertTrue(self.journal_path(config).is_file())

    def test_live_home_and_skills_locks_block_install(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        script = """import os, sys
from pathlib import Path
p = Path(sys.argv[1])
p.parent.mkdir(parents=True, exist_ok=True)
with p.open('a+b') as handle:
    handle.write(b'0'); handle.flush(); handle.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    print('locked', flush=True)
    sys.stdin.read(1)
"""
        for path in (config["codex_home"] / ".ai-harness/portable/install.lock",
                     config["skills_dir"] / ".ai-harness-portable.lock"):
            with self.subTest(lock=path.name):
                child = subprocess.Popen([sys.executable, "-B", "-c", script, str(path)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True)
                try:
                    self.assertEqual(child.stdout.readline().strip(), "locked")
                    error = self.assertRejected(lambda: install(directory, config))
                    self.assertEqual(error.code, "LOCKED")
                    self.assertFalse((config["skills_dir"] / "fix-closure-gate/SKILL.md").exists())
                    self.assertFalse((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").exists())
                finally:
                    child.communicate("x", timeout=5)
        install(directory, config)
        self.assertEqual((config["skills_dir"] / "fix-closure-gate/SKILL.md").read_bytes(), b"fix-v1\n")

    def journal_path(self, config):
        path = config["codex_home"] / ".ai-harness/portable/journal.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_pending_journal_blocks_install_without_payload_changes(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        journal = self.journal_path(config)
        journal.write_text('{"schema_version": 1, "changes": []}')
        before = journal.read_bytes()
        error = self.assertRejected(lambda: install(directory, config))
        self.assertEqual(error.code, "RECOVERY_REQUIRED")
        self.assertEqual(journal.read_bytes(), before)
        self.assertFalse((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").exists())
        self.assertFalse((config["skills_dir"] / "fix-closure-gate/SKILL.md").exists())

    def test_corrupt_journal_recovery_is_read_only(self):
        recover = self.api("lifecycle", "recover")
        config = self.config()
        journal = self.journal_path(config)
        journal.write_text("{broken json")
        sentinel = config["codex_home"] / "config.toml"
        sentinel.write_bytes(b"user config")
        self.assertRejected(lambda: recover(config))
        self.assertEqual(journal.read_text(), "{broken json")
        self.assertEqual(sentinel.read_bytes(), b"user config")

    def test_recovery_rejects_unverified_root_and_preserves_outside(self):
        recover = self.api("lifecycle", "recover")
        config = self.config()
        sentinel = self.write("outside/sentinel", b"outside")
        journal = self.journal_path(config)
        journal.write_text(json.dumps({"schema_version": 1,
            "roots": {"home": str(sentinel.parent), "skills": str(config["skills_dir"])},
            "changes": [{"root": "home", "target": "sentinel", "before": None, "after": None}],
            "transaction_files": [], "before_receipt": None}))
        self.assertRejected(lambda: recover(config))
        self.assertEqual(sentinel.read_bytes(), b"outside")
        self.assertTrue(journal.exists())

    def test_receipt_cannot_claim_user_config_ownership(self):
        uninstall = self.api("lifecycle", "uninstall")
        config = self.config()
        receipt_path = config["codex_home"] / ".ai-harness/portable/receipt.json"
        receipt_path.parent.mkdir(parents=True)
        sentinel = config["codex_home"] / "config.toml"
        sentinel.write_bytes(b"user config")
        receipt_path.write_text(json.dumps({"schema_version": 1,
            "roots": {"home": str(config["codex_home"]), "skills": str(config["skills_dir"])},
            "modules": {"base": "1.0.0"}, "agents_block": None,
            "files": [{"root": "home", "target": "config.toml", "module": "base",
                       "sha256": hashlib.sha256(b"user config").hexdigest()}]}))
        self.assertRejected(lambda: uninstall(config))
        self.assertEqual(sentinel.read_bytes(), b"user config")
