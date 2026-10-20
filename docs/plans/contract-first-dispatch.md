# CONTRACT_FIRST_DISPATCH_PLAN

## 目标

冻结后续 `ai-harness` 控制面升级的实施依据，优先解决以下问题：

- `plan` 的所有权与冻结入口不够明确
- 执行型子代理的最终提示词质量仍依赖临场发挥
- `work_order / dispatch_packet / return_packet` 的字段尚不足以稳定支撑复杂委派
- 结构化合同与最终提示词之间缺少稳定映射

本方案当前作为实施真源使用；截至 2026-04-07，本轮已完成“三项控制面硬闸门”下沉、文档同步与集成测试补齐。

## 冻结结论

### 1. 默认工作模式切换为方案 A：双窗口

- `Window A = Plan Window`
- `Window B = Execute Window`

默认流程：

1. 在 `Plan Window` 接收需求。
2. 仅委派阅读型子代理收集上下文、起草 `plan draft`。
3. 回收阅读型子代理结果后，进入 `plan freeze` 阶段。
4. `plan freeze` 阶段不再继续委派子代理，只由主窗口与用户交互、修订并冻结正式 `plan`。
5. `Plan Window` 冻结正式 `plan.md` 并同步生成 `plan.json` 后，再进入 `Execute Window`。
6. `Execute Window` 先完整阅读冻结 `plan.md`，再按需读取 `plan.json` 并委派阅读型子代理补齐本轮局部上下文。
7. `Execute Window` 基于冻结 `plan` 与局部阅读结果生成 `work_order / dispatch_packet / dispatch_message_raw`，再派发执行型子代理。
8. `Execute Window` 在阅读型子代理回报返回前，只允许做非重叠的协调准备，不做并行重复阅读。

补充冻结结论：

- 只要任务进入本双窗口 / contract-first 流程，无论任务大小，都必须先经过主窗口与用户的交互式方案冻结。
- 不允许把“任务简单”作为跳过 `Plan Window`、跳过方案冻结或直接进入实施的理由。

### 1.1 `Plan Window` 只冻结阶段概览，不预写详细工单

`Plan Window` 当前只负责冻结：

- 总目标
- `scope_in / scope_out`
- 验收口径
- 停止条件
- 风险
- 阶段顺序概览

`Plan Window` 不负责提前写满：

- 每个阶段的逐文件改法
- 每个阶段的详细 `work_order`
- 每个阶段的详细 `dispatch_packet`
- 每个执行型子代理的最终提示词

这些内容统一由 `Execute Window` 在完整阅读冻结方案并补齐局部上下文后再细化。

### 2. `plan` 所有权固定在主窗口

- `plan_owner = main_window`
- `subagent_role_in_plan = read_and_draft_only`
- `execution_may_start_only_after_plan_freeze = true`
- `no_subagent_dispatch_during_plan_freeze = true`
- `plan_md_is_semantic_source = true`
- `plan_json_is_structured_projection = true`

阅读型子代理可以：

- 阅读文档、代码、测试与历史 run 留痕
- 产出 `plan draft`
- 列风险、问题、候选方案与边界建议
- 罗列支撑结论的相关代码与文档证据路径
- 输出 `evidence_summary`，说明“为什么这些文件与本次任务相关”

阅读型子代理不可以：

- 直接冻结正式 `plan`
- 在 `plan` 未冻结前下发执行型工单
- 代替主窗口与用户完成范围确认
- 只给结论而不给关键证据路径

### 3. 合同派发优先于提示词润色

后续升级的第一优先级固定为：

- 先补强 `plan / work_order / dispatch_packet / return_packet` 的合同能力
- 再把合同稳定编译成高质量 `dispatch_message_raw`

理由：

- 只有提示词而没有强合同，长期一定漂移
- 只有合同而没有高质量提示词，执行质量仍不稳定
- 因此必须采用 `contract-first, prompt-compiled` 的路线

### 4. 子代理真正执行时，必须同时依赖两层输入

- 结构化合同层：`work_order` 与必要时的 `dispatch_packet`
- 最终提示词层：`dispatch_message_raw`

冻结要求：

