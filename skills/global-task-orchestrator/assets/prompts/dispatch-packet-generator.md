# Batch 3 `dispatch_packet` 编译提示词模板

当任务跨模块、跨多文件、存在依赖顺序或停点风险时，必须补充 `dispatch_packet`，并把其字段稳定编译进最终执行提示词。

## 核心要求

- `dispatch_packet` 是复杂任务逐文件施工图，不是可选注释。
- `dispatch_message_raw` 必须显式承接 `dispatch_packet` 关键字段，避免执行时语义丢失。
- 复杂任务中与 `mandatory reads`、默认中文输出、回执正文所有权相关的约束，必须在现有字段中显式落盘。
- 若缺逐文件施工图导致无法安全实施，应停止并回报 `blocked`。

## 字段到提示词的映射规则

请在编译时至少覆盖以下字段，并写入明确可执行语句：

- 顺序：`execution_order`
- 读写闸门：`read_before_write`
- 不变量：`invariants`
- 禁改清单：`forbidden_changes`
- 依赖说明：`dependency_notes`
- 完成信号：`done_signals`
- 校验关注点：`verification_focus`
- 回退策略：`fallback_strategy`
- 交接说明：`handoff_notes`
- 逐文件改法：`change_spec`（复杂任务默认必填）

## 编译落地格式建议

- 先按 `execution_order` 组织执行步骤，再将 `change_spec` 逐文件展开。
- 在每个关键步骤明确相关 `invariants` 与 `forbidden_changes`。
- 在验收段落绑定 `verification_focus` 与 `done_signals`。
- 在风险段落明确 `fallback_strategy`，并给出触发条件。
- 在收尾段落明确 `handoff_notes`，便于审查与下游回收。

## Batch 3.5 规则下沉提示

- `forbidden_changes` 至少应禁止跳过 `read_paths_mandatory`（或 `read_before_write`）与 `mandatory reads` 要求。
- `verification_focus` 至少应检查三项规则是否到位：默认中文输出、mandatory reads、`return_packet` 正文由执行子代理本人填写。
- `handoff_notes` 至少应要求审查环节确认“主协调器不得代写”回执正文。
- 不新增字段名，只在既有字段值中补固定语句和验收表达。

## 边界约束

- 该模板只定义如何编译复杂任务施工图，不新增 Batch 3.5 的合同字段或脚本校验逻辑。
- 说明性文本默认中文；字段名、路径、脚本参数、代码标识符保持原样。
