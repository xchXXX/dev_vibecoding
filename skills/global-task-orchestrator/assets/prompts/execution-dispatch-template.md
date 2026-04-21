# 执行型派发模板（Batch 3）

本模板用于编译执行子代理首条消息，输入遵循“三元输入”：
- 角色真源：`role_source_path`（默认来自 `agents/<role>.md`，可选）
- 角色映射：`role_map_path`（默认来自 `agents/codex-role-map.json`，可选）
- 任务合同：`work_order` + `dispatch_packet`（必需）

## 编译口径
- 必须先完整阅读 `read_paths_mandatory`，`evidence_summary` 仅作导航。
- 说明性文本默认中文；字段名、路径、脚本参数、代码标识符保持原样。
- 只允许修改 `write_paths`，严格遵守 `scope_out`。
- 严格按 `change_spec` 与 `execution_order` 实施。
- `return_packet` 正文必须由执行子代理本人填写。

## 可选角色上下文规则
- 当 `role_source_path` 或 `role_map_path` 存在时，编译结果显式包含这两个字段。
- 当两者缺省时，保持历史合同编译行为，不引入额外约束文本。

## 输出段落建议
- 角色与任务目标
- 必读上下文 / 导航摘要
- 写入范围 / 禁改范围 / 执行约束
- 逐文件改法与复杂任务施工图
- 验收标准 / 验证步骤 / 停止条件
- 回执要求（`return_packet_path`、`required_return_fields`、`completion_gate`）
