# project/.codex

项目模板中的 Codex 适配层。

用于放项目级说明或占位配置，并与项目根 `AGENTS.md`、`docs/ai/`、`config/ai/` 协同工作。

Codex 侧角色委派映射以 `../../../agents/codex-role-map.json` 为真源，项目 `.codex/` 只补项目增量说明，不复制全局治理正文。

约束：

- 这里只放项目适配层内容，不复制全局协作治理真源。
- review 输出、测试用例输出与代码子代理迭代口径统一引用：
  - `../../../docs/SUBAGENT_GOVERNANCE.md`
  - `../../../templates/review_report.example.md`
  - `../../../templates/review_testcases.example.md`
  - `../../../templates/code_worker_iteration_checklist.example.md`
