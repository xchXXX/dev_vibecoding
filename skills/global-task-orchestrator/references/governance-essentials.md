# 治理入口

本页只导航，不维护流程、预算或机器字段的第二份正文。

- [批准分工与依赖](workflow.md#批准分工与依赖)：按方案确定代理复用及执行顺序。
- [计划代理与结果预检](state-schema.md#计划代理与只读结果预检)：计划身份字段、只读提交预检和正式接收。
- [Plan 阅读示例](plan-reading-examples.md)：小修复、普通功能、复杂并行改造的呈现样例。

- [方案指南](plan-guide.md)：完整需求映射、方案呈现与交接。
- [任务流程](workflow.md)：阶段、六工件前置、职责、依赖与普通返工。
- [黑盒方法](blackbox-methodology.md)：分层选择、准备与停止出口。
- [协作治理](../../../docs/SUBAGENT_GOVERNANCE.md)：真实派发、身份与运行数边界、职责独立性及证据真实性。
- [SKILL](../SKILL.md)：实际加载目录、公开 CLI 与当前任务的操作入口。
- [状态使用说明](state-schema.md)、[包内 schema](../schemas/orchestrator-task-state.schema.json)：字段真源与载荷使用；示例只在本 references 目录维护。
- [CFM](../../command-failure-memory/SKILL.md)：真实命令失败、预期 Red 条件和闭环。

平台真实隔离与新顶层效果验收必须保留实际工具证据；提示、状态声明及结构校验不能代替。
