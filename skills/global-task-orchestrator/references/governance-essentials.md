# 治理摘要

本文件只收录 `global-task-orchestrator` 直接依赖的最小治理规则，不替代全量真源 `docs/SUBAGENT_GOVERNANCE.md`。

## 窗口分工

- `Plan Window`：负责补上下文、定稿边界、验收、停止条件、方案文档与施工文档。
- `Execute Window`：负责继续同一个 `task_id`，按已定稿合同组织实施、验证、审查与返工。
- 同一个正式长任务只对应一个 `task_id`；`Plan Window` 与 `Execute Window` 共享它。

## 委派闸门

- 每一批、每一阶段都必须先委派一个或多个子代理执行或审查，不能由主协调器直接收口。
- `Plan Window` 只能派阅读型子代理。
- 执行型与审查型子代理只能由 `Execute Window` 派发。

## 实施顺序

- 长任务必须先冻结六要点：要做什么、不做什么、改哪些地方、怎么实现落地、怎么验收、有什么风险。
- 必须保留并交叉校验六工件：`state.json / task.md / events.jsonl / plan.md / execution.md / acceptance.md`。
- 正式代码实施前，必须先完成当前批次相关的核心文档同步。
- 核心文档同步后，必须先完成测试补齐与测试执行。
- 进入 `code_impl` 前，必须先让 `validate` 通过 `verification_contract` 完整性闸门。
- 之后才进入代码或配置实现。
- 进入 `review` 前，必须再让 `validate` 通过 `review_evidence` 覆盖闸门。

## Execute Handoff

- `Plan Window` 定稿后应输出一段专供 `Execute Window` 使用的交接提示。
- 该交接至少应包含：
  - `task_id`
  - `current_phase`
  - `objective`
  - `scope_in / scope_out`
  - `acceptance`
  - `stop_conditions`
  - 必读路径
  - 首批建议子任务或现有 `subtasks` 摘要
  - 禁止事项与委派要求

## 当前阶段

- `current_phase` 默认收敛到最小推荐枚举：`planning / doc_sync / test_sync / code_impl / review / blocked`
- `planning` 进入 `Execute Window` 时，默认先从 `doc_sync` 起步，不直接进入代码实现
- `code_impl / review` 都要求根层 `verification_contract` 已定稿；`review` 还要求 evidence slot 已被执行型或测试型子任务回填

## 推荐路由

- 核心文档同步：优先派给 `doc-curator`
- 测试补齐与测试执行：优先派给 `test-verifier`
- 审查与验收：优先派给 `reviewer`

## 审查返工

- 审查不通过时，一律退回原执行型子代理返工。
- 主协调器只负责转发 findings、等待返工、重新组织复验。
- 主协调器不直接代修失败项。
- 复审必须回到同一原 reviewer。`max_fix_rounds=3` 按 `finding_id` 独立计数，只有实际 fix dispatch 递增；第三轮后仍 open 则 `blocked`/人工裁决。

## 等待与收口

- 主协调器必须等待子代理自然完成，不能因为耗时长而提前收口、打断或改派。
- 只有真实阻塞时，才允许结束当前子代理轮次并回到主协调器。