- 复杂任务不得只给提示词不给合同
- 执行型子代理不得只看合同而没有最终派发提示词
- 最终提示词必须从合同出发生成，而不是临场即兴拼接

## 当前问题判断

结合当前真源状态，当前最需要优化的不是某一个单字段，而是整条派发链：

`plan -> work_order -> dispatch_packet -> dispatch_message_raw -> return_packet -> review`

当前主要薄弱点：

1. `plan` 的“草案”和“正式冻结版”边界还不够显式。
2. `work_order` 已有基本字段，但对子代理所需上下文、边界和禁改范围约束不够强。
3. `dispatch_packet` 已有逐文件改法雏形，但仍不足以表达复杂任务的依赖、停点和不变量。
4. `dispatch_message_raw` 目前仍偏人工提示词，尚未形成稳定模板。
5. `return_packet` 已有完成回执能力，但对偏离施工图、未改项和阻塞点的表达还不够完整。
6. 阅读型子代理回报目前缺少强制证据字段，主窗口难以快速判断结论是否可靠。
7. 子代理输出若不压缩，会把主窗口重新拖回长上下文状态，削弱双窗口分工。

## 对象升级方向

### 1. `plan`

`plan` 继续回答：

- 改什么
- 为什么改
- 边界是什么
- 验收是什么
- 停止条件是什么

新增冻结规则：

- `plan` 必须明确 `scope_in / scope_out / acceptance / stop_conditions`
- `plan` 必须标记 `status=draft|frozen`
- 只有主窗口可把 `status` 从 `draft` 变为 `frozen`
- 未冻结 `plan` 不得派发执行型子代理
- 绑定既有方案的 bootstrap、进入 `Execute Window` 的 validate 与 run 验收闸门只接受 `status=frozen`；`draft` 只允许停留在 `Plan Window`
- 冻结方案默认采用双件制：`plan.md` 作为语义真源，`plan.json` 作为结构化投影
- `plan.md -> plan.json` 的同步转化责任固定归 `Plan Window` 主协调器，不归 `Execute Window`，不归任何子代理
- `plan.json` 应回指 `source_plan_doc`
- 若 `plan.md / plan.json` 冲突，以 `plan.md` 为准；`Execute Window` 必须停止并退回，不得自行脑补修正

新增证据要求：

- `plan draft` 必须附带证据清单
- 证据清单至少包含：
  - `relevant_code_paths`
  - `relevant_doc_paths`
  - `key_findings_with_evidence`
- `plan draft` 应补充：
  - `evidence_summary`
- 主窗口在冻结 `plan` 前，必须能从子代理回报中定位到关键代码与关键文档

### 2. `work_order v2`

在现有字段基础上，后续补强为至少包含：

- `role`
- `task_goal`
- `scope_in`
- `scope_out`
- `read_paths_mandatory`
- `read_paths_optional`
- `write_paths`
- `context_paths`
- `evidence_summary`
- `constraints`
- `acceptance_criteria`
- `verification_steps`
- `stop_conditions`
- `dispatch_message_raw`
- `return_packet_path`

新增判断：

- 若缺 `context_paths`，复杂工单默认视为信息不足
- 若缺 `read_paths_mandatory`，执行型工单不得派发
- 若缺 `evidence_summary`，复杂工单默认视为上下文导航不足
- 若缺 `scope_out`，执行边界默认不合格
- 若缺 `acceptance_criteria`，工单不得派发
- `required_return_fields` 只能在仓库最低回执字段集合之上追加，不能删减或替换最低集合
- `validate` 校验 `return_packet` 时，必须按“仓库最低字段集合 + work_order.required_return_fields”并集执行

### 3. `dispatch_packet v2`

`dispatch_packet` 继续作为复杂任务的逐文件施工图，后续补强为至少包含：

- `change_spec`
- `execution_order`
- `read_before_write`
- `invariants`
- `forbidden_changes`
- `dependency_notes`
- `done_signals`
- `verification_focus`
- `fallback_strategy`
- `handoff_notes`

其中：

- `invariants` 用于声明哪些外部行为、接口或契约不得被破坏
- `forbidden_changes` 用于显式禁止越权修改
- `fallback_strategy` 用于说明子代理卡住时应回退到什么边界
- `handoff_notes` 用于给 review 或下游工单提供回收入口

