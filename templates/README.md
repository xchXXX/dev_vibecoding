# templates

本目录保存当前控制面模板真源。

当前关键模板：

- `task-state.example.json`
- `verification-contract.example.json`
- `task-summary.example.md`
- `task-events.example.jsonl`
- `review_report.example.md`
- `review_testcases.example.md`
- `code_worker_iteration_checklist.example.md`

其中：

- `task-state.example.json` 对应唯一真源 `state.json`
- `verification-contract.example.json` 对应长任务或修复任务进入实现/复审前的最小 `verification_contract` 骨架
- `task-summary.example.md` 对应人读摘要 `task.md`
- `task-events.example.jsonl` 对应可选事件流 `events.jsonl`

项目接入与文档分流模板：

- `project/docs/tasks/plan.template.md`
- `project/docs/tasks/execution.template.md`
- `project/docs/tasks/acceptance.template.md`
- `project/docs/modules/contract.template.md`
- `project/docs/modules/design.template.md`
- `project/docs/modules/delivery.code-map.template.md`
- `project/docs/modules/delivery.engineering.template.md`

这些模板的职责不是美化格式，而是固定：

- 任务期文档最低要有哪些文件和章节
- 模块长期真源最低要有哪些文档骨架
- 进入代码实现前，哪些文档项不允许缺位
