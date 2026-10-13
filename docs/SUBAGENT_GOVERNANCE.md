# SUBAGENT GOVERNANCE

## 目标

本文定义新控制面下主协调器、执行型子代理、审查型子代理的统一治理口径。
当前 GTO 使用六份工件和 state version=3。当前工具只接受 workflow_revision=3；历史状态保留，继续旧任务须使用当时固定的工具包，不自动升级。

## 适用范围

GTO 启动条件唯一遵循 [全局入口模板](../templates/codex/AGENTS.global.md)。本文的 GTO 阶段、角色和工件要求仅适用于用户已选择 GTO 的任务，不作为普通 Git 提交、推送、代码改造或日常运维的自动启动条件。

- 全局真源：`ai-harness/`
- 运行时投放：Codex skills、managed `AGENTS.md`、规则索引与 doctor 流程
- 项目适配层：各项目 `AGENTS.md`、`docs/ai/`、`config/ai/`

项目规则系统兼容说明：

- 本文是跨项目复用的全局治理真源，不替代项目仓库自己的 rules system。
- 项目级规则应由各仓库在 `rules/registry/*` 与 `rules/items/<kind>/*` 中维护，并由项目入口文档引用。
- 历史上的旧控制面对象仅可作为迁移背景，不再是运行时合同来源。

## 角色分工

