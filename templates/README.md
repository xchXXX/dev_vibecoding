# templates

本目录保存当前六工件控制面与项目接入模板真源。

当前关键模板：

- GTO 合同唯一示例：[revision-3-contract.example.json](../skills/global-task-orchestrator/references/revision-3-contract.example.json)，经同包 init 生成六工件
- `verification-contract.example.json`
- `task-summary.example.md`
- `task-events.example.jsonl`
- `review_report.example.md`
- `review_testcases.example.md`
- `code_worker_iteration_checklist.example.md`

其中：

- GTO 的持久 state 由公开 init 从合同生成，不手工维护完整 state 模板
- `verification-contract.example.json` 对应长任务或修复任务进入实现/复审前的最小 `verification_contract` 骨架
- `task-summary.example.md` 对应人读摘要 `task.md`
- `task-events.example.jsonl` 对应必备事件流 `events.jsonl`

六工件必须按同一 `task_id` 配套维护：

- `docs/ai/tasks/<task-id>/state.json`
- `docs/ai/tasks/<task-id>/task.md`
- `docs/ai/tasks/<task-id>/events.jsonl`
- `docs/tasks/<task-id>/plan.md`
- `docs/tasks/<task-id>/execution.md`
- `docs/tasks/<task-id>/acceptance.md`

新任务字段以 GTO 包内 schema 为准，six_points 为唯一可编辑合同输入，镜像由 init 派生。从仓库根校验任务时使用：

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action validate \
  --repo-root . \
  --task-id <task-id> \
  --json
```

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
