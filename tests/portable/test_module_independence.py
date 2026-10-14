"""Module selection must not imply installation of orchestration or base."""
from support import PortableCase


class ModuleIndependenceTests(PortableCase):
    def test_fix_install_has_no_implicit_base_or_gto_dependency(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle(entries=[("base", "home", ".ai-harness/portable/runtime/rules/example.md", b"base"),
                                            ("fix", "skills", "fix-closure-gate/SKILL.md", b"fix"),
                                            ("gto", "skills", "global-task-orchestrator/SKILL.md", b"gto")])
        config = self.config()
        install(directory, config, selected=["fix"])
        self.assertTrue((config["skills_dir"] / "fix-closure-gate/SKILL.md").is_file())
        self.assertFalse((config["skills_dir"] / "global-task-orchestrator").exists())
        self.assertFalse((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").exists())

    def test_unknown_module_selection_has_no_payload_writes(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle()
        config = self.config()
        self.assertRejected(lambda: install(directory, config, selected=["unknown"]))
        self.assertFalse((config["codex_home"] / ".ai-harness/portable/runtime/rules/example.md").exists())
        self.assertFalse((config["skills_dir"] / "fix-closure-gate/SKILL.md").exists())