计划代理分配与职责分开表达，同代号复用、异代号区分，按批准依赖派发；测试与验收是否复用由方案决定，并满足已有独立性约束。唯一行为说明见 [批准分工与依赖](../skills/global-task-orchestrator/references/workflow.md#批准分工与依赖)。结果在派发时提供对应完整模板，正式提交前使用 [只读预检](../skills/global-task-orchestrator/references/state-schema.md#计划代理与只读结果预检)，结构通过不替代证据判断。

- Plan 与 Execute：职责、控制工件前置条件和流程图统一见下文“双窗口模式”引用的 GTO 真源；控制器只机械维护 `state.json`、`events.jsonl` 与确定性状态推进。
- 阅读型子代理：先读取 `task.md` 导航指向的批准合同，再按主协调器真实派遣 prompt 中显式给出的 `assignment`、`read_paths`、`write_paths` 与验收要求补充上下文并产出证据化摘要。
- 执行型子代理：先读取 `task.md` 导航指向的批准合同，再按真实派遣 prompt 中显式给出的 `assignment`、`read_paths`、`write_paths` 与验收要求修改授权文件，并把结果交回控制器写入 `state.json.subtasks[].result`。
- 审查型子代理：基于控制器真实实现的 `build-review-brief` 结果做多维度审查与验收，不读取无关子任务，也不代替执行型子代理直接补做实现。

## 双窗口模式

任务呈现与交接见 [方案指南](../skills/global-task-orchestrator/references/plan-guide.md)；通用施工图和 Plan/Execute 职责见 [任务流程与职责](../skills/global-task-orchestrator/references/workflow.md)。本页引用该入口，不另写一套窗口职责或流程图。

## 批次与路由规则

Plan 完整要求清单见 [方案指南](../skills/global-task-orchestrator/references/plan-guide.md)；通用流程、六工件前置、测试负责人复用及两条普通返工回路见 [GTO 任务流程与职责](../skills/global-task-orchestrator/references/workflow.md)；黑盒选层与执行唯一见 [分层黑盒测试方法论](../skills/global-task-orchestrator/references/blackbox-methodology.md)。本文不重复维护流程正文；目标规范不等于同候选代码、安装或验收已经通过。

## 等待与收口规则

- 主协调器必须在线等待子代理自然完成，不能因为耗时而提前收口、跳过、催关闭。
- 仅仅因为执行时间长、回报慢或暂未收口，不得向子代理催促、强制收尾、打断或改派。
- 只有出现以下阻塞时，才允许结束当前子代理轮次并回到主协调器：
  - 明确死循环
  - 多轮重复无进展
  - 缺少必须的权限或外部环境
  - 冻结方案失效，继续执行会扩大范围
- 出现阻塞时，必须把具体阻塞点、已尝试动作与下一步建议写入对应 `subtask.result`，不能笼统写“未完成”。
- 主协调器等待自然完成并回收真实结果；容量以派发时平台运行状态及实际返回为准，不根据等待或完成状态猜测线程占用。

## 候选、昂贵验收与证据失效

以下是 revision 3 的规范合同；机械实施状态须另以同候选 schema、控制器测试及新进程真实行为证明，不能由文档表述推定门禁已经实现。当前包不兼容 revision 2 或未声明 workflow_revision 的合同。

阶段顺序、发现者与原整合者分工及两条普通返工回路见 [任务流程](../skills/global-task-orchestrator/references/workflow.md)；黑盒停止出口见 [分层黑盒测试方法论](../skills/global-task-orchestrator/references/blackbox-methodology.md)。以下只定义证据真实性与失效边界。

- review 和验收分别留下实际使用证据，不能共用一次操作冒充两个阶段。Windows 原生 Agent 使用官方 Browser 操作网页，包括运行在 WSL 服务上的页面；Windows GUI 仅在 Windows-native Agent environment 使用 Computer Use，WSL 不得先试调。非 UI 任务使用真实 CLI/API 并明确 UI 不适用原因。证据包含执行者、工具、实际入口/命令、操作范围、结果及引用，截图、HTTP 200 或工具名称本身不等于业务路径通过。
- 候选包含代码、配置、运行输入、验收项和全部受影响正式文档，发现者新增测试也在范围内。验收前变化需对应审查覆盖；验收中修复变化由原验收者承担 delta 检查。验收后纯文档遗漏同步只在无实质行为/契约变化时收口，不能成为任意文档豁免名单。
- 预算与 attempt kind 的机械限制见包内 schema、控制器及 [状态使用说明](../skills/global-task-orchestrator/references/state-schema.md)。准备检查与正式效果分流，资源消耗不因换 ID 清零；证据映射只覆盖各自验收范围，未覆盖不得推断通过。

## 进入下一步的闸门

- 进入下一步前，所有本批次相关子代理都必须：
  - 自然完成
  - 结果被回收到 `state.json`
  - 满足该节点的阶段出口：例如初始测试提供有效 Red，实施完成 Green 与相关回归
- 相关依赖节点未达到其合同出口时不得推进；不把初始测试的有效 Red 误当作验收失败。

## 统一控制面对象合同

### 长任务六份工件

- `docs/ai/tasks/<task_id>/state.json`：唯一真源。
- `docs/ai/tasks/<task_id>/task.md`：人读摘要。
- `docs/ai/tasks/<task_id>/events.jsonl`：append-only 关键事件流。
- `docs/tasks/<task_id>/plan.md`：冻结目标、范围、非目标、方案、风险和验收标准。
- `docs/tasks/<task_id>/execution.md`：冻结施工顺序、批次、写入范围、验证命令和返工路由。
- `docs/tasks/<task_id>/acceptance.md`：回填验收证据、未决项和最终结论。

约束：

- 新流程不得再依赖任何历史旧控制面对象、旧会话目录或旧派发消息载体。
- 旧对象名不得作为新的字段别名继续存在于正式合同中。
- 若需要记录执行合同，必须写入 `state.json.subtasks[].assignment`。
- 若需要记录执行结果，必须写入 `state.json.subtasks[].result`。
- `events.jsonl` 只追加事件，不承担当前状态真源职责。
- 六份工件在长任务中全部必备，不按窗口数或并行度缩减。控制器应交叉校验 `task_id`、施工摘要对应的机器合同、验收标准和批准状态；合同变更后旧批准自动失效。
- 当前 state 只接受 `version=3`；CLI 只接受 `orchestrator_ctl.py --help` 当前公开并实际实现的 action 与 GNU 双横线参数。
- 机器侧控制器解析完整 state 以执行机械校验和状态推进；它只为审查场景实现 `build-review-brief`。普通委派 prompt 由主协调器显式组织。
- state 只保留流程判断所需的短摘要、仓库相对路径、哈希、commit range、命令名与结论；不得保存完整 stdout、完整 diff、完整 prompt 或聊天记录。
- 不生成独立 implementer report、test report、review package 或其他承担当前状态职责的 package；已有正式证据保持在原位置，state 只记录路径、哈希与短摘要。

## 真实隔离派发与身份

- 无历史派发必须由平台实际调用参数实现，例如平台支持时使用 `fork_turns="none"`；提示词只能描述边界，不能冒充隔离机制。
- 主协调器先在真实派遣 prompt 中明确 `task.md` 及其合同入口、`assignment`、`read_paths`、`write_paths` 与验收要求，再由平台以无历史模式派发；控制器通过 `bind-dispatch` 把平台返回值绑定到 `subtask.dispatch`。绑定记录至少包含 `agent_key`、真实 `platform_agent_id`、`context_mode=isolated`、`brief_kind` 与 `brief_sha256`。
- `platform_agent_id` 只能取自派发工具返回值，不接受子代理自报身份作为证明。高风险审查与最终审查的 reviewer 必须与被审实现者使用不同的真实 `platform_agent_id`。
- 子代理只能按真实派遣 prompt 中的当前合同工作。若平台不支持真实无历史派发，当前派发必须阻塞并升级给主协调器，不能降级为提示词隔离。
- 默认已安装 GTO 的入口与最小治理载荷必须携带上述平台派发要求，不能依赖子代理偶然读取本完整文档。`context_mode=isolated` 只是待核对的声明，不能代替真实工具参数与平台返回身份；验收必须交叉比对可观察派发记录。`fork_turns="all"`、省略参数后继承历史、或仅在提示词宣称隔离，均不得绑定为无历史派发。
- 每次派发前核对运行子代理数，派发后不得超过 3。新职责使用不同的新代理；只按流程明确要求复用原作者、原整合者、原 reviewer、原验收者或测试负责人。不得把所有新职责都交给少数既有代理。实际创建失败时保留回执，不伪造身份或由父协调器替代独立审查、验收。

## Workspace 基线

- 进入写入阶段前，控制器只读检查并记录当前 workspace 是 primary checkout 还是 linked worktree，以及 branch、`HEAD`、dirty paths、计划 write paths 与既有 dirty paths 的 overlap。
- state 中只保存 `<repo-root>` 和仓库相对路径等逻辑位置，不保存盘符、用户名或本机绝对仓库根。
- write overlap 未归属或未裁决时不得进入 `code_impl`。裁决只记录采用的基线与边界，不授权覆盖、清理或还原用户改动。
- workspace 动作只检查、捕获和校验；控制器和子代理不得自动创建、切换、移动、删除或清理 worktree，也不得扫描或同步其他 clone。

### `task_state`

- 回答：任务改什么、为什么改、边界是什么、当前处于哪个阶段、有哪些 `subtask`。
- 状态字段值域以包内 schema 为准。schema 容许 draft 不表示公开 CLI 支持运行或激活 draft；新 init 在合同通过后创建 active 状态，不额外建立草稿激活入口。
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
- 结果字段与合法载荷统一见 [包内状态说明](../skills/global-task-orchestrator/references/state-schema.md) 及其引用的 schema，不在本页维护第二份字段列表。
- `written_by` 与 `written_role` 是必填身份字段；当前 `written_role` 与绑定的 `dispatch.agent_key` 对齐；`subtask.role` 表示职责，`assignment` 没有 `role`。`written_by` 对齐工具返回的 `platform_agent_id`。字段允许值以同候选 schema 为准，不手填重复身份。
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
- `read_paths` 是关键入口，允许沿调用链继续阅读；仍有合同冲突或需要越界时回报主协调器，不自行脑补。

## 统一落盘口径

- `docs/ai/tasks/<task_id>/state.json`
- `docs/ai/tasks/<task_id>/task.md`
- `docs/ai/tasks/<task_id>/events.jsonl`（必备）
- `docs/tasks/<task_id>/plan.md`
- `docs/tasks/<task_id>/execution.md`
- `docs/tasks/<task_id>/acceptance.md`

项目侧可以补充本仓目录、模块与运维口径，但不再承担上述对象的通用合同正文，也不为当前 GTO 新建第二套状态或历史 run 路由。

## 全局协作原则

语言、唯一真源和变更约束统一见 [全局入口模板](../templates/codex/AGENTS.global.md) 及规则索引指向的叶子条款；本文只维护子代理职责与证据边界。

## 验收与返工规则

按 [通用回路](../skills/global-task-orchestrator/references/workflow.md#回路与阶段出口) 判断普通问题来源；黑盒另按 [分层方法论](../skills/global-task-orchestrator/references/blackbox-methodology.md) 选层、准备、停止和分类。实际身份、稳定 finding、预算、候选和证据关联由同候选 schema/控制器校验，不能换人或换 ID 清零。历史任务记录保留，当前包不迁移旧合同。

## 最终整体审查门禁

- revision 3 的完整独立审查在整合和全部正式文档完成之后、真实验收之前。完整审查与后续范围复审共同覆盖最新候选，不要求验收后 final/pass。
- 通过真实验收后由一个文档子代理直接排查并同步正式文档遗漏与六工件事实；纯文字纠正可直接收口，不限于空白或排版，不增加双人文档 review。真正行为或契约变化返回验收链，并保留同步范围与判断依据。

## 审查触发规则

- 默认不采用“每个子代理动作都再派一个审查子代理”的模式。
- 阅读型子代理的回报，默认由当前窗口主协调器直接审阅。
- revision 3 在实现与整合完成并同步正式文档后集中完整审查，修复后做范围复审；不对每个执行动作重复派审查。
- 纯阅读、纯盘点、纯证据收集结果，不默认再开独立审查子代理。
- 以下场景在整合后集中触发审查型子代理；revision 3 验收修复直接走同验收者复验，验收后的单文档子代理纯文字同步不重复触发审查：
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
- 发现者必须实际补回归测试或可执行证明并记录命令、范围、退出结果与证据；无法执行时明确阻塞，不能只输出测试建议。

## 测试规则

- 执行型子代理每一轮迭代都必须补齐并运行本轮要求的测试；初始实现轮次也不例外。
- 执行型子代理提交结果时，必须说明：
  - 新增或修改了哪些测试文件 / 测试名
  - 实际运行了哪些测试命令
  - 测试结果
- 测试必须优先验证外部行为、合同、稳定 issue/type、产物结构与可观察结果。

## 文档与代码同步规则

- 只要规则、合同、模板或行为口径发生变化，文档必须先于代码更新。
- 主协调器先组织需求、接口和测试合同；实现与整合者在独立完整 review 前同步全部受影响正式文档。验收通过后一个文档子代理直接查漏同步，纯文字纠正不触发复验，真正行为或契约变化返回验收链；历史任务文档保持只读。
- 若文档、测试、代码存在同一批次中的强同步关系，必须在同一批次内连续收口，不能交叉漂移。
- 项目侧入口文档只保留引用、项目级 rules system 与项目增量规则；全局原则见 templates/codex/AGENTS.global.md，流程见 [GTO 任务流程](../skills/global-task-orchestrator/references/workflow.md)；本文只维护协作职责与证据边界。

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

Plan 完整要求清单见 [方案指南](../skills/global-task-orchestrator/references/plan-guide.md)；通用流程、六工件前置、测试负责人复用及两条普通返工回路见 [GTO 任务流程与职责](../skills/global-task-orchestrator/references/workflow.md)；黑盒选层与执行唯一见 [分层黑盒测试方法论](../skills/global-task-orchestrator/references/blackbox-methodology.md)。本文不重复维护流程正文；目标规范不等于同候选代码、安装或验收已经通过。

## 推荐模板

- 审查输出模板：`templates/review_report.example.md`
- 审查测试用例模板：`templates/review_testcases.example.md`
- 执行迭代清单：`templates/code_worker_iteration_checklist.example.md`

## 角色选择与派发

- 主协调器先根据已冻结的 subtask 合同选择阅读、实施、测试、文档或审查职责，再使用平台实际可用的代理能力派发。
- 角色语义、读写边界、允许的 shell 操作和验收要求由主协调器从冻结合同提取，并在平台真实派遣 prompt 中显式给出；普通委派不依赖独立 agents catalog 或角色映射兼容层。
- 平台不支持合同要求的隔离、权限或独立 reviewer 身份时，当前派发必须阻塞并交回主协调器裁决。

## 黑盒验收、归因和清理

层级选择、准备修复、场景停止、结果分类、Memory/CFM 报告和高成本批准，唯一见 [分层黑盒测试方法论](../skills/global-task-orchestrator/references/blackbox-methodology.md)。本节只补充 GTO 多代理治理所需的证据与清理边界。

- 评估者与被测者职责分离；评分材料留在验收侧，不投放业务目录。正常全局 AGENTS、已安装 skill 和项目入口属于真实使用环境。显式执行效果与隐式发现能力分开判定，本次合同要求显式调用时不能改成隐式触发测试。
- 核对实际 CODEX_HOME、安装来源、候选与 receipt、会话真实加载、真实身份、公开调用参数与可观察父子轨迹。工具返回、文件修改、真实退出码和产物是证据；自报完成或状态字段不能替代实际行为，也不读取私有推理补证据。
- 环境按机器工具、项目依赖、浏览器运行时、Windows/外部能力分层，复用当前入口。Windows 官方 Browser/Computer Use 与 WSL CLI 证据按实际调用分开报告；不引入通用安装器、daemon 或反复全量 doctor。
- 分别报告准备状态、效果、业务结果和覆盖缺口；未触发、未运行、失败和通过不得混同。隔离 CLI/自动测试证明确定性边界，真实顶层 skill 使用证明效果，不能互相替代。
- 保留原始输入、候选与版本、真实会话 ID、轨迹、诊断、命令结果、验收映射和清理结果；没有证据的根因标为假设，凭据不得进入证据。
- 仅停止和清理本轮自有且获准的进程、工作副本、隔离 runtime、缓存和服务数据。失败先留必要证据；不动主工作区、其他任务、真实 CFM 数据或活动 worktree。获准后续效果轮次从冻结夹具开始，保留旧失败，不能改写历史为通过。

## 实施完成与候选职责覆盖

revision 3 的整合必须等全部声明 work 子任务 completed；显式 dependency 没写全不能放行，完成整合结果和后续审查、冻结、验收、finalize 同样检查此条件。所有职责的可执行回归测试和其他实质写入都纳入 candidate_inputs，包含 reviewer 和验收发现者。六工件仍通过控制器维护事实；仅 `.tmp/`、`.artifacts/` 下明确 `.log` 文件可作为非候选日志，不豁免目录、测试文件或执行输入。需要将日志用于实际执行时，显式声明为 runtime_input_paths。

初始测试依据需求与可观察行为独立设计；整合子代理不得提前介入影响测试。独立测试和全部实现 TDD 完成之后才开展整合工作。验收通过后的单文档子代理可直接进行纯文字纠正与遗漏同步，不限于空白或排版；只有真正行为、契约或配置变化才返回验收链。新增接口字段须在独立行为测试及实现后与 schema、示例统一核对，不能将提前设计的字段当作测试答案。

## 发现者文档与测试责任的返工边界

- review/验收发现者负责失败测试、根因、方案及正式文档同步；若判定文档不适用，应说明既有契约足够的理由，不能在不适用说明中把可选文案补充转交代码返工者。需要补充时仍由发现者先同步。
- 原整合者的初次整合写域可以包含正式文档和整合测试，但不能自动成为finding返工的写权限。finding返工只按问题合同修复产品代码/运行配置并运行已冻结的发现者测试；不得借历史宽write_paths修改发现者测试或正式文档。若测试本身有误或需要新增说明，交回发现者处理。
- 路径与角色按语义判断：skills、references、rules中的运行时Markdown可能就是产品源码，不能按.md后缀一刀切禁止。采用候选document_paths、正式文档/测试位置及finding约定识别受保护工件；被测业务中的tests目录不能仅因纳入代码指纹就变为返工者可改的发现者测试。
- 文档回执written_by表示承担该同步责任的发现者，复审别人写的说明不能冒充亲自完成正文更新。可如实保留not_applicable并说明复核，不得用回执改作者来掩盖阶段责任转移。

## 并发任务、固定运行版本与能力证明

当前操作合同见 [GTO 运行与证据](../skills/global-task-orchestrator/references/runtime-evidence.md)。普通流程职责维护于全局 AGENTS 模板；技能开关唯一声明在 `config/ai/skill-policy.json`，由 `scripts/configure-skill-policy.py` 更新实际 path 配置，插件升级后重新检查路径并用新会话验明。方法技能不能接管流程。磁盘配置、CLI 快照验证和真实新会话加载分别报告。
