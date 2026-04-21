# 控制面对象说明

- `plan`：任务目标、边界、验收、停止条件；语义真源为冻结 `plan.md`，结构化投影为同步生成的 `plan.json`。
- `work_order`：执行分工单，必须包含 `change_spec`、`execution_steps`、`verification_steps`、`dispatch_message_raw`。
- `dispatch_packet`：复杂工单的逐文件详细改法。
- `return_packet`：执行型子代理自行填写的完成回执、验证结果、风险与后续建议。
- `session_files`：`.ai/session/<task_id>/task_plan.md`、`findings.md`、`progress.md`。

最小关系：
- 先冻结 `plan`
- 由 `Plan Window` 同步维护 `plan.md -> plan.json`
- 再生成一个或多个 `work_order`
- 必要时为 `work_order` 补 `dispatch_packet`
- 为执行型工单预分配 `return_packet_path`
- 执行完成后由执行子代理先写 `return_packet`
- 主协调器回收并推进状态
- 全程持续更新 `session_files`

主协调器在拆单时必须显式补齐：
- `dispatch_message_raw`
- 工单读写范围
- 停止条件
- 验证步骤
- 与 `step_id` 的映射关系
- `return_packet_path`
- `return_packet_required`
- `required_return_fields`
- `completion_gate`
- `state_owner`

主协调器保留的动作：
- 冻结 `plan`
- 同步维护 `plan.md / plan.json`
- 正式派单
- 接收或拒收 `return_packet`
- 更新 `task_plan.md / findings.md / progress.md`
- 正式推进工单与阶段状态