### 4. `dispatch_message_raw`

`dispatch_message_raw` 升级为一等公民，不再只作为“顺手记录一下的原始消息”。

后续要求：

- 必须由合同对象生成
- 必须显式包含任务目标、必读上下文、写入范围、禁改范围、逐文件改法、验收标准、停止条件、回执要求
- 必须显式包含：
  - `先阅读 read_paths_mandatory 再开始修改`
  - `evidence_summary 仅作导航，不能代替原文件阅读`
- 编译前置至少包括 `task_goal / read_paths_mandatory / write_paths / scope_out / acceptance_criteria / stop_conditions / return_packet_path`；复杂任务还要求 `dispatch_packet.read_before_write / execution_order / change_spec` 可解析
- 若编译前置缺失，必须阻断派发并补齐合同，不允许降级为人工兜底提示词
- `validate` 不只检查关键词，还必须检查 `dispatch_message_raw` 与合同编译结果一致
- 主协调器应在派发时显式要求：除字段名、路径、脚本参数、代码标识符与协议字段外，输出与落盘说明性文本默认使用中文
- 不允许主协调器长期依赖自由发挥手写派发消息

后续最少提供三类模板：

- 文档型子代理模板
- 代码型子代理模板
- 审查型子代理模板

### 5. `return_packet v2`

在现有字段基础上，后续补强为至少包含：

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

新增要求：

- 不允许只写“已完成”而不说明哪些计划项未改
- 不允许只写“已验证”而不说明运行了什么
- 不允许只写“blocked”而不说明具体阻塞点
- `work_order.required_return_fields` 只能扩展，不能削弱仓库最低回执字段集合
- `return_packet` 正文必须由执行该工单的子代理填写；主协调器不得代写正文，缺失或不合格时必须退回原执行型子代理补写

## 派发与回收工作流

### 阶段 A：Plan Window

允许：

- 阅读委派
- 方案答疑
- 风险收集
- `plan draft` 修订
- 正式 `plan` 冻结与落盘

强制要求：

- `Plan Window` 的上下文引入默认完全由阅读型子代理承担
- 阅读型子代理必须给出相关代码和文档作为证据，而不是只给摘要结论
- `Plan Window` 在冻结正式 `plan` 前，必须先审阅阅读型子代理回报中的证据路径
- 一旦进入 `plan freeze` 阶段，不再继续委派任何子代理
- `plan freeze` 只允许主窗口基于已回收材料与用户反馈收敛并落盘
- `Plan Window` 只冻结阶段概览与阶段边界，不提前细化每阶段施工工单
- `Plan Window` 冻结方案时，必须同步落盘正式 `plan.md` 与 `plan.json`
- 即使任务较小，只要进入本流程，也必须经过主窗口与用户的交互式方案冻结

不允许：

- 执行型工单派发
- 代码、配置、模板、schema 实施
- 未冻结方案即进入实施窗口
- 在 `plan freeze` 阶段继续追加新的子代理委派

### 阶段 B：Execute Window

前置条件：

- `plan.status = frozen`
- `plan` 已落盘
- `acceptance / scope_out / stop_conditions` 已明确

强制步骤：

- `Execute Window` 必须先完整阅读冻结 `plan`
- `Execute Window` 理解方案时默认先读 `plan.md`，再按需读取 `plan.json`
- 在派发执行型子代理前，必须先派阅读型子代理补齐本轮局部上下文
- 不允许 `Execute Window` 只凭冻结 `plan` 摘要直接生成执行型工单
- 局部阅读回报也必须附相关代码与文档证据路径
- 生成执行型工单时，必须显式给出 `read_paths_mandatory` 与 `evidence_summary`
- 当前阶段的具体工作、详细工单与最终提示词，统一在 `Execute Window` 内细化
- 在阅读型子代理回报返回前，只允许做非重叠的协调准备，例如文件存在性检查、路径与落盘入口检查、工单骨架预创建和阻塞项预发现
- `Execute Window` 不负责把冻结方案重新解释成另一版 `plan.json`；若发现 `plan.md / plan.json` 不一致，必须停止并退回
- 正式实施顺序固定为“冻结方案 -> 文档 / 清单 -> 测试 -> 代码 / 配置”，不得跳步
- 若某一分支确实不存在，必须在冻结方案中明确写为“不适用”或“本批不涉及”，而不是在执行阶段临时跳过

