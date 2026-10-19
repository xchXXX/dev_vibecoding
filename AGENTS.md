# AGENTS

本文件是 `ai-harness` 在当前项目中的默认读取入口，只保留项目边界、少量高优先级硬约束，以及规则系统装配说明。

全局稳定协作原则唯一维护在 [全局入口模板](templates/codex/AGENTS.global.md)，安装入口由 bootstrap 生成；本页只补充项目规则装配与目录边界。

## 默认读取顺序

每次进入本仓库时，默认按以下顺序读取和装配规则：

1. 读取本文件。
2. 读取 `rules/registry/RULES_INDEX.json` 的元数据。
3. 固定读取索引中仅有的三条 `activation=always_on` 规则：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。
4. 其余规则由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮实际操作自由决定是否读取；`intents`、`paths`、`summary` 与 `linked_skill` 只提供判断线索，不组成固定套餐，也不自动触发 skill。
5. 若当前仓库作为别的项目的全局规则根被引用，只导出其中 `scope != project` 的条目。

说明：

- 规则真源位于当前仓库 `rules/`；其中绝大多数 `rules/items/*` 条目属于跨项目全局规则，项目独属规则只保留少量 architecture 入口。
- 全局规则真源位于当前仓库 `rules/`；其他项目消费本仓规则时，必须把当前仓库根作为 `<harness-root>` 显式传给 `--global-rules-root`，不自动发现同机其他 clone。
- 规则文件名一律使用中文。
- 目录按 `kind` 分；`scope` 通过 frontmatter 表达，不通过目录编码。
- Python 只在离线维护或验收时生成、校验 `RULES_INDEX.json`；正常交互链不运行 Python matcher，不生成 `task_profile`，也不按任务类型拼装规则套餐。

## 真源入口

- 总纲：`docs/plans/AI_HARNESS_MASTER_PLAN.md`
- 项目真源入口：`docs/ARCHITECTURE.md`、`docs/CODEX_COMPAT.md`、`docs/SUBAGENT_GOVERNANCE.md`、`docs/PROJECT_TEMPLATE.md`、`rules/registry/RULES_ENTRY.md`

## Bootstrap 与全局模板入口

- 新机器 clone 后，从仓库根运行 `python3 ./scripts/bootstrap-local.py --codex-home <已核实的Windows-Codex-home的WSL路径>`，由脚本以当前仓库作为默认 `<harness-root>`。
- 需要选择其他已知 harness 时，只能显式传入 Python CLI 对应参数或设置 `AI_HARNESS_ROOT`；不扫描同机 clone，也不自动同步其他工作区。
- 全局 Codex 入口模板位于 `templates/codex/AGENTS.global.md`，由 bootstrap 渲染到 `CODEX_HOME/AGENTS.md`；模板和本仓入口不保存机器绝对路径。

## 仓库目录边界

- `skills/`、`rules/`、`schemas/`、`scripts/`、`templates/`、`tests/`、`docs/` 为项目真源目录。
- 正式文档、临时目录、测试目录与隔离目录必须按本仓规则收口在仓库内部；仓库父目录不作为本项目真源目录。

## 规则系统分工

- `AGENTS.md`：默认必读入口与高优先级项目边界。
- `rules/registry/`：规则系统入口、schema、分类说明与元数据索引。
- `rules/items/`：按 `kind` 组织的规则叶子文件；当前仓库中除 `仓库目录边界`、`真源入口` 外，其余条目默认作为全局规则维护。
- `skills/*/SKILL.md`：复杂多步流程与可复用工作流真源。
- `scripts/` 与 `tests/`：可执行校验与回归闸门。
- 缺失工具的分层安装与授权边界由索引中的 `global.policy.WSL工具分层与缺失依赖处理` 按当前操作决定是否适用。

若项目规则与全局规则发生冲突，必须通过项目规则 frontmatter 显式声明 `overrides`；未声明时不得静默覆盖。

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](skills/global-task-orchestrator/references/acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](skills/global-task-orchestrator/references/streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。

项目接入条件见 [项目模板](docs/PROJECT_TEMPLATE.md)，公开操作示例见 [接入与检查](docs/harness-usage-examples.md)。版本、安装与实际会话加载分别报告，不因展示成功放行执行。
