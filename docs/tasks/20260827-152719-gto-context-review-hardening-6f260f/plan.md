# GTO 按需上下文、工作区基线与审查闭环增强方案

## 任务目标

在只保留 `global-task-orchestrator`（GTO）这一套任务编排控制面的前提下，补齐五类能力：按需读取任务状态、真实隔离派发、工作区基线、代理身份约束、finding 返修与最终整体审查硬门禁。

目标不是再造一套开发流程，而是把当前主要依靠文字约定的做法变成 `state.json + schema + PowerShell 控制器 + 行为测试` 能够验证的合同。

## 背景与问题

当前 GTO 已经具备单一任务状态、子任务依赖、读写路径、角色分工、验证结果和 review evidence 等基础能力，也能把 finding 返回实施链路。但只读核对发现以下缺口：

- 模型通常可能接收整份 `state.json`，状态变大后会占用上下文；现有 brief 还没有按 coordinator、implementer、reviewer 做严格字段投影。
- “子代理只接收自己的任务上下文”目前主要靠提示词约束，尚未把平台的无历史派发参数和真实代理 ID 写入状态并验证。
- dirty worktree 没有结构化基线，也没有“目标文件与既有改动重叠时阻止实施”的硬门禁。
- 高风险任务的独立 reviewer、finding 返回原实现者、同 reviewer 范围化复审，主要是文字约定，缺少身份和 lineage 校验。
- 完成状态没有强制要求一次覆盖最新 `HEAD` 的最终整体 review。
- 旧任务中曾出现独立 implementer report、test report 和多轮 review package；这些不是本方案需要的真源文件，后续证据统一收口到 state 的短摘要、路径、哈希和提交范围。

当前仓库位于普通 `main` checkout，并非独立 worktree；基线提交为 `bebf35ff6501a92103f48f6b6bb48e9ade1040dc`，存在 30 个 dirty 路径。计划写入范围与 `docs/ARCHITECTURE.md`、`docs/SUBAGENT_GOVERNANCE.md` 两个既有修改重叠，因此本 Plan Window 只新增任务文档，不直接改这些文件。

## 范围

- 同步架构、子代理治理和两份 workflow 规则，冻结单控制面合同。
- 扩展 GTO skill、PowerShell 控制器、状态 schema、状态模板和三类代理说明。
- 扩展 `global-task-orchestrator.skill-doc.ps1` 与 `control-plane.integration.ps1`，先冻结 RED，再实现 GREEN。
- 增加 coordinator view、subtask brief、review brief 三类最小状态投影。
- 增加工作区检查、基线捕获、dirty overlap 门禁和 worktree 元数据。
- 增加真实派发绑定、代理身份、finding lineage、范围化复审、修复轮次上限和 final review 门禁。
- 对已有任务合同给出一次性迁移边界，不长期保留双轨字段。

## 非目标

- 不恢复、兼容或依赖已禁用的 SDD 工作流。
- 不实现文件系统级安全沙箱；本方案只解决上下文卫生和任务治理。
- 不让脚本自动创建、删除、切换或清理 Git worktree。
- 不自动扫描或同步其他 clone。
- 不把完整命令输出、完整 diff、完整提示词、聊天记录写入 `state.json`。
- 不新增 implementer report、test report 或 review package 作为必备产物。
- 不提交、合并、推送、变基或清理当前仓库已有改动。

## 约束与依赖

- `state.json` 始终是唯一任务真源；`task.md` 仅由控制器生成。
- PowerShell 可以在机器侧读取完整 JSON，但输出给模型的默认结果必须是最小投影。
- 正常子任务不得自行读取完整 state；完整读取只允许用于状态损坏诊断、schema 迁移、投影诊断和最终控制面审计。
- 上下文隔离必须依赖派发工具提供的无历史参数，例如平台支持时使用 `fork_turns="none"`；提示词只描述边界，不被当作隔离证明。
- 正式文档和状态只保存 `<repo-root>` 等逻辑路径，不持久化用户名、盘符或本机绝对仓库根。
- 进入 `doc_sync` 前必须重新核对 `HEAD`、dirty 路径和两个重叠文件的哈希，并明确本次施工基线。
- 当前没有可直接使用且已忽略的 `.worktrees/` 或 `worktrees/` 目录；没有用户明确选择时不得自行创建。

## 方案摘要

### 1. 状态按需投影

在 `orchestrator_ctl.ps1` 中增加或增强以下动作：

- `get-task-view -View coordinator`：仅返回目标、阶段、阻塞、依赖、workspace 摘要和下一可执行项。
- `build-subtask-brief`：只返回该子任务的 assignment、读写边界、依赖结果摘要、所需合同和验证要求。
- `build-review-brief`：只返回目标 finding、被审差异范围、修复摘要、必要证据、reviewer 身份和上一轮结论。
- `build-execute-handoff`：只输出 Execute Window 所需的短合同，不透传整份状态。

控制器可以解析完整 state；模型默认看不到未被投影的字段。测试使用无关哨兵字段证明投影没有意外泄露。

### 2. 真实隔离派发与代理身份

新增 `bind-dispatch`，在派发工具返回真实 ID 后写入：

- `agent_key`
- `platform_agent_id`
- `context_mode=isolated`
- `brief_kind`
- `brief_sha256`

