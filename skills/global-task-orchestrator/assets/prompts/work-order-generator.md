# `work_order` 生成提示模板（Batch 3）

目标：从冻结方案与已确认上下文生成可直接派发的 `work_order`，并可稳定编译 `dispatch_message_raw`。

## 必填合同字段
- `task_goal`
- `read_paths_mandatory`
- `write_paths`
- `scope_out`
- `change_spec`
- `execution_steps`
- `verification_steps`
- `acceptance_criteria`
- `stop_conditions`
- `return_packet_path`
- `required_return_fields`
- `completion_gate`

## 可选角色上下文字段（新增，兼容模式）
- `role_source_path`：建议指向 `agents/<role>.md`
- `role_map_path`：建议指向 `agents/codex-role-map.json`

生成规则：
- 仅当任务需要显式传递角色真源或映射依据时写入以上字段。
- 当不写入时，不影响旧合同编译结果，保持历史工单兼容。
- 禁止新增未冻结字段名，优先复用现有合同字段承载约束。

## `dispatch_message_raw` 编译约束
- 必须声明“先读 `read_paths_mandatory` 再改动”。
- 必须声明“说明性文本默认中文”。
- 必须声明“`return_packet` 正文由执行子代理本人填写”。
- 必须声明“信息不足返回 `blocked`”。
