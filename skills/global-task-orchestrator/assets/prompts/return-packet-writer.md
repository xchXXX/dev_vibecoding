# return_packet 填写模板

执行型子代理在完成工单前，先写 `return_packet`，再向主协调器声明完成。`return_packet` 正文必须由执行子代理本人编写，主协调器及其他角色不得替代撰写。请从合约级别审视 `templates/return_packet.example.json` 中定义的 v2 字段，务必逐项填写自己亲自验证过的事实。

Batch 3.5 固定补充语句：该所有权约束必须同步写入合同对象字段值（如 `constraints`、`acceptance_criteria`、`dispatch_message_raw`、`handoff_notes`）与最小校验闸门，不得只停留在口头约定。

必须满足：
- 路径使用 `work_order.return_packet_path`
- 内容只写自己实际执行与验证过的事实
- 不擅自修改 `task_plan.md / findings.md / progress.md`
- 若未完成，使用 `status=partial` 或 `status=blocked`
- `summary` 中的行为必须与 `verification_commands` 所列的命令一致
- `status=completed` 只能在 `verification_result` 明确通过后才写入

至少填写：
- `work_order_id`
- `status`
- `summary`
- `changed_files`
- `verification`
- `risks`
- `written_by`
- `written_role`

关键 v2 字段（合约要求，必须存在，即便数组为空或写明“无”）：
- `planned_files_not_changed`：列明根据 dispatch_packet/contract-plan 预留的不动文件，或填 `[]` 表示无此类约束。
- `verification_commands`：详列所有用于验证本次变更的命令行（如 work_order 中提供的校验命令）。
- `verification_result`：以简洁语句说明命令执行结果与校验结论。
- `deviations_from_dispatch`：描述任意与 dispatch_packet 预期不一致的改动或省略。
- `blocked_by`：列出阻塞当前工单的待办事项或外部依赖，未阻塞时写 `[]`。
- `follow_up_needed`：指出需要后续工单、测试、复核等的事项，或者填 `[]`。

推荐补充：
- `written_at`
- `downstream_hint`
- `next_actions`

禁止：
- 在回执里替主协调器做最终验收结论
- 伪造未执行的验证结果
- 未写回执就声称工单完成