允许：

- 完整阅读冻结 `plan`
- 派阅读型子代理补局部上下文
- 做非重叠的协调准备
- 生成 `work_order`
- 复杂任务补 `dispatch_packet`
- 生成 `dispatch_message_raw`
- 派发执行型子代理
- 回收 `return_packet`
- 组织 review / 返工 / 复验

不允许：

- 未经局部阅读委派即直接派执行型子代理
- 绕过冻结 `plan` 直接下发代码工单
- 用审查结论反向替代正式 `return_packet`
- 只给摘要而不给必读文件集合就派发执行型子代理
- 并行重复阅读阅读型子代理正在覆盖的同一批局部上下文

### 阶段 C：执行型子代理阅读与实施

执行型子代理默认工作方式：

- 先读取 `read_paths_mandatory`
- 再参考 `evidence_summary`
- 必要时结合 `dispatch_packet` 的顺序理解逐文件改法
- 完成上述阅读后，才允许修改 `write_paths`

执行型子代理不应承担：

- 从全仓自由探索上下文
- 仅凭二手摘要直接实施
- 在读完必读文件前开始修改

读后闸门：

- 若执行型子代理读完 `read_paths_mandatory` 后仍无法确定改法，必须退回 `Execute Window`
- 不允许因信息不足而自行脑补
- `Execute Window` 应通过补阅读型子代理、补工单或补 `dispatch_packet` 解决，而不是要求执行型子代理猜测

## 子代理输出压缩规则

默认原则：

- 主窗口不接收子代理的长过程全文
- 主窗口只接收结构化结果与必要摘要
- 压缩不能牺牲证据路径、偏离项、阻塞点与验证事实

## 落盘语言规则

- 对任何落盘文件，能用中文表达的地方尽量使用中文。
- 优先中文的对象包括：
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
- 主协调器在派发阅读型、执行型、审查型子代理时，应显式把“默认中文输出”写入派发消息；若子代理返回内容大面积使用英文且不属于机器可读字段，默认视为不合格。

## 方案文档与 JSON 的读取优先级

- 对涉及方案理解、边界判断、验收口径、停止条件的补上下文任务，主协调器与子代理默认优先读取 Markdown 真源。
- `plan.json` 主要用于字段提取、自动化校验、执行侧引用与审查侧结构化消费。
- 不允许只凭 `plan.json` 跳过 `plan.md` 的方案理解。
- 推荐仓库级冻结方案路径为 `docs/plans/<plan-name>.md`；跨项目或机器级事项可继续使用根目录总纲方案文档。

### 阅读型子代理

默认输出应压缩为：

- `summary`
- `relevant_code_paths`
- `relevant_doc_paths`
- `key_findings_with_evidence`
- `unknowns`
- `recommended_next_step`

要求：

- 不回传大段探索过程
- 不粘贴长篇原文
- 主窗口能凭该输出定位到原始证据即可

### 执行型子代理

默认输出以 `return_packet` 为主，额外自然语言摘要应压缩为：

- 实际改了什么
- 实际验证了什么
- 哪些计划项未完成
- 哪些地方偏离了 `dispatch_packet`
- 当前风险与下一步建议

要求：

- 不重复讲完整实现过程
- 不把工单输入全文重新抄回
- 以事实、改动、验证、偏离、风险为主

### 审查型子代理

默认输出应压缩为：

- `结论：通过 / 不通过`
- `findings`
- `关键依据`
- `残余风险`

要求：

- 没有 findings 时保持极短
- 有 findings 时按问题展开，不输出无关背景

### 压缩边界

以下内容不得被压缩掉：

- 关键代码路径
- 关键文档路径
- 结论与证据的对应关系
- 实际改动文件
- 实际验证命令或验证事实
- 阻塞原因
- 偏离施工图的地方

## 审查策略

默认不采用“每个子代理动作都再派一个审查子代理”的模式。

冻结结论：

