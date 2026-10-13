# templates/project

新项目脚手架模板落点。

项目模板只保留适配层，不复制全局通用规则真源。

接入时至少应引用：
- `../../docs/SUBAGENT_GOVERNANCE.md`
- `../../rules/items/<kind>/*` 中 `scope=global` 的跨项目基线规则
- `../../templates/review_report.example.md`
- `../../templates/review_testcases.example.md`
- `../../templates/code_worker_iteration_checklist.example.md`

角色委派最小接入步骤：
1. 在项目根 `AGENTS.md` 声明“角色优先”入口，引用全局 `../../docs/SUBAGENT_GOVERNANCE.md`，不复制正文。
2. 在 `docs/ai/README.md` 记录 role-first 委派入口与项目增量边界。
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
