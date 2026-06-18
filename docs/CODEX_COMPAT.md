# CODEX_COMPAT

## 目标

说明 Claude 与 Codex 的能力差异，以及 `ai-harness` 如何为 Codex 提供最小兼容闭环。

当前批次在保留最小边界的前提下，已落地 `sync-codex.ps1`、Codex doctor 与故障记忆脚本。

## 冻结结论

- Claude 侧依赖：`agents + hooks + settings`
- Codex 侧最小闭环依赖：`skills + AGENTS.md + scripts + doctor`
- 截至 `2026-06`，Codex 已支持自身 hooks；当前仓库已落地项目级 `PreToolUse` 最小接线

## 不做错误假设

- 不假设 Codex hooks 与 Claude hooks 完全等价
- 不假设 Codex hooks 已覆盖所有工具与所有等价写入路径
- 不假设 Codex 能自动识别任意自定义目录下的 skills
- 不把 `~/.codex/skills/` 运行时目录当作长期真源
- 不假设 `codex exec` 内部 PowerShell 一定处于 FullLanguage；关键 skill 需要提供受限会话可用的兼容入口
- 不假设 Windows 上的 `codex exec` blind forward-test 一定能稳定穿过失败 shell 回合；CLI 诊断与真实子代理盲测要分开验收
- 不假设“已经切到 `pwsh7`”就等于 Windows 命令不再有 quoting、wrapper 或保留名噪音问题

## 三层映射

### 1. 全局真源层

- 路径：`C:/Users/72385/dev/ai-harness/skills/*`
- 职责：维护固定白名单 Codex skills 的长期真源

### 2. 运行时投放层

- 路径：`C:/Users/72385/.codex/skills/*`
- 职责：接收真源同步后的运行时 skill

### 3. 项目适配层

- 路径：`<project>/AGENTS.md`
- 路径：`<project>/docs/ai/`
- 路径：`<project>/config/ai/`
- 路径：`<project>/rules/registry/*`
- 路径：`<project>/rules/items/<kind>/*`
- 职责：提供项目边界、入口、增量规则与项目专属模板

## 当前最小托管范围

本批次冻结固定白名单多 skill 托管：

- `global-task-orchestrator`
- `command-failure-memory`
- `pre-dev-benchmark`

本批次不把 `skills/.system/*`、其他第三方 runtime skill、插件目录或任意目录同步纳入托管范围。

## Codex 最小兼容策略

### 1. skill 真源

在固定白名单源路径维护真源，再同步到：

- `C:/Users/72385/.codex/skills/`

### 2. 项目边界

项目仍通过以下入口提供本项目约束与上下文：

- `AGENTS.md`
- `docs/ai/`
- `config/ai/`
- `rules/registry/RULES_ENTRY.md`
- `rules/registry/*`
- `rules/items/<kind>/*`

其中：

- `docs/SUBAGENT_GOVERNANCE.md` 继续作为跨项目复用的全局治理真源。
- `rules/registry/* + rules/items/<kind>/*` 作为项目级 rules system，负责当前仓库的可消费规则入口。
- 历史上的 `rules/common/SUBAGENT_RULES.md` 不再视为项目规则唯一入口；若仍被旧留痕引用，只按兼容语境保留。

### 3. 最小闭环

Codex 侧最小闭环由以下组合承担：

- `skills/global-task-orchestrator/**`
- `skills/command-failure-memory/**`
- `skills/pre-dev-benchmark/**`
- `sync-codex.ps1`
- 最小 Codex doctor / validate 校验
- 项目入口文档与运行留痕

当平台可用时，Codex hooks 可作为额外 guardrail 挂载在这套闭环之前；但 hooks 不代替：

- `scripts/*.ps1` 的统一规则判断
- doctor / validate 的最终校验
- CI 或提交前检查的硬闸门

当前推荐分工：

- hooks：前置观测、补提示、补上下文
- `validate-doc-routing.ps1`：文档分流与实现前闸门真源
- `validate-plan-docs.ps1`：长任务 `plan.md / execution.md / acceptance.md` 章节真源

当前已落地的 Codex hook 配置落点：

- `<repo>/.codex/config.toml`
- `hooks/codex/scripts/PreToolUse.ps1`

当前最小接线只负责在 `PreToolUse` 中调用 `validate-doc-routing.ps1` 并输出提示，不把 `validate-plan-docs.ps1` 接入通用写入前闸门。

## Codex hooks 口径

截至 `2026-06` 的官方能力下，Codex hooks 可在 `PreToolUse` 中命中 Bash、`apply_patch` 文件编辑与 MCP 工具调用，并可执行 `deny`、`additionalContext`、`updatedInput` 一类前置守卫动作。

但官方同时明确：hooks 属于 guardrail，而不是完整 enforcement boundary。原因包括：

- 不是所有工具路径都保证被同一类 hook 覆盖
- 模型可能通过其他等价工具路径完成相近动作
- 规则判断若只写在 hook 中，跨客户端与离线校验会失去一致性

因此本仓库推荐：

- 把真正的规则判断收口到脚本与规则系统
- 把 hooks 视为这些脚本的触发器或提示器，而不是替代物
- 在当前仓库口径里，把 Codex hook 默认定位为“观测/提示”，不把其退出码当作可靠硬闸门

