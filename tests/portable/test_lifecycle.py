"""Real filesystem ownership checks; never read or write an actual Codex home."""
import json
from support import PortableCase


class LifecycleTests(PortableCase):
    def test_reinstall_after_uninstall_accepts_retained_empty_skill_directory(self):
        install = self.api("lifecycle", "install")
        uninstall = self.api("lifecycle", "uninstall")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        uninstall(config)
        retained = config["skills_dir"] / "fix-closure-gate"
        self.assertTrue(retained.is_dir())
        self.assertEqual(list(retained.iterdir()), [])
        install(directory, config)
        self.assertEqual((retained / "SKILL.md").read_bytes(), b"fix-v1\n")
        self.assertEqual((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").read_bytes(), b"base-v1\n")

    def test_agents_management_preserves_external_crlf_bytes(self):
        install = self.api("lifecycle", "install")
        uninstall = self.api("lifecycle", "uninstall")
        directory, _ = self.bundle(entries=[("base", "home", "AGENTS.md", b"# Managed rules\n")])
        config = self.config()
        config["codex_home"].mkdir()
        agents = config["codex_home"] / "AGENTS.md"
        original = "# 我的规则\r\n\r\nKeep user text.\r\n".encode("utf-8")
        agents.write_bytes(original)
        install(directory, config)
        installed = agents.read_bytes()
        self.assertTrue(installed.startswith(original))
        self.assertEqual(installed.count(b"<!-- ai-harness:portable:start -->"), 1)
        self.assertEqual(installed.count(b"<!-- ai-harness:portable:end -->"), 1)
        with_suffix = installed + b"\r\nUser addition after installation.\r\n"
        agents.write_bytes(with_suffix)
        uninstall(config)
        self.assertEqual(agents.read_bytes(), original + b"\r\nUser addition after installation.\r\n")

    def test_agents_existing_unowned_marker_blocks_install(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle(entries=[("base", "home", "AGENTS.md", b"# Managed rules\n")])
        config = self.config()
        config["codex_home"].mkdir()
        agents = config["codex_home"] / "AGENTS.md"
        original = b"User\n<!-- ai-harness:portable:start -->\nExisting\n<!-- ai-harness:portable:end -->\n"
        agents.write_bytes(original)
        self.assertRejected(lambda: install(directory, config))
        self.assertEqual(agents.read_bytes(), original)

    def test_agents_managed_block_edit_blocks_uninstall(self):
        install = self.api("lifecycle", "install")
        uninstall = self.api("lifecycle", "uninstall")
        directory, _ = self.bundle(entries=[("base", "home", "AGENTS.md", b"# Managed rules\n")])
        config = self.config()
        install(directory, config)
        agents = config["codex_home"] / "AGENTS.md"
        changed = agents.read_bytes().replace(b"# Managed rules", b"# User customized rules")
        agents.write_bytes(changed)
        self.assertRejected(lambda: uninstall(config))
        self.assertEqual(agents.read_bytes(), changed)

    def test_install_creates_selected_files_and_receipt(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        self.assertEqual((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").read_bytes(), b"base-v1\n")
        self.assertEqual((config["skills_dir"] / "fix-closure-gate/SKILL.md").read_bytes(), b"fix-v1\n")
        receipt = json.loads((config["codex_home"] / ".ai-harness/portable/receipt.json").read_text())
        self.assertEqual(receipt["modules"], {"base": "1.0.0", "fix": "1.0.0"})
        self.assertEqual(len(receipt["files"]), 2)

    def test_dry_run_leaves_absent_install_roots_absent(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config, dry_run=True)
        self.assertFalse(config["codex_home"].exists())
        self.assertFalse(config["skills_dir"].exists())

    def test_unmanaged_same_name_file_blocks_entire_install(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        existing = config["skills_dir"] / "fix-closure-gate/SKILL.md"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"user skill")
        self.assertRejected(lambda: install(directory, config))
        self.assertEqual(existing.read_bytes(), b"user skill")
        self.assertFalse((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").exists())

    def test_unmanaged_skill_directory_blocks_new_file_inside_it(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        existing = config["skills_dir"] / "fix-closure-gate/notes.txt"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"user notes")
        self.assertRejected(lambda: install(directory, config))
        self.assertEqual(existing.read_bytes(), b"user notes")
        self.assertFalse((existing.parent / "SKILL.md").exists())

    def test_update_preserves_unselected_module_and_user_data(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        user_paths = [config["codex_home"] / "hooks.json", config["codex_home"] / "memories/note.md",
                      config["skills_dir"] / "personal/SKILL.md"]
        for path in user_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"user bytes\r\n")
        new, _ = self.bundle("new", "2.0.0", [("base", "home", ".ai-harness/portable/runtime/rules/example.md", b"base-v2\n"),
                                             ("fix", "skills", "fix-closure-gate/SKILL.md", b"fix-v2\n")])
        install(new, config, selected=["fix"])
        self.assertEqual((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").read_bytes(), b"base-v1\n")
        self.assertEqual((config["skills_dir"] / "fix-closure-gate/SKILL.md").read_bytes(), b"fix-v2\n")
        for path in user_paths:
            self.assertEqual(path.read_bytes(), b"user bytes\r\n")
        receipt = json.loads((config["codex_home"] / ".ai-harness/portable/receipt.json").read_text())
        self.assertEqual(receipt["modules"], {"base": "1.0.0", "fix": "2.0.0"})

    def test_uninstall_one_module_preserves_other_module_and_extra_files(self):
        install = self.api("lifecycle", "install")
        uninstall = self.api("lifecycle", "uninstall")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        extra = config["skills_dir"] / "fix-closure-gate/user-notes.txt"
        extra.write_bytes(b"keep")
        uninstall(config, selected=["fix"])
        self.assertFalse((extra.parent / "SKILL.md").exists())
        self.assertEqual(extra.read_bytes(), b"keep")
        self.assertEqual((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").read_bytes(), b"base-v1\n")

    def test_drift_blocks_entire_uninstall_before_deletion(self):
        install = self.api("lifecycle", "install")
        uninstall = self.api("lifecycle", "uninstall")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        changed = config["skills_dir"] / "fix-closure-gate/SKILL.md"
        changed.write_bytes(b"user edit")
        self.assertRejected(lambda: uninstall(config))
        self.assertEqual(changed.read_bytes(), b"user edit")
        self.assertEqual((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").read_bytes(), b"base-v1\n")

    def test_drift_blocks_update_and_preserves_receipt(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        receipt = config["codex_home"] / ".ai-harness/portable/receipt.json"
        original_receipt = receipt.read_bytes()
        changed = config["skills_dir"] / "fix-closure-gate/SKILL.md"
        changed.write_bytes(b"local customization")
        new, _ = self.bundle("new", "2.0.0", [("base", "home", ".ai-harness/portable/runtime/rules/example.md", b"base-v2"),
                                             ("fix", "skills", "fix-closure-gate/SKILL.md", b"fix-v2")])
        self.assertRejected(lambda: install(new, config))
        self.assertEqual(receipt.read_bytes(), original_receipt)
        self.assertEqual(changed.read_bytes(), b"local customization")
        self.assertEqual((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").read_bytes(), b"base-v1\n")

    def test_malformed_receipt_cannot_delete_user_files(self):
        uninstall = self.api("lifecycle", "uninstall")
        config = self.config()
        receipt = config["codex_home"] / ".ai-harness/portable/receipt.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"files": [{"target": "../../outside"}]}')
        sentinel = self.write("outside", b"keep")
        self.assertRejected(lambda: uninstall(config))
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_doctor_is_read_only_and_does_not_claim_session_verification(self):
        install = self.api("lifecycle", "install")
        doctor = self.api("lifecycle", "doctor")
        directory, _ = self.bundle()
        config = self.config()
        install(directory, config)
        before = self.snapshot(self.root)
        report = doctor(config)
        self.assertIs(report["session_verified"], False)
        self.assertEqual(self.snapshot(self.root), before)

    def test_symlink_target_parent_is_rejected_without_writing_outside(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        config["codex_home"].mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        link = config["codex_home"] / ".ai-harness/portable/runtime/rules"
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest("Host cannot create test symlink: " + str(error))
        self.assertRejected(lambda: install(directory, config))
        self.assertEqual(list(outside.iterdir()), [])
