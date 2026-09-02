# 使用模式

## 非长任务

- 问答和低风险小任务不强制启动 GTO 六工件。
- 是否属于长任务由 Codex 根据用户意图、范围和风险判断，脚本不做自然语言分类。

## 长任务模式

- 必须维护 `docs/ai/tasks/<task_id>/state.json + task.md + events.jsonl`。
- 必须同时维护 `docs/tasks/<task_id>/plan.md + execution.md + acceptance.md`。
- 不因子任务数量、窗口数量或是否并行而删减任何一份。

## CLI JSON 载荷

- `init-task` 只接受 `--contract-json-file "$contract_json_file"`；所有子任务、审查和 finding fix 结果只接受 `--result-json-file "$result_json_file"`。
- 文件内容必须是一个 JSON 值。读取失败、JSON 解析失败或载荷字段校验失败时，控制器不得修改 `state.json`、`task.md` 或 `events.jsonl`。
- `--result-json` 和 `--contract-json` 已移除，不保留兼容入参。

## 不再使用的旧对象

以下对象不再是正式控制面：

- `plan.json`
- `work_order`
- `dispatch_packet`
- `return_packet`
- `.ai/session/*`
- `dispatch_message_raw`
