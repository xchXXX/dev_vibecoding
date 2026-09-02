# schemas

本目录保存当前控制面 schema 真源。

GTO 唯一当前 schema 真源：

- `orchestrator-task-state.schema.json`：定义 `docs/ai/tasks/<task_id>/state.json` 的唯一当前合同，只接受 `version=3`。

其他 schema：

- `task-event.schema.json`
- `command-failure-case.schema.json`
其中：

- `task-event.schema.json` 定义 `events.jsonl` 的单行事件对象
