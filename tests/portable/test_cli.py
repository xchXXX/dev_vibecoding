"""Invoke the actual CLI and assert exits, JSON and installed bytes."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from support import PortableCase, REPO


class CliTests(PortableCase):
    def test_start_session_snapshot_escape_rejection_does_not_write_skill_cache(self):
        skill = self.root / "skills/global-task-orchestrator"
        for name in ("start_session.py", "runtime_evidence.py"):
            self.write("skills/global-task-orchestrator/scripts/" + name,
                       (REPO / "skills/global-task-orchestrator/scripts" / name).read_bytes())
        task_id = "synthetic-snapshot-rejection"
        consumer = self.root / "consumer"
        state = {"acceptance_gate": {"current_candidate": {
            "runtime_snapshot": {"path": "../outside", "sha256": "a" * 64}}}}
        self.write("consumer/docs/ai/tasks/" + task_id + "/state.json", json.dumps(state))
        for relative in ("docs/ai/tasks/" + task_id + "/task.md",
                         "docs/ai/tasks/" + task_id + "/events.jsonl",
                         "docs/tasks/" + task_id + "/plan.md",
                         "docs/tasks/" + task_id + "/execution.md",
                         "docs/tasks/" + task_id + "/acceptance.md"):
            self.write("consumer/" + relative, "Synthetic rejection fixture; not a successful resume.\n")
        sentinel = self.write("outside/user.txt", b"outside user bytes\r\n")
        before_skill = self.snapshot(skill)
        before_consumer = self.snapshot(consumer)
        environment = dict(os.environ)
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        environment.pop("PYTHONPYCACHEPREFIX", None)
        result = subprocess.run([sys.executable, str(skill / "scripts/start_session.py"),
                                 "--task-id", task_id, "--repo-root", str(consumer), "--json"],
                                cwd=self.root, env=environment, capture_output=True,
                                text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIs(report["ok"], False)
        self.assertIn("runtime snapshot escapes repository", report["errors"])
        self.assertEqual(self.snapshot(consumer), before_consumer)
        self.assertEqual(sentinel.read_bytes(), b"outside user bytes\r\n")
        self.assertEqual(self.snapshot(skill), before_skill,
                         "Actual snapshot rejection must not create bytecode in the installed skill")

    def test_plain_python_gto_help_allows_uninstall_and_reinstall(self):
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("Real jsonschema installation is required for the canonical GTO controller")
        source = REPO / "skills/global-task-orchestrator"
        relatives = ["SKILL.md", "scripts/orchestrator_ctl.py", "scripts/runtime_evidence.py",
                     "scripts/capability_gate.py", "scripts/acceptance_batches.py"]
        directory, _ = self.bundle(entries=[
            ("gto", "skills", "global-task-orchestrator/" + relative,
             (source / relative).read_bytes()) for relative in relatives])
        config = self.config()
        config["codex_home"].mkdir()
        sentinel = config["codex_home"] / "config.toml"
        user_bytes = b"# User-owned configuration\r\nfixture = true\r\n"
        sentinel.write_bytes(user_bytes)
        flags = ["--codex-home", config["codex_home"], "--skills-dir", config["skills_dir"],
                 "--modules", "gto", "--json"]
        installed = self.cli("install", "--bundle", directory, *flags)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        controller = config["skills_dir"] / "global-task-orchestrator/scripts/orchestrator_ctl.py"
        environment = dict(os.environ)
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        environment.pop("PYTHONPYCACHEPREFIX", None)
        help_result = subprocess.run([sys.executable, str(controller), "--help"], cwd=self.root,
                                     env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(help_result.returncode, 0, help_result.stdout + help_result.stderr)
        self.assertIn("--action", help_result.stdout)
        uninstalled = self.cli("uninstall", *flags)
        self.assertEqual(uninstalled.returncode, 0, uninstalled.stdout + uninstalled.stderr)
        self.assertEqual(sentinel.read_bytes(), user_bytes)
        residual = sorted(str(path.relative_to(config["skills_dir"]))
                          for path in config["skills_dir"].rglob("*.pyc"))
        reinstalled = self.cli("install", "--bundle", directory, *flags)
        self.assertEqual(reinstalled.returncode, 0,
                         reinstalled.stdout + reinstalled.stderr + " Residual bytecode: " + repr(residual))
        self.assertIs(json.loads(reinstalled.stdout)["ok"], True)
        self.assertEqual(controller.read_bytes(), (source / "scripts/orchestrator_ctl.py").read_bytes())
        self.assertEqual(sentinel.read_bytes(), user_bytes)

    def test_documented_python_install_and_doctor_leave_package_unchanged(self):
        directory, manifest = self.bundle()
        for source in [REPO / "scripts/harness.py", *sorted((REPO / "modules/harness").rglob("*.py"))]:
            relative = source.relative_to(REPO).as_posix()
            content = source.read_bytes()
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            manifest["payload_files"].append({"source": relative, "sha256": hashlib.sha256(content).hexdigest()})
        self.save_manifest(directory, manifest)
        before = self.snapshot(directory)
        environment = dict(os.environ)
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        environment.pop("PYTHONPYCACHEPREFIX", None)
        home = self.root / "documented recipient home"
        for action in ("install", "doctor"):
            with self.subTest(action=action):
                result = subprocess.run([sys.executable, str(directory / "scripts/harness.py"),
                                         action, "--codex-home", str(home), "--json"],
                                        cwd=self.root, env=environment, capture_output=True,
                                        text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertIs(report["ok"], True)
                if action == "doctor":
                    self.assertIs(report["installed"], True)
        self.assertEqual(self.snapshot(directory), before,
                         "Documented ordinary Python invocation must not add or modify package files")

    def test_duplicate_configuration_options_reject_before_install_writes(self):
        directory, _ = self.bundle()
        for option in ("codex-home", "skills-dir", "environment", "config"):
            for same in (True, False):
                with self.subTest(option=option, same=same):
                    case = self.root / (option + ("-same" if same else "-different"))
                    case.mkdir()
                    home_a, home_b = case / "home-a", case / "home-b"
                    skills_a, skills_b = case / "skills-a", case / "skills-b"
                    sentinel = case / "user.txt"
                    sentinel.write_bytes(b"existing user bytes\r\n")
                    values = {"codex-home": (home_a, home_b), "skills-dir": (skills_a, skills_b),
                              "environment": ("auto", "linux")}
                    for label, home in (("a", home_a), ("b", home_b)):
                        (case / (label + ".json")).write_text(json.dumps({"codex_home": str(home)}), encoding="utf-8")
                    values["config"] = (case / "a.json", case / "b.json")
                    first, second = values[option]
                    flags = [] if option in ("codex-home", "config") else ["--codex-home", home_a]
                    flags += ["--" + option, first, "--" + option, first if same else second]
                    result = self.cli("install", "--bundle", directory, *flags, "--json")
                    self.assertEqual(sentinel.read_bytes(), b"existing user bytes\r\n")
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    report = json.loads(result.stdout)
                    self.assertIs(report["ok"], False)
                    self.assertEqual(report["code"], "CONFIG_INVALID")
                    for target in (home_a, home_b, skills_a, skills_b):
                        self.assertFalse(target.exists(), "configuration rejection must precede all installation writes")

    def test_duplicate_json_home_rejects_public_install_without_writes(self):
        directory, _ = self.bundle()
        for same in (True, False):
            with self.subTest(same=same):
                case = self.root / ("json-same" if same else "json-different")
                case.mkdir()
                home_a, home_b = case / "home-a", case / "home-b"
                raw = ('{"codex_home":' + json.dumps(str(home_a)) + ',"codex_home":'
                       + json.dumps(str(home_a if same else home_b)) + '}')
                config_file = case / "settings.json"
                config_file.write_text(raw, encoding="utf-8")
                before = config_file.read_bytes()
                result = self.cli("install", "--bundle", directory, "--config", config_file, "--json")
                self.assertEqual(config_file.read_bytes(), before)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["code"], "CONFIG_INVALID")
                self.assertIs(report["ok"], False)
                self.assertFalse(home_a.exists())
                self.assertFalse(home_b.exists())

    def test_doctor_blocks_gto_and_git_workflow_when_only_git_is_missing(self):
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest("Real jsonschema installation is required to isolate the missing-Git case")
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle(entries=[
            ("gto", "skills", "global-task-orchestrator/SKILL.md",
             b"---\nname: global-task-orchestrator\ndescription: fixture\n---\n# GTO\n")])
        config = self.config()
        install(directory, config)
        environment = dict(os.environ, PATH="")
        result = subprocess.run([sys.executable, "-B", str(REPO / "scripts/harness.py"),
                                 "doctor", "--codex-home", str(config["codex_home"]),
                                 "--skills-dir", str(config["skills_dir"]), "--json"],
                                cwd=self.root, env=environment, capture_output=True,
                                text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIs(report["dependencies"]["git"], False)
        self.assertIs(report["dependencies"]["jsonschema"], True)
        self.assertIs(report["ok"], True)
        self.assertIs(report["session_verified"], False)
        self.assertIn("git_workflow", report["blocked_capabilities"])
        self.assertIn("gto", report["blocked_capabilities"],
                      "GTO requires Git even when jsonschema is available")

    def test_doctor_reports_gto_dependency_block_without_failing_file_integrity(self):
        install = self.api("lifecycle", "install")
        directory, _ = self.bundle(entries=[
            ("gto", "skills", "global-task-orchestrator/SKILL.md",
             b"---\nname: global-task-orchestrator\ndescription: fixture\n---\n# GTO\n")])
        config = self.config()
        install(directory, config)
        result = subprocess.run([sys.executable, "-S", "-B", str(REPO / "scripts/harness.py"),
                                 "doctor", "--codex-home", str(config["codex_home"]),
                                 "--skills-dir", str(config["skills_dir"]), "--json"],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIs(report["ok"], True, "missing optional GTO dependency must not invalidate installed files")
        self.assertIs(report["session_verified"], False)
        self.assertIn("gto", report.get("blocked_capabilities", []),
                      "doctor must identify GTO as blocked when jsonschema is unavailable")
        next_step = report.get("next_step", "").lower()
        self.assertTrue("jsonschema" in next_step or "requirements" in next_step,
                        "doctor must explain dependency preparation before suggesting a new session")

    def test_packaged_cli_defaults_bundle_to_its_own_root_from_unrelated_cwd(self):
        directory, manifest = self.bundle()
        sources = [REPO / "scripts/harness.py", *sorted((REPO / "modules/harness").rglob("*.py"))]
        for path in sources:
            relative = path.relative_to(REPO).as_posix()
            content = path.read_bytes()
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            manifest["payload_files"].append({"source": relative, "sha256": hashlib.sha256(content).hexdigest()})
        self.save_manifest(directory, manifest)
        unrelated = self.root / "unrelated cwd"
        unrelated.mkdir()
        home = self.root / "recipient home"
        result = subprocess.run([sys.executable, "-B", str(directory / "scripts/harness.py"),
                                 "install", "--codex-home", str(home), "--json"],
                                cwd=unrelated, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIs(json.loads(result.stdout)["ok"], True)
        self.assertEqual((home / "skills/fix-closure-gate/SKILL.md").read_bytes(), b"fix-v1\n")
        self.assertEqual((home / ".ai-harness/portable/runtime/rules/example.md").read_bytes(), b"base-v1\n")

    def cli(self, *args):
        script = REPO / "scripts/harness.py"
        self.assertTrue(script.is_file(), "Missing frozen production CLI scripts/harness.py")
        result = subprocess.run([sys.executable, "-B", str(script), *map(str, args)],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        return result

    def test_install_doctor_update_uninstall_json_lifecycle(self):
        directory, _ = self.bundle()
        config = self.config()
        flags = ["--codex-home", config["codex_home"], "--skills-dir", config["skills_dir"], "--json"]
        install = self.cli("install", "--bundle", directory, *flags)
        self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
        self.assertIs(json.loads(install.stdout)["ok"], True)
        doctor = self.cli("doctor", *flags)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertIs(json.loads(doctor.stdout)["session_verified"], False)
        new, _ = self.bundle("new", "2.0.0", [("base", "home", ".ai-harness/portable/runtime/rules/example.md", b"base-v2"),
                                             ("fix", "skills", "fix-closure-gate/SKILL.md", b"fix-v2")])
        update = self.cli("update", "--bundle", new, "--modules", "fix", *flags)
        self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
        self.assertEqual((config["skills_dir"] / "fix-closure-gate/SKILL.md").read_bytes(), b"fix-v2")
        uninstall = self.cli("uninstall", *flags)
        self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
        self.assertFalse((config["skills_dir"] / "fix-closure-gate/SKILL.md").exists())

    def test_dry_run_has_no_installation_side_effects(self):
        directory, _ = self.bundle()
        config = self.config()
        result = self.cli("install", "--bundle", directory, "--codex-home", config["codex_home"],
                          "--skills-dir", config["skills_dir"], "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIs(json.loads(result.stdout)["ok"], True)
        self.assertFalse(config["codex_home"].exists())
        self.assertFalse(config["skills_dir"].exists())

    def test_missing_home_returns_nonzero_structured_error(self):
        result = self.cli("doctor", "--codex-home", "relative-home", "--json")
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIs(payload["ok"], False)
        self.assertTrue(payload["code"])
        self.assertTrue(payload["message"])

    def test_unknown_option_is_rejected(self):
        result = self.cli("doctor", "--codex-home", self.root / "home", "--unknown-option")
        self.assertNotEqual(result.returncode, 0)

    def test_human_and_json_success_modes_both_install_same_bytes(self):
        directory, _ = self.bundle()
        for name, json_mode in (("human", []), ("json", ["--json"])):
            result = self.cli("install", "--bundle", directory, "--codex-home", self.root / name,
                              "--modules", "fix", *json_mode)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(result.stdout.strip())
            self.assertEqual((self.root / name / "skills/fix-closure-gate/SKILL.md").read_bytes(), b"fix-v1\n")
