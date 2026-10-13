# PROJECT_TEMPLATE

## 目标

定义项目接入 `ai-harness` 时的最小适配层，确保项目仓库只保留入口、项目级规则系统、增量规则和当前任务状态，不复制全局通用规则真源。

## 全局与项目的分层

全局统一规则、review 输出模板、测试用例模板和代码子代理迭代清单，统一维护在：

- `docs/SUBAGENT_GOVERNANCE.md`
- `rules/items/<kind>/*` 中 `scope=global` 的跨项目目录与存储基线
- `templates/review_report.example.md`
- `templates/review_testcases.example.md`
- `templates/code_worker_iteration_checklist.example.md`

项目级规则真源统一维护在：

- `rules/registry/RULES_ENTRY.md`
- `rules/registry/*`
- `rules/items/<kind>/*`

说明：

- `docs/SUBAGENT_GOVERNANCE.md` 是跨项目复用的全局治理真源。
- `ai-harness/rules/items/<kind>/*` 中 `scope=global` 的条目是跨项目复用的规则真源。
- `rules/registry/* + rules/items/<kind>/*` 是当前项目仓库的 rules system 真源。
- `rules/common/SUBAGENT_RULES.md` 不再作为项目规则唯一入口；如需提及，只能作为历史兼容说明。

项目仓库只保留：

- `AGENTS.md`
- `modules/`
- `docs/modules/`
- `docs/tasks/`
- `docs/ai/`
- `config/ai/`
- `config/local/` 的本地覆盖入口
- `tests/fixtures/`
- `rules/registry/*`
- `rules/items/<kind>/*`
- 项目专属 `.codex/`
- 项目业务文档、部署文档与本仓特有脚本

## 消费全局规则

消费项目必须把选定的 harness 根显式传给 GNU 参数 `--global-rules-root <harness-root>`。未提供该参数时只处理项目本地规则，不自动扫描或同步同机其他 clone；项目文档、模板和配置不得复制机器绝对路径。

```bash
harness_root=/path/to/ai-harness
project_root=/path/to/project
python3 "$harness_root/scripts/generate_rules_index.py" \
  --repo-root "$project_root" \
  --global-rules-root "$harness_root"
python3 "$harness_root/scripts/validate_rules.py" \
  --repo-root "$project_root" \
  --global-rules-root "$harness_root"
```

## 项目入口应承担的职责

### `AGENTS.md`

- 只写高层强制规约、禁忌与入口
- 引用全局 `ai-harness` 协作规则真源
- 引用项目级 `rules/registry/RULES_ENTRY.md` 作为仓库规则入口
- 记录本仓额外约束，例如语言、目录、部署口径

### `docs/ai/`

- 只维护当前 GTO 的项目任务状态与人读摘要
- 在 `docs/ai/tasks/<task-id>/` 维护 `state.json`、`task.md` 与必备的 `events.jsonl`
- 不再复制通用 subagent / review / testing 规则全文

### `rules/registry/` 与 `rules/items/`

- `rules/registry/` 负责项目规则入口、元数据索引与分类说明
- `rules/items/<kind>/` 负责按类别拆分的项目规则条目
- Codex 固定读取项目 `AGENTS.md`、索引元数据及恰好三条 `activation=always_on` 规则；其余规则由 Codex 结合语义、目标、风险、阶段和本轮操作自由选读
- Python 只离线生成、校验索引，不为每个任务拼装固定规则套餐

### 长任务文档

任务工件及 Plan/Execute 顺序见 [GTO 流程真源](../skills/global-task-orchestrator/references/workflow.md)。`acceptance.md` 在确认后与其余五工件一起编制，验收阶段只回填实际证据；不能等验收时才创建。流程与返工正文不复制到项目模板。

### `config/ai/`

- 只保留本项目环境声明、注册表和样例。
- 不重复保存全局 review/testcase/worker 模板副本，除非项目明确需要局部覆盖。



## 推荐最小骨架

```text
<project>/
  AGENTS.md
  .codex/
  modules/
  docs/modules/
  docs/tasks/
  docs/ai/tasks/
  config/ai/
  config/local/
  tests/fixtures/
  rules/registry/
  rules/items/
  scripts/
  .tmp/
  .artifacts/
```

## 项目接入检查点

- 已在 `AGENTS.md` 写入全局规则真源入口
- 已在 `AGENTS.md` 或其他项目入口写入 `rules/registry/RULES_ENTRY.md` 入口
- 已创建 `docs/ai/tasks/`，且当前任务包含 `state.json`、`task.md` 与必备 `events.jsonl`
- 已建立 `rules/registry/*` 与 `rules/items/<kind>/*` 的项目级 rules system
- 已按全局基线预留 `modules/`、`docs/modules/`、`docs/tasks/`、`tests/fixtures/`、`.tmp/` 与 `.artifacts/`
- 涉及长任务时，已约定 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md` 与核心文档/测试同步、代码实现的先后顺序
- 已为当前 GTO 预留 `docs/ai/tasks/`，并明确六份工件和 `events.jsonl` 必备
- 已明确历史 task/run 只读且不参与当前实现路由
