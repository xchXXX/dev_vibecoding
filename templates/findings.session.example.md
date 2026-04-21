---
task_id: <task-id>
plan_id: <plan-id>
doc_type: findings
owner: main-coordinator
status: in_progress
updated_at: 2026-03-27 16:00:00
---

# 发现记录

## 发现条目

entry_id: F-001
step_id: S2
summary: 确认三件套需结构化元字段与 machine_block
path: docs/ai/SESSION_PLANNING_STANDARD.md
impact: 可提升续接稳定性与自动校验可行性
next_action: 按模板回填当前会话三件套

entry_id: F-002
step_id: S3
summary: 工单需保留原始下发消息
path: config/ai/schemas/work_order.schema.json
impact: 追溯缺口可补齐
next_action: 增加 dispatch_message_raw 字段

## machine_block
```json
{
  "task_id": "<task-id>",
  "plan_id": "<plan-id>",
  "doc_type": "findings",
  "status": "in_progress",
  "entries": [
    {"entry_id": "F-001", "step_id": "S2", "path": "docs/ai/SESSION_PLANNING_STANDARD.md"},
    {"entry_id": "F-002", "step_id": "S3", "path": "config/ai/schemas/work_order.schema.json"}
  ],
  "updated_at": "2026-03-27 16:00:00"
}
```
