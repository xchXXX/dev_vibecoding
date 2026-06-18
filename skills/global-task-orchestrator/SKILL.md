---
name: global-task-orchestrator
description: 面向仓库级复杂改动的全局主协调 skill。用于接收新需求、定稿任务合同、维护单一 task state，并基于 state.json 中的 subtasks 动态委派阅读、实施、验证和审查。适用于需要跨模块协作、并行子任务和统一验收的任务；使用时默认维护 docs/ai/tasks/<task_id>/state.json，并按需维护 task.md 与 events.jsonl。
---

# Global Task Orchestrator

充当主协调器，但不再维护多层冗余控制面。

## 任务身份

- 一个正式长任务只对应一个 `task_id`。
- `Plan Window` 与 `Execute Window` 若处理同一个长任务，必须共享同一个 `task_id`。
- 只有在“目标、范围、验收已变成另一件事”时，才允许新建 `task_id`。
- 不能把“新开一个执行窗口”误判成“新任务”。
- `current_phase` 保留在 `state.json` 中，作为控制面内部状态；用户不需要在每次调用 skill 时重复声明。
- `current_phase` 默认使用最小推荐枚举：`planning / doc_sync / test_sync / code_impl / review / blocked`。

## 核心文件

- `docs/ai/tasks/<task_id>/state.json`
  - 唯一真源
  - 必须写清任务目标、边界、验收、阶段、子任务、验证与结果
  - 进入 `code_impl / review` 前，必须补齐根层 `verification_contract`
- `docs/ai/tasks/<task_id>/task.md`
  - 人读摘要
  - 从 `state.json` 渲染或人工精修，但不作为第二真源
- `docs/ai/tasks/<task_id>/events.jsonl`
  - 可选 append-only 事件流
  - 只记录关键事件，不再拆成 `progress/findings/orchestration_log/return_packet`

## Plan Window

适用于“开始一个新的正式长任务”或“继续定稿已有长任务合同”的阶段。

1. 对新长任务，先用 `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action new-task` 生成 `task_id`。
2. 用 `-Action init-task` 初始化 `state.json`、`task.md`、`events.jsonl`。
3. 委派阅读型子代理补上下文，再在 `state.json` 中定稿 `objective / scope_in / scope_out / acceptance / stop_conditions / decisions / current_phase / subtasks`。
4. 同步定稿该任务的方案文档、施工文档与验收文档。
5. 用 `-Action sync-task-md` 同步生成当前摘要。
6. 在任务合同定稿后，为 `Execute Window` 生成交接提示词；交接内容至少应覆盖 `task_id / current_phase / objective / scope_in / scope_out / acceptance / stop_conditions / 必读路径 / 首批建议子任务 / 禁止事项`。
7. 交接提示词必须明确：不要重新 `init-task`，不要把新开执行窗口误判成新任务，不要跳过子代理直接收口。
8. `Plan Window` 不直接进入实施。

## Execute Window

适用于“按已定稿合同继续实施”的阶段。

1. 不新建 `task_id`，而是继续已有 `task_id`。
2. 先完整读取 `state.json`，再按需读取 `task.md`、方案文档、施工文档与验收文档。
3. 读取 `state.json.current_phase` 作为当前控制面阶段，不要求用户重复声明。
4. 若 handoff 中已给出首批建议子任务，应先按该批次起步；只有发现已定稿合同与当前代码现实冲突时，才退回主协调器重新裁决。
5. 先把当前批次拆成 `subtasks`，必要时用 `-Action build-subtask-brief` 或 `-Action build-execute-handoff` 生成交接内容。
6. 若 `current_phase` 仍为 `planning`，默认先组织核心文档同步，再组织测试补齐与测试执行，不直接进入代码实现。
7. 若准备把 `current_phase` 推进到 `code_impl`，先运行 `-Action validate`，确认 `verification_contract` 六个字段已齐。
8. 若准备把 `current_phase` 推进到 `review`，再运行 `-Action validate`，确认 `verification_contract.review_evidence` 已被已完成执行型或测试型子任务覆盖。
9. 先委派子代理执行当前批次，再由主协调器等待回收结果、推进状态与组织复验。

