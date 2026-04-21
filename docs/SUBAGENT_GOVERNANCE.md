# SUBAGENT GOVERNANCE

## 目标

本文收口全局主协调器、执行型子代理、审查型子代理在各 batch / phase 实施中的统一规则。
项目仓库不应复制本文全文，只应在项目入口文档中引用本文，并补充项目增量约束。

## 适用范围

- 全局真源：`ai-harness/`
- 运行时投放：Claude / Codex 相关同步与 doctor 流程
- 项目适配层：各项目 `AGENTS.md`、`docs/ai/`、`config/ai/`

## 角色分工

- 主协调器：冻结方案、拆批次、下发工单、等待完成、回收结果、推进全局状态。
- 执行型子代理：在允许写入范围内修改文档、配置、测试、代码，并按工单完成验证。
- 审查型子代理：只做多维度审查与验收，不代替执行型子代理修改失败项。

## 双窗口模式

默认工作模式固定为：

- `Plan Window`：方案裁决窗口
- `Execute Window`：方案执行协调窗口

### `Plan Window`

职责：

- 接收需求
- 委派阅读型子代理引入上下文
- 基于阅读回报与用户反馈修订方案
- 冻结正式 `plan`
- 同步落盘正式 `plan.md` 与 `plan.json`

规则：

- `Plan Window` 的上下文引入默认完全由阅读型子代理承担。
- `Plan Window` 只冻结阶段概览、边界、验收与停止条件，不提前细化每阶段施工工单。
- 一旦进入 `plan freeze` 阶段，不再继续委派任何子代理。
- `plan freeze` 阶段只允许主窗口基于已回收材料与用户反馈收敛并落盘。
- `plan.md` 是冻结方案的语义真源，`plan.json` 是由 `Plan Window` 同步生成的结构化投影。
- `Plan Window` 必须对 `plan.md -> plan.json` 的字段映射负责；若 bootstrap 仅预创建了占位 `plan.json`，冻结时必须覆盖为正式内容。
- 若 `Plan Window` 已冻结正式双件，后续 bootstrap 只允许显式绑定该 `plan.md + plan.json`，不得再自动新建 task 级 draft `plan.md` 或占位 `plan.json` 覆盖冻结结果。
- 若 `plan.md` 与 `plan.json` 冲突，以 `plan.md` 为准。
- 只要任务进入本 orchestrator 流程，无论任务大小，都必须先经过主窗口与用户的交互式方案冻结，不得跳过 `Plan Window` 直接进入实施。

### `Execute Window`

职责：

- 完整阅读冻结方案
- 委派阅读型子代理补齐本轮局部上下文
- 细化当前阶段工作
- 生成 `work_order / dispatch_packet / dispatch_message_raw`
- 派发执行型子代理并回收 `return_packet`

规则：

- `Execute Window` 必须先完整阅读冻结 `plan`。
- `Execute Window` 理解方案时默认先读冻结 `plan.md`，再按需读取 `plan.json` 提取结构化字段；不允许只靠 `plan.json` 代替方案理解。
- 在派发执行型子代理前，必须先派阅读型子代理补齐本轮局部上下文。
- 当前阶段的具体工作、详细工单与最终提示词，统一在 `Execute Window` 内细化。
- 不允许只凭冻结 `plan` 摘要直接生成执行型工单。
- `Execute Window` 在派出阅读型子代理后，只允许做非重叠的协调准备动作，不得并行重复阅读子代理正在覆盖的上下文。
- `Execute Window` 不负责重新解释或改写冻结 `plan` 语义；若发现 `plan.md / plan.json` 不一致，必须停止并退回。

## 批次与路由规则

- 每一批、每一 phase 都必须先委派一个或多个子代理执行或审查，不能由主协调器跳过子代理直接收口。
- `Plan Window` 只能派阅读型子代理；执行型子代理只能由 `Execute Window` 派发。
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
- 只有出现以下阻塞时，才允许结束当前子代理轮次并回到主协调器：
  - 明确死循环
  - 多轮重复无进展
  - 缺少必须的权限或外部环境
  - 冻结方案失效，继续执行会扩大范围
- 出现阻塞时，必须记录具体阻塞点、已尝试动作与下一步建议，不能笼统写“未完成”。

## 进入下一步的闸门

