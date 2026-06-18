# SUBAGENT GOVERNANCE

## 目标

本文定义新控制面下主协调器、执行型子代理、审查型子代理的统一治理口径。
本轮迁移已彻底切离旧控制面，不保留兼容层；任何流程、模板、说明都必须以 task 控制面三件套为准。

## 适用范围

- 全局真源：`ai-harness/`
- 运行时投放：Claude / Codex 相关同步与 doctor 流程
- 项目适配层：各项目 `AGENTS.md`、`docs/ai/`、`config/ai/`

项目规则系统兼容说明：

- 本文是跨项目复用的全局治理真源，不替代项目仓库自己的 rules system。
- 项目级规则应由各仓库在 `rules/registry/*` 与 `rules/items/<kind>/*` 中维护，并由项目入口文档引用。
- 历史上的旧控制面对象仅可作为迁移背景，不再是运行时合同来源。

## 角色分工

- 主协调器：维护 `state.json` 真源、选择角色、分配 `subtask`、等待完成、回收结果、推进整体状态。
- 阅读型子代理：只读补上下文，基于 `task_state + subtask` 产出证据化摘要。
- 执行型子代理：在允许写入范围内修改文档、配置、测试、代码，并把结果写回 `state.json.subtasks[].result`。
- 审查型子代理：基于 `task_state + subtask` 做多维度审查与验收，不代替执行型子代理直接补做实现。

## 双窗口模式

默认工作模式固定为：

- `Plan Window`：方案裁决窗口
- `Execute Window`：方案执行协调窗口

### `Plan Window`

职责：

- 接收需求
- 委派阅读型子代理引入上下文
- 基于阅读回报与用户反馈修订方案
- 冻结正式任务状态
- 同步落盘 `state.json` 与 `task.md`

规则：

- `Plan Window` 的上下文引入默认完全由阅读型子代理承担。
- `Plan Window` 只冻结阶段概览、边界、验收与停止条件，不提前细化实施细节以外的无关内容。
- 一旦进入冻结阶段，不再继续委派任何子代理。
- 正式任务状态的唯一真源是 `docs/ai/tasks/<task_id>/state.json`。
- `task.md` 是面向人的摘要视图，必须从 `state.json` 同步生成或维护，不得反向篡改机器真源。
- 若 `task.md` 与 `state.json` 冲突，以 `state.json` 为准，并应尽快修正 `task.md`。
- 只要任务进入本 orchestrator 流程，无论任务大小，都必须先经过主窗口与用户的交互式方案冻结，不得跳过 `Plan Window` 直接进入实施。

### `Execute Window`

职责：

- 完整阅读 `task_state`
- 委派阅读型子代理补齐本轮局部上下文
- 细化当前阶段工作
- 在 `state.json.subtasks[].assignment` 中写入执行合同
- 派发执行型或审查型子代理并回收 `state.json.subtasks[].result`

规则：

- `Execute Window` 必须先完整阅读 `state.json`，再按需读取 `task.md` 获取人读摘要。
- 在派发执行型或审查型子代理前，必须先确认目标 `subtask` 已存在且 `assignment` 完整。
- 当前阶段的具体工作、详细合同与验收门禁，统一在 `subtask` 中细化；其中执行说明写在 `subtask.assignment`，读写边界写在顶层 `subtask.read_paths / subtask.write_paths`。
- 不允许脱离 `task_state` 单独生成散落在仓库其他位置的执行合同。
- `Execute Window` 在派出阅读型子代理后，只允许做非重叠的协调准备动作，不得并行重复阅读子代理正在覆盖的上下文。
- `Execute Window` 不负责重写已冻结方案语义；若发现任务状态核心字段冲突，必须停止并退回 `Plan Window`。

## 批次与路由规则

- 每一批、每一 phase 都必须先委派一个或多个子代理执行或审查，不能由主协调器跳过子代理直接收口。
- `Plan Window` 只能派阅读型子代理；执行型与审查型子代理只能由 `Execute Window` 派发。
- 是否并行由依赖关系决定：
  - 相互独立的阅读、审查、纯验证任务可并行。
  - 文档、清单、测试、代码存在强依赖时必须串行。
- 只要任务进入正式实施，必须按以下顺序推进，不得跳步：
  1. 冻结方案
  2. 更新文档与清单
  3. 更新或新增测试
  4. 更新代码与配置
