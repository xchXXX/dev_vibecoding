# templates/project

新项目脚手架模板落点。

项目模板只保留适配层，不复制全局通用规则真源。

接入时至少应引用：
- `../../docs/SUBAGENT_GOVERNANCE.md`
- `../../rules/common/SUBAGENT_RULES.md`
- `../../templates/review_report.example.md`
- `../../templates/review_testcases.example.md`
- `../../templates/code_worker_iteration_checklist.example.md`

角色委派最小接入步骤：
1. 在项目根 `AGENTS.md` 声明“角色优先”入口，引用全局 `../../docs/SUBAGENT_GOVERNANCE.md`，不复制正文。
2. 在 `docs/ai/README.md` 记录 role-first 委派入口与项目增量边界。
3. 在 `config/ai/README.md` 记录项目级配置覆盖边界。
4. 在 `.claude/` 与 `.codex/` 仅放项目增量说明，并指向全局 `../../agents/*.md` 与 `../../agents/codex-role-map.json`。

模板目录建议包含：
- `AGENTS.md`
- `.claude/`
- `.codex/`
- `docs/ai/`
- `config/ai/`
- `scripts/`
