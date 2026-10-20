# CODEX FIXED SUBAGENT DELEGATION PLAN

## 冻结元数据

- `task_id`: `codex-fixed-subagent-delegation-20260407-145034-kewd`
- `plan_id`: `PLAN-CODEX-FIXED-SUBAGENT-DELEGATION-20260407-145034-KEWD`
- `status`: `frozen`
- `source_plan_doc`: `docs/plans/codex-fixed-subagent-delegation.md`
## 背景与问题

当前仓库已经沉淀了 `ai-harness/agents/*.md` 这一层角色真源，但在 Codex 侧的实际委派仍偏向直接使用 `explorer`。这会带来三个问题：

- 任务语义和子代理底层类型耦合，阅读、审查、实现、验证经常混用。
- 每次委派都要临时拼 prompt，角色约束、停止条件和交接格式不稳定。
- `agents/` 目录中的角色定义没有被纳入 Codex 的正式调度闭环，无法形成稳定的任务合同与回收口径。

本方案的目标不是扩展 Codex 平台原生子代理类型，而是在固定底层类型 `default / explorer / worker` 之上建立一层仓库自定义的角色编排体系，使主协调器以后按“角色”而不是按“裸 agent_type”委派任务。

## 输入真源

- `docs/AGENTS.md`
- `docs/CODEX_COMPAT.md`
- `docs/SUBAGENT_GOVERNANCE.md`
- `agents/README.md`
- `agents/manifest.json`
- `skills/global-task-orchestrator/SKILL.md`
- `skills/global-task-orchestrator/references/agent-selection-matrix.md`
- `skills/global-task-orchestrator/references/dynamic-routing-rules.md`

## 目标

- 冻结一套“固定类型子代理 + 自定义角色层”的 Codex 委派方案。
- 明确 `agents/*.md`、角色映射、委派合同、回收验收之间的关系。
- 规定按阶段推进的实施顺序，避免在未冻结治理规则前直接改 orchestrator 和脚本。
- 让后续任务委派默认面向 `planner / reader / reviewer / backend-implementer / frontend-implementer / test-verifier / doc-curator / ops-runbook` 等角色，而不是直接面向 `explorer`。

## 非目标

- 不试图新增 Codex 平台原生子代理类型。
- 不假设 Codex 会自动扫描 `ai-harness/agents/` 并把其中每个角色注册为平台级 agent。
- 不在本批直接实现全量运行时代码、同步脚本、doctor 扩展或 project adapter 改造。
- 不引入新的未冻结控制面对象，仍沿用现有 `plan / work_order / dispatch_packet / return_packet`。

## 冻结结论

### 1. 底层类型固定，上层角色自定义

Codex 侧底层执行形态继续固定为：

- `default`
- `explorer`
- `worker`

仓库自定义角色作为独立一层存在，不与底层类型混写。每次委派先选“角色”，再由编排层把角色映射到一个底层 `agent_type`。

### 2. `agents/*.md` 是角色真源，不是原生 agent_type 注册表

`ai-harness/agents/*.md` 继续承担以下职责：

- 定义角色目标、职责边界、禁止事项、输入输出、停止条件、交接规则。
- 作为 Claude 侧 `~/.claude/agents/` 的长期真源。
- 作为 Codex 侧角色约束的语义真源。

它不直接决定 Codex 的底层 `agent_type`，也不承担平台注册功能。

### 3. 引入 `codex-role-map` 作为桥接层

新增一个仓库级角色映射文件，建议路径：

- `ai-harness/agents/codex-role-map.json`

该文件的职责是：

- 把业务角色映射到 `default / explorer / worker`。
- 为每个角色声明推荐 `model`、`reasoning_effort`、是否允许写入、是否允许 shell。
- 为主协调器提供统一的委派入口，避免每次人工判断和手写 prompt。

### 4. 子代理委派必须合同化

所有子代理委派都必须显式落到现有控制面对象：

- `plan`
- `work_order`
- `dispatch_packet`
- `return_packet`

不允许主协调器直接把自然语言需求原样扔给子代理后等待自由发挥。

### 5. 角色与底层类型的初始映射冻结如下

建议首批冻结以下映射：

