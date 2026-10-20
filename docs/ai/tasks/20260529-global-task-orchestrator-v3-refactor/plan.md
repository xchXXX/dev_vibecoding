# 方案文档

## 任务

- `task_id`: `20260529-global-task-orchestrator-v3-refactor`
- 主题：`global-task-orchestrator` 控制面瘦身重构

## 目标

- 删除旧的 `plan / work_order / dispatch_packet / return_packet / .ai/session` 运行时控制面。
- 重建为：
  - `state.json`：唯一真源
  - `task.md`：人读摘要
  - `events.jsonl`：可选事件流
- 同步更新 skill、治理文档、agent 文档、schema、template 与测试。

## 关键决定

- `json` 负责真源与校验；`md` 只做摘要，不再双真源。
- 子代理合同不再单独落 `work_order.json`，改为 `state.json.subtasks[].assignment`。
- 子代理结果不再单独落 `return_packet.json`，改为 `state.json.subtasks[].result`，必要时同时追加事件。
- `dispatch_message_raw` 不再持久化；需要派发时由 `build-subtask-brief` 运行时生成。

## 新控制面文件

### `state.json`

必须写清：

- 任务身份：`task_id`、`title`、`status`、`owner`
- 任务目标：`objective`
- 边界：`scope_in`、`scope_out`
- 验收：`acceptance`
- 停止条件：`stop_conditions`
- 已确认决定：`decisions`
- 当前阶段：`current_phase`
- 子任务列表：`subtasks[]`

`subtasks[]` 每项至少写清：

- `subtask_id`
- `title`
- `role`
- `status`
- `dependencies`
- `read_paths`
- `write_paths`
- `assignment.goal`
- `assignment.must_include`
- `assignment.verification`

`completed` 或 `blocked` 时写入 `result`，至少包含：

- `result.status`
- `result.summary`
- `result.changed_files`
- `result.planned_files_not_changed`
- `result.verification.commands`
- `result.verification.result`
- `result.deviations`
- `result.blocked_by`
- `result.risks`
- `result.follow_up`
- `result.written_by`
- `result.written_role`

### `task.md`

必须写清：

- 当前任务目标
- 关键决定
- 当前阶段
- 子任务分工
- 主要风险
- 下一步动作

### `events.jsonl`

每行一个 JSON 事件，至少写清：

- `ts`
- `actor`
- `type`
- `summary`
- `refs`

## 删除范围

默认删除旧正式控制面：

- `docs/ai/runs/<task_id>/plan.json`
- `docs/ai/runs/<task_id>/work_orders/*.json`
- `docs/ai/runs/<task_id>/dispatch_packets/*.json`
- `docs/ai/runs/<task_id>/return_packets/*.json`
- `docs/ai/runs/<task_id>/orchestration_log.md`
- `.ai/session/<task_id>/*`

同时删除依赖这些对象的旧 skill 逻辑、模板、schema 和测试。

## 验收

- skill 本体文件显著收缩，旧 prompts/checklists/session files 不再作为正式依赖。
- 治理文档明确声明 `state.json` 为唯一真源。
- control-plane 集成测试全部切换到新动作和新失败模式。
