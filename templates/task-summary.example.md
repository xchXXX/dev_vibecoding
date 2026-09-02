# 示例任务：同步当前任务模板

Task ID: `20300102-030405-template-refresh`

## 要做什么

把当前任务模板同步到 version=3 与六工件合同。

## 不做什么

- 不修改历史任务证据。

## 改哪些地方

- `templates/`
- `skills/pre-dev-benchmark/`

## 怎么实现落地

先用聚焦测试确认模板漂移，再最小修改并执行独立审查。

## 怎么验收

- 状态模板通过当前 schema。
- 文档命令可从仓库根直接运行。
- 六工件内容保持一致。

## 有什么风险

- 工作树中的既有改动可能与目标文件重叠。

## 当前状态

- status: `active`
- current_phase: `code_impl`
- next_action: `dispatch_ready_subtask`
