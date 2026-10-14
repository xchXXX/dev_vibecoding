"""Legacy publication must preserve user hooks and preflight whole skill trees."""
import importlib.util
import json
import subprocess
import sys
from support import PortableCase, REPO


class LegacySafetyTests(PortableCase):
    def test_doctor_observes_user_hooks_without_managing_them(self):
        home = self.root / "isolated-home"
        hooks = self.write("isolated-home/hooks.json",
                           b'{"hooks":{"PostToolUse":[{"id":"user.callback","command":"notify"}]}}\r\n')
        config = self.write("isolated-home/config.toml",
                            b'post_completion_hook = "/usr/local/bin/user-callback"\r\n')
        originals = {path: path.read_bytes() for path in (hooks, config)}
        result = subprocess.run([sys.executable, "-B", str(REPO / "scripts/doctor-core.py"),
                                 "--root", str(REPO), "--codex-home", str(home), "--json"],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
        report = json.loads(result.stdout)
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        self.assertNotIn("hook_configuration_present", report["errors"])
        audit = report["codex_audit"]["hooks"]
        self.assertIs(audit["ok"], True)
        self.assertIs(audit.get("managed"), False)
        self.assertTrue(audit.get("observations"), "user hooks should remain visible as observations")
        self.assertTrue(report["errors"], "missing installation must still fail the rest of the audit")
        self.assertIs(report["ok"], False)
        self.assertNotEqual(result.returncode, 0)

    def test_sync_rejects_linked_skills_parent_before_any_publication(self):
        self.assert_parent_link_rejected("skills")

    def test_sync_rejects_linked_metadata_parent_before_any_publication(self):
        self.assert_parent_link_rejected(".ai-harness")

    def assert_parent_link_rejected(self, relative):
        module, source, home = self.sync_fixture()
        home.mkdir()
        (home / "user-config.txt").write_bytes(b"user home bytes\r\n")
        outside = self.root / "outside-install-home"
        outside.mkdir()
        (outside / "user-data.txt").write_bytes(b"outside user bytes\r\n")
        link = home / relative
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest("Host cannot create test symlink: " + str(error))
        home_before = self.snapshot(home)
        outside_before = self.snapshot(outside)
        home_entries = {path.relative_to(home).as_posix() for path in home.rglob("*")}
        outside_entries = {path.relative_to(outside).as_posix() for path in outside.rglob("*")}
        result = module.synchronize(source, home)
        self.assertIs(result["ok"], False, "a linked installation parent must block sync before publication")
        self.assertEqual(self.snapshot(home), home_before)
        self.assertEqual(self.snapshot(outside), outside_before)
        self.assertEqual({path.relative_to(home).as_posix() for path in home.rglob("*")}, home_entries)
        self.assertEqual({path.relative_to(outside).as_posix() for path in outside.rglob("*")}, outside_entries)
        self.assertTrue(link.is_symlink())

    def sync_fixture(self):
        scripts = str(REPO / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location("portable_legacy_sync", REPO / "scripts/sync-codex.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = self.root / "source"
        home = self.root / "isolated-home"
        self.write("source/rules/registry/RULES_ENTRY.md", "# Fixture harness\n")
        for name in module.MANAGED_SKILLS:
            self.write(f"source/skills/{name}/SKILL.md", f"original {name}\n")
        return module, source, home

    def test_bootstrap_default_hook_behavior_preserves_existing_bytes(self):
        home = self.root / "isolated-home"
        original = (b'{\r\n  "hooks": {"SessionStart": [{"hooks": [{"type": "command", '
                    b'"command": "echo fixture-user-hook"}]}]},\r\n  "user_setting": true\r\n}\r\n')
        hooks = self.write("isolated-home/hooks.json", original)
        result = subprocess.run([sys.executable, "-B", str(REPO / "scripts/bootstrap-local.py"),
            "--harness-root", str(REPO), "--codex-home", str(home),
            "--skip-sync", "--skip-rules", "--skip-doctor", "--json"],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIs(json.loads(result.stdout)["ok"], True)
        self.assertEqual(hooks.read_bytes(), original, "default bootstrap must not rewrite user hooks")

    def test_first_sync_rejects_unowned_skill_before_any_tree_replacement(self):
        module, source, home = self.sync_fixture()
        name = module.MANAGED_SKILLS[-1]
        self.write(f"isolated-home/skills/{name}/notes.txt", "unmanaged user skill contents\n")
        before = self.snapshot(home / "skills")
        result = module.synchronize(source, home)
        self.assertIs(result["ok"], False, "an unknown existing skill directory must block full sync")
        self.assertEqual(self.snapshot(home / "skills"), before)
        self.assertFalse((home / ".ai-harness/codex-sync.receipt.json").exists())

    def test_managed_drift_blocks_full_sync_without_partial_updates(self):
        module, source, home = self.sync_fixture()
        self.assertIs(module.synchronize(source, home)["ok"], True)
        for name in module.MANAGED_SKILLS:
            (source / "skills" / name / "SKILL.md").write_text("new source version\n")
        drift = home / "skills" / module.MANAGED_SKILLS[-1] / "SKILL.md"
        drift.write_bytes(b"user customization\r\n")
        before = self.snapshot(home)
        result = module.synchronize(source, home)
        self.assertIs(result["ok"], False, "managed hash drift must block full sync")
        self.assertEqual(self.snapshot(home), before)

    def test_unknown_extra_file_blocks_full_sync_without_deleting_user_data(self):
        module, source, home = self.sync_fixture()
        self.assertIs(module.synchronize(source, home)["ok"], True)
        for name in module.MANAGED_SKILLS:
            (source / "skills" / name / "SKILL.md").write_text("new source version\n")
        extra = home / "skills" / module.MANAGED_SKILLS[-1] / "personal-notes.md"
        extra.write_bytes(b"unreceipted user file")
        before = self.snapshot(home)
        result = module.synchronize(source, home)
        self.assertIs(result["ok"], False, "unreceipted extra files must block destructive tree sync")
        self.assertEqual(self.snapshot(home), before)
