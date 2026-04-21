---
task_id: <task-id>
plan_id: <plan-id>
doc_type: progress
owner: main-coordinator
status: in_progress
updated_at: 2026-03-27 16:00:00
---

# 进度日志

## 方案入口

- 语义真源：`docs/plans/<plan-name>.md`
- 结构化投影：`docs/ai/runs/<task-id>/plan.json`

## 事件记录（追加）

entry_id: P-001
step_id: S1
status: done
action: 冻结 plan.md 并同步 plan.json
path: docs/plans/<plan-name>.md
next_step: 执行模板与规则更新

entry_id: P-002
step_id: S2
status: in_progress
action: 校验 plan.json 投影字段与脚本链路
path: docs/ai/runs/<task-id>/plan.json
next_step: 更新脚本与最小校验

## machine_block
```json
{
  "task_id": "<task-id>",
  "plan_id": "<plan-id>",
  "doc_type": "progress",
  "status": "in_progress",
  "source_plan_doc": "docs/plans/<plan-name>.md",
  "plan_json_path": "docs/ai/runs/<task-id>/plan.json",
  "entries": [
    {"entry_id": "P-001", "step_id": "S1", "status": "done"},
    {"entry_id": "P-002", "step_id": "S2", "status": "in_progress"}
  ],
  "updated_at": "2026-03-27 16:00:00"
}
```
