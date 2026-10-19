# GTO 昂贵验收轻量门禁

Task ID: `20260903-165003-316417-expensive-acceptance-gates`

## 要做什么

以最小改动为 GTO 增加跨项目通用的便宜检查先行、前置审查、候选冻结、昂贵验收限次、证据版本绑定和终态不可重开门禁，并让本次自举施工从任务合同开始实际遵守新流程。

## 不做什么

- 不为语音模拟或任何单一业务项目编写专用流水线。
- 不实现预检问题自动学习、环境自动修复、守护进程、通用重试器或新的第二控制面。
- 不迁移到新的 state 主版本，不保留双轨控制器，不修改任务范围外文件，不调用真实外部模型或真实浏览器作为本次控制面调试工具。
- 不提交、不推送、不清理用户工作区，除非用户后续明确要求。

## 改哪些地方

- skills/global-task-orchestrator
- schemas/orchestrator-task-state.schema.json
- schemas/task-event.schema.json
- tests/harness/test_control_plane.py
- docs/SUBAGENT_GOVERNANCE.md
- docs/ARCHITECTURE.md
- docs/plans/AI_HARNESS_MASTER_PLAN.md
- rules/items/workflow
- rules/registry/RULES_INDEX.json
- docs/tasks/20260903-165003-316417-expensive-acceptance-gates
- docs/ai/tasks/20260903-165003-316417-expensive-acceptance-gates

## 怎么实现落地

保留 state version=3，增加 workflow_revision=2 及轻量 acceptance_gate；控制器在每次写状态前后执行完整语义校验；bind-dispatch 只允许依赖已完成且无 dispatch/result 的 ready 子任务；昂贵验收绑定冻结候选与不可覆盖的 attempt 历史，代码或配置变化使证据过期；安全和边界审查、未关闭 finding、最终文档与最终审查由机械门禁排序。旧 GTO 管理本次自举，但本次人工执行同一顺序且绝不重绑终态子任务。

## 怎么验收

- 旧行为的最小复现先稳定失败：终态重绑、依赖未完成派发、status/result 矛盾、审查倒序、过期候选证据和覆盖验收历史均被测试命中。
- 新合同能表达通用阶段、冻结候选、acceptance item 到证据映射、max_expensive_attempts=4、同候选完整验收最多一次、同候选环境重试最多一次、第三和第四次需人工批准。
- 控制器拒绝 completed/blocked/in_progress 子任务重绑，拒绝依赖未完成或状态矛盾的写入，且失败不改变 state.json、task.md、events.jsonl。
- 安全或边界审查未通过、存在未关闭 finding、候选未冻结或已过期时，拒绝派发昂贵验收；候选输入变化后既有真实验收自动失效。
- 每次昂贵验收保留独立 attempt、候选哈希、结果分类、真实调用次数、耗时、失败阶段和证据引用，后一轮不能覆盖前一轮。
- 最终文档只能在当前候选验收通过后确认，最终审查和 finalize 只接受当前候选及完整证据。
- 聚焦控制面测试、完整 harness 回归、schema 与规则索引校验、文档路由校验和本任务范围 git diff --check 通过，并取得独立 final/pass。

## 有什么风险

- 这是控制器自举改造；旧 GTO 本身不能强制新流程，因此本任务必须人工遵守终态不重开、依赖顺序和先审查后冻结。
- schema 与控制器同时变化可能破坏现有 v3 任务读取；新增字段必须保持旧 v3 状态可读，并用临时仓库覆盖兼容性。
- 候选哈希范围过宽会频繁误失效，过窄会复用错误证据；只哈希合同声明的候选代码、配置和运行输入。
- max_expensive_attempts=4 容易被误解为默认允许重跑四遍；必须同时限制同候选完整验收一次，并从第三次开始要求人工批准。
- 若实现需要新 action 或字段明显超出轻量范围，停止扩张并回到用户裁决。

## 当前状态

- status: `completed`
- current_phase: `review`
- next_action: `none`