- 阅读型子代理的回报，默认由当前窗口主协调器直接审阅
- 只有执行型工单完成并进入验收闸门时，才默认需要审查型子代理
- 纯阅读、纯盘点、纯证据收集结果，不默认再开独立审查子代理

必须触发审查型子代理的场景：

- 修改代码、配置、schema、template、skill、rules、governance 文档
- 修改 `work_order / dispatch_packet / return_packet` 合同
- 修改运行时 install / sync / doctor 行为
- 需要明确“通过 / 不通过”验收结论的批次收口

可不单独触发审查型子代理的场景：

- 阅读型子代理提交 `plan draft`
- 阅读型子代理提交局部上下文回报
- 纯证据罗列、资产盘点、历史事实归档

主协调器对阅读型子代理的最低检查要求：

- 是否给出关键结论
- 是否给出相关代码路径
- 是否给出相关文档路径
- 是否给出“结论 -> 证据”对应关系
- 是否仍存在必须向用户澄清的未知项

## 后续实施批次

### Batch 1：治理规则与方案入口冻结

当前状态：

- 已完成

阶段目标：

- 把当前方案中已经冻结的双窗口、阅读委派、`plan freeze`、执行前补局部上下文、输出压缩与审查触发规则，同步回写到治理规则与 orchestrator skill 真源。

本阶段范围：

- `docs/SUBAGENT_GOVERNANCE.md`
- `skills/global-task-orchestrator/SKILL.md`
- 必要时与上述规则直接相关的引用入口文档

本阶段不展开：

- schema 字段升级
- 模板样例升级
- 提示词模板重写
- 校验脚本与测试实现

本阶段主要产出：

- 文档侧正式规则与本方案一致
- orchestrator skill 的阶段切换口径与本方案一致
- `contract-first`、`plan_owner`、`no_subagent_dispatch_during_plan_freeze`、执行前局部阅读补齐、输出压缩与审查策略完成真源收口
- `plan.md` 真源、`plan.json` 投影、`Plan Window` 负责同步转化、`Execute Window` 读文优先的规则完成真源收口

进入执行窗口后的细化原则：

- 由 `Execute Window` 先阅读本方案与现有治理文档
- 再派阅读型子代理补齐 `SUBAGENT_GOVERNANCE.md` 与 `SKILL.md` 的局部上下文
- 最后按实际差异生成当前 batch 的 `work_order / dispatch_packet / dispatch_message_raw`

### Batch 2：schema 与模板升级

当前状态：

- 已完成

阶段目标：

- 把本方案中冻结的合同升级方向，落实到 `work_order / dispatch_packet / return_packet` 的 schema 与示例模板中。

本阶段范围：

- `schemas/work_order.schema.json`
- `schemas/dispatch_packet.schema.json`
- `schemas/return_packet.schema.json`
- `templates/work_order.example.json`
- `templates/dispatch_packet.example.json`
- `templates/return_packet.example.json`

本阶段不展开：

- 提示词模板重写
- orchestrator 行为代码变更
- install / sync / doctor 逻辑变更

本阶段主要产出：

- `read_paths_mandatory / read_paths_optional / evidence_summary` 等新口径被正式写入 schema 或样例
- `return_packet` 对未改项、偏离项、验证事实与阻塞点的表达得到正式收口
- 模板能直接支撑后续 `dispatch_message_raw` 编译
- 本批已完成对象仍限 `work_order / dispatch_packet / return_packet` 合同；`plan.md / plan.json` 双件制规则由 Batch 1 治理真源承接

进入执行窗口后的细化原则：

- 由 `Execute Window` 先阅读本方案与现有 schema/template 真源
- 再派阅读型子代理比对“当前字段”与“目标字段”
- 对差异进行分批拆单，而不是在方案里提前写死逐文件改法

### Batch 2.5：`plan` 双件制模板与脚本收口

当前状态：

- 已完成

阶段目标：

- 把已冻结的 `plan.md` 真源 / `plan.json` 投影规则正式落实到 `plan` 相关 schema、样例与最小落盘脚本中，避免继续生成占位 `plan.json` 或沿用旧字段口径。

本阶段范围：

