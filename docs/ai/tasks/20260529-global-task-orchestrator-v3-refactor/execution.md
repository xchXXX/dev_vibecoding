# 施工文档

## 施工顺序

1. 落本次任务控制面与方案文档。
2. 重写治理文档、agent 角色说明与角色映射顺序。
3. 重写 schema/template 到新控制面。
4. 重写 `global-task-orchestrator` skill：
   - 删旧脚本
   - 删旧 prompts/checklists/references
   - 新建最小 references
   - 新建单入口 `orchestrator_ctl.ps1`
5. 重写 control-plane 测试与测试说明。
6. 委派并行施工。
7. 委派审查；若失败，退回对应施工子代理返工。
8. 跑最小验证并收口。

## 并行策略

- 文档治理与 agent 口径可以独立施工。
- skill/runtime 与 schema/template 可以独立施工，但都要遵守同一 `state.json` 字段定义。
- 测试改造依赖 runtime 动作定型，因此放在 runtime 初稿后接入。
- 审查单独由 `reviewer` 负责，不直接修实现。

## 施工注意

- 不保留旧控制面兼容层。
- 不把 `task.md` 再次升级为第二真源。
- 不新增新的冗余派生文件。
- 对外说明、结论、摘要默认中文；字段名和路径保持原样。

## 需要特别写清的控制面字段

### `state.json`

- `status` 只允许表达任务总体状态，不要混入子任务状态。
- `subtasks[].status` 只表达该子任务状态。
- `subtasks[].assignment` 只写派发要求，不写执行结果。
- `subtasks[].result` 只写执行结果，不回写指令。

### `task.md`

- 只写摘要、阶段、风险、下一步。
- 不复制整份 `state.json`。

### `events.jsonl`

- 只追加，不回改历史事件。
- 事件摘要必须能被人直接读懂。
