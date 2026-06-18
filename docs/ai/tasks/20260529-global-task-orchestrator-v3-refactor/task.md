# 任务摘要

## 基本信息

- `task_id`: `20260529-global-task-orchestrator-v3-refactor`
- 标题：`global-task-orchestrator` 控制面瘦身重构
- 当前状态：`completed`
- 当前阶段：`completed`

## 当前目标

本任务要把 `global-task-orchestrator` 从旧多文件控制面彻底切到新模型：

- `state.json`：唯一运行时真源
- `task.md`：人读摘要视图
- `events.jsonl`：可选 append-only 事件流

本轮同时要求同步收口 skill、治理文档、agents、schema、template 和测试口径，不保留旧控制面兼容层。

## 关键决定

- `state.json` 是唯一真源，`task.md` 不再承载方案正文或结构化真源职责。
- 子任务执行合同统一写入 `state.json.subtasks[].assignment`。
- 子任务执行结果统一写入 `state.json.subtasks[].result`。
- `events.jsonl` 只做事件追加，不替代当前状态。
- 旧 `plan / work_order / dispatch_packet / return_packet / .ai/session` 不再作为正式控制面。

## 子任务分工

### `ST-docs-governance`

- 角色：`doc-curator`
- 状态：`completed`
- 目标：重写治理文档、agent 输入输出口径和控制面说明，统一到 `task_state / subtask / result`。
- 结果：治理文档、agents、Codex 兼容说明与本任务摘要页已经统一到新控制面口径。

### `ST-skill-runtime`

- 角色：`backend-implementer`
- 状态：`completed`
- 目标：重写 orchestrator skill 与脚本接口，收敛到 `init-task / sync-task-md / append-event / build-subtask-brief / validate`。
- 结果：旧 control-plane runtime 已删除，新的 `orchestrator_ctl.ps1`、schema 与模板已落地。

### `ST-tests`

- 角色：`test-verifier`
- 状态：`completed`
- 依赖：`ST-skill-runtime`
- 目标：把 control-plane 集成测试和测试说明整体切到新控制面动作与失败模式。
- 结果：17 个 control-plane happy path / bad path 场景已全部通过。

### `ST-review`

- 角色：`reviewer`
- 状态：`completed`
- 依赖：`ST-docs-governance`、`ST-skill-runtime`、`ST-tests`
- 目标：统一审查文档、skill、schema、template、测试与控制面口径是否一致。
- 结果：首轮审查发现的缺口已退回原施工子代修复，最终复审通过，无新的阻断 findings。

## 主要风险

- `task.md` 目前是人工摘要，如果后续只改 `state.json` 不同步摘要，仍可能再次漂移。
- 当前黑盒测试已覆盖 runtime 合同，但摘要层仍主要依赖 reviewer 复验，而不是自动化约束。
- 旧控制面对象虽然已退出正式路径，但历史 run 留痕仍存在仓库中，后续阅读时容易与新运行时合同混淆。

## 下一步动作

1. 本轮三件套已经收口完成，后续演进优先继续以 `state.json` 为唯一真源。
2. 若后续继续扩展 `task.md` 摘要字段，建议同步补更强的一致性断言，降低人工摘要漂移风险。
3. 若再发生 reviewer findings，继续沿用“退回原施工子代返工，再复审”的闭环，而不是由主协调器直接代修。

## 参考

- 真源状态：`state.json`
- 详细方案：`plan.md`
- 实施顺序：`execution.md`
