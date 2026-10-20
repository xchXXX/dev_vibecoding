# ARCHITECTURE

## 目标

建立一套不绑定单项目、可在本机多个项目复用的纯 Codex/WSL 开发控制面与运行时接入体系。

## 三层模型

### 1. 全局真源层

抽象路径：`<harness-root>/`；实际机器路径由 bootstrap 的显式参数、明确环境变量或脚本所在仓库确定，不写入通用合同。

职责：

- 保存长期维护的 AI 方法论文档与 Codex skills 真源。
- 保存 `scope=global` 的跨项目规则正文与 `RULES_INDEX.json` 元数据索引。
- 保存 schemas、templates、WSL Python 脚本、doctor、sync 与测试真源。
- 作为后续新项目脚手架的唯一来源。

禁止：

- 把 `CODEX_HOME` 运行时目录当作长期真源维护。
- 把某个业务项目仓库当作全局方法论真源。
- 在正常交互链中运行规则 matcher 或生成全正文聚合视图。

### 2. 运行时投放层

职责：

- 接收全局真源同步后的 Codex skills 与 managed `AGENTS.md`。
- 保存机器本地 receipt、备份和审计状态。
- 只负责被 Codex 识别与执行，不承载长期设计讨论。

运行时目标：

- `CODEX_HOME/skills/`
- `CODEX_HOME/AGENTS.md`
- `CODEX_HOME/.ai-harness/`

运行时目录只由受管同步入口定点更新，不做全盘 takeover，也不作为设计真源。

### 3. 项目适配层

职责：

- 放项目边界、模块入口、项目增量规则与项目私有配置。
- 放项目正式代码、模块文档、任务文档和 AI 控制面状态。
- 通过项目 `AGENTS.md` 与规则索引连接全局能力。

接入本 harness 的项目应保留：

- `AGENTS.md`
- `docs/ai/`
- `config/ai/`
- `rules/registry/RULES_INDEX.json`
- `rules/items/<kind>/*`
- 项目业务、部署与模块文档
- 项目专属脚本

通用 orchestrator、schema、template、skills 和规则正文不得复制成项目私有第二真源。

## 运行时映射

全局真源：

- `<harness-root>/skills/*`
- `<harness-root>/rules/items/<kind>/*`
- `<harness-root>/rules/registry/RULES_INDEX.json`
- `<harness-root>/schemas/*`
- `<harness-root>/scripts/*`
- `<harness-root>/templates/*`

运行时：

- `CODEX_HOME/skills/*`
- `CODEX_HOME/AGENTS.md`

项目适配：

- `<project>/AGENTS.md`
- `<project>/docs/ai/`
- `<project>/config/ai/`
- `<project>/rules/registry/RULES_INDEX.json`
- `<project>/rules/items/<kind>/*`

## 跨项目文件落点基线

- 项目正式代码默认收口在 `<project>/modules/<module-name>/`，模块内部按职责组织。
- 模块正式文档默认收口在 `<project>/docs/modules/<module-name>/contract|design|delivery/`。
- 长任务文档收口在 `<project>/docs/tasks/<task-id>/plan.md|execution.md|acceptance.md`。
- 当前 GTO 状态、摘要与事件流收口在 `<project>/docs/ai/tasks/<task-id>/state.json|task.md|events.jsonl`；既有 `docs/ai/runs/` 只作为历史证据，不参与当前控制面路由。
- 冻结测试夹具收口在 `<project>/tests/fixtures/<module-name>/`。
- 临时文件与非真源产物收口在 `<project>/.tmp/<module-name>/` 与 `<project>/.artifacts/<module-name>/`。
- PoC / Spike 使用 `<project>/modules/arch-poc/` 与 `<project>/docs/modules/arch-poc/`，运行产物收口在 `<project>/modules/arch-poc/debug/out/`。

## 规则系统

- Codex 固定读取全局与项目 `AGENTS.md`、当前可用的 `RULES_INDEX.json`，以及三条最小必读规则：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。
- 其他规则由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮实际操作自由决定是否读取。
- 索引中的 `summary`、`intents`、`paths` 和 `linked_skill` 只提供相关性提示，不构成固定规则套餐、强制路由或自动 skill 触发。
- `RULES_INDEX.json` 是唯一机器元数据索引，不内嵌正文；Python 只离线生成和校验索引。
- 正常链不生成 `task_profile`，不调用 Python matcher，不生成或消费包含所有正文的 resolved 视图。
- 冲突与覆盖关系以规则 frontmatter 和离线校验结果为准；Codex 读取相关规则后负责解释当前适用边界。
- 其他项目消费本仓全局规则时显式传入 `--global-rules-root <harness-root>`；未提供该参数时只处理项目本地规则，不自动发现其他 clone。

## WSL 运行边界

- Codex 开发控制面固定使用通用 WSL 开发发行版中的 Linux 原生工具。
- 文档校验、规则离线生成/校验、GTO、bootstrap、sync、doctor、CFM 与测试统一使用 `python3` 和 Linux 命令。
- Windows 原生 Agent 使用 PowerShell/文件工具及官方 Browser、Computer Use；项目 Git/Python/Node/测试构建通过已核实发行版的 wsl.exe --exec 在 Linux 执行，不替换为 Windows 项目依赖、旧 launcher、batch 或 hook。
- 规则真源与全局安装发布入口唯一；独立任务可使用经核实的隔离 worktree，优先复用空闲工作区，原生工具创建和归档；不扫描、同步无关 clone 或干扰活动任务。
- 机器迁移事实保留在对应历史任务记录，不作为其他机器的安装或删除指令。
- Command Failure Memory 使用已核实的 `<CODEX_HOME>/memories/command-failure-memory`，不迁移、不复制。

