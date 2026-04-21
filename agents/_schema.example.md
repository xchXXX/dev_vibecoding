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

- `frozen_plan`（必填，当前任务冻结方案）
- `work_order`（必填，任务合同与写入边界真源）
- `dispatch_packet`（可选；复杂任务时应读取并遵循）
- `read_paths_mandatory` 对应材料（必读）
- 角色所需的其他最小上下文

## 输出

- 该 agent 应产出的文件、结论或验证结果
- 若 `work_order.return_packet_required=true`，必须写入 `return_packet_path`
- `return_packet` 至少覆盖 `required_return_fields`

## 工作规则

- 优先遵守冻结方案
- 先完成 `read_paths_mandatory` 再执行写入
- 只在 `write_paths` 允许范围内工作
- 发现边界冲突时立即停止并回报

## 停止条件

- 需求边界不清
- 缺少 `frozen_plan` 或 `work_order`
- `frozen_plan` 与 `work_order` 语义冲突
- 需要写入未授权路径或命中禁改路径
- 发现上游方案与现状冲突，且无法在当前阶段消解

## 协作交接

- 说明通常交给谁继续处理
- 交接时必须附带范围、改动清单、验证结果、风险与后续动作
- 主协调器验收通过前不得标记任务完成
- 若阻塞结束，必须在结构化回收中明确 `blocked_by`