| 角色 | 底层类型 | 用途 |
| --- | --- | --- |
| `planner` | `default` | 方案冻结、边界收敛、批次拆分 |
| `reader` | `explorer` | 定向阅读、证据收集、局部上下文补齐 |
| `reviewer` | `default` | 风险审查、回归审查、验收裁决 |
| `backend-implementer` | `worker` | 后端逻辑、脚本、服务端实现 |
| `frontend-implementer` | `worker` | 前端页面、样式、交互实现 |
| `test-verifier` | `worker` | 测试设计、补测、验证执行 |
| `doc-curator` | `worker` | 文档落盘、规范收敛、入口同步 |
| `ops-runbook` | `worker` | 运维手册、排障说明、运行验证 |

### 6. 委派消息必须由“角色真源 + 任务合同”编译生成

后续不再依赖临时手写 prompt。每次子代理首条消息都应由以下输入编译得到：

- `agents/<role>.md`
- `work_order`
- `dispatch_packet`
- 当前批次的 `read_paths_mandatory`
- 验收要求与返回字段

主协调器不再直接说“派个 explorer 看看”，而应明确说“派一个 `reader` 角色，由 `explorer` 底层承载”。

### 7. 回收结果只认结构化结果

主窗口不接收子代理长篇过程全文，只接收：

- 阅读型回报：`summary`、`relevant_code_paths`、`relevant_doc_paths`、`key_findings_with_evidence`、`unknowns`、`recommended_next_step`
- 执行型回报：`return_packet`
- 审查型回报：通过/不通过结论、findings、关键依据、残余风险

没有结构化结果，不视为完成。

## 目标架构

### A. 四层结构

1. 平台层  
固定底层子代理类型：`default / explorer / worker`

2. 角色层  
仓库角色真源：`ai-harness/agents/*.md`

3. 调度层  
角色映射、任务分类、委派消息编译、运行参数选择

4. 合同层  
`plan / work_order / dispatch_packet / return_packet`

### B. 数据流

```text
用户任务
-> 主协调器判断任务类型
-> 选择业务角色
-> 读取 codex-role-map
-> 生成 work_order / dispatch_packet
-> 编译 dispatch_message_raw
-> spawn_agent(agent_type=default|explorer|worker)
-> 子代理执行
-> 输出 return_packet 或结构化阅读/审查结果
-> 主协调器验收并推进下一阶段
```

## 任务分类与路由规则

### 阅读类

适用场景：

- 需求不明，需要补上下文
- 需要找调用链、证据路径、相关文档
- 需要回答具体 codebase question

路由：

- 角色：`reader`
- 底层类型：`explorer`

强约束：

- 只读，不改文件
- 必须给证据路径
- 结论不能脱离原文件阅读

### 规划类

适用场景：

- 目标和边界未冻结
- 需要分阶段方案
- 需要批次拆分、定义验收和停止条件

路由：

- 角色：`planner`
- 底层类型：`default`

强约束：

- 只冻结方案，不直接实施
- 明确范围、非目标、验收、停止条件

### 审查类

适用场景：

- 需要 review 代码或文档改动
- 需要判断是否满足验收
- 需要识别 bug、回归和测试缺口

路由：

- 角色：`reviewer`
- 底层类型：`default`

强约束：

- 以 findings 为主
- 默认不直接修复
- 必须按证据输出结论

### 实施类

适用场景：

- 需要改代码、文档、测试、运行说明

路由：

- `backend-implementer -> worker`
- `frontend-implementer -> worker`
- `doc-curator -> worker`
- `test-verifier -> worker`
- `ops-runbook -> worker`

强约束：

- 必须限定写入范围
- 必须先读 `read_paths_mandatory`
- 必须写 `return_packet`

## 委派合同冻结

### `work_order` 最小字段

执行型委派至少必须包含：

- `role`
- `objective`
- `read_paths_mandatory`
- `read_paths_optional`
- `evidence_summary`
- `write_scope`
- `constraints`
- `required_return_fields`
- `return_packet_path`
- `return_packet_required=true`
- `completion_gate=return_packet_written_and_accepted`
- `state_owner=main-coordinator`

### `dispatch_packet` 触发条件

满足以下任一情况必须补 `dispatch_packet`：

