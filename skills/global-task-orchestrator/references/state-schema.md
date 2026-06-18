# state.json 字段说明

`state.json` 是唯一真源。

根字段最少包含：

- `task_id`
- `title`
- `status`
- `owner`
- `objective`
- `scope_in`
- `scope_out`
- `acceptance`
- `stop_conditions`
- `decisions`
- `current_phase`
- `subtasks`
- `updated_at`
- `version`

`verification_contract` 是根层对象合同；在进入 `code_impl` 或 `review` 前必须存在，最少包含：

- `verification_contract.minimal_repro`
- `verification_contract.hit_proof`
- `verification_contract.diagnostic_checks`
- `verification_contract.acceptance_checks`
- `verification_contract.non_goals`
- `verification_contract.review_evidence`

`subtasks[]` 最少包含：

- `subtask_id`
- `title`
- `role`
- `status`
- `dependencies`
- `read_paths`
- `write_paths`
- `assignment`

`assignment` 最少包含：

- `goal`
- `must_include`
- `verification`

`result` 在子任务完成或阻塞时写入。

`subtask.read_paths / subtask.write_paths` 是读写边界真源，不放进 `assignment` 内重复维护。

`result` 在 `completed` 和 `blocked` 状态下都必须存在，至少包含：

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

执行型或测试型子任务如要为复审补证据，写入：

- `result.review_evidence.<slot>`

额外约束：

- `result.written_role` 必须等于对应的 `subtask.role`
- `result.changed_files` 与 `result.planned_files_not_changed` 的每一项都必须落在 `subtask.write_paths` 内
- `blocked` 子任务必须填写非空的 `result.blocked_by`
- 当 `current_phase` 为 `code_impl` 或 `review` 时，`verification_contract` 六个字段都必须齐备
- 当 `current_phase` 为 `review` 时，`verification_contract.review_evidence` 中每个 evidence slot，都必须被至少一个已完成执行型或测试型 `subtask.result.review_evidence` 覆盖