派发分两步：先由控制器生成 brief，再以平台无历史参数启动代理，最后绑定真实 ID。高风险 reviewer 的 `platform_agent_id` 必须与实现者不同。若平台不支持无历史派发，任务必须停下并明确说明，不能用一句“忽略之前上下文”冒充隔离。

### 3. 工作区基线

新增 `inspect-workspace` 与 `capture-workspace-baseline`：

- 识别 primary checkout 或 linked worktree、分支、`HEAD`、common git dir 和工作树状态。
- 只在 state 中记录逻辑 `<repo-root>`、提交、dirty 路径和目标重叠，不保存机器绝对路径。
- `code_impl` 前若 write paths 与未归属 dirty 路径重叠，且没有明确基线决定，则 validator 阻止继续。
- 控制器只检查、记录和验证，不自动管理 worktree 生命周期。

### 4. finding、返修和范围化复审

finding 采用结构化字段，至少包含 `finding_id`、严重级别、目标路径、摘要、证据和状态。每个 finding 通过 `lineage` 绑定原实现者和原 reviewer：

1. task review 产生 finding；
2. finding 返回原实现者修复；
3. 原 reviewer 只收到 finding、修复差异摘要和必要证据；
4. 如果修复扩大了文件或语义范围，必须记录原因并升级 review scope；
5. 同一 finding 最多三轮，之后进入 `blocked` 或人工裁决。

### 5. 最终整体 review

`result.review.kind` 区分 `task`、`re_review`、`final`，`verdict` 区分 `pass`、`fail`、`needs_more_evidence`。任务只有在以下条件满足后才能完成：

- 所有必需证据槽都有覆盖；
- finding 已关闭或有显式残余风险裁决；
- 独立 reviewer 给出 `final/pass`；
- final review 覆盖当前最新 `HEAD` 或明确的最终变更哈希。

### 6. 控制状态体积

state 仅保存可以判断流程的结构化事实：短摘要、相对路径、哈希、commit range、命令名和结论。大对象保留在原工具输出或已有正式文件中，state 只记录其路径与摘要。这样不是让 Codex“聪明地自行挑着读”，而是由控制脚本在进入模型前就完成裁剪。

## 风险与回退

- **dirty 重叠风险**：进入 Execute Window 前重新比较两份目标文档哈希；若变化无法归属，停止并让用户决定基线。回退是不修改重叠文件。
- **投影过度裁剪**：先以行为测试冻结每个角色必需字段；缺少证据时扩充特定投影，不退回默认整份 state。
- **身份自报风险**：身份只能来自派发工具返回值并由 `bind-dispatch` 写入，不接受子代理在结果中自报 ID 作为证明。
- **旧任务迁移风险**：先只读统计活跃消费方，再提供一次性迁移；若必须长期双轨则触发停止条件。
- **schema 与 PowerShell 漂移**：同一组正反 fixture 同时经过 JSON schema 和控制器 validator。
- **review 变成死循环**：固定三轮上限，并要求 blocked 或人工裁决。
- **回退方式**：每批次仅改其 write paths；任一批次失败时停止后续批次，保留 RED 和诊断，不自动还原用户既有改动。

## 验收标准

- 三类投影只包含授权字段，无关哨兵不会出现。
- 派发记录含真实平台代理 ID、隔离模式和 brief 哈希；高风险 reviewer 与实现者身份不同。
- dirty overlap 未决时无法进入实现阶段；明确决定后才允许继续。
- finding 能返回原实现者，同 reviewer 只做范围化复审，范围扩张会触发升级。
- 三轮返修上限可验证，不能无限循环。
- 没有覆盖最新 HEAD 的 final review 时，任务不能变为 completed。
- state 不含完整 stdout、diff、prompt、chat 等长载荷。
- 新增 RED 均由最小实现转 GREEN，既有相关测试保持通过。
- 文档、规则、schema、模板、skill 和测试合同一致，正式产物无机器绝对路径。
- 独立 reviewer 对最终 diff、证据和残余风险给出明确结论。

## 阶段划分

1. `planning`：完成工作区只读基线、方案、施工计划、验收合同和任务 state；等待用户复核书面方案。
2. `doc_sync`：重新确认工作区基线，先同步架构、治理和 workflow 规则。
3. `test_sync`：按文档合同补行为测试并记录预期 RED。
4. `code_impl`：依次实现 schema/模板与 PowerShell 控制器、skill、代理说明，使 RED 转 GREEN。
5. `review`：finding 返修、范围化复审、相关全量回归和覆盖最新 HEAD 的最终整体审查。

## 需先同步的核心文档与测试

核心文档与规则：

- `docs/ARCHITECTURE.md`
- `docs/SUBAGENT_GOVERNANCE.md`
- `rules/items/workflow/复杂任务全局编排.md`
- `rules/items/workflow/子代理委派与协作.md`
- `skills/global-task-orchestrator/references/state-schema.md`

核心测试：

- `tests/harness/global-task-orchestrator.skill-doc.ps1`
- `tests/harness/control-plane.integration.ps1`

生产实现：

- `schemas/orchestrator-task-state.schema.json`
- `templates/orchestrator/state.template.json`
- `skills/global-task-orchestrator/SKILL.md`
- `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`
- `agents/backend-implementer.md`
- `agents/reviewer.md`
- `agents/test-verifier.md`
