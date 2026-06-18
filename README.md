# ai-harness

`ai-harness` 是面向本机后续所有项目复用的 AI 协作全局真源目录。

## 总纲入口

当前真实状态、phase 路线图与推荐下一步，统一见：

- `docs/plans/AI_HARNESS_MASTER_PLAN.md`

## 核心文档入口

- `docs/ARCHITECTURE.md`
- `docs/plans/contract-first-dispatch.md`
- `docs/SUBAGENT_GOVERNANCE.md`
- `docs/CODEX_COMPAT.md`
- `docs/PROJECT_TEMPLATE.md`
- `docs/MIGRATION.md`

## 规则真源入口

- 全局协作治理真源：`docs/SUBAGENT_GOVERNANCE.md`
- 项目级 rules system 入口：`rules/registry/RULES_ENTRY.md`
- 项目级规则索引与解析产物：`rules/registry/*`
- 项目级规则条目：`rules/items/<kind>/*`

说明：
- `docs/SUBAGENT_GOVERNANCE.md` 负责跨项目复用的全局治理口径。
- `rules/registry/* + rules/items/<kind>/*` 负责当前仓库可消费的项目规则系统。
- `rules/registry/RULES_RESOLVED.json` 应理解为按当前调用上下文解析后的规则视图；是否包含全局规则，取决于当次是否显式提供或成功解析到全局规则根。
- `rules/common/SUBAGENT_RULES.md` 不再作为项目规则唯一入口；若在历史文档中出现，只应按兼容/迁移语境理解。

## 目录入口

- `agents/`
- `hooks/`
- `rules/`
- `schemas/`
- `scripts/`
- `skills/`
- `templates/`
- `tests/`