- 进入下一步前，所有本批次相关子代理都必须：
  - 自然完成
  - 结果被回收
  - 完成验收
- 只要仍有一个相关子代理未完成或未验收通过，就不能推进到下一步。

## 统一控制面对象合同

### `plan`

- 回答：改什么、为什么改、边界是什么、验收是什么。
- 中大型改动必须先冻结 `plan`，再拆成一个或多个 `work_order`。
- `plan` 允许 `draft` 与 `frozen` 两种状态。
- 只有 `Plan Window` 可把 `plan` 从 `draft` 变为 `frozen`。
- 未冻结 `plan` 不得派发执行型子代理。
- 绑定既有方案的 bootstrap、进入 `Execute Window` 的 validate 与 run 验收闸门只接受 `status=frozen`；`draft` 只允许停留在 `Plan Window`。
- 正式冻结方案默认以 `plan.md` 作为语义真源；仓库级任务建议落盘到 `docs/plans/<plan-name>.md`，跨项目或机器级事项可继续使用根目录总纲方案文档。
- `plan.json` 作为 `plan.md` 的结构化投影，由 `Plan Window` 在冻结时同步生成，供执行、审查与自动化字段消费使用。
- `plan.json` 应至少回指 `source_plan_doc`，用于标明对应的冻结方案文档路径。
- `plan draft` 必须附证据清单，至少包含：
  - `relevant_code_paths`
  - `relevant_doc_paths`
  - `key_findings_with_evidence`
  - `evidence_summary`

### `work_order`

- 回答：谁改哪几个文件、最低可执行改法是什么、怎么验收。
- `work_order` 必须包含最小可执行改法，至少写清：
  - `change_spec`
  - `execution_steps`
  - `verification_steps`
  - `dispatch_message_raw`
- 执行型 `work_order` 还应明确：
  - `read_paths_mandatory`
  - `read_paths_optional`
  - `evidence_summary`
  - `scope_out`
- 执行型 `work_order` 应补齐以下字段，以便主协调器统一管理状态：
  - `return_packet_path`
  - `return_packet_required`
  - `expected_written_role`
  - `required_return_fields`
  - `completion_gate`
  - `state_owner`
- `expected_written_by` 在 writer 身份已知时应显式写入；`validate` 会校验 `return_packet.written_by / written_role` 与工单合同一致，并拒绝明显协调器身份。
- 当 writer 身份尚未知晓时，`hydrate` 应回填机器可校验的 `expected_written_by_patterns`；`validate` 先校验 `expected_written_by` 精确值，其次校验 `expected_written_by_patterns`，最后才允许使用 `role / expected_written_role / work_order_id` 派生出的锚定身份模式合同。
- `expected_written_by_patterns` 只能使用锚定的字面身份模式，且必须落在工单可派生的允许集合内；不能写成 `.*`、`\d/\w/\s`、分组、量词或其他可弱化作者绑定的宽松正则。
- `written_by` 不能写成任意非协调器字符串；即使没有显式 `expected_written_by`，也必须匹配工单合同允许的作者身份模式。
- `dispatch_packet_required=true` 是显式复杂任务闸门，可覆盖数量型启发式，避免“小文件数但高复杂度”任务漏掉 `dispatch_packet`。
- 若缺 `read_paths_mandatory`，执行型工单不得派发。
- `required_return_fields` 只能在仓库最低回执字段集合之上追加，不能删减最低集合。
- `dispatch_message_raw` 必须从 `work_order / dispatch_packet` 稳定编译，不得自由发挥手写；若编译前置缺失，工单应阻断并补齐合同。
- `hydrate` 不只在 `dispatch_message_raw` 缺失时运行；它必须重编译并修复陈旧内容，且在工单 JSON 不可解析、编译失败、`dispatch_packet_path` 越界或复杂任务缺施工图时非零退出。
- `validate` 不只检查 `dispatch_message_raw` 关键词，还要检查它与合同编译结果一致。
- `evidence_summary` 只作导航，不能代替原文件阅读。

### `dispatch_packet`

- 回答：每个文件具体怎么改、先后顺序、停在哪些点。
- 复杂任务必须补 `dispatch_packet`。默认至少在以下场景补齐：
  - 跨模块任务
  - 超过 3 个写入文件
  - 有明确状态机或数据契约改造
  - `work_order` 本身已不足以表达逐文件改法