## 当前阶段

- `planning`：任务合同尚在定稿，或刚从 `Plan Window` 交接到 `Execute Window`。
- `doc_sync`：优先同步当前批次相关的核心文档与入口说明。
- `test_sync`：补齐并执行当前批次要求的测试。
- `code_impl`：进入代码或配置实现。
- `review`：进入验收与复审。
- `blocked`：出现真实阻塞，等待主协调器裁决或外部条件变化。

## 实施顺序

1. 先定稿 `state.json / task.md / 方案文档 / 施工文档 / 验收文档` 中的任务合同层。
2. 再由 `Execute Window` 组织当前批次相关的核心文档同步。
3. 再由 `Execute Window` 组织测试补齐与测试执行。
4. 之后才进入代码或配置实现。
5. 执行型子代理完成后，把结果写回 `state.json.subtasks[].result`，必要时追加事件。
6. 进入 `code_impl` 前，用 `-Action validate` 校验 `verification_contract` 是否齐备。
7. 进入 `review` 前，用 `-Action validate` 校验 evidence slot 是否已被执行型或测试型子任务覆盖。
8. 平时也用 `-Action validate` 校验任务状态、子任务合同与事件流。

## 子任务最小合同

`state.json.subtasks[]` 至少包含：

- `subtask_id`
- `title`
- `role`
- `status`
- `dependencies`
- `read_paths`
- `write_paths`
- `assignment.goal`
- `assignment.must_include`
- `assignment.verification`

若当前批次会进入实现或复审，根层 `verification_contract` 至少包含：

- `minimal_repro`
- `hit_proof`
- `diagnostic_checks`
- `acceptance_checks`
- `non_goals`
- `review_evidence`

完成后写入：

- `result.status`
- `result.summary`
- `result.changed_files`
- `result.planned_files_not_changed`
- `result.verification.commands`
- `result.verification.result`
- `result.deviations`
- `result.blocked_by`
- `result.risks`
- `result.follow_up`
- `result.written_by`
- `result.written_role`

执行型或测试型子任务若承担复审证据回填，再补：

- `result.review_evidence.<slot>`

## 主协调规则

- `state.json` 是唯一真源；不要再并行维护 `plan/work_order/dispatch_packet/return_packet`。
- `task.md` 只能摘要，不复制整份 JSON。
- `events.jsonl` 只追加，不回写历史事件。
- 长任务中，主协调器不能跳过子代理直接代做执行型或审查型工作。
- `Plan Window` 只能派阅读型子代理；执行型与审查型子代理只能由 `Execute Window` 派发。
- 当前批次相关的核心文档同步、测试补齐与测试执行，由 `Execute Window` 负责组织并委派：
  - 文档同步优先派给 `doc-curator`
  - 测试补齐与测试执行优先派给 `test-verifier`
- `code_impl` 与 `review` 共用同一组 phase，不新增 phase；只是额外复用 `validate` 做两层闸门。
- `code_impl` 前闸门只检查 `verification_contract` 是否齐。
- `review` 前闸门除了检查 `verification_contract` 外，还检查 `verification_contract.review_evidence` 的 slot 是否已被已完成执行型或测试型子任务覆盖。
- `build-execute-handoff` 不能只给窗口切换提示，必须给到可直接起步的首批建议子任务与边界摘要。
- 执行型与审查型子代理都必须先读 `state.json`，再读被分配的 `subtask`。
- 说明性文本默认中文；字段名、路径、脚本参数与代码标识符保持原样。

## 参考

- 字段说明：`references/state-schema.md`
- 使用模式：`references/usage-modes.md`
- 治理摘要：`references/governance-essentials.md`
