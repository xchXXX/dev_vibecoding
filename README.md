# ai-harness

`ai-harness` 是面向多个项目复用的纯 Codex/WSL 协作真源。

## 总纲入口

当前架构、运行合同与实施主线统一见：

- `docs/plans/AI_HARNESS_MASTER_PLAN.md`

## 核心文档入口

- `docs/ARCHITECTURE.md`
- `docs/SUBAGENT_GOVERNANCE.md`
- `docs/CODEX_COMPAT.md`
- `docs/PROJECT_TEMPLATE.md`

## 规则真源入口

- 跨项目稳定原则真源：`templates/codex/AGENTS.global.md`；实际全局入口由安装工具生成。
- GTO 方案编制与交接：`skills/global-task-orchestrator/references/plan-guide.md`；任务流程与职责：`skills/global-task-orchestrator/references/workflow.md`。
- 协作证据与治理入口：`docs/SUBAGENT_GOVERNANCE.md`
- 项目级 rules system 入口：`rules/registry/RULES_ENTRY.md`
- 规则元数据索引与格式规范：`rules/registry/*`
- 项目级规则条目：`rules/items/<kind>/*`

说明：
- `docs/SUBAGENT_GOVERNANCE.md` 负责跨项目复用的全局治理口径。
- Codex 固定读取 `AGENTS.md`、`RULES_INDEX.json` 元数据和恰好三条 `activation=always_on` 规则；其余规则由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮操作自由选读。
- Python 只离线生成、校验规则索引，不参与正常交互中的语义选读。
- 其他项目消费本仓全局规则时显式使用 `--global-rules-root <harness-root>`；未提供该参数时不承诺自动发现本仓或同机其他 clone。
- 当前 GTO 长任务只维护 `state.json`、`task.md`、`events.jsonl`、`plan.md`、`execution.md`、`acceptance.md` 六份工件；`events.jsonl` 必备。
- 历史 task/run 和旧方案只保存历史事实，当前入口不把它们路由为实现真源。

## 正式命令

已有安装只发布 GTO 时，可在审查通过后使用 `python3 scripts/sync-codex.py --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --skill global-task-orchestrator --json`，仅联带 GTO 状态 schema 并保留其它技能安装与 receipt。首次安装、全量同步和路径选择见 `docs/CODEX_COMPAT.md`。

先核实 Windows 宿主 CODEX_HOME，将其 WSL 等价绝对路径设为 CODEX_HOME；未设置则停止，不回退 Linux HOME。正式脚本从 WSL 使用 `python3` 和 GNU 双横线参数运行，例如：

```bash
python3 scripts/bootstrap-local.py --harness-root "$PWD" --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --json
python3 scripts/validate_rules.py --repo-root "$PWD" --json
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action validate --repo-root "$PWD" --task-id "$task_id" --json
```

## 目录入口

- `rules/`
- `schemas/`
- `scripts/`
- `skills/`
- `templates/`
- `tests/`

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](skills/global-task-orchestrator/references/acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](skills/global-task-orchestrator/references/streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。