- `schemas/plan.schema.json`
- `templates/plan.example.json`
- `templates/progress.session.example.md`
- `skills/global-task-orchestrator/scripts/bootstrap-task.ps1`
- `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`
- 必要时与上述对象直接相关的最小辅助脚本

本阶段不展开：

- `work_order / dispatch_packet / return_packet` 再次扩字段
- 提示词模板重写
- 审查策略调整
- 大范围运行时重构

本阶段主要产出：

- `plan.schema.json` 能表达 `plan.json` 作为 `plan.md` 结构化投影的最小字段口径
- `plan.example.json` 与双件制规则一致，并显式包含 `source_plan_doc`
- bootstrap 不再只生成“待主协调器补充”的长期占位 `plan.json`
- bootstrap 在绑定既有冻结方案时，必须显式接收 `SourcePlanDoc + SourcePlanJson`，且不得自动新建 task 级 draft `plan.md`
- hydrate / validate 侧具备最小能力，能够检查 `plan.json` 与 `source_plan_doc` 等关键字段是否齐备
- `progress.session` 示例不再把旧式 `plan.json` 用法写成唯一入口，而是体现 `plan.md` 真源优先

进入执行窗口后的细化原则：

- 由 `Execute Window` 先阅读本方案、`schemas/plan.schema.json`、`templates/plan.example.json` 与相关脚本真源
- 再派阅读型子代理比对“当前 `plan` 合同/脚本行为”与“已冻结双件制规则”
- 最后按实际差异生成当前 batch 的 `work_order / dispatch_packet / dispatch_message_raw`

### Batch 3：提示词模板升级

当前状态：

- 待开始

阶段目标：

- 建立“由合同对象稳定编译出最终派发提示词”的提示词真源，减少执行窗口的临场拼接。

本阶段范围：

- `skills/global-task-orchestrator/assets/prompts/work-order-generator.md`
- `skills/global-task-orchestrator/assets/prompts/dispatch-packet-generator.md`
- `skills/global-task-orchestrator/assets/prompts/return-packet-writer.md`
- 新增执行型派发模板
- 新增审查型派发模板

本阶段不展开：

- schema 再次扩容
- 运行时代码逻辑变更
- 通用 prompt library 扩张

本阶段主要产出：

- `dispatch_message_raw` 的编译口径固定
- 执行型子代理提示词中明确 mandatory reads、禁改范围、验收标准、停止条件与回执要求
- 审查型子代理提示词中明确“结论 / findings / 依据 / 残余风险”的压缩输出要求
- Batch 3 可以在提示词正文层显式承载中文优先、mandatory reads 与回执正文所有权等执行提示，但此时只视为提示词承载，不视为合同/校验闸门已完成下沉

进入执行窗口后的细化原则：

- 由 `Execute Window` 先阅读本方案、当前 prompt 真源与当前合同样例
- 再派阅读型子代理定位现有提示词薄弱点
- 按“代码型 / 审查型 / 回执型”三个方向拆工单，不在方案阶段提前写死具体模板正文

### Batch 3.5：规则下沉到派发合同与验收闸门

当前状态：

- 进行中（本轮已完成脚本与验收闸门下沉；模板真源统一收口另行批次化整理）

阶段目标：

- 把已经冻结在治理文档、规则文档与 skill 真源中的关键规则，继续下沉到 `work_order / dispatch_packet / dispatch_message_raw / return_packet` 模板、脚本校验与验收闸门中，避免默认假定子代理已自行阅读全部真源文档。

本阶段范围：

- `skills/global-task-orchestrator/assets/prompts/work-order-generator.md`
- `skills/global-task-orchestrator/assets/prompts/dispatch-packet-generator.md`
- `skills/global-task-orchestrator/assets/prompts/return-packet-writer.md`
- `templates/work_order.example.json`
- `templates/dispatch_packet.example.json`
- `templates/return_packet.example.json`
- `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`
- 与派发 / 回收 / 验收直接相关的最小检查清单或脚本

本阶段不展开：

- 新增大批控制面对象
- 重新设计双窗口模式
- 扩大为通用 prompt library
- 与当前派发链无关的运行时重构

本阶段主要产出：

