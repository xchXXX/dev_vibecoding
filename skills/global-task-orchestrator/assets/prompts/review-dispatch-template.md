# 审查型派发模板（Batch 3）

本模板用于编译审查子代理派发消息，输入同样采用“三元输入”：
- 角色真源：`role_source_path`（可选）
- 角色映射：`role_map_path`（可选）
- 任务合同：`work_order` + `dispatch_packet`（必需）

## 审查编译要求
- 先读 `read_paths_mandatory`，再输出结论；`evidence_summary` 仅作导航。
- 以 findings 和证据路径为主，不用过程叙述替代结论。
- 说明性文本默认中文；字段名与路径保持原样。
- 不得越权修改 `scope_out` 指定之外内容。

## 可选角色上下文规则
- 若 `role_source_path` / `role_map_path` 提供，则在派发正文中显式列出，作为审查角色边界依据。
- 若两字段缺失，沿用历史审查派发文本，不改变旧工单兼容性。

## 输出结构建议
- 结论（通过/不通过）
- findings
- 关键依据（代码/文档路径 + 验证动作）
- 残余风险
- 必要测试补充（如需）
