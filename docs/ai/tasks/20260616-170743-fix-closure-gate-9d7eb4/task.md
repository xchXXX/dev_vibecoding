# 任务摘要

## 基本信息

- `task_id`: `20260616-170743-fix-closure-gate-9d7eb4`
- `title`: 修复闭环闸门与返工降本机制
- `status`: `completed`
- `owner`: `main-coordinator`

## 目标

- 为实施类任务建立前置收口闸门，强制区分结果通过与修复点命中证明，降低审查后小问题返工成本。

## 范围

### Scope In

- 新增一个独立 skill，暂名“修复闭环闸门”，负责最小复现、命中证明、diagnostic 与 acceptance 分层，以及审查前证据链定义。
- 设计触发该 skill 的规则条件，覆盖 bugfix、fallback 或 catch 分支修复、高成本集成测试链路、需要审查复核的实施任务。
- 设计 global-task-orchestrator 与该 skill 的接入方式，使长任务在进入实现前和进入复审前都能检查 verification contract。
- 设计最小模板、字段或轻校验方式，确保 minimal_repro、hit_proof、acceptance_checks、non_goals 与 review evidence 不只停留在口头约定。
- 将 verification contract 以最小风险方式接入 state.json、schema、任务模板、orchestrator validate 与相关测试。

### Scope Out

- 不重定义 pre-dev-benchmark 的原始定位，不把项目前 benchmark 体系设计与单次实施任务的修复闭环混为一体。
- 不把修复闭环优化直接塞进 global-task-orchestrator 作为长期真源；global-task-orchestrator 只负责长任务编排与闸门接入。
- 不在首版一次性重构全部历史任务的既有任务文档资产或全部既有 rules/skills。
- 不为历史任务批量回填 verification contract 或 review evidence。

## 验收标准

- 新 skill 的职责、非职责、输入输出合同和最小工作流被明确定稿并落盘，且不污染 pre-dev-benchmark 与 global-task-orchestrator 的边界。
- 长任务控制面中明确出现 verification_contract 根对象，并至少包含 minimal_repro、hit_proof、diagnostic_checks、acceptance_checks、non_goals、review_evidence。
- 规则触发条件被定义清楚，能够说明哪些任务必须先走修复闭环闸门，哪些任务可以跳过。
- global-task-orchestrator 的接入方式被落盘，能够在进入实现前与进入复审前检查 verification contract 是否齐备、review evidence slot 是否已补齐。
- 任务期文档真源固定在 docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/，并与 validate-plan-docs.ps1、validate-doc-routing.ps1 的三件套闸门保持一致。

## 停止条件

- 发现新 skill 与现有 skill 或规则边界无法无歧义定义，继续实施只会制造职责重叠。
- 发现 state.json 的最小字段扩展会破坏现有 global-task-orchestrator 编排或验证脚本，且没有低风险兼容路径。
- 发现应先统一仓库级任务文档真源与校验口径，否则当前设计只能新增一层局部补丁。
- 发现执行窗口若继续推进会被迫同时改写过多历史控制面资产，超出本任务首版收口范围。

## 关键决定

- 不复用 pre-dev-benchmark 处理本问题；另起独立 skill 承载单次实施任务的修复闭环闸门。
- global-task-orchestrator 只负责编排接入与硬闸门，不承载修复闭环优化的长期真源。
- 按当前任务文档规则，将本任务的人类任务文档固定在 docs/tasks/<task_id>/plan.md、execution.md 与 acceptance.md。
- 本任务以 docs/tasks/<task_id>/ 三件套为唯一人类任务文档真源，并要求 validate-plan-docs.ps1 与 validate-doc-routing.ps1 保持同一收口口径。
- verification contract 以 state.json 根层 verification_contract 对象承载，实际 review evidence 回写到执行型或测试型 subtask.result.review_evidence。

## 当前阶段

- `current_phase`: `review`

## 子任务

### read-boundaries

- `title`: 梳理 skill、规则与任务文档真源边界
- `role`: `reader`
- `status`: `completed`
- `goal`: 确认新 skill、global-task-orchestrator、pre-dev-benchmark、docs/tasks 与 validate 脚本之间的职责边界，产出冲突清单与建议收口口径。

### design-skill-contract

- `title`: 定稿修复闭环闸门 skill 合同
- `role`: `planner`
- `status`: `completed`
- `goal`: 落盘新 skill 的职责、非职责、输入输出合同、最小工作流与命名口径。
- `dependencies`: `read-boundaries`

### design-rule-trigger

- `title`: 定稿触发规则与闸门口径
- `role`: `planner`
- `status`: `completed`
- `goal`: 落盘哪些任务 intent 或任务特征必须命中新 skill，以及进入实现前、进入复审前分别检查什么。
- `dependencies`: `read-boundaries`, `design-skill-contract`

### design-state-integration

- `title`: 定稿 state.json 与审查证据接入方式
- `role`: `planner`
- `status`: `completed`
- `goal`: 落盘 verification_contract 在 state.json 中的最小承载字段，以及审查前证据链如何挂接到 global-task-orchestrator。
- `dependencies`: `design-skill-contract`, `design-rule-trigger`

### implementation-batch

- `title`: 执行窗口落盘 skill、规则、模板与校验
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 由执行窗口按已定稿合同实施新 skill、规则、模板与校验，并组织文档同步、测试同步、代码实现与复审闭环。
- `dependencies`: `design-state-integration`

### verification-pass

- `title`: 执行窗口汇总测试结果并补齐 review_evidence
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 汇总本批验证结果，为 review 阶段补齐 evidence slot 覆盖，并确认 verification_contract 已能挡住“只有结果通过、没有命中证明”的送审路径。
- `dependencies`: `implementation-batch`

### formal-review

- `title`: 正式审阅修复闭环闸门首版接入
- `role`: `reviewer`
- `status`: `completed`
- `goal`: 对修复闭环闸门首版的 skill、规则、state/schema/template、sync/runtime 接入和任务控制面做正式只读审阅，确认是否仍存在实现缺陷、口径漂移、回归风险或测试遗漏。
- `dependencies`: `verification-pass`

### review-rework-1

- `title`: 返工 reviewer 指出的控制面与文档口径问题
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 修复 reviewer 首轮指出的 3 个问题：completed 任务未强制所有 subtasks 收口、当前任务控制面误标完成态、以及 fix-closure-gate 对根层 review_evidence 的语义漂移。
- `dependencies`: `formal-review`

### formal-review-r2

- `title`: 正式复审修复闭环闸门返工结果
- `role`: `reviewer`
- `status`: `completed`
- `goal`: 对 reviewer 首轮 findings 的返工结果做二次正式复审，确认是否还有任何剩余问题；若无则给出 pass。
- `dependencies`: `review-rework-1`

## 更新时间

- `2026-06-17T02:48:48+08:00`

