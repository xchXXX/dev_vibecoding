# 使用模式

## 最小模式

- 只维护 `state.json`
- 适合小任务或单窗口任务

## 常规模式

- 维护 `state.json + task.md`
- 适合需要用户确认和跨窗口恢复的任务

## 并行模式

- 维护 `state.json + task.md + events.jsonl`
- 适合多个子任务并行、需要审查闭环或需要事件审计的任务

## 不再使用的旧对象

以下对象不再是正式控制面：

- `plan.md`
- `plan.json`
- `work_order`
- `dispatch_packet`
- `return_packet`
- `.ai/session/*`
- `dispatch_message_raw`
