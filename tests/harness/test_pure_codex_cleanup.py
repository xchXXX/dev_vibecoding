from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_HOME = Path("/mnt/c/Users/Laptop/.claude")
HISTORICAL_CONTRACT_PREFIXES = (
    "docs/ai/tasks/",
    "docs/ai/runs/",
    "docs/tasks/",
    ".artifacts/",
)
ACTIVE_TRUTH_FILES = (
    "AGENTS.md",
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/CODEX_COMPAT.md",
    "docs/HOOKS.md",
    "docs/INSTALL.md",
    "docs/PROJECT_TEMPLATE.md",
    "docs/SUBAGENT_GOVERNANCE.md",
    "docs/plans/AI_HARNESS_MASTER_PLAN.md",
    "scripts/README.md",
    "schemas/README.md",
    "templates/README.md",
)
ACTIVE_TRUTH_TREES = ("rules", "schemas", "skills", "templates")
ACTIVE_TRUTH_SUFFIXES = {".md", ".json", ".jsonl", ".yaml", ".yml", ".toml"}
RETIRED_CONTRACT_TERMS = {
    "claude": re.compile(r"(?i)(?:\bclaude\b|\.claude(?:/|\\))"),
    "windows-gui-bridge": re.compile(r"(?i)(?:\bcomputer_use_wsl\b|\bbrowser_use_wsl\b|node-repl-wsl-compat|windows-computer-use-wsl)"),
    "hook": re.compile(
        r"(?i)(?:\bhooks?\b|\bhooks?/|(?:claude|codex|runtime|command|pretooluse|posttooluse)\s+hooks?\b|"
        r"\bhooks?\s+(?:runtime|settings|handlers|manifest|真源))"
    ),
    "RULES_RESOLVED": re.compile(r"RULES_RESOLVED"),
    "task-profile-matcher": re.compile(r"(?i)(?:task_profile|规则\s*matcher|rule\s*matcher)"),
    "legacy-packet": re.compile(
        r"(?i)\b(?:work_order|dispatch_packet|return_packet|dispatch_message_raw)\b"
    ),
}
NEGATED_OR_HISTORICAL_MARKERS = (
    "不", "无", "删除", "移除", "清理", "清空", "退休", "退役", "废弃", "旧", "历史",
    "避免", "禁止", "仅用于", "retired", "legacy", "deprecated", "removed",
)
CLAUSE_SEPARATOR = re.compile(r"[，,；;。]")
ACTIVE_ACTION_PATTERN = (
    r"(?:启用|使用|支持|保留|恢复|路由|调用|执行|作为|"
    r"\benabl(?:e|ed|es|ing)\b|\bus(?:e|ed|es|ing)\b|"
    r"\bsupport(?:ed|s|ing)?\b|\bretain(?:ed|s|ing)?\b|"
    r"\broute(?:d|s|ing)?\b|\binvok(?:e|ed|es|ing)\b|\brun(?:s|ning)?\b)"
)
ACTIVE_ACTION = re.compile(ACTIVE_ACTION_PATTERN, re.IGNORECASE)
PROHIBITIVE_ACTION = re.compile(
    r"(?:(?:不(?:再|应|得|可|要|能|会)?|禁止|避免|停止|移除|删除|清理|"
    r"do\s+not|don't|must\s+not|never|avoid|stop)\s*.{0,32})"
    + ACTIVE_ACTION_PATTERN,
    re.IGNORECASE,
)
EXPLICIT_HISTORICAL_SCOPE = re.compile(r"(?i)(?:历史上|曾经|过去|previously|historically)")
CURRENT_SCOPE = re.compile(r"(?i)(?:当前|现在|现行|仍|继续|currently|still)")


def relative_paths(paths: list[Path]) -> list[str]:
    return sorted(path.relative_to(REPO_ROOT).as_posix() for path in paths)


def active_truth_paths(repo_root: Path = REPO_ROOT) -> list[Path]:
    paths = [repo_root / relative for relative in ACTIVE_TRUTH_FILES]
    for relative_root in ACTIVE_TRUTH_TREES:
        root = repo_root / relative_root
        if not root.is_dir():
            continue
        paths.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.casefold() in ACTIVE_TRUTH_SUFFIXES
        )
    active = []
    for path in dict.fromkeys(paths):
        if not path.is_file():
            continue
        relative = path.relative_to(repo_root).as_posix()
        if any(relative.startswith(prefix) for prefix in HISTORICAL_CONTRACT_PREFIXES):
            continue
        active.append(path)
    return sorted(active)


