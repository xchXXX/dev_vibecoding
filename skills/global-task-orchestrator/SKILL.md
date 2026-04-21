---
name: global-task-orchestrator
description: 面向仓库级复杂改动的全局主协调 skill。用于用户给出新需求、改动点、重构目标或跨模块问题后，先由 Plan Window 委派阅读型子代理补齐上下文并冻结方案；再由 Execute Window 阅读冻结方案、补局部上下文、细化工单并派发执行型子代理。适用于不应预设为单一路径、需要由已确认方案决定执行分支的主协调任务。
---

# Global Task Orchestrator

充当全局主协调器。先组织阅读与方案收敛，再组织动态拆单、并行执行、结果回收。

## 双窗口模式

本 skill 默认运行在双窗口模式中：

- `Plan Window`：方案裁决窗口
- `Execute Window`：方案执行协调窗口

固定规则：

- `Plan Window` 只负责引入上下文、修订并冻结正式 `plan`
- `Plan Window` 只冻结阶段概览、边界、验收与停止条件，不预写详细工单
- 一旦进入 `plan freeze` 阶段，`Plan Window` 不再继续委派任何子代理
- `Plan Window` 冻结方案时必须同步落盘 `plan.md` 与 `plan.json`；其中 `plan.md` 是语义真源，`plan.json` 是结构化投影
- 只要任务进入本 skill 的 orchestrator 流程，无论任务大小，都必须先在 `Plan Window` 与用户交互并冻结方案
- `Execute Window` 必须先完整阅读冻结 `plan`
- `Execute Window` 理解方案时默认先读 `plan.md`，再按需读取 `plan.json`
- `Execute Window` 必须先派阅读型子代理补齐本轮局部上下文，再细化当前阶段工作与工单
- 执行型子代理只能由 `Execute Window` 派发
- `Execute Window` 派出阅读型子代理后，只允许做非重叠的协调准备动作

## 核心职责

- 接收用户需求并判断是否进入委派模式
- 为中大型任务初始化 `task_id`、run 目录与 `session_files`
- 在 `Plan Window` 委派 `reader` 角色产出 `plan draft`
- 冻结正式 `plan.md` 并同步生成 `plan.json`
- 在 `Execute Window` 基于冻结方案与局部阅读结果生成 `work_order / dispatch_packet`
- 预分配 `return_packet_path`，要求执行型子代理自行填写 `return_packet`
- 回收 `return_packet`，统一更新 `orchestration_log` 与 `session_files`

## 角色优先路由（阶段5升级）

- 路由入口固定为 `role`，禁止直接以裸 `agent_type`（`default / explorer / worker`）下发工单
- `agent_type` 必须由 `agents/codex-role-map.json` 解析得到，消费顺序固定为：
  - `select_role`
  - `resolve_role_map`
  - `build_work_order_and_dispatch_packet`
  - `compile_dispatch_message`
- `Plan Window` 默认阅读路由：`reader -> explorer`
- `Execute Window` 默认审查路由：`reviewer -> default`
- 实施与验证路由保持角色语义：
  - `doc-curator -> worker`
  - `test-verifier -> worker`
  - `backend-implementer -> worker`
  - `frontend-implementer -> worker`
  - `ops-runbook -> worker`
- 若 `role` 缺失或 role-map 无法解析，必须 `blocked` 并补齐合同，不得手写兜底 `agent_type`
- 失败回退方向固定为：
  - 上下文不足 -> `reader`
  - 方案不清 -> `planner`
  - 风险未收敛 -> `reviewer`
  - 验证不足 -> `test-verifier`

## 默认规则