- 跨模块任务
- 写入文件超过 3 个
- 涉及状态机、契约或数据结构改造
- 单个 `work_order` 无法表达逐文件改法和先后顺序

### `return_packet` 最小字段

最小回收口径至少包含：

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

## 角色文件规范增补

现有 `agents/*.md` 已具备角色说明，但为支撑 Codex 委派，应统一补齐或校验以下结构：

1. `角色目标`
2. `负责范围`
3. `不负责`
4. `输入`
5. `输出`
6. `工作规则`
7. `停止条件`
8. `协作交接`

必要时允许在正文补充以下 Codex 相关语义，但不把这类控制字段硬塞进 frontmatter：

- 推荐底层类型
- 默认输出字段
- 是否允许写入
- 是否要求 shell
- 默认验收方式

## 委派消息编译规则

建议新增一个“委派消息编译器”，职责是把角色真源和任务合同编译成首条子代理消息。其输出至少要包含：

- 你当前扮演的角色
- 本次目标
- 必读路径
- 可选阅读路径
- 允许写入范围
- 禁止事项
- 完成前必须返回的字段
- 若信息不足时的回退要求

编译器职责只负责把合同翻译成稳定 prompt，不擅自增删工作边界。

## 失败与回退规则

出现以下情况必须中止当前委派并回退：

- `reader` 越权修改文件
- 执行型子代理未写 `return_packet`
- 输出缺关键字段
- 结论缺证据路径
- 子代理试图扩大用户未确认范围
- 多个执行型子代理写入同一责任边界
- `plan.md / plan.json` 语义冲突

回退方向：

- 上下文不足 -> 回退 `reader`
- 方案不清 -> 回退 `planner`
- 结果存在风险 -> 交给 `reviewer`
- 验证不充分 -> 交给 `test-verifier`

## 质量门禁

### 合同门禁

没有以下字段不得派发执行型子代理：

- `objective`
- `read_paths_mandatory`
- `write_scope`
- `required_return_fields`
- `return_packet_path`

### 角色门禁

必须确认本次任务和所选角色一致：

- 阅读任务不派 `worker`
- 实现任务不派 `explorer`
- 审查任务不与实现任务混单

### 回收门禁

以下任一条件不满足都不能标记完成：

- 结构化结果齐全
- 证据路径齐全
- 验证动作已说明
- 风险和偏差已记录

## 分阶段实施顺序

正式实施顺序遵循“先方案、再文档、再测试、最后代码”的统一规则。本方案冻结的推荐阶段如下。

### 阶段 0：方案冻结与文档落盘

目标：

- 冻结本方案本身
- 明确术语、边界、非目标、阶段顺序

范围：

- `docs/plans/codex-fixed-subagent-delegation.md`
- 对应结构化 `plan.json`

产物：

- 语义真源 Markdown
- 结构化投影 JSON

验收：

- 角色层、映射层、合同层边界写清
- 实施顺序固定成阶段

### 阶段 1：角色层规范化

目标：

- 把现有 `agents/*.md` 统一整理成可被 Codex 编排层稳定消费的角色真源

范围：

- `agents/README.md`
- `agents/_schema.example.md`
- 首批角色文件

动作：

- 补齐统一章节结构
- 明确每个角色的输入输出和停机条件
- 为后续 `reviewer`、`reader` 增补或冻结角色定义

验收：

- 角色文件结构统一
- 不再混淆“角色定义”和“底层 agent_type”

### 阶段 2：角色映射层冻结

目标：

- 引入 `codex-role-map.json`
- 冻结角色到底层类型的映射、推荐模型和运行约束

范围：

- `agents/codex-role-map.json`
- 相关说明文档

动作：

- 为首批角色写入底层 `agent_type`
- 声明推荐 `model / reasoning_effort / allow_write / allow_shell`

验收：

- 所有首批角色都能稳定落到固定底层类型
- 主协调器不再依赖人工脑补选型

### 阶段 3：合同与模板升级

目标：

- 让 `work_order / dispatch_packet / return_packet` 能显式承载角色委派

范围：

- `templates/work_order.example.json`
- `templates/dispatch_packet.example.json`
- `templates/return_packet.example.json`
- `schemas/*.json`

动作：

