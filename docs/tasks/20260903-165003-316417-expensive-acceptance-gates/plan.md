# GTO 昂贵验收轻量门禁

Task ID: `20260903-165003-316417-expensive-acceptance-gates`

## 任务目标

以最小改动为 GTO 增加跨项目通用的便宜检查先行、前置审查、候选冻结、昂贵验收限次、证据版本绑定和终态不可重开门禁，并让本次自举施工从任务合同开始实际遵守新流程。

## 背景与问题

近期一个长任务把真实外部模型、真实浏览器、真实数据库组成的完整验收重复派发 11 次，前 10 次累计约 6 小时。根因不是并行代理不足，而是旧 GTO 缺少机械门禁：终态子任务可以重新绑定，依赖和前置审查不阻止派发，验收结果没有绑定冻结候选，后一轮还能覆盖前一轮状态。

本方案不优化某个业务项目，也不取消真实验收。它把所有项目都能复用的最小原则写进控制器：普通问题在便宜检查和前置审查阶段收敛；真实验收只验证冻结候选；每次真实调用有次数、版本和证据归属。

## 范围

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

## 非目标

- 不为语音模拟或任何单一业务项目编写专用流水线。
- 不实现预检问题自动学习、环境自动修复、守护进程、通用重试器或新的第二控制面。
- 不迁移到新的 state 主版本，不保留双轨控制器，不修改任务范围外文件，不调用真实外部模型或真实浏览器作为本次控制面调试工具。
- 不提交、不推送、不清理用户工作区，除非用户后续明确要求。

## 约束与依赖

- 这是控制器自举改造；旧 GTO 本身不能强制新流程，因此本任务必须人工遵守终态不重开、依赖顺序和先审查后冻结。
- schema 与控制器同时变化可能破坏现有 v3 任务读取；新增字段必须保持旧 v3 状态可读，并用临时仓库覆盖兼容性。
- 候选哈希范围过宽会频繁误失效，过窄会复用错误证据；只哈希合同声明的候选代码、配置和运行输入。
- max_expensive_attempts=4 容易被误解为默认允许重跑四遍；必须同时限制同候选完整验收一次，并从第三次开始要求人工批准。
- 若实现需要新 action 或字段明显超出轻量范围，停止扩张并回到用户裁决。

## 方案摘要

保留 state version=3，增加 workflow_revision=2 及轻量 acceptance_gate；控制器在每次写状态前后执行完整语义校验；bind-dispatch 只允许依赖已完成且无 dispatch/result 的 ready 子任务；昂贵验收绑定冻结候选与不可覆盖的 attempt 历史，代码或配置变化使证据过期；安全和边界审查、未关闭 finding、最终文档与最终审查由机械门禁排序。旧 GTO 管理本次自举，但本次人工执行同一顺序且绝不重绑终态子任务。

### 通用理想流程

1. 冻结需求、验收条目和非目标。
2. 先同步核心文档，并为每个缺陷写最低成本的复现与命中证明。
3. 运行单元、接口、schema、状态机、权限和故障注入等便宜且确定的检查。
4. 在真实验收之前完成安全、权限、异常恢复和兼容边界审查；finding 全部关闭。
5. 对候选代码、配置和声明的运行输入生成不可变指纹。
6. 只对这个冻结候选执行昂贵验收，并把每条验收标准映射到证据；一条真实主流程可以覆盖多条标准，不重复跑同一业务链。
7. 业务失败先回到本地复现、修复和复审，再冻结新候选；纯环境失败才允许同候选范围化重试一次。
8. 当前候选验收通过后才写最终完成事实，然后由独立 reviewer 覆盖最新候选并 final/pass。

### 轻量数据模型

- `workflow_revision=2`：只有显式采用新合同的任务启用新字段；旧 `version=3` 状态仍可读取，但所有任务都立即获得终态不可重绑和依赖门禁。
- `subtasks[].stage`：只表达 `work / cheap_check / pre_acceptance_review / expensive_acceptance / final_documentation / final_review` 六类顺序，不建立新的阶段引擎。
- `acceptance_gate`：保存候选输入、当前候选、验收条目、次数策略和历史尝试；不建立第二套状态文件。
- `expensive_acceptance` 尝试使用唯一子任务 ID 和不可变 attempt 元数据；失败后不重开原子任务。需要下一次时由受控 action 创建新 attempt，并保留前一轮。

### 次数规则

- `max_expensive_attempts=4` 是整个任务的绝对上限，不是默认赠送四次重跑机会。
- `max_full_attempts_per_candidate=1`：同一冻结候选只跑一次完整昂贵验收。
- `max_environment_retries_per_candidate=1`：只有明确归类为环境失败时，同一候选可对失败步骤补跑一次。
- `approval_required_from_attempt=3`：第三、第四次必须记录人工批准和理由；第五次机械拒绝。
- `product_failure` 必须产生 finding，完成本地命中证明、原实现者修复、同 reviewer 复审并冻结新候选，才能创建下一 attempt。
- `environment_failure` 不证明产品失败，也不允许借机改代码；候选一旦变化就不能使用环境重试名义。

