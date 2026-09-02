# GTO 按需上下文、工作区基线与审查闭环验收

## 验收目标

证明 GTO 在不引入第二控制面的情况下，能够让模型默认只接收当前角色所需上下文，并对 dirty workspace、真实代理身份、finding 返修、范围化复审和最终整体 review 建立可执行硬门禁。

本文件已在 Execute Window 中按真实最终证据更新。Execute Window 在用户确认的当前 `main` primary dirty baseline 上完成增量施工，没有自动创建、切换、移动、删除或清理 worktree/clone，也没有扫描或同步其他 clone。GTO v2 单栈实现已经完成，正式封账状态与最终审查事实统一以唯一 `state.json` 为准。

## 验收标准

1. `state.json` 仍是唯一任务真源，`task.md` 由控制器生成，不出现第二份人工维护状态。
2. `get-task-view -View coordinator`、`build-subtask-brief`、`build-review-brief` 使用字段 allowlist，fixture 中的无关哨兵、其他子任务内容和长载荷不会泄露。
3. 子任务 dispatch 记录真实 `platform_agent_id`、`context_mode=isolated`、`brief_kind` 和 `brief_sha256`；缺任一项时不能进入执行。
4. 高风险 reviewer 的真实代理身份不同于 implementer；身份来自平台派发结果，不接受子代理自报。
5. workspace 记录 checkout 类型、分支、`HEAD`、baseline、dirty paths 和 write-path overlap；正式状态只使用 `<repo-root>` 与相对路径。
6. dirty overlap 未被明确归属或裁决时，validator 阻止进入 `code_impl`。
7. finding 使用稳定 `finding_id`，返回原实现者修复；re-review 由原 reviewer 执行，默认输入只有 finding、fix delta 和必要证据。
8. 修复扩大路径或语义范围时必须记录原因并升级审查；同一 finding 最多三轮。
9. 没有独立 reviewer 的 `final/pass`，或 final review 未覆盖最新 `HEAD`/最终变更哈希时，任务不能标记 completed。
10. state 不保存完整 stdout、完整 diff、完整 prompt 或聊天记录，只保存短摘要、路径、哈希、commit range 和结论。
11. 文档、规则、schema、模板、skill、角色说明和测试的字段与术语一致。
12. 新增行为测试经历可解释 RED→GREEN，既有 GTO 文档合同和 control-plane 相关回归保持通过。
13. 正式写入范围不包含用户名、盘符或本机绝对仓库根。
14. 最终独立 reviewer 审阅真实 diff、验证证据、workspace 基线和残余风险，并给出明确 verdict。

## 必备证据

- Plan Window 的只读 workspace 基线：checkout 类型、分支、`HEAD`、dirty paths、目标 overlap 和文件哈希。
- Execute Window 开始前的新鲜 workspace 基线与用户确认的施工选择。
- 三类投影的实际 JSON 示例及无关哨兵不泄露断言。
- `bind-dispatch` 的真实代理 ID、隔离模式和 brief 哈希正反 fixture。
- dirty overlap 阻断与已裁决后放行的正反 fixture。
- 高风险同身份 reviewer 被拒绝的 fixture。
- finding 返回原实现者、同 reviewer 范围化复审、范围扩张升级和三轮上限的 fixture。
- completed 缺少最新 HEAD final review 时被拒绝、补齐后通过的 fixture。
- schema 与 PowerShell validator 对同一组正反 fixture 的结果。
- `global-task-orchestrator.skill-doc.ps1` 与 `control-plane.integration.ps1` 的新鲜完整结果。
- 计划文档、doc routing、JSON 解析、机器绝对路径扫描和 `git diff --check` 结果。
- 独立 final reviewer 的 verdict、finding 列表、覆盖的最终 HEAD/哈希和残余风险。

### 已取得的最终证据

- Execute Window 已在用户确认的当前 `main` primary dirty baseline 上完成；workspace 全程只检查并记录，没有自动管理 worktree/clone。
- GTO v2 单栈实现已完成，`state.json` 保持唯一真源，按需投影、真实派发绑定、workspace overlap、finding lineage、范围化复审和 final review 门禁均已落地。
- `control-plane.integration.ps1`：`62/62` 通过。
- `global-task-orchestrator.skill-doc.ps1`：`PASS`。
- `rules-index.integration.ps1`：`7/7` 通过。
- `validate-plan-docs.ps1`：`12/12` 通过。
- `validate-doc-routing.ps1`：`4/4` 通过。
- schema 校验、GTO `validate`、PowerShell AST、机器绝对路径、禁用 payload 与 `git diff --check`：全部 `PASS`。
- 同一独立 reviewer `/root/review_gto_005` 已关闭 `F001` 至 `F009`；20 文件 review 的最终状态、覆盖的 `HEAD` 与 ordinal content manifest hash 以唯一 `state.json` 为真源。

## 未决项

- 无功能未决项。
- 任务外既有 dirty 内容仍是 workspace 边界与残余风险；本任务没有覆盖、清理或归属这些内容，该边界不阻断本任务验收。

## 最终结论

最终结论为：**实现与验收通过。**

正式封账状态、review verdict、覆盖的 `HEAD` 与 ordinal content manifest hash 以唯一 `state.json` 为准；本文不复制会随最终文件集合变化的控制面状态或哈希。
