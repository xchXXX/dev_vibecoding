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

### 显式 GTO 任务文档

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

目录骨架说明文件职责，不要求空项目一次创建所有目录，也不因任务规模自动启用 GTO。

| 适用条件 | 接入要求 |
| --- | --- |
| 所有接入项目 | `AGENTS.md` 指向已选择的全局真源、项目边界和规则入口；使用可用规则索引，普通任务采用简洁验收清单 |
| 项目有增量规则 | 在项目 `rules/` 维护并生成索引；不复制全局正文作为第二真源 |
| 使用 harness Git 策略检查 | 由项目维护者确认实际约定并填写 `config/ai/git-policy.json`；不自动猜测策略 |
| 首次执行项目测试或构建 | 按实际 manifest/lock 配置 `config/ai/environment.json`，运行项目环境检查；可选能力只声明确实需要的部分 |
| 用户明确选择 GTO | 按 GTO 合同创建六工件、冻结版本、分工和证据；只接入 harness 不要求当前存在 GTO 任务 |

Git 配置存在且合法时按阶段检查；应已接入但配置缺失或损坏时，先处理配置问题，不能视为检查成功。明确未接入的项目先核对原有约定、分支、dirty 和工作区归属；不以未接入放行推送、合并或发布，也不自动补造策略。完整合同见 [Git 配置接口](modules/git-workflow/contract/README.md)。本仓或示例缺配置时同样遵守此边界。

历史 task/run 只读保留，不参与当前实现路由。最小操作示例见 [接入与检查示例](harness-usage-examples.md)。

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](../skills/global-task-orchestrator/references/acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](../skills/global-task-orchestrator/references/streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。
