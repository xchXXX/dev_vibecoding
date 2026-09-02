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
- `docs/AGENTS.md`

## 规则真源入口

- 全局协作治理真源：`docs/SUBAGENT_GOVERNANCE.md`
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

正式脚本从 WSL 使用 `python3` 和 GNU 双横线参数运行，例如：

```bash
python3 scripts/bootstrap-local.py --harness-root "$PWD" --codex-home "$CODEX_HOME" --json
python3 scripts/validate_rules.py --repo-root "$PWD" --json
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action validate --repo-root "$PWD" --task-id "$task_id" --json
```

## 目录入口

- `agents/`
- `contexts/`
- `rules/`
- `schemas/`
- `scripts/`
- `skills/`
- `templates/`
- `tests/`