## WSL 工具基线

- 基础：`git`、`rg`、`curl`、`wget`、`rsync`、`file`、`lsof`、`python3`、`python3-venv`、Codex 只读沙箱所需的 `bwrap`、Linux `node`/`npm`。
- 通用工具：`jq`、`unzip`、`zip`、`tree`、`strace`、`shellcheck`、`shfmt`、`fzf`、`fd`、`sqlite3`、`dos2unix`。
- 构建：`build-essential`、`pkg-config`、`cmake`、`ninja`、`python3-pip`。
- 包管理：Linux 原生 `pnpm`，最终 PATH 不得命中非 Linux 可执行文件。
- 工具由本机部署批次一次性安装；bootstrap 与 doctor 只检查，不静默安装。
- 遇到缺失项时，由 `global.policy.WSL工具分层与缺失依赖处理` 按 WSL 系统包、项目依赖与浏览器自动化运行时选择安装层；索引元数据仅帮助 Codex 按当前操作决定是否读取该规则。

## 协作治理真源

- 主协调器、执行型子代理和审查型子代理治理收口在 `docs/SUBAGENT_GOVERNANCE.md`。
- 可执行规则正文收口在 `rules/items/<kind>/*`，元数据索引收口在 `rules/registry/RULES_INDEX.json`。
- 统一模板收口在 `templates/`，复杂流程收口在 `skills/*/SKILL.md`。
- 项目入口只保留发现方式、项目边界与增量约束，不复制统一治理正文。

## GTO 单栈控制面

- `global-task-orchestrator` 是显式选择 GTO 后的唯一编排控制面，正常链由 WSL Python 3 实现；普通任务不因规模启用 GTO。
- GTO 任务保留六份工件：`docs/ai/tasks/<task_id>/state.json|task.md|events.jsonl` 和 `docs/tasks/<task_id>/plan.md|execution.md|acceptance.md`。
- `state.json` 是唯一机器状态真源；其余五份分别承担人读摘要、关键事件、方案、施工和验收证据职责。
- 当前 state 只接受 `version=3`；控制器 action 只以 `orchestrator_ctl.py --help` 公开且实际实现的 GNU 双横线接口为准。
- 语义判断由 Codex 完成。普通委派先让目标代理读取 `task.md` 指向的批准合同，再由主协调器在平台真实派遣 prompt 中显式给出 `assignment`、`read_paths`、`write_paths` 与验收要求；控制器只机械维护 `state.json`、`events.jsonl`，并为审查场景实现 `build-review-brief`。
- 无历史派发由平台真实参数提供，并绑定真实 `platform_agent_id`、`brief_kind` 与 `brief_sha256`。
- workspace 层只检查并记录 checkout、branch、`HEAD`、dirty paths 与 write overlap；不自动处理 worktree 或用户既有改动。
- finding 使用稳定 ID，revision 3 保存发现者复现、根因、修复方案、失败证明及文档同步结论；代码修复固定由原整合责任者承担，review finding 回原 reviewer 范围复审，验收 finding 回同一验收者范围复验；第三轮实际修复后仍 open 则 blocked。历史记录保留当时事实；当前包不兼容旧合同。
- 当前通用流程和普通返工、skill 黑盒出口统一见 [GTO 流程真源](../skills/global-task-orchestrator/references/workflow.md)；字段和可用接口核对同候选 schema 与实际 CLI，在途任务使用其冻结运行版本和同一合同；当前包不兼容旧合同。
- 旧 revision 2 活动任务沿用其冻结的候选、预算和终审合同，不批量迁移；当前字段与兼容边界见 GTO 包内 schema 和状态说明。派发容量与身份复用见 SUBAGENT_GOVERNANCE.md，不推定等待或已完成代理的线程占用。

## 历史证据边界

- `docs/ai/runs/*`、已冻结旧任务文档与 sandbox 夹具属于历史证据，不代表当前合同。
- 活跃入口、长期合同与新生成索引必须遵守本文；历史证据不做机械替换。

## GTO revision 3

- 当前通用流程和普通返工、skill 黑盒出口统一见 [GTO 流程真源](../skills/global-task-orchestrator/references/workflow.md)；字段和可用接口核对同候选 schema 与实际 CLI，在途任务使用其冻结运行版本和同一合同；当前包不兼容旧合同。

## 并发任务、固定运行版本与能力证明

当前操作合同见 [GTO 运行与证据](../skills/global-task-orchestrator/references/runtime-evidence.md)。普通流程职责维护于全局 AGENTS 模板；技能开关唯一声明在 `config/ai/skill-policy.json`，由 `scripts/configure-skill-policy.py` 更新实际 path 配置，插件升级后重新检查路径并用新会话验明。方法技能不能接管流程。磁盘配置、CLI 快照验证和真实新会话加载分别报告。

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](../skills/global-task-orchestrator/references/acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](../skills/global-task-orchestrator/references/streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。