- 默认模式是 `proposal-confirm-then-execute`
- 默认窗口切换是：`Plan Window -> Execute Window`
- 正式实施顺序固定为“先方案、再文档、再测试、最后代码”；只要进入实施，就不得跳步
- 若某一分支确实不存在，必须在冻结方案中明确记为“不适用”或“本批不涉及”，而不是在执行阶段临时跳过
- 若多个工单互不依赖，应并行；若存在前置依赖，应串行
- 跨模块、多文件、契约或状态机改造必须补 `dispatch_packet`
- 所有具体改法必须落盘到 `plan / work_order / dispatch_packet / return_packet / session_files`
- `plan.md` 是冻结方案的唯一语义真源；`plan.json` 仅作为结构化投影与自动化消费入口
- 绑定既有冻结方案时，bootstrap 只接受 `status=frozen` 的 `plan.json`；`draft` 方案不得进入 `Execute Window`
- 阅读型子代理必须给出相关代码路径、相关文档路径与证据摘要
- 主协调器与子代理补方案上下文时，默认优先读取 Markdown 真源，再按需读取 JSON 合同
- 执行型 `work_order` 必须包含：
  - `read_paths_mandatory`
  - `read_paths_optional`
  - `evidence_summary`
  - `expected_written_role`
  - `return_packet_path`
  - `return_packet_required=true`
  - `required_return_fields`
  - `completion_gate=return_packet_written_and_accepted`
  - `state_owner=main-coordinator`
- `expected_written_by` 在 writer 身份已知时应显式落盘；`validate` 会校验 `written_by / written_role` 与工单合同一致，并拒绝明显协调器身份
- 当 writer 身份尚未知晓时，`hydrate` 应回填机器可校验的 `expected_written_by_patterns`；`validate` 先校验 `expected_written_by`，其次校验 `expected_written_by_patterns`，最后才允许使用 `role / expected_written_role / work_order_id` 派生出的锚定身份模式合同
- `expected_written_by_patterns` 只能使用锚定的字面身份模式，且必须属于工单可派生的允许集合；不能写 `.*`、`\d/\w/\s`、分组、量词等会弱化作者绑定的正则
- `written_by` 不能写成任意非协调器字符串；即使没有显式 `expected_written_by`，也必须命中工单合同允许的作者身份模式
- `dispatch_packet_required=true` 是显式复杂任务闸门，可覆盖仅靠文件数/改动数的启发式判断
- `required_return_fields` 只能在仓库最低回执字段集合之上追加，不能删减
- `dispatch_message_raw` 必须由 `work_order / dispatch_packet` 稳定编译，并明确要求：先读取 `read_paths_mandatory`，`evidence_summary` 仅作导航，不能代替原文件阅读
- `hydrate` 必须重编译并修复陈旧 `dispatch_message_raw`；若工单 JSON 不可解析、编译前置字段缺失、`dispatch_packet_path` 越界、或复杂任务缺 `dispatch_packet.read_before_write / execution_order / change_spec`，必须非零退出并阻断自动化
- `dispatch_packet_path` 与 `return_packet_path` 除了 task run 前缀外，还必须拒绝穿过 symlink / junction / reparse point 的路径跳转
- `validate` 对缺失 `work_orders` 目录或当前 task run 下 `work_order` 数量为 0 必须直接失败
- `validate` 必须要求 `-TaskId`
- `hydrate` 对目标路径不存在、目标 task 缺 `work_orders`、或解析后目标集合为 0 必须非零退出
- `compile-dispatch-message.ps1` 对空目标目录也必须非零退出
- `dispatch_packet_path` 与 `return_packet_path` 都必须位于当前 `docs/ai/runs/<task_id>/...` 边界内
- `return_packet_path` 必须指向当前 `work_order_id` 的回执，不能复用同 run 的其他工单回执
- `validate` 不只检查 `dispatch_message_raw` 关键词，还检查它是否与合同编译结果一致
- 主协调器派发子代理时必须显式要求：除字段名、路径、脚本参数、代码标识符与协议字段外，输出与落盘说明性文本默认使用中文
- 主协调器不得代写 `return_packet` 正文；只能做结构校验、字段兜底与状态推进
- 若 `return_packet` 缺失、正文过薄或事实不清，必须退回原执行型子代理补写，不得由主协调器代补正文
- 主窗口默认不接收子代理的长过程全文，只接收结构化结果与必要摘要
- 对任何落盘文件，能用中文表达的地方尽量使用中文；字段名、路径、脚本参数与代码标识符保持机器可读

## 阶段 A：Plan Window 阅读委派

