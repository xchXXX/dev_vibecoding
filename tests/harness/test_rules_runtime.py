from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
REGISTRY_ROOT = REPO_ROOT / "rules" / "registry"
EXPECTED_ALWAYS_ON_RULE_IDS = {
    "global.policy.变更约束",
    "global.workflow.用户提问先回答再继续",
    "global.style.说明默认使用中文",
}


def load_rules_runtime():
    module_path = SCRIPTS_ROOT / "rules_index.py"
    if not module_path.is_file():
        raise AssertionError(f"missing WSL rules runtime: {module_path}")
    spec = importlib.util.spec_from_file_location("ai_harness_rules_index", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load WSL rules runtime: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RulesFreeReadContractTests(unittest.TestCase):
    def load_committed_index(self) -> dict:
        return json.loads((REGISTRY_ROOT / "RULES_INDEX.json").read_text(encoding="utf-8"))

    def test_index_has_exactly_three_always_on_rules(self) -> None:
        index = self.load_committed_index()
        actual = {
            rule["id"]
            for rule in index["rules"]
            if rule.get("activation") == "always_on"
        }

        self.assertEqual(EXPECTED_ALWAYS_ON_RULE_IDS, actual)

    def test_index_contains_metadata_but_no_rule_body(self) -> None:
        index = self.load_committed_index()
        forbidden_body_fields = {"body", "content", "markdown", "rule_text"}

        for rule in index["rules"]:
            with self.subTest(rule_id=rule.get("id")):
                self.assertTrue(forbidden_body_fields.isdisjoint(rule))

    def test_rules_index_is_the_only_machine_metadata_index(self) -> None:
        machine_indexes = {path.name for path in REGISTRY_ROOT.glob("RULES_*.json")}

        self.assertEqual({"RULES_INDEX.json"}, machine_indexes)
        self.assertFalse(
            (REGISTRY_ROOT / "RULES_RESOLVED.json").exists(),
            "RULES_RESOLVED.json must not be a committed or runtime artifact",
        )

    def test_python_runtime_has_no_semantic_profile_or_matcher_api(self) -> None:
        runtime = load_rules_runtime()
        forbidden_runtime_api = {
            "PROFILE_FIELDS",
            "validate_task_profile",
            "_path_matches",
            "match_rules",
        }

        for name in sorted(forbidden_runtime_api):
            with self.subTest(name=name):
                self.assertFalse(
                    hasattr(runtime, name),
                    f"rules_index.py must stay mechanical; remove runtime semantic API {name}",
                )

    def test_agents_and_entry_delegate_optional_rule_selection_to_codex(self) -> None:
        for relative_path in ("AGENTS.md", "rules/registry/RULES_ENTRY.md"):
            text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                for fragment in (
                    "Codex",
                    "对话语义",
                    "目标内容",
                    "风险",
                    "当前阶段",
                    "本轮实际操作",
                    "自由",
                    "paths",
                ):
                    self.assertIn(fragment, text)
                self.assertIn("正常交互链不", text)
                self.assertIn("task_profile", text)
                self.assertIn("固定", text)
                self.assertIn("套餐", text)


class RulesCliTests(unittest.TestCase):
    def run_json_cli(self, script_name: str, *arguments: str) -> dict:
        script_path = SCRIPTS_ROOT / script_name
        self.assertTrue(script_path.is_file(), f"missing Python CLI: {script_path}")
        process = subprocess.run(
            [sys.executable, str(script_path), *arguments, "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            0,
            process.returncode,
            f"{script_name} failed\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}",
        )
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"{script_name} did not emit one JSON document: {error}\n{process.stdout}")
        self.assertTrue(payload.get("ok"), payload)
        return payload

    def test_generate_and_validate_rules_have_wsl_python_clis(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-rules-output-") as temp_dir:
            output_dir = Path(temp_dir)
            generated = self.run_json_cli(
                "generate_rules_index.py",
                "--repo-root",
                str(REPO_ROOT),
                "--output-dir",
                str(output_dir),
            )
            self.assertEqual(str(output_dir.resolve()), str(Path(generated["output_dir"]).resolve()))
            self.assertNotIn("resolved_rule_count", generated)
            self.assertEqual(
                {"RULES_INDEX.json", "RULES_INDEX.md"},
                {path.name for path in output_dir.iterdir()},
            )
            generated_index = json.loads(
                (output_dir / "RULES_INDEX.json").read_text(encoding="utf-8")
            )
            for rule in generated_index["rules"]:
                self.assertNotIn("body", rule)
            self.assertFalse((output_dir / "RULES_RESOLVED.json").exists())

        validated = self.run_json_cli("validate_rules.py", "--repo-root", str(REPO_ROOT))
        self.assertNotIn("resolved_rule_count", validated)

    def test_tooling_rule_is_generated_as_optional_layered_global_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-harness-tooling-rule-") as temp_dir:
            output_dir = Path(temp_dir)
            self.run_json_cli(
                "generate_rules_index.py",
                "--repo-root",
                str(REPO_ROOT),
                "--output-dir",
                str(output_dir),
            )
            generated_index = json.loads(
                (output_dir / "RULES_INDEX.json").read_text(encoding="utf-8")
            )

        rule_id = "global.policy.缺失工具分层与依赖处理"
        generated_rule = next(
            (rule for rule in generated_index["rules"] if rule["id"] == rule_id),
            None,
        )
        self.assertIsNotNone(generated_rule, "missing environment-neutral tooling decision rule")
        self.assertEqual("global", generated_rule["scope"])
        self.assertEqual("policy", generated_rule["kind"])
        self.assertEqual("model_decision", generated_rule["activation"])
        self.assertEqual(
            "rules/items/policy/缺失工具分层与依赖处理.md",
            generated_rule["file_path"],
        )
        self.assertIn("dependency", generated_rule["intents"])
        self.assertIn("browser", generated_rule["intents"])

        runtime = load_rules_runtime()
        metadata, body, _ = runtime.parse_frontmatter(
            REPO_ROOT / generated_rule["file_path"]
        )
        self.assertEqual(rule_id, metadata["id"])
        for layer_terms in (
            ("机器公共工具", "项目依赖", "可选服务/GUI", "运行环境"),
            ("项目", "manifest/lock", "venv/node_modules", "不跨系统复用"),
            ("Browser", "Windows", "WSL", "宿主实际能力", "app-managed"),
            ("系统工具缺失", "已授权范围", "不静默提权", "等价证据"),
            ("第三方源", "广泛升级", "卸载", "发行版变更", "授权"),
        ):
            with self.subTest(layer_terms=layer_terms):
                self.assertTrue(
                    all(term in body for term in layer_terms),
                    f"tooling rule misses boundary: {layer_terms}",
                )

if __name__ == "__main__":
    unittest.main()
