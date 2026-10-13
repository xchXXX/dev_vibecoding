# schemas

本目录保存共享 schema；GTO 专属 schema 随 skill 包维护。

GTO 唯一当前 schema 真源：

- [GTO 包内 schema](../skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json)：定义 `docs/ai/tasks/<task_id>/state.json` 的唯一当前合同，只接受 `version=3`。

其他 schema：

- `task-event.schema.json`
- `command-failure-case.schema.json`
- `wsl-tool-baseline.schema.json`
- `project-environment.schema.json`：项目 Python 声明在 `requirements_file` 与 `pyproject_file` 中二选一；`pyproject_file` 可声明要核对的 `extras`。
- `windows-external-capabilities.schema.json`：约束 v3 原生能力声明；每项包含 `id`、`kind=windows_native`、`provider`、`required_plugins`，不接受旧 WSL 桥或 transport 配置。
其中：

- `task-event.schema.json` 定义 `events.jsonl` 的单行事件对象

## Revision 3 合同核对

方案编制见 [方案指南](../skills/global-task-orchestrator/references/plan-guide.md)，通用流程见 [任务流程与职责](../skills/global-task-orchestrator/references/workflow.md)，字段见 [状态合同](../skills/global-task-orchestrator/references/state-schema.md)，操作见 [控制器指南](../skills/global-task-orchestrator/references/controller-guide.md)。当前包只接受当前合同，历史证据保留当时事实。