1. 接收用户需求并判断是否进入委派模式。
2. 运行 `scripts/orchestrator_ctl.ps1 -Action new-task` 分配唯一 `task_id`。
3. 运行 `scripts/orchestrator_ctl.ps1 -Action bootstrap` 初始化 run/session 骨架与 `plan.json` 落盘位；若绑定既有冻结方案，必须显式传入 `-SourcePlanDoc` 与 `-SourcePlanJson`，且 `source plan.json.status` 必须为 `frozen`，不得自动新建 task 级 draft `plan.md`。
4. 通过主窗口与用户交互确认目标、范围、非目标、验收与停止条件，不得跳过交互式方案冻结。
5. 下发 `reader` 角色子代理，只允许读取文档和代码，产出 `plan draft`、风险、澄清问题与证据路径。
6. 将阅读结论回填到 `task_plan.md`、`findings.md`、`progress.md`。

阅读型子代理回报至少应包含：

- `summary`
- `relevant_code_paths`
- `relevant_doc_paths`
- `key_findings_with_evidence`
- `unknowns`
- `recommended_next_step`

需要读取详细控制面定义时，优先查看：

- `references/repo-control-plane-map.md`
- `references/control-plane-objects.md`
- `references/plan-loop.md`

## 阶段 B：Plan Window 冻结

1. 与用户进行多轮答疑、方案修订与边界确认。
2. 仅当目标、范围、非目标、验收、停止条件足够明确时，才可视为冻结。
3. 使用 `assets/checklists/plan-freeze-checklist.md` 作为冻结前检查。
4. 进入 `plan freeze` 阶段后，不再继续委派任何子代理。
5. 由 `Plan Window` 基于已回收材料与用户反馈冻结正式 `plan.md`。
6. 由 `Plan Window` 基于同一份冻结内容同步生成或覆盖正式 `plan.json`；若 `plan.md / plan.json` 冲突，以 `plan.md` 为准。

冻结前检查：

- 是否已具备关键代码与关键文档证据路径
- 是否仍存在必须向用户澄清的未知项
- 是否已把阶段概览、边界、验收与停止条件写清

## 阶段 C：Execute Window 启动与局部阅读

1. 新开 `Execute Window`。
2. 先完整阅读冻结 `plan.md`。
3. 再按需读取对应 `plan.json` 提取结构化字段；不允许只凭 `plan.json` 代替方案理解。
4. 若发现 `plan.md / plan.json` 不一致，立即停止并退回 `Plan Window` 或用户确认，不得自行改写冻结语义。
5. 根据当前 batch / 阶段派 `reader` 角色补齐局部上下文。
6. 局部阅读回报也必须附相关代码与文档证据路径。
7. 仅在局部上下文补齐后，才允许细化当前阶段的工作与工单。
8. 在阅读型子代理回报返回前，只允许做非重叠的协调准备，例如文件存在性检查、路径与落盘入口检查、工单骨架预创建和阻塞项预发现；不得并行重复阅读同一批局部上下文。

## 阶段 D：动态拆单与路由

1. 根据冻结方案和局部阅读结果选择执行模式，而不是强制固定流水线。
2. 先判断是否需要以下分支：文档、测试、代码、运维、验证、排查。
3. 再判断哪些分支可以并行，哪些必须串行。
4. 为每个分支生成独立 `work_order`；必要时补 `dispatch_packet`。
5. 在生成工单后，运行 `scripts/orchestrator_ctl.ps1 -Action hydrate` 兜底补齐字段。
6. 执行型工单下发前，必须确认：
  - `role` 已写入并可在 `agents/codex-role-map.json` 解析
  - `read_paths_mandatory` 已写入
  - `evidence_summary` 已写入
  - `expected_written_role` 已写入；若已知具体执行身份，再写入 `expected_written_by`
  - 复杂任务已显式写入 `dispatch_packet_required=true`
  - `required_return_fields` 已包含仓库最低回执字段集合
  - `dispatch_message_raw` 已由当前合同稳定编译，且与合同一致
  - `dispatch_packet_path` 位于当前 task run 下
  - `return_packet_path` 已落盘
  - `return_packet_required` 仍为 `true`，且 `return_packet_path` 绑定的是当前工单回执
  - `completion_gate` 已写入