- 补 `role`、`write_scope`、`required_return_fields` 等字段口径
- 冻结阅读型、审查型、执行型的最小回收字段

验收：

- 合同字段能表达角色委派
- 不改编排代码也能手动按新合同下发

### 阶段 4：委派消息编译器落地

目标：

- 把“角色真源 + 合同”编译成稳定的子代理首条消息

范围：

- `skills/global-task-orchestrator/scripts/compile-dispatch-message.ps1`
- 相关 prompt 模板

动作：

- 为不同角色生成固定模板
- 把角色约束、必读路径、写入范围、返回字段统一编译进 dispatch message

验收：

- 不再手写大段委派 prompt
- 同一角色在不同任务上的输出口径稳定

### 阶段 5：orchestrator 路由升级

目标：

- 让主协调器按“角色”而不是按“裸 explorer/worker/default”工作

范围：

- `skills/global-task-orchestrator/SKILL.md`
- `skills/global-task-orchestrator/references/*`
- 必要的控制脚本

动作：

- 在 Plan Window 默认路由 `reader`
- 在 Execute Window 按任务类型选择 `reviewer / doc-curator / test-verifier / implementer`
- 增加显式的角色选择矩阵与失败回退矩阵

验收：

- 阅读、审查、实现、验证有稳定入口
- 不再出现“一律派 explorer”作为默认行为

### 阶段 6：验证与治理收口

目标：

- 对新方案做合同校验、行为校验和文档校验

范围：

- `tests/harness/*`
- `docs/SUBAGENT_GOVERNANCE.md`
- `docs/CODEX_COMPAT.md`

动作：

- 增加角色映射有效性校验
- 增加 dispatch message 编译一致性校验
- 增加回收字段和质量门禁校验

验收：

- 角色映射变更可验证
- 合同缺字段时能阻断派发

### 阶段 7：项目适配与渐进启用

目标：

- 让仓库内外项目逐步从“裸 agent_type 委派”迁移到“角色委派”

范围：

- `AGENTS.md`
- 项目侧 `docs/ai/`
- 项目侧 `config/ai/`

动作：

- 在入口文档中补角色委派说明
- 仅同步项目侧增量边界，不复制全局治理正文
- 先在少数高价值流程中启用：阅读、审查、代码实现

验收：

- 新任务优先走角色委派
- 历史任务可渐进迁移，不要求一次性切换

## 推荐首批落地范围

为了降低风险，首批只建议启用 5 个角色：

- `planner`
- `reader`
- `reviewer`
- `backend-implementer`
- `test-verifier`

原因：

- 已覆盖方案、阅读、审查、实现、验证五条主链路。
- 能解决“默认派 explorer”的核心问题。
- 能在不一次性重构全部文档和脚本的前提下形成最小闭环。

## 风险

- 若角色定义和底层映射同时修改，容易出现责任漂移。
- 若未先升级合同模板，orchestrator 虽然能派角色，但回收口径仍会不稳定。
- 若过早并行启用过多角色，容易在写入范围和责任边界上冲突。
- 若项目侧文档未同步入口说明，团队成员仍可能继续按裸 `explorer` 心智使用子代理。

## 停止条件

出现以下任一情况时，应停止进入下一阶段并回到方案修订：

- 发现现有控制面 schema 无法承载角色委派的最小字段
- 发现某些角色职责本质冲突，无法稳定映射到一个底层类型
- 发现 `global-task-orchestrator` 现有规则与新角色编排不可兼容
- 需要引入新的平台级原生 agent_type 才能继续推进

## 阶段总览

1. 阶段 0：方案冻结与文档落盘
2. 阶段 1：角色层规范化
3. 阶段 2：角色映射层冻结
4. 阶段 3：合同与模板升级
5. 阶段 4：委派消息编译器落地
6. 阶段 5：orchestrator 路由升级
7. 阶段 6：验证与治理收口
8. 阶段 7：项目适配与渐进启用

## 当前冻结结论

- 本方案已冻结“固定底层类型 + 自定义角色层 + 合同化委派 + 分阶段实施”的总体路线。
- 首批推荐先做文档和合同，再做模板和编排，再做验证和项目适配。
- 后续如进入正式实施，应以本文件作为语义真源，并同步维护结构化 `plan.json` 投影。