- 真源文档中的关键规则不再只停留在文档层，而能稳定编译进 `work_order / dispatch_packet / dispatch_message_raw`
- 子代理默认不再被假定“已阅读治理文档”；凡需对子代理生效的规则，都必须经由合同对象、派发提示词或脚本校验下发
- 主协调器派发时默认显式要求中文输出，且该要求由模板稳定生成，而不是临时补一句
- `return_packet` “必须由执行子代理本人填写正文、主协调器不得代写”的约束进入模板与验收闸门
- 对“缺 mandatory reads / 缺中文输出要求 / 缺回执正文所有权约束”的工单，具备最小拒收或阻断能力
- 本轮已新增 `control-plane-common.ps1` 与 `compile-dispatch-message.ps1`，并补强 `bootstrap-task.ps1 / ensure-work-order-fields.ps1 / validate-control-plane.ps1`，把三项关键规则下沉到脚本硬闸门
- Batch 3.5 承担上述规则的合同对象、模板字段与最小校验闸门下沉；Batch 3 只负责提示词正文承载与编译口径，不单独宣告这些规则已完成治理闭环

进入执行窗口后的细化原则：

- 由 `Execute Window` 先阅读本方案、当前治理真源、当前合同样例与当前提示词真源
- 再派阅读型子代理比对“文档规则”与“实际派发对象 / 校验闸门”之间的缺口
- 最后按“合同模板补强 / 提示词编译补强 / 校验闸门补强”三个方向拆工单，而不是让子代理默认巡航阅读全部文档

### Batch 4：校验脚本与测试升级

当前状态：

- 已完成

阶段目标：

- 为前面三个 batch 的规则升级补最小校验与回归测试，使双窗口与合同派发闸门可验证。

本阶段范围：

- 工单字段完整性校验
- `dispatch_packet` 复杂任务门槛校验
- `return_packet` 回收完整性校验
- 双窗口模式与合同派发回归测试

本阶段不展开：

- 新的业务能力开发
- 托管范围扩大到 `.system/*`、plugins 或第三方 skill
- 与本方案无关的 broader doctor 扩展

本阶段主要产出：

- 至少一组 happy path / bad path 测试覆盖关键闸门
- `bootstrap + validate + control-plane.integration.ps1` 已覆盖 `plan.status=frozen`、最低 `return_packet` 字段集合不可弱化、`dispatch_message_raw` 合同编译一致性等关键闸门
- 执行窗口可据此判断某个工单是否可派发、某个回执是否可收口
- 规则、模板、提示词与验证口径形成闭环

进入执行窗口后的细化原则：

- 由 `Execute Window` 先阅读本方案与现有测试/脚本真源
- 再派阅读型子代理盘点当前校验缺口与测试入口
- 基于真实缺口拆单，不在方案阶段提前硬编码测试实现细节

## 验收口径

本方案后续落地完成的最低标准是：

1. `plan` 的主窗口所有权已固化，且文档、skill 与模板口径一致。
2. 复杂任务的执行型工单无法绕过 `dispatch_packet` 或等价逐文件施工图。
3. `dispatch_message_raw` 已不再依赖自由发挥，而由合同对象稳定生成。
4. `return_packet` 已能表达未改项、偏离项、验证命令与阻塞原因。
5. 至少有一组 happy path / bad path 测试覆盖双窗口与合同派发核心闸门。
6. `bootstrap` 与 `validate` 已把 `plan.status=frozen`、`required_return_fields` 最低集合兜底、`dispatch_message_raw` 合同一致性做成可执行硬闸门。

## 非目标

- 本批次不直接改动现有项目仓库 run 留痕
- 本批次不直接扩大到 `.system/*`、plugins 或第三方 skill 托管
- 本批次不重新设计 Claude hooks
- 本批次不把任意提示词工程扩大为通用 LLM prompt library

## 停止条件

出现以下任一情况时，不允许进入正式实施：

- 双窗口所有权规则尚未冻结
- `plan` 与执行阶段边界仍不清晰
- schema、模板、skill、规则之间存在明显冲突
- 需要扩大到未冻结范围才能继续

## 方案入口

本方案作为后续实施真源入口使用。后续若发生字段调整、批次顺序变化或验收口径变化，必须优先回写本文，再进入实施。