- 若工单显式声明 `dispatch_packet_required=true`，即使不满足数量启发式，也必须补 `dispatch_packet`。
- 使用 `dispatch_packet` 时，必须在 `work_order` 中写明 `dispatch_packet_path`。
- `dispatch_packet_path` 必须位于当前 `docs/ai/runs/<task_id>/dispatch_packets/` 下，不得漂到 task run 外。

### `return_packet`

- 回答：实际改了什么、验证了什么、风险是什么、是否触发停止条件。
- `return_packet` 由执行该工单的子代理填写，不由主协调器代写正文。
- 主协调器不得新建、重写或补写 `return_packet` 的正文事实；若 `return_packet` 缺失、正文过薄或事实不清，必须退回原执行子代理补写。
- 主协调器只允许对 `return_packet` 做结构校验、字段兜底、路径回填与状态推进，不得把这些动作伪装成执行子代理的正文回执。
- 没有 `return_packet`，工单不能视为完成。
- 当 `return_packet_required=true` 时，缺失 `return_packet` 是 validate error，不是 warning。
- `return_packet_required` 不能被手工改成 `false` 作为绕过手段；执行型工单默认必须要求回执。
- `return_packet_path` 必须绑定当前 `work_order_id` 对应的回执，不能挟持同 run 里其他工单的回执文件。
- `return_packet` 最低字段口径应至少包含：
  - `work_order_id`
  - `status`
  - `summary`
  - `changed_files`
  - `planned_files_not_changed`
  - `verification_commands`
  - `verification_result`
  - `deviations_from_dispatch`
  - `blocked_by`
  - `risks`
  - `follow_up_needed`
  - `written_by`
  - `written_role`
- `validate` 校验回执时，必须同时满足仓库最低字段集合与 `work_order.required_return_fields` 的并集。
- `validate` 校验回执时，还必须校验 `written_role` 是否匹配 `expected_written_role`，并在 `expected_written_by` 存在时校验 `written_by` 精确匹配。
- 若 `expected_written_by_patterns` 存在，`validate` 还必须校验 `written_by` 命中至少一个模式；非法正则本身也必须作为 validate error。
- `dispatch_packet_path` 与 `return_packet_path` 除了目录前缀外，还必须拒绝穿过 symlink / junction / reparse point 的路径跳转。
- `validate` 对缺失 `work_orders` 目录或当前 task run 下 `work_order` 数量为 0 必须直接失败，不能因为“没有对象可检查”而误判成功。
- `validate` 必须要求 `-TaskId`，不能把 task run 作用域当可选参数。
- `hydrate` 对目标路径不存在、目标 task 缺 `work_orders`、或解析后目标集合为 0 必须非零退出，不能把空集合视为成功。
- `compile-dispatch-message.ps1` 对空目标目录也必须非零退出，不能把“没有编译任何工单”视为成功。
- 执行型子代理提交完成结果时，应说明：
  - 哪些计划项未完成
  - 哪些地方偏离了 `dispatch_packet`
  - 运行了什么验证命令或验证步骤

## 阅读与证据规则

- 阅读型子代理必须罗列支撑结论的相关代码和文档证据路径，不能只给摘要结论。
- 对涉及方案、边界、验收、停止条件的补上下文任务，主协调器与子代理默认优先阅读 Markdown 真源，再按需读取 JSON 合同；不允许只凭 JSON 跳过文档语义。
- `Plan Window` 在冻结正式 `plan` 前，必须先审阅阅读型子代理回报中的证据路径。
- `Execute Window` 的局部阅读回报也必须附相关代码与文档证据路径。
- `Execute Window` 派出阅读型子代理后，允许做的准备动作仅包括：
  - 文件存在性检查
  - 路径与入口检查
  - 落盘位置检查
  - 工单骨架预创建
  - 明显阻塞项预发现
- `Execute Window` 不允许在阅读子代理回报返回前并行重复以下工作：
  - 系统性重读同一批局部上下文
  - 提前定字段改法
  - 提前写详细工单正文
  - 提前形成实现结论
- 执行型子代理开始修改前，必须先读取 `read_paths_mandatory`。
- 执行型子代理可以参考 `evidence_summary`，但不得用其代替原文件阅读。
- 若执行型子代理读完 `read_paths_mandatory` 后仍无法确定改法，必须退回 `Execute Window`，不得自行脑补。

