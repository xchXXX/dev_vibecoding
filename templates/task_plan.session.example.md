---
task_id: <task-id>
plan_id: <plan-id>
doc_type: task_plan
owner: main-coordinator
status: in_progress
updated_at: 2026-03-27 16:00:00
---

# 任务计划

## 目标
- [一句话目标]

## 范围
- 包含：
- 不包含：

## 步骤记录

step_id: S1
title: 冻结方案
status: done
acceptance: 方案、边界与验收已冻结
depends_on: -

step_id: S2
title: 文档更新
status: in_progress
acceptance: 文档与模板已落盘
depends_on: S1

step_id: S3
title: 工程实施
status: todo
acceptance: 脚本与校验完成
depends_on: S2

step_id: S4
title: 回归验证
status: todo
acceptance: 关键验证通过并完成交接
depends_on: S3

## 决策记录
| decision_id | decision | rationale |
|---|---|---|
| D1 | 文档先行 | 保证实现可复核 |

## machine_block
```json
{
  "task_id": "<task-id>",
  "plan_id": "<plan-id>",
  "doc_type": "task_plan",
  "status": "in_progress",
  "steps": [
    {"step_id": "S1", "status": "done"},
    {"step_id": "S2", "status": "in_progress"},
    {"step_id": "S3", "status": "todo"},
    {"step_id": "S4", "status": "todo"}
  ],
  "updated_at": "2026-03-27 16:00:00"
}
```