- 若某一分支确实不存在，必须在冻结方案中明确记为“不适用”或“本批不涉及”，而不是在执行时临时跳过。
- 未完成当前批次验收前，不得跳到下一批次。

## 等待与收口规则

- 主协调器必须在线等待子代理自然完成，不能因为耗时而提前收口、跳过、催关闭。
- 仅仅因为执行时间长、回报慢或暂未收口，不得向子代理催促、强制收尾、打断或改派。
- 只有出现以下阻塞时，才允许结束当前子代理轮次并回到主协调器：
  - 明确死循环
  - 多轮重复无进展
  - 缺少必须的权限或外部环境
  - 冻结方案失效，继续执行会扩大范围
- 出现阻塞时，必须把具体阻塞点、已尝试动作与下一步建议写入对应 `subtask.result`，不能笼统写“未完成”。

## 进入下一步的闸门

- 进入下一步前，所有本批次相关子代理都必须：
  - 自然完成
  - 结果被回收到 `state.json`
  - 完成验收
- 只要仍有一个相关子代理未完成或未验收通过，就不能推进到下一步。

## 统一控制面对象合同

### task 控制面三件套

- `docs/ai/tasks/<task_id>/state.json`：唯一真源。
- `docs/ai/tasks/<task_id>/task.md`：人读摘要。
- `docs/ai/tasks/<task_id>/events.jsonl`：可选 append-only 事件流。

约束：

- 新流程不得再依赖任何历史旧控制面对象、旧会话目录或旧派发消息载体。
- 旧对象名不得作为新的字段别名继续存在于正式合同中。
- 若需要记录执行合同，必须写入 `state.json.subtasks[].assignment`。
- 若需要记录执行结果，必须写入 `state.json.subtasks[].result`。
- `events.jsonl` 只追加事件，不承担当前状态真源职责。

### `task_state`

- 回答：任务改什么、为什么改、边界是什么、当前处于哪个阶段、有哪些 `subtask`。
- `task_state.status` 至少覆盖 `draft`、`active`、`blocked`、`completed`、`archived`。
- 只有 `Plan Window` 可把任务从 `draft` 推进到可执行状态（通常为 `active`）。
- `draft` 状态的 `task_state` 不得派发执行型或审查型子代理。
- 正式冻结方案默认写入 `state.json`；`task.md` 只是人读摘要，不是结构化真源。
- `task_state` 的必填字段以 state schema 为准；本文只描述治理语义，不重复维护一份会漂移的最小字段清单。
- 常见核心字段通常会覆盖 `task_id`、`title`、`status`、`objective`、范围信息、验收信息、停止条件与 `subtasks`，但具体必填集合应由 schema 和校验脚本裁决。

### `subtask.assignment`

- 回答：谁做、做哪些文件、最低可执行改法是什么、怎么验收。
- `assignment` 是子代理执行合同真源，至少应明确：
  - `goal`
  - `must_include`
  - `verification`
- `subtask.read_paths` 与 `subtask.write_paths` 是顶层读写边界真源，不放在 `assignment` 内重复维护。
- 复杂任务可在 `assignment` 内补充 `constraints`、`ordered_steps`、`scope_out`、`evidence_summary`。
- `evidence_summary` 只作导航，不能代替原文件阅读。
- 若缺少 `subtask.read_paths` 或 `subtask.write_paths`，执行型合同不得派发。
- 主协调器不得把合同散落到控制面外的独立文件中规避治理。

### `subtask.result`

- 回答：实际改了什么、验证了什么、风险是什么、是否触发停止条件。
- `result` 由执行该 `subtask` 的子代理填写，不由主协调器代写正文事实。
- 主协调器不得新建、重写或补写 `result` 的正文事实；若 `result` 缺失、正文过薄或事实不清，必须退回原执行子代理补写。
- 主协调器只允许做结构校验、状态推进与必要的非事实性字段兜底，不得把这些动作伪装成子代理结果。
- 无论 `subtask.status` 最终是 `completed` 还是 `blocked`，都必须写 `result`；没有 `result`，`subtask` 不能视为收口。
- `result` 最低字段口径应至少包含：
  - `status`
  - `summary`
  - `changed_files`
  - `planned_files_not_changed`
  - `result.verification.commands`
  - `result.verification.result`
  - `deviations`
  - `blocked_by`
  - `risks`
  - `follow_up`
  - `written_by`
  - `written_role`