## 统一落盘口径

- `docs/plans/<plan-name>.md`（仓库级冻结方案文档真源，建议路径）
- `docs/ai/runs/<task-id>/plan.json`
- 若 run 通过既有冻结方案绑定生成，`docs/ai/runs/<task-id>/plan.json` 必须来自已冻结 `plan.json` 投影，不允许只绑定 Markdown 而缺少正式结构化投影
- `docs/ai/runs/<task-id>/work_orders/*.json`
- `docs/ai/runs/<task-id>/dispatch_packets/*.json`
- `docs/ai/runs/<task-id>/return_packets/*.json`
- `docs/ai/runs/<task-id>/orchestration_log.md`
- `.ai/session/<task-id>/task_plan.md`
- `.ai/session/<task-id>/findings.md`
- `.ai/session/<task-id>/progress.md`

项目侧可以补充本仓目录、模块与运维口径，但不再承担上述对象的通用合同正文。

## 落盘语言规则

- 对任何落盘文件，能用中文表达的地方尽量使用中文。
- 优先使用中文的对象包括：
  - `plan`
  - `work_order`
  - `dispatch_packet`
  - `return_packet`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
  - 审查报告与测试建议
- 文件路径、字段名、脚本参数、代码标识符、协议字段等必须保持机器可读或生态约定的内容，不强行翻译。
- 在 `json`、Markdown、回执和会话留痕中，说明性文本、结论、风险、建议、验收说明、证据摘要默认优先中文。
- 主协调器在派发阅读型、执行型、审查型子代理时，必须显式要求：除字段名、路径、脚本参数、代码标识符与协议字段外，输出内容和落盘说明性文本默认使用中文。
- 若子代理返回或落盘内容大面积使用英文，且不属于机器可读字段或生态约定内容，默认视为不符合口径；主协调器应要求其改写为中文后再收口。

## 验收与返工规则

- 复验不得由主协调器自行完成，必须由专门审查型子代理负责。
- 审查必须是多维度的；不能用“测试通过”替代代码审查、合同审查、运行时审查。
- 审查维度应按任务选择，至少覆盖与本批次直接相关的维度，例如：
  - 合同 / 边界 / 非目标
  - runtime / install / sync / receipt / doctor
  - hook / guard / helper / 行为回归
  - 文档 / 模板 / 入口引用
- 审查不通过时：
  - 一律退回原执行型子代理返工
  - 主协调器只负责转发 findings、等待返工、重新组织复验
  - 主协调器不直接代修失败项

## 审查触发规则

- 默认不采用“每个子代理动作都再派一个审查子代理”的模式。
- 阅读型子代理的回报，默认由当前窗口主协调器直接审阅。
- 只有执行型工单完成并进入验收闸门时，才默认需要审查型子代理。
- 纯阅读、纯盘点、纯证据收集结果，不默认再开独立审查子代理。
- 必须触发审查型子代理的场景包括：
  - 修改代码、配置、schema、template、skill、rules、governance 文档
  - 修改 `work_order / dispatch_packet / return_packet` 合同
  - 修改运行时 install / sync / doctor 行为
  - 需要明确“通过 / 不通过”验收结论的批次收口

## 审查输出规则

- 审查型子代理必须明确给出：
  - `结论：通过 / 不通过`
  - 阻断 findings
  - 支撑通过的关键依据
  - 必要时的残余风险
- 当需要补测试时，审查型子代理不能只说“缺什么测试”，必须输出可直接落地的具体测试用例。
- 具体测试用例至少应包含：
  - 建议测试名
  - 建议放入的测试文件路径
  - 输入场景或构造方式
  - 预期断言
  - 为何这是行为 / 契约测试而不是实现过拟合

## 测试规则

- 执行型子代理每一轮迭代都必须补齐并运行本轮要求的测试；初始实现轮次也不例外。
- 新增或修改的测试集合，以审查型子代理给出的具体测试用例为准。
- 执行型子代理提交结果时，必须说明：
  - 新增或修改了哪些测试文件 / 测试名
  - 实际运行了哪些测试命令
  - 测试结果
- 测试必须优先验证外部行为、合同、稳定 issue/type、产物结构与可观察结果。
- 测试不得对以下内容过拟合：
  - 私有 helper 名称
  - 局部变量
  - 临时目录名
  - 内部动作顺序
  - 仅用于实现的 marker 文本