## Windows 命令口径

- Windows 默认执行基线统一为 `pwsh` / PowerShell 7。
- 复杂命令不要优先写成脆弱 one-liner；遇到多层引号、正则、长文本参数、here-string、跨 shell 转发或 SSH 内嵌脚本时，应优先改为 `.ps1` / `.py` 脚本块或分步执行。
- `.cmd` 只作为简单参数兼容入口；复杂参数默认直连 `.py` 或 `.ps1`，不要继续让 Windows batch 参与二次拆解。
- `ghost snapshot` 的 `NUL` 保留名索引失败默认先视为平台噪音候选，不直接等同于任务失败，也不直接等同于任务成功。
- 只有当用户目标命令本身失败，或证据表明该异常直接破坏目标产物时，才把它升级为任务失败。
- 若目标命令表面成功但产物不完整，应先判为“可疑状态”并补最小验证，不要仅因看到 `NUL` 日志就自动进入失败闭环，也不要直接宣布成功。

## `sync-codex.ps1` 最小边界

- 只负责固定白名单源路径到 `~/.codex/skills/*` 的同步投放
- 当前最小目标是固定白名单多 skill：
  - `global-task-orchestrator`
  - `command-failure-memory`
  - `pre-dev-benchmark`
- 当前固定映射：
  - `skills/global-task-orchestrator -> ~/.codex/skills/global-task-orchestrator`
  - `skills/command-failure-memory -> ~/.codex/skills/command-failure-memory`
  - `skills/pre-dev-benchmark -> ~/.codex/skills/pre-dev-benchmark`
- 最小支持 install / sync 语义
- 默认不接管未托管运行时目录
- 不扩展到：
  - `.system/*`
  - 插件
  - 通用任意目录同步
  - 项目目录内 skill 清理
- `codex-sync.receipt.json` 已升级为多 skill 结构：
  - `managed_skills`
  - 聚合后的 `managed_files`
- `command-failure-memory` 以独立 skill 形式分发，不再作为 `global-task-orchestrator` 的长期内嵌脚本存在。

## Codex doctor / validate 最小边界

本批次冻结的最小 doctor / validate 口径只校验：

- 真源 skill 存在
- 运行时 skill 存在
- 关键文件已同步
- 真源与运行时基本一致
- `codex_audit` 以多 skill 结构输出，先逐 skill 审计，再汇总聚合结论
- `command-failure-memory` 独立 skill 的脚本漂移、缺失与 receipt 目标偏差可被检测

本批次不扩展为：

- 更广泛的项目 doctor
- Claude settings merge / override
- 项目接入清理

## 非目标

- 不做项目接入清理
- 不做 `.claude/settings.local.json` 收敛
- 不做更大范围 evals
- 不做 `.system/*` 或其他第三方 runtime skill 托管
- 不做 Codex 运行时目录的全盘 takeover

## 最小验收项

- 已冻结真源与运行时映射：
  - `ai-harness/skills/*`
  - `~/.codex/skills/*`
- 已冻结当前最小托管目标：
  - `global-task-orchestrator`
  - `command-failure-memory`
- 已冻结额外 repo-local skill 真源映射：
  - `skills/pre-dev-benchmark -> ~/.codex/skills/pre-dev-benchmark`
- 已冻结 `sync-codex.ps1` 的最小职责与非目标边界
- 已冻结 Codex doctor / validate 的最小校验项与非目标边界
- 已落地独立 skill 的全局故障记忆脚本，并复用固定白名单多 skill 的 sync/doctor 最小边界完成分发与校验
- `command-failure-memory` 运行时优先通过 `.cmd -> .py` 兼容入口调用，避免把自动闭环建立在直接 `.ps1` 调用可用这一错误前提上
- `command-failure-memory` 在省略 `-CodexHome` 时优先跟随 `CODEX_HOME`，未设置时再回退到 `~/.codex`，避免临时 runtime 与真实 home 混写

## 阶段2兼容口径：固定底层类型 + 自定义角色映射层

- Codex 平台底层仍只使用 `default / explorer / worker` 三种原生类型。
- 仓库在 `agents/codex-role-map.json` 冻结自定义角色映射，提供 `agent_type`、`model`、`reasoning_effort`、`allow_write`、`allow_shell` 等运行建议。
- 映射层是仓库侧编排桥接，不是平台级注册表；`codex-role-map` 的新增或修改不会创建新的平台原生 `agent_type`。
- 主协调器在派发时必须先选角色再查映射，避免直接以裸 `agent_type` 作为任务语义入口。

## 阶段6兼容口径：验证能力收口

- 自阶段6起，`skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate` 将角色映射纳入 Codex 兼容闭环验证。
- 最小新增校验能力：
  - `codex-role-map` 的 `agent_type` 枚举合法性校验。
  - 冻结必需角色覆盖校验。
  - `codex-role-map` 与 `agents/manifest.json` 一致性校验（角色集合与读写/shell 能力对齐）。
- 校验失败时返回可定位错误，不再允许“映射缺口但继续派发”的弱一致状态。
