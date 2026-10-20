# 任务合同

本次为用户批准的手工协调施工，六工件记录事实，不调用GTO控制器维护本任务。

## do

统一初始测试委派、发现者根因与测试文档责任、整合返工、review与验收独立闭环，并验证默认安装的无提示实际行为。

## do_not

- 本次不调用GTO编排
- 不提交合并或覆盖既有未提交改动
- 不修改无关Windows能力实现
- 不把模拟回执当真实黑盒通过

## change_areas

- docs/SUBAGENT_GOVERNANCE.md及相关规范
- rules/items/workflow及相关policy、registry
- skills/global-task-orchestrator
- schemas/orchestrator-task-state.schema.json
- templates/orchestrator及示例
- tests/harness和必要黑盒夹具/runner
- 本次六工件和获审后默认安装区域
- scripts/sync-codex.py：仅GTO投放选项，保留其他受管内容及回执

## implementation

文档先行和六工件；并行测试子代理；唯一整合实施；完整首审与范围复审；通过后统一投放；新进程无提示完整黑盒；验收失败直接整合返工与范围复验；单文档子代理收尾。

## acceptance

- 初始测试委派写入隔离、全部work后整合送审
- 发现者定位根因给方案补失败证明及同步文档，整合者独占代码返工
- 完整首审和范围复审，首次验收始终全范围
- 验收失败修复后直接复验，不回review；有效覆盖全部验收项
- review和验收实际使用证据，WSL网页Browser、Windows GUI仅native
- 源码review后投放默认区并校验同候选，fresh无流程提示黑盒真实轨迹验证
- 单文档子代理验收后查漏同步，实质变化返回验收

## risks

- 既有dirty工作受保护，仅改授权范围
- machine doctor发现既有Windows runtime/global入口漂移，默认部署验收前需解决；项目doctor通过
- 黑盒未触发分支不得冒充已覆盖，缺失必需能力如实阻塞
- 源码候选与默认安装需hash一致，新进程消除热更新误判
