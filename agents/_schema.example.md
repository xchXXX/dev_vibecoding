---
name: example-agent
description: 示例 agent。说明负责什么，以及明确不负责什么。
tools: Read, Write
model: inherit
---

## 角色目标

用一句话说明该 agent 的核心目标。

## 负责范围

- 列出该 agent 应做的事
- 只保留跨项目可复用的职责

## 不负责

- 列出禁止越界的事项
- 明确哪些事情必须回交主协调器

## 输入

- `task_state`（必填，来自 `docs/ai/tasks/<task_id>/state.json`）
- `subtask`（必填，当前处理的 `state.json.subtasks[]` 项）
- `subtask.assignment`（必读，任务合同与写入边界真源）
- `subtask.read_paths` 对应材料（必读）
- 角色所需的其他最小上下文

## 输出

- 该 agent 应产出的文件、结论或验证结果
- 结果必须写回 `state.json.subtasks[].result`
- `completed` 与 `blocked` 两类终态都必须写 `result`
- `result` 至少覆盖：`status`、`summary`、`changed_files`、`planned_files_not_changed`、`result.verification.commands`、`result.verification.result`、`deviations`、`blocked_by`、`risks`、`follow_up`、`written_by`、`written_role`

## 工作规则

- 优先遵守 `task_state` 与 `subtask.assignment`
- 先完成 `subtask.read_paths` 再执行写入
- 只在 `subtask.write_paths` 允许范围内工作
- 发现边界冲突时立即停止并回报

## 停止条件

- 需求边界不清
- 缺少 `task_state` 或 `subtask`
- `task_state` 与 `subtask.assignment` 语义冲突
- 需要写入未授权路径或命中禁改路径
- 发现上游方案与现状冲突，且无法在当前阶段消解

## 协作交接

- 说明通常交给谁继续处理
- 交接时必须附带范围、改动清单、验证结果、风险与后续动作
- 主协调器验收通过前不得标记任务完成
- 若阻塞结束，必须在结构化结果中明确 `blocked_by`

