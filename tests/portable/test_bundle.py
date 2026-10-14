"""Catch acceptance of tampered files and paths escaping either install root."""
import copy
import hashlib
import json
import subprocess
from support import PortableCase


class BundleTests(PortableCase):
    def test_build_declares_dependencies_entrypoint_and_candidate_platforms(self):
        build = self.api("bundle", "build_release")
        load = self.api("bundle", "load_bundle")
        source, commit = self.fixed_source()
        output = self.root / "release"
        build(source, output, "1.0.0", commit)
        manifest = load(output)
        with self.subTest(metadata="dependencies"):
            self.assertEqual(manifest.get("dependencies"), {
                "python": ">=3.11", "git": {"required_for": ["build", "git_workflow", "gto"]},
                "jsonschema": {"specifier": ">=4.10.3,<5", "required_for": ["gto"]}})
        with self.subTest(metadata="build_entrypoint"):
            self.assertEqual(manifest.get("build_entrypoint"), "scripts/harness.py build")
        with self.subTest(metadata="support_matrix"):
            self.assertEqual(manifest.get("support_matrix"), {
                "windows": {"status": "candidate", "session_verified": False},
                "linux": {"status": "candidate", "session_verified": False},
                "wsl": {"status": "candidate", "session_verified": False}})

    def test_load_rejects_missing_or_malformed_release_metadata(self):
        load = self.api("bundle", "load_bundle")
        directory, original = self.bundle()
        load(directory)
        for field in ("dependencies", "build_entrypoint", "support_matrix"):
            with self.subTest(missing=field):
                malformed = copy.deepcopy(original)
                del malformed[field]
                self.save_manifest(directory, malformed)
                self.assertEqual(self.assertRejected(lambda: load(directory)).code, "BUNDLE_INVALID")
        for keys, value in (
                (("dependencies",), []),
                (("dependencies", "python"), []),
                (("dependencies", "git", "required_for"), "build"),
                (("dependencies", "jsonschema", "specifier"), 4),
                (("build_entrypoint",), []),
                (("support_matrix",), []),
                (("support_matrix", "windows"), {"status": "candidate"}),
                (("support_matrix", "wsl", "session_verified"), "false")):
            with self.subTest(malformed=".".join(keys)):
                malformed = copy.deepcopy(original)
                target = malformed
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                self.save_manifest(directory, malformed)
                self.assertEqual(self.assertRejected(lambda: load(directory)).code, "BUNDLE_INVALID")

    def fixed_source(self):
        source = self.root / "source"
        for path, content in {
            "templates/codex/AGENTS.global.md": "# Fixture rules\n",
            "rules/items/policy/example.md": "# Example\n",
            "rules/registry/RULES_INDEX.json": '{"rules": []}\n',
            "modules/harness/__init__.py": "",
            "modules/harness/config.py": "# fixture config\n",
            "scripts/harness.py": "print('fixture')\n",
            "skills/fix-closure-gate/SKILL.md": "---\nname: fix-closure-gate\ndescription: fixture\n---\n# Fix\n",
            "memories/private.txt": "FIXTURE USER MEMORY MUST NOT SHIP\n",
            ".tmp/private.txt": "FIXTURE TEMP MUST NOT SHIP\n",
            "config/local/secret.json": '{"fixture": "DO NOT SHIP"}\n',
        }.items():
            self.write("source/" + path, content)
        def git(*args):
            return subprocess.run(["git", "-C", str(source), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git("init", "--quiet")
        git("add", ".")
        git("-c", "user.name=Portable Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "test fixture")
        return source, git("rev-parse", "HEAD")

    def test_build_reads_fixed_commit_and_is_deterministic(self):
        build = self.api("bundle", "build_release")
        load = self.api("bundle", "load_bundle")
        source, commit = self.fixed_source()
        build(source, self.root / "first", "1.0.0", commit)
        self.write("source/rules/items/policy/example.md", "DIRTY CONTENT MUST NOT SHIP\n")
        build(source, self.root / "second", "1.0.0", commit)
        first = self.snapshot(self.root / "first")
        self.assertEqual(first, self.snapshot(self.root / "second"))
        manifest = load(self.root / "first")
        self.assertEqual(manifest["source_commit"], commit)
        payload = b"\n".join(first.values())
        self.assertIn(b"# Example", payload)
        for excluded in (b"DIRTY CONTENT", b"FIXTURE USER MEMORY", b"FIXTURE TEMP", b"DO NOT SHIP"):
            self.assertNotIn(excluded, payload)
        self.assertFalse(any(".git/" in path for path in first))

    def test_build_rejects_mutable_source_reference(self):
        build = self.api("bundle", "build_release")
        source, _ = self.fixed_source()
        self.assertRejected(lambda: build(source, self.root / "output", "1.0.0", "HEAD"))

    def test_build_exports_recipient_docs_and_git_runtime_without_private_design(self):
        build = self.api("bundle", "build_release")
        load = self.api("bundle", "load_bundle")
        source, _ = self.fixed_source()
        design = "docs/modules/portable-harness/design/internal.md"
        install_doc = "docs/INSTALL.md"
        git_script = "scripts/check_git_workflow.py"
        git_contract = "docs/modules/git-workflow/contract/README.md"
        for relative, content in {
            design: "AUTHOR_PRIVATE_DESIGN_SENTINEL D:/author/private/task-history\n",
            install_doc: "RECIPIENT_INSTALL_GUIDE\n",
            git_script: "print('GIT_WORKFLOW_RUNTIME')\n",
            git_contract: "GIT_WORKFLOW_CONTRACT\n",
        }.items():
            self.write("source/" + relative, content)
        subprocess.run(["git", "-C", str(source), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(source), "-c", "user.name=Portable Fixture",
                        "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                        "commit", "--quiet", "-m", "recipient package fixture"], check=True, capture_output=True)
        commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True).stdout.strip()
        output = self.root / "export"
        build(source, output, "1.0.0", commit)
        manifest = load(output)
        exported = self.snapshot(output)
        all_bytes = b"\n".join(exported.values())
        with self.subTest(boundary="private design excluded"):
            self.assertNotIn(b"AUTHOR_PRIVATE_DESIGN_SENTINEL", all_bytes)
            self.assertFalse(any("/design/" in path for path in exported))
        with self.subTest(boundary="recipient install instructions included"):
            self.assertIn(install_doc, {row["source"] for row in manifest["payload_files"]})
            self.assertEqual((output / install_doc).read_bytes(), b"RECIPIENT_INSTALL_GUIDE\n")
        files = {row["target"]: row for row in manifest["files"]}
        for relative, expected in ((git_script, b"print('GIT_WORKFLOW_RUNTIME')\n"),
                                   (git_contract, b"GIT_WORKFLOW_CONTRACT\n")):
            with self.subTest(runtime=relative):
                target = ".ai-harness/portable/runtime/" + relative
                self.assertIn(target, files)
                self.assertEqual(files[target]["module"], "base")
                self.assertEqual((output / files[target]["source"]).read_bytes(), expected)

    def test_build_filters_project_rules_from_files_and_exported_index(self):
        build = self.api("bundle", "build_release")
        load = self.api("bundle", "load_bundle")
        source, _ = self.fixed_source()
        global_path = "rules/items/policy/example.md"
        project_path = "rules/items/architecture/private-project-rule.md"
        global_id = "global.policy.fixture"
        project_id = "project.architecture.private-fixture"
        for relative, identifier, scope, body in (
                (global_path, global_id, "global", "PUBLIC_GLOBAL_RULE"),
                (project_path, project_id, "project", "PRIVATE_PROJECT_RULE_MUST_NOT_SHIP")):
            self.write("source/" + relative,
                       f"---\nid: {identifier}\nscope: {scope}\n---\n{body}\n")
        index = {"schema_version": "2.0", "repo_root": "<repo-root>", "local_rule_count": 2,
                 "global_rules": {"mode": "none", "roots": [], "discovered": False, "searched": []},
                 "rules": [{"id": global_id, "scope": "global", "file_path": global_path},
                           {"id": project_id, "scope": "project", "file_path": project_path}]}
        self.write("source/rules/registry/RULES_INDEX.json", json.dumps(index))
        subprocess.run(["git", "-C", str(source), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(source), "-c", "user.name=Portable Fixture",
                        "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                        "commit", "--quiet", "-m", "rule scope fixture"], check=True, capture_output=True)
        commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True).stdout.strip()
        output = self.root / "export"
        build(source, output, "1.0.0", commit)
        manifest = load(output)
        targets = {row["target"] for row in manifest["files"]}
        self.assertIn(".ai-harness/portable/runtime/" + global_path, targets)
        self.assertNotIn(".ai-harness/portable/runtime/" + project_path, targets)
        exported_index = next(row for row in manifest["files"]
                              if row["target"].endswith("/rules/registry/RULES_INDEX.json"))
        exported = json.loads((output / exported_index["source"]).read_text())
        self.assertEqual([row["id"] for row in exported["rules"]], [global_id])
        self.assertEqual(exported["local_rule_count"], 1)
        all_bytes = b"\n".join(self.snapshot(output).values())
        self.assertNotIn(b"PRIVATE_PROJECT_RULE_MUST_NOT_SHIP", all_bytes)
        self.assertNotIn(project_id.encode(), all_bytes)

    def test_valid_handwritten_bundle_loads(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle()
        actual = load(directory)
        self.assertEqual(actual["version"], "1.0.0")
        self.assertEqual(actual["files"], manifest["files"])

    def test_tampered_install_file_is_rejected(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle()
        (directory / manifest["files"][0]["source"]).write_bytes(b"tampered")
        self.assertRejected(lambda: load(directory))

    def test_payload_tools_are_hash_checked(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle()
        content = b"print('fixture')\n"
        tool = self.write("bundle/scripts/harness.py", content)
        manifest["payload_files"] = [{"source": "scripts/harness.py", "sha256": hashlib.sha256(content).hexdigest()}]
        self.save_manifest(directory, manifest)
        load(directory)
        tool.write_bytes(b"corrupt")
        self.assertRejected(lambda: load(directory))

    def test_source_and_target_unsafe_paths_are_rejected(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle()
        record = manifest["files"][0]
        for field in ("source", "target"):
            original = record[field]
            for unsafe in ("../outside", "/absolute", "C:/escape", "a/../../escape", "..\\escape"):
                with self.subTest(field=field, unsafe=unsafe):
                    record[field] = unsafe
                    self.save_manifest(directory, manifest)
                    self.assertRejected(lambda: load(directory))
            record[field] = original

    def test_case_insensitive_target_collision_is_rejected(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle(entries=[("fix", "skills", "fix-closure-gate/SKILL.md", b"one"),
                                                    ("fix", "skills", "fix-closure-gate/skill.md", b"two")])
        self.assertRejected(lambda: load(directory))

    def test_unknown_module_root_and_schema_are_rejected(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle()
        for field, bad in (("module", "unknown"), ("root", "other-home")):
            old = manifest["files"][0][field]
            manifest["files"][0][field] = bad
            self.save_manifest(directory, manifest)
            self.assertRejected(lambda: load(directory))
            manifest["files"][0][field] = old
        manifest["schema_version"] = 999
        self.save_manifest(directory, manifest)
        self.assertRejected(lambda: load(directory))

    def test_symlink_source_is_rejected(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle()
        source = directory / manifest["files"][0]["source"]
        outside = self.write("outside.md", source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(outside)
        except OSError as error:
            self.skipTest("Host cannot create test symlink: " + str(error))
        self.assertRejected(lambda: load(directory))

    def test_build_refuses_nonempty_output_without_overwriting(self):
        build = self.api("bundle", "build_release")
        self.write("output/owned.txt", b"user data")
        before = self.snapshot(self.root / "output")
        self.assertRejected(lambda: build(self.root / "source", self.root / "output", "1.0.0", "a" * 40))
        self.assertEqual(self.snapshot(self.root / "output"), before)

    def test_unlisted_file_in_bundle_is_rejected(self):
        load = self.api("bundle", "load_bundle")
        directory, _ = self.bundle()
        self.write("bundle/payload/not-listed.txt", b"unexpected")
        self.assertRejected(lambda: load(directory))

    def test_unlisted_nested_manifest_is_rejected(self):
        load = self.api("bundle", "load_bundle")
        directory, _ = self.bundle()
        self.write("bundle/extra/manifest.json", '{"not": "listed"}')
        error = self.assertRejected(lambda: load(directory))
        self.assertEqual(error.code, "BUNDLE_INVALID")

    def test_base_module_cannot_write_user_config(self):
        load = self.api("bundle", "load_bundle")
        directory, _ = self.bundle(entries=[("base", "home", "config.toml", b"unauthorized")])
        self.assertRejected(lambda: load(directory))

    def test_module_cannot_claim_another_skill_directory(self):
        load = self.api("bundle", "load_bundle")
        directory, _ = self.bundle(entries=[("fix", "skills", "global-task-orchestrator/SKILL.md", b"unauthorized")])
        self.assertRejected(lambda: load(directory))

    def test_windows_reserved_target_names_are_rejected_on_every_host(self):
        load = self.api("bundle", "load_bundle")
        directory, manifest = self.bundle()
        for target in ("fix-closure-gate/CON", "fix-closure-gate/nul.txt", "fix-closure-gate/file:stream"):
            with self.subTest(target=target):
                manifest["files"][1]["target"] = target
                self.save_manifest(directory, manifest)
                self.assertRejected(lambda: load(directory))