7. 复杂任务若满足以下任一条件，必须追加 `reviewer` 审查工单：
  - 跨模块或跨角色并行合流
  - 契约、状态机、数据结构变更
  - `changed_files` 超过 3 个
  - 验证结论含未关闭高风险
8. 使用 `assets/checklists/routing-checklist.md` 做拆单前检查。

动态路由细则见：

- `references/dynamic-routing-rules.md`
- `references/agent-selection-matrix.md`
- `references/orchestration-examples.md`

## 阶段 E：执行、回收与验收

1. 派发执行型子代理。
2. 执行型子代理必须先读取 `read_paths_mandatory`，再参考 `evidence_summary` 与 `dispatch_packet` 实施修改。
3. 若读完 `read_paths_mandatory` 后仍无法确定改法，执行型子代理必须退回 `Execute Window`，不得自行脑补。
4. 每个执行型子代理必须先在固定 `return_packet_path` 写入 `return_packet`，再声明完成；`return_packet` 正文必须由该执行型子代理本人填写。
5. 若回收时发现 `return_packet` 缺失、正文过薄、事实不清，或 `written_by / written_role` 不符合工单合同，必须退回原执行型子代理补写，不得由主协调器代写正文。
6. 必要时运行 `scripts/orchestrator_ctl.ps1 -Action hydrate-return` 对回执做字段兜底，但不得覆盖执行子代理的正文事实。
7. 主协调器在每轮回收后更新：
  - `docs/ai/runs/<task_id>/orchestration_log.md`
  - `.ai/session/<task_id>/progress.md`
  - `.ai/session/<task_id>/findings.md`
8. 没有 `return_packet`、`return_packet` 缺关键字段、或作者身份不符合工单合同，工单不得标记为完成。
9. 审查型工单由 `reviewer` 承接，按风险触发，不对每个阅读动作默认强制触发。
10. 对照 `plan.acceptance` 统一验收；验证失败则回到相应阶段修订。
11. 对 `plan / work_order / dispatch_packet / return_packet / session_files` 等落盘对象，说明性文本、结论、风险、建议、证据摘要默认优先中文。
12. 若子代理回馈主协调器的自然语言摘要或落盘说明性文本大面积使用英文，且不属于机器可读字段，应视为不合格并要求其改写为中文。

## 推荐资源

- 阅读型子代理草稿提示词：`assets/prompts/reader-plan-draft.md`
- 方案答疑模板：`assets/prompts/plan-clarification-loop.md`
- 工单生成模板：`assets/prompts/work-order-generator.md`
- 分发包生成模板：`assets/prompts/dispatch-packet-generator.md`
- 回执填写模板：`assets/prompts/return-packet-writer.md`
- 用户状态汇报模板：`assets/snippets/user-status-summary.md`
- 调度日志模板：`assets/snippets/orchestration-log-entry.md`

## 脚本接口

- `scripts/orchestrator_ctl.ps1 -Action new-task -Topic <topic> -RepoRoot <repo-root>`
- `scripts/orchestrator_ctl.ps1 -Action bootstrap -TaskId <task-id> -RepoRoot <repo-root> [-SourcePlanDoc <plan-md>] [-SourcePlanJson <plan-json>]`
- `scripts/orchestrator_ctl.ps1 -Action hydrate -Path <work-order-or-dir> -RepoRoot <repo-root>`
- `scripts/orchestrator_ctl.ps1 -Action hydrate-return -Path <return-packet-or-dir> -RepoRoot <repo-root>`
- `scripts/orchestrator_ctl.ps1 -Action validate -TaskId <task-id> -RepoRoot <repo-root>`
- `scripts/orchestrator_ctl.ps1 -Action inspect -TaskId <task-id> -RepoRoot <repo-root>`

## 停止条件

出现以下任一情况时，停止执行型派发并回到主协调阶段：

- 文档与代码设计冲突
- 用户新增目标导致原 `plan` 失效
- 需要写入未授权路径
- 缺少关键上下文，无法安全拆单
- 执行子代理无法按要求写入 `return_packet`
- `Plan Window` 缺少关键证据路径仍试图冻结方案
- `Execute Window` 未补局部阅读就试图派发执行型子代理
- 角色未映射到合法 `agent_type` 或 role-map 与合同冲突