## 文档与代码同步规则

- 只要规则、合同、模板或行为口径发生变化，文档必须先于代码更新。
- 若文档、测试、代码存在同一批次中的强同步关系，必须在同一批次内连续收口，不能交叉漂移。
- 项目侧入口文档只保留引用与项目增量规则；统一规则真源仍在本文。

## 子代理输出压缩规则

- 主窗口不接收子代理的长过程全文，只接收结构化结果与必要摘要。
- 阅读型子代理默认压缩输出为：
  - `summary`
  - `relevant_code_paths`
  - `relevant_doc_paths`
  - `key_findings_with_evidence`
  - `unknowns`
  - `recommended_next_step`
- 执行型子代理默认以 `return_packet` 为主，只补最小必要摘要：
  - 实际改了什么
  - 实际验证了什么
  - 哪些计划项未完成
  - 哪些地方偏离了 `dispatch_packet`
  - 当前风险与下一步建议
- 审查型子代理默认只回：
  - `结论：通过 / 不通过`
  - `findings`
  - `关键依据`
  - `残余风险`
- 以下内容不得被压缩掉：
  - 关键代码路径
  - 关键文档路径
  - 结论与证据的对应关系
  - 实际改动文件
  - 实际验证命令或验证事实
  - 阻塞原因
  - 偏离施工图的地方

## 总体方案与 Phase 路线图规则

- 凡中大规模实施，必须先落一份“总体方案 + 实施计划 / phase 路线图”文档，再进入正式代码实施。
- 该文档必须在正式代码实施前冻结到指定根目录或全局真源约定位置。
- 跨项目或机器级事项，默认使用项目总纲文档；当前约定入口为：`C:\Users\72385\dev\ai-harness\docs\plans\AI_HARNESS_MASTER_PLAN.md`
- 仓库级事项可使用对应仓库根目录或已约定的全局真源位置，但必须在入口文档中显式引用。
- 后续每个 phase / 批次如果发生状态变化、范围变化、验收结论变化或推荐下一步变化，必须同步回写该总纲文档。

## 推荐模板

- 审查输出模板：`templates/review_report.example.md`
- 审查测试用例模板：`templates/review_testcases.example.md`
- 执行迭代清单：`templates/code_worker_iteration_checklist.example.md`

## 阶段2治理补充：角色优先调度顺序

- 执行型委派必须遵循固定顺序：`先选角色 -> 查 codex-role-map -> 生成合同 -> 下发执行`。
- 禁止跳过角色层直接按裸 `default/explorer/worker` 委派执行任务。
- 若角色在 `agents/codex-role-map.json` 中无映射，必须阻断派发并回退到方案或映射修订流程。

## 映射变更最小审查要求

- 任何 `agents/codex-role-map.json` 变更都必须附带：变更角色清单、映射前后差异、风险说明。
- 审查必须确认 `agent_type` 仍仅来自 `default / explorer / worker`，不得引入新平台原生类型。
- 审查必须确认文档口径一致：`agents/*.md` 负责角色语义，`codex-role-map` 负责底层映射。
- 审查结论需明确是否需要同步更新 `work_order` 模板或调度规则（本阶段仅记录，不提前实施阶段3+改造）。

## 阶段6治理补充：角色映射有效性与回退

- `validate-control-plane.ps1` 必须在任务验收前校验 `agents/codex-role-map.json` 与 `agents/manifest.json`。
- 角色映射有效性至少包含三类硬门禁：
  - `agent_type` 只能是 `default / explorer / worker`。
  - `codex-role-map` 必须覆盖冻结必需角色：`planner`、`reader`、`reviewer`、`backend-implementer`、`frontend-implementer`、`test-verifier`、`doc-curator`、`ops-runbook`。
  - `codex-role-map` 与 `manifest` 双向一致（角色集合、`allow_write` 与 `allow_shell` 对应 `tools` 能力）。
- 任一角色映射门禁失败时，当前批次必须判定为未通过，不得继续派发执行型子代理。
- 角色映射失败回退策略：
  - 映射缺失或非法：回退到阶段2映射修订流程。
  - 映射与 manifest 不一致：先修订映射/清单并补充审查，再重新执行 validate。
  - 若修订会触及阶段7入口适配范围：立即阻断并升级为 `blocked`，不得跨阶段硬改。