- `written_by` 与 `written_role` 是必填身份字段；`validate` 应校验 `written_role` 是否匹配 `assignment.role`，并拒绝缺失或明显错配的作者身份。
- `changed_files` 必须是实际发生改动的文件集合；其每一项都必须落在 `subtask.write_paths` 内，空改动任务可写空数组但不得越界伪报。
- `blocked_by`、`deviations`、`follow_up` 必须保留字段；无内容时可为空数组或空值，但不能省略整个字段。
- `blocked` 的 `subtask` 还必须在 `result.blocked_by` 中写清阻塞来源，并在 `summary` 或 `follow_up` 中说明已尝试动作与下一步建议。
- `result.verification.result` 必须与 `result.verification.commands` 对齐；无法验证时必须说明原因与风险。

## 阅读与证据规则

- 阅读型子代理必须罗列支撑结论的相关代码和文档证据路径，不能只给摘要结论。
- 对涉及方案、边界、验收、停止条件的补上下文任务，主协调器与子代理默认优先阅读 `task.md` 与 Markdown 真源，再按需读取 `state.json` 结构化字段。
- `Plan Window` 在冻结正式任务状态前，必须先审阅阅读型子代理回报中的证据路径。
- `Execute Window` 的局部阅读回报也必须附相关代码与文档证据路径。
- 执行型与审查型子代理开始工作前，必须先读取 `subtask.read_paths`。
- 若读完 `subtask.read_paths` 后仍无法确定改法或结论，必须退回主协调器，不得自行脑补。

## 统一落盘口径

- `docs/ai/tasks/<task_id>/state.json`
- `docs/ai/tasks/<task_id>/task.md`
- `docs/ai/tasks/<task_id>/events.jsonl`（可选）

项目侧可以补充本仓目录、模块与运维口径，但不再承担上述对象的通用合同正文。

## 落盘语言规则

- 对任何落盘文件，能用中文表达的地方尽量使用中文。
- 优先使用中文的对象包括：
  - `task.md`
  - `state.json` 中的说明性字段
  - `subtask.assignment` 中的说明性字段
  - `subtask.read_paths / subtask.write_paths` 对应的人读说明
  - `subtask.result` 中的说明性字段
  - 审查报告与测试建议
- 文件路径、字段名、脚本参数、代码标识符、协议字段等必须保持机器可读或生态约定的内容，不强行翻译。
- 在 JSON、Markdown 与事件流中，说明性文本、结论、风险、建议、验收说明、证据摘要默认优先中文。
- 主协调器在派发阅读型、执行型、审查型子代理时，必须显式要求：除字段名、路径、脚本参数、代码标识符与协议字段外，输出内容和落盘说明性文本默认使用中文。

## 验收与返工规则

- 复验不得由主协调器自行完成，必须由专门审查型子代理负责。
- 审查必须是多维度的；不能用“测试通过”替代代码审查、合同审查、运行时审查。
- 同一轮任务的后续复审默认复用同一个专门审查型子代理；只有崩溃或不可恢复异常时才允许更换。
- 审查不通过时：
  - 一律退回原执行型子代理返工
  - 主协调器必须完整转发 findings、等待返工、重新组织复验
  - 主协调器不直接代修失败项

## 审查触发规则

- 默认不采用“每个子代理动作都再派一个审查子代理”的模式。
- 阅读型子代理的回报，默认由当前窗口主协调器直接审阅。
- 只有执行型 `subtask` 完成并进入验收闸门时，才默认需要审查型子代理。
- 纯阅读、纯盘点、纯证据收集结果，不默认再开独立审查子代理。
- 必须触发审查型子代理的场景包括：
  - 修改代码、配置、schema、template、skill、rules、governance 文档
  - 修改 `state.json` 中的任务合同字段结构
  - 修改运行时 install / sync / doctor 行为
  - 需要明确“通过 / 不通过”验收结论的批次收口

## 审查输出规则

- 审查型子代理必须明确给出：
  - `结论：通过 / 不通过 / 证据不足`
  - 阻断 findings
  - 支撑结论的关键依据
  - 必要时的残余风险
- 当需要补测试时，审查型子代理不能只说“缺什么测试”，必须输出可直接落地的具体测试用例。

