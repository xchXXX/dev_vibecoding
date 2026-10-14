"""Catch precedence inversions, cwd-dependent JSON paths and unsafe guessing."""
import json
from pathlib import Path
from support import PortableCase


class ConfigTests(PortableCase):
    def test_duplicate_json_fields_are_rejected_even_when_values_match(self):
        resolve = self.api("config", "resolve_config")
        values = {"codex_home": (str(self.root / "home-a"), str(self.root / "home-b")),
                  "skills_dir": (str(self.root / "skills-a"), str(self.root / "skills-b")),
                  "environment": ("auto", "linux")}
        for key, (first, different) in values.items():
            for second in (first, different):
                with self.subTest(key=key, same=first == second):
                    pairs = [] if key == "codex_home" else [("codex_home", str(self.root / "home-a"))]
                    pairs.extend([(key, first), (key, second)])
                    raw = "{" + ",".join(json.dumps(k) + ":" + json.dumps(v) for k, v in pairs) + "}"
                    config_file = self.write("duplicate.json", raw)
                    before = self.snapshot(self.root)
                    error = self.assertRejected(lambda: resolve({}, config_file, {}))
                    self.assertEqual(error.code, "CONFIG_INVALID")
                    self.assertEqual(self.snapshot(self.root), before)
                    for name in ("home-a", "home-b", "skills-a", "skills-b"):
                        self.assertFalse((self.root / name).exists())

    def test_cli_overrides_json_and_environment(self):
        resolve = self.api("config", "resolve_config")
        config_file = self.write("settings/config.json", json.dumps({
            "codex_home": "json-home", "skills_dir": "json-skills", "environment": "linux"}))
        actual = resolve({"codex_home": str(self.root / "cli-home"),
                          "skills_dir": str(self.root / "cli-skills"), "environment": "wsl"},
                         config_file, {"CODEX_HOME": str(self.root / "env-home"),
                                       "CODEX_SKILLS_DIR": str(self.root / "env-skills"),
                                       "HARNESS_ENVIRONMENT": "windows"})
        self.assertEqual(actual["codex_home"], self.root / "cli-home")
        self.assertEqual(actual["skills_dir"], self.root / "cli-skills")
        self.assertEqual(actual["environment"], "wsl")
        self.assertIsInstance(actual["codex_home"], Path)
        self.assertEqual(set(actual["sources"]), {"codex_home", "skills_dir", "environment"})
        self.assertEqual(actual["sources"], {"codex_home": "cli", "skills_dir": "cli", "environment": "cli"})

    def test_json_relative_paths_resolve_from_config_directory(self):
        resolve = self.api("config", "resolve_config")
        config_file = self.write("配置/config.json", json.dumps({
            "codex_home": "home", "skills_dir": "skills", "environment": "linux"}))
        actual = resolve({}, config_file, {"CODEX_HOME": str(self.root / "env-home")})
        self.assertEqual(actual["codex_home"], self.root / "配置" / "home")
        self.assertEqual(actual["skills_dir"], self.root / "配置" / "skills")
        self.assertEqual(actual["environment"], "linux")
        self.assertEqual(actual["sources"], {"codex_home": "config", "skills_dir": "config", "environment": "config"})

    def test_environment_inputs_and_home_relative_skills_default(self):
        resolve = self.api("config", "resolve_config")
        actual = resolve({}, environ={"CODEX_HOME": str(self.root / "home"),
                                      "HARNESS_ENVIRONMENT": "linux"})
        self.assertEqual(actual["codex_home"], self.root / "home")
        self.assertEqual(actual["skills_dir"], self.root / "home" / "skills")
        self.assertEqual(actual["environment"], "linux")
        self.assertEqual(actual["sources"], {"codex_home": "env", "skills_dir": "default", "environment": "env"})
        separate = resolve({}, environ={"CODEX_HOME": str(self.root / "home"),
                                         "CODEX_SKILLS_DIR": str(self.root / "skills")})
        self.assertEqual(separate["skills_dir"], self.root / "skills")

    def test_missing_home_is_rejected_without_guessing_from_home(self):
        resolve = self.api("config", "resolve_config")
        self.assertRejected(lambda: resolve({}, environ={"HOME": str(self.root),
                                                         "USERPROFILE": str(self.root)}))

    def test_unknown_cli_and_json_fields_are_rejected(self):
        resolve = self.api("config", "resolve_config")
        self.assertRejected(lambda: resolve({"codex_home": str(self.root), "project_root": "x"}, environ={}))
        bad = self.write("bad.json", json.dumps({"codex_home": str(self.root), "token": "fixture-not-secret"}))
        self.assertRejected(lambda: resolve({}, bad, {}))

    def test_invalid_environment_and_non_string_paths_are_rejected(self):
        resolve = self.api("config", "resolve_config")
        for values in ({"codex_home": str(self.root), "environment": "guess"},
                       {"codex_home": 42}, {"codex_home": str(self.root), "skills_dir": []}):
            with self.subTest(values=values):
                self.assertRejected(lambda: resolve(values, environ={}))

    def test_invalid_json_is_structured_error_and_read_only(self):
        resolve = self.api("config", "resolve_config")
        bad = self.write("broken.json", "{broken")
        before = self.snapshot(self.root)
        self.assertRejected(lambda: resolve({}, bad, {}))
        self.assertEqual(self.snapshot(self.root), before)

    def test_relative_cli_paths_and_empty_paths_are_rejected(self):
        resolve = self.api("config", "resolve_config")
        for values in ({"codex_home": "relative/home"}, {"codex_home": ""},
                       {"codex_home": str(self.root), "skills_dir": "relative/skills"}):
            with self.subTest(values=values):
                self.assertRejected(lambda: resolve(values, environ={}))

    def test_config_path_through_symlink_is_rejected(self):
        resolve = self.api("config", "resolve_config")
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "linked-home"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest("Host cannot create test symlink: " + str(error))
        self.assertRejected(lambda: resolve({"codex_home": str(link)}, environ={}))
