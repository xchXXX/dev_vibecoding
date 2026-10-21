# templates/project

新项目脚手架模板落点。

项目模板只保留适配层，不复制全局通用规则真源。

接入时至少应引用：
- `../../docs/SUBAGENT_GOVERNANCE.md`
- `../../rules/items/<kind>/*` 中 `scope=global` 的跨项目基线规则
- `../../templates/review_report.example.md`
- `../../templates/review_testcases.example.md`
- `../../templates/code_worker_iteration_checklist.example.md`

接入条件唯一见 [项目接入检查点](../../docs/PROJECT_TEMPLATE.md#项目接入检查点)，操作见 [最小示例](../../docs/harness-usage-examples.md)。普通任务不要求创建 GTO 工件。以下步骤仅在实际委派时使用，GTO 约定仅在显式选择 GTO 后适用：
1. 在项目根 `AGENTS.md` 声明“角色优先”入口，引用全局 `../../docs/SUBAGENT_GOVERNANCE.md`，不复制正文。
2. 显式选择 GTO 后按其合同创建任务工件，不为普通任务预建任务状态。
3. 在 `config/ai/README.md` 记录项目级配置覆盖边界。
4. 在 `.codex/` 仅放项目增量说明；子代理提示词与派发约定引用 `../../skills/global-task-orchestrator/SKILL.md`，不维护项目角色模板。
5. 按全局目录基线建立 `modules/`、`docs/modules/`、`docs/tasks/`、`tests/fixtures/`、`.tmp/` 与 `.artifacts/`。

模板目录建议包含：
- `AGENTS.md`
- `.codex/`
- `modules/`
- `docs/modules/`
- `docs/tasks/`
- `docs/ai/`
- `config/ai/`
- `config/local/`
- `tests/fixtures/`
- `scripts/`

普通施工默认采用两个核心工件、文档测试先行和独立 review/验收，规则见 [任务与工作区合同](../../docs/modules/git-workflow/contract/task-workspace.md)。仅只读任务免登记；子代理继承父任务而不重新初始化。