### 证据复用与失效

- 每个验收条目都有稳定 ID、验证层级和 `evidence_refs`；同一真实会话可以同时为多条条目提供证据。
- 证据只有在 `candidate_id`、验收条目合同和相关运行输入未变化时可以复用。
- 候选路径内容、配置、数据版本或外部模型标识变化时，当前候选变为 stale，旧昂贵验收不再满足最终门禁。
- 只改与候选无关的任务控制文档，不应让业务候选误失效；最终文档自身仍由最终 reviewer 纳入最新审查范围。

### 本次自举如何实际执行新流程

本任务由旧 GTO 初始化，因此旧控制器尚不能自动阻止错误派发。主协调器必须人工执行同一规则：只派发依赖已经完成的子任务；任何 `in_progress/completed/blocked` 子任务不再 bind；审查发现问题只走稳定 finding、原实现者修复和同 reviewer 复审；`REVIEW-SEC-001` 通过后才执行 `FREEZE-LOCAL-001`；候选冻结后只复用已经通过的本地证据。本任务不需要外部真实模型或浏览器，昂贵验收阶段明确为不适用，不能为了测试新门禁制造真实调用。

## 风险与回退

- 这是控制器自举改造；旧 GTO 本身不能强制新流程，因此本任务必须人工遵守终态不重开、依赖顺序和先审查后冻结。
- schema 与控制器同时变化可能破坏现有 v3 任务读取；新增字段必须保持旧 v3 状态可读，并用临时仓库覆盖兼容性。
- 候选哈希范围过宽会频繁误失效，过窄会复用错误证据；只哈希合同声明的候选代码、配置和运行输入。
- max_expensive_attempts=4 容易被误解为默认允许重跑四遍；必须同时限制同候选完整验收一次，并从第三次开始要求人工批准。
- 若实现需要新 action 或字段明显超出轻量范围，停止扩张并回到用户裁决。

## 验收标准

- 旧行为的最小复现先稳定失败：终态重绑、依赖未完成派发、status/result 矛盾、审查倒序、过期候选证据和覆盖验收历史均被测试命中。
- 新合同能表达通用阶段、冻结候选、acceptance item 到证据映射、max_expensive_attempts=4、同候选完整验收最多一次、同候选环境重试最多一次、第三和第四次需人工批准。
- 控制器拒绝 completed/blocked/in_progress 子任务重绑，拒绝依赖未完成或状态矛盾的写入，且失败不改变 state.json、task.md、events.jsonl。
- 安全或边界审查未通过、存在未关闭 finding、候选未冻结或已过期时，拒绝派发昂贵验收；候选输入变化后既有真实验收自动失效。
- 每次昂贵验收保留独立 attempt、候选哈希、结果分类、真实调用次数、耗时、失败阶段和证据引用，后一轮不能覆盖前一轮。
- 最终文档只能在当前候选验收通过后确认，最终审查和 finalize 只接受当前候选及完整证据。
- 聚焦控制面测试、完整 harness 回归、schema 与规则索引校验、文档路由校验和本任务范围 git diff --check 通过，并取得独立 final/pass。

## 阶段划分

1. `DOC-DESIGN-001`：先做旧规范压力基线，再同步通用流程真源和本施工文档。
2. `TEST-GATES-001`：写黑盒 Red，确认失败原因就是旧门禁缺失。
3. `IMPL-GATES-001`：最小修改 controller 和 schema，使聚焦测试转 Green。
4. `VERIFY-GATES-001`：执行本地便宜检查、兼容回归和文档/schema 校验。
5. `REVIEW-SEC-001`：候选冻结前完成安全、原子性、权限和边界审查；finding 必须闭环。
6. `FREEZE-LOCAL-001`：冻结当前候选，核对证据未失效；本次昂贵真实验收记为不适用。
7. `DOC-FINAL-001`：候选验收后再写最终事实。
8. `REVIEW-FINAL-001`：独立终审最新候选，通过后才能 finalize。

## 需先同步的核心文档与测试

- 长期真源：`skills/global-task-orchestrator/SKILL.md` 及 references、`docs/SUBAGENT_GOVERNANCE.md`、`docs/ARCHITECTURE.md`、`docs/plans/AI_HARNESS_MASTER_PLAN.md`、相关 workflow rules。
- 可执行合同：`schemas/orchestrator-task-state.schema.json`、`schemas/task-event.schema.json`。
- Red 测试：`tests/harness/test_control_plane.py` 中终态重绑、依赖越序、状态矛盾、前置审查、候选过期、attempt 不覆盖和次数审批场景。