## 测试规则

- 执行型子代理每一轮迭代都必须补齐并运行本轮要求的测试；初始实现轮次也不例外。
- 执行型子代理提交结果时，必须说明：
  - 新增或修改了哪些测试文件 / 测试名
  - 实际运行了哪些测试命令
  - 测试结果
- 测试必须优先验证外部行为、合同、稳定 issue/type、产物结构与可观察结果。

## 文档与代码同步规则

- 只要规则、合同、模板或行为口径发生变化，文档必须先于代码更新。
- 长任务进入正式代码实施前，主协调器必须先同步当前批次相关的核心架构、模块、契约、入口与测试文档；该范围不包含过去长任务遗留的方案文档与施工文档。
- 若文档、测试、代码存在同一批次中的强同步关系，必须在同一批次内连续收口，不能交叉漂移。
- 项目侧入口文档只保留引用、项目级 rules system 与项目增量规则；统一规则真源仍在本文。

## 子代理输出压缩规则

- 主窗口不接收子代理的长过程全文，只接收结构化结果与必要摘要。
- 阅读型子代理默认压缩输出为：
  - `summary`
  - `relevant_code_paths`
  - `relevant_doc_paths`
  - `key_findings_with_evidence`
  - `unknowns`
  - `recommended_next_step`
- 执行型子代理默认以 `subtask.result` 为主，只补最小必要摘要：
  - 实际改了什么
  - 实际验证了什么
  - 哪些计划项未完成
  - 哪些地方偏离了 `subtask.assignment`
  - 当前风险与下一步建议
- 审查型子代理默认只回：
  - `结论：通过 / 不通过 / 证据不足`
  - `findings`
  - `关键依据`
  - `残余风险`

## 总体方案与 Phase 路线图规则

- 凡中大规模实施，必须先落一份“总体方案 + 实施计划 / phase 路线图”文档，再进入正式代码实施。
- 长任务默认至少落两份文档：方案文档与施工文档；两者都应满足项目定义的固定必填字段。
- 该文档必须在正式代码实施前冻结，并反映到 `state.json`。
- 跨项目或机器级事项，默认使用项目总纲文档；当前约定入口为：`C:\Users\72385\dev\ai-harness\docs\plans\AI_HARNESS_MASTER_PLAN.md`
- 仓库级事项可使用对应仓库根目录或已约定的全局真源位置，但必须在入口文档中显式引用。

## 推荐模板

- 审查输出模板：`templates/review_report.example.md`
- 审查测试用例模板：`templates/review_testcases.example.md`
- 执行迭代清单：`templates/code_worker_iteration_checklist.example.md`

## 角色优先调度顺序

- 执行型委派必须遵循固定顺序：`先选角色 -> 查 codex-role-map -> 读取 task_state -> 锁定 subtask -> 写入 assignment -> 下发执行`。
- 禁止跳过角色层直接按裸 `default/explorer/worker` 委派执行任务。
- 若角色在 `agents/codex-role-map.json` 中无映射，必须阻断派发并回退到方案或映射修订流程。

## 映射变更最小审查要求

- 任何 `agents/codex-role-map.json` 变更都必须附带：变更角色清单、映射前后差异、风险说明。
- 审查必须确认 `agent_type` 仍仅来自 `default / explorer / worker`，不得引入新平台原生类型。
- 审查必须确认文档口径一致：`agents/*.md` 负责角色语义，`codex-role-map` 负责底层映射。
- 审查结论需明确是否需要同步更新 `task_state/subtask` 调度规则。

## 角色映射有效性与回退

- `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate` 必须在任务验收前校验 `agents/codex-role-map.json` 与 `agents/manifest.json`。
- 角色映射有效性至少包含三类硬门禁：
  - `agent_type` 只能是 `default / explorer / worker`。
  - `codex-role-map` 必须覆盖冻结必需角色：`planner`、`reader`、`reviewer`、`backend-implementer`、`frontend-implementer`、`test-verifier`、`doc-curator`、`ops-runbook`。
  - `codex-role-map` 与 `manifest` 双向一致（角色集合、`allow_write` 与 `allow_shell` 对应 `tools` 能力）。
- 任一角色映射门禁失败时，当前批次必须判定为未通过，不得继续派发执行型子代理。

