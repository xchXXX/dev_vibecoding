# AGENTS

本文件是 `ai-harness` 在当前项目中的默认读取入口，只保留项目边界、少量高优先级硬约束，以及规则系统装配说明。

## 默认读取顺序

每次进入本仓库时，默认按以下顺序读取和装配规则：

1. 读取本文件。
2. 读取 `rules/registry/RULES_ENTRY.md`。
3. 读取 `rules/registry/RULES_INDEX.json` 中 `activation=always_on` 的规则，按 `scope` 区分全局基线与项目增量。
4. 再按任务意图、目标路径、`linked_skill` 按需加载其他规则或对应 skill。
5. 若当前仓库作为别的项目的全局规则根被引用，只导出其中 `scope != project` 的条目。

说明：

- 规则真源位于当前仓库 `rules/`；其中绝大多数 `rules/items/*` 条目属于跨项目全局规则，项目独属规则只保留少量 architecture 入口。
- 全局规则真源位于 `C:/Users/72385/dev/ai-harness/rules/`。
- 规则文件名一律使用中文。
- 目录按 `kind` 分；`scope` 通过 frontmatter 表达，不通过目录编码。

## 真源入口

- 总纲：`C:/Users/72385/dev/ai-harness/docs/plans/AI_HARNESS_MASTER_PLAN.md`
- 项目真源入口：`docs/ARCHITECTURE.md`、`docs/CODEX_COMPAT.md`、`docs/SUBAGENT_GOVERNANCE.md`、`docs/AGENTS.md`、`docs/PROJECT_TEMPLATE.md`、`rules/registry/RULES_ENTRY.md`

## 仓库目录边界

- `agents/`、`skills/`、`hooks/`、`rules/`、`schemas/`、`scripts/`、`templates/`、`tests/`、`docs/`、`contexts/` 为项目真源目录。
- `C:/Users/72385/dev/` 根目录只允许保留 `ai-harness/` 与 `AGENTS.md`；其他文档、临时目录、测试目录与隔离目录都必须进入 `ai-harness/` 内部

## 规则系统分工

- `AGENTS.md`：默认必读入口与高优先级项目边界。
- `rules/registry/`：规则系统入口、schema、分类说明、索引与解析结果。
- `rules/items/`：按 `kind` 组织的规则叶子文件；当前仓库中除 `仓库目录边界`、`真源入口` 外，其余条目默认作为全局规则维护。
- `skills/*/SKILL.md`：复杂多步流程与可复用工作流真源。
- `scripts/` 与 `tests/`：可执行校验与回归闸门。

若项目规则与全局规则发生冲突，必须通过项目规则 frontmatter 显式声明 `overrides`；未声明时不得静默覆盖。