def affirmative_contract_names(line: str) -> list[str]:
    antecedent_matches: set[str] = set()
    matched: set[str] = set()
    current_antecedent = False
    for clause in CLAUSE_SEPARATOR.split(line):
        clause_matches = [name for name, pattern in RETIRED_CONTRACT_TERMS.items() if pattern.search(clause)]
        prohibited = bool(PROHIBITIVE_ACTION.search(clause))
        historical = bool(EXPLICIT_HISTORICAL_SCOPE.search(clause) and not CURRENT_SCOPE.search(clause))
        if prohibited:
            continue
        antecedent_matches.update(clause_matches)
        if historical:
            continue
        if clause_matches:
            if "hook" in clause_matches and not ACTIVE_ACTION.search(clause):
                clause_matches.remove("hook")
            if not clause_matches:
                continue
            has_marker = any(
                marker.casefold() in clause.casefold() for marker in NEGATED_OR_HISTORICAL_MARKERS
            )
            if not has_marker or ACTIVE_ACTION.search(clause):
                matched.update(clause_matches)
            continue
        if CURRENT_SCOPE.search(clause) and ACTIVE_ACTION.search(clause):
            current_antecedent = True
    if not matched and current_antecedent:
        matched.update(antecedent_matches)
    return sorted(matched)


def affirmative_retired_contract_hits(repo_root: Path = REPO_ROOT) -> list[str]:
    hits: list[str] = []
    for path in active_truth_paths(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        negative_section = False
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
            stripped = line.strip()
            if re.match(r"^#{1,6}\s", stripped) or stripped.endswith("："):
                negative_section = any(
                    marker.casefold() in stripped.casefold()
                    for marker in NEGATED_OR_HISTORICAL_MARKERS
                )
            if negative_section:
                continue
            matched = affirmative_contract_names(line)
            if matched:
                hits.append(f"{relative}:{line_number} [{','.join(matched)}] {line.strip()}")
    return hits


class PureCodexRepositoryCleanupTests(unittest.TestCase):
    maxDiff = None

    def test_active_repository_has_no_claude_runtime_assets(self) -> None:
        # Break caught: a Claude-only catalog, hook, installer, template, test, or
        # top-level active document is left behind in the Codex-only repository.
        exact_targets = (
            REPO_ROOT / "agents/manifest.json",
            REPO_ROOT / "hooks/claude",
            REPO_ROOT / "templates/project/.claude",
        )
        remaining = [path for path in exact_targets if path.exists()]

        named_scopes = (
            REPO_ROOT / "scripts",
            REPO_ROOT / "tests",
        )
        for scope in named_scopes:
            if scope.is_dir():
                remaining.extend(
                    path
                    for path in scope.rglob("*")
                    if "claude" in path.name.casefold()
                )

        # Only top-level docs are active product/governance documents here.
        # Task records and historical prose are intentionally outside this gate.
        docs_root = REPO_ROOT / "docs"
        remaining.extend(
            path
            for path in docs_root.iterdir()
            if path.is_file() and "claude" in path.name.casefold()
        )

        self.assertEqual(
            [],
            relative_paths(list(dict.fromkeys(remaining))),
            "Claude-only active repository assets remain",
        )

    def test_formal_codex_control_plane_has_no_windows_entrypoints(self) -> None:
        # Break caught: the formal bootstrap/sync/doctor, GTO, rules/CFM, or
        # acceptance surface still ships a PowerShell/batch entrypoint.
        entrypoint_scopes = (
            REPO_ROOT / "scripts",
            REPO_ROOT / "skills/global-task-orchestrator",
            REPO_ROOT / "skills/command-failure-memory",
            REPO_ROOT / "tests/harness",
            REPO_ROOT / "tests/benchmarks",
        )
        windows_entrypoints = [
            path
            for scope in entrypoint_scopes
            if scope.is_dir()
            for path in scope.rglob("*")
            if path.is_file() and path.suffix.casefold() in {".ps1", ".cmd"}
        ]
        # Machine-consumed agent descriptors can silently keep routing the
        # normal path through a deleted Windows launcher, so inspect only those
        # declarations rather than grepping prose or historical documents.
        descriptor_paths = (
            REPO_ROOT / "agents/codex-role-map.json",
            REPO_ROOT / "skills/global-task-orchestrator/agents/openai.yaml",
            REPO_ROOT / "skills/command-failure-memory/agents/openai.yaml",
        )
        descriptor_violations: dict[str, list[str]] = {}
        for path in descriptor_paths:
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8-sig").casefold()
            suffixes = [suffix for suffix in (".ps1", ".cmd") if suffix in source]
            if suffixes:
                descriptor_violations[path.relative_to(REPO_ROOT).as_posix()] = suffixes
        violations = {
            "windows_entrypoints": relative_paths(windows_entrypoints),
            "descriptor_dependencies": descriptor_violations,
        }
        self.assertEqual(
            {"windows_entrypoints": [], "descriptor_dependencies": {}},
            violations,
            "formal Codex/WSL control-plane or acceptance path still uses Windows launchers",
        )

    def test_active_truth_has_no_affirmative_retired_contracts(self) -> None:
        # Break caught: a file with an innocuous active filename reintroduces a
        # retired runtime, matcher, resolved view, or packet in its body.
        self.assertEqual(
            [],
            affirmative_retired_contract_hits(),
            "active truth still makes affirmative retired-contract claims",
        )

    def test_active_truth_scan_ignores_historical_records_but_reads_active_bodies(self) -> None:
        # Break caught: cleanup either starts policing immutable task history or
        # regresses to checking only filenames and misses active prose drift.
        with tempfile.TemporaryDirectory() as raw:
            fixture = Path(raw)
            (fixture / "docs/ai/tasks/TASK-OLD").mkdir(parents=True)
            (fixture / "docs/ai/runs/RUN-OLD").mkdir(parents=True)
            (fixture / "docs/tasks/TASK-OLD").mkdir(parents=True)
            (fixture / ".artifacts").mkdir()
            for relative in (
                "docs/ai/tasks/TASK-OLD/task.md",
                "docs/ai/runs/RUN-OLD/log.md",
                "docs/tasks/TASK-OLD/plan.md",
                ".artifacts/report.md",
            ):
                (fixture / relative).write_text("Use computer_use_wsl as the active runtime.\n", encoding="utf-8")
            (fixture / "README.md").write_text("Use computer_use_wsl as the active runtime.\n", encoding="utf-8")

            hits = affirmative_retired_contract_hits(fixture)

        self.assertEqual(1, len(hits), hits)
        self.assertTrue(hits[0].startswith("README.md:1 "), hits)

    def test_active_truth_scan_does_not_exempt_mixed_affirmative_contracts(self) -> None:
        # Break caught: one negated or historical word exempts an entire line
        # even when a later clause affirmatively enables the retired runtime.
        with tempfile.TemporaryDirectory() as raw:
            fixture = Path(raw)
            (fixture / "README.md").write_text(
                "## 历史记录\n"
                "Use computer_use_wsl as the active runtime.\n"
                "## 当前规则\n"
                "不要恢复旧 computer_use_wsl。\n"
                "不要恢复旧 hook；但当前仍启用 computer_use_wsl 作为正常运行时。\n",
                encoding="utf-8",
            )

            hits = affirmative_retired_contract_hits(fixture)

        self.assertEqual(1, len(hits), hits)
        self.assertTrue(hits[0].startswith("README.md:5 [windows-gui-bridge]"), hits)

        partial_retirement = (
            "`bootstrap-local.py` 会从用户级 `hooks.json` 中只移除稳定 id "
            "`openai.command-safety-gateway.v1` 的退休项，保留其他 hook 和顶层字段。"
        )
        self.assertEqual(["hook"], affirmative_contract_names(partial_retirement))


class PureCodexUserRuntimeCleanupTests(unittest.TestCase):
    def test_claude_user_runtime_is_absent(self) -> None:
        # Break caught: the explicitly retired user-level Claude runtime still
        # exists after repository cleanup.
        self.assertFalse(
            CLAUDE_HOME.exists(),
            f"retired Claude user runtime still exists: {CLAUDE_HOME}",
        )


if __name__ == "__main__":
    unittest.main()
