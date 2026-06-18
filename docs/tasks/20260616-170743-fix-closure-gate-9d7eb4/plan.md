# 任务目标

- 为实施类任务建立一套前置收口闸门，强制区分“结果通过”和“修复点被证明命中”，降低审查后小问题返工带来的大回归成本。
- 该机制既要能被普通修复任务单独复用，也要能被长任务编排稳定接入。

## 背景与问题

- 当前痛点不是“审查本身太多”，而是第一次实施前没有把验证拆成低成本、确定性、分层的收口合同。
- 实际使用中容易出现三种混淆：
  - 把“整套测试通过”误当成“修复点已经被证明命中”。
  - 在没有确定性最小复现的情况下，直接围着高成本集成套件反复跑，导致定位成本被放大。
  - 在证据链还不闭环时，过早判断“问题已收口”，把缺口留给后续审查子代理指出。
- 仓库当前已将任务期文档目录规则与 `scripts/validate-plan-docs.ps1` 收口到 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md`，不再继续向 `docs/plans/` 漂移。

## 范围

- 落盘一个独立于 `pre-dev-benchmark` 的新 skill，暂名“修复闭环闸门”。
- 定义该 skill 的职责、非职责、输入输出合同和最小工作流。
- 定义该 skill 的触发条件，包括 bugfix、fallback 或 catch 分支修复、高成本集成测试链路、需要审查复核的实施任务。
- 设计 `global-task-orchestrator` 在长任务中的接入方式，使其在进入实现前和进入复审前都能检查 verification contract。
- 继续收紧 `docs/tasks/` 三件套与校验脚本、规则闸门、审查口径之间的一致性，并把 verification contract 以最小风险方式接进控制面。

## 非目标

- 不重写 `pre-dev-benchmark` 的定位，不把项目前 benchmark 设计与单次实施任务收口混为一谈。
- 不把修复闭环能力直接塞进 `global-task-orchestrator` 作为长期真源。
- 不在首版一次性迁移全部历史 `docs/plans/` 文档。
- 不一次性为全部历史任务批量回填 verification contract 或 review evidence。

## 约束与依赖

- 说明性内容、方案文档与施工文档默认使用中文。
- 任务文档按当前较新的真源目录落在 `docs/tasks/<task-id>/`；AI 控制面状态落在 `docs/ai/tasks/<task-id>/`。
- 本任务需要同时尊重 `global-task-orchestrator`、`pre-dev-benchmark`、任务文档目录规则和现有校验脚本，不允许靠口头约定跳过 verification contract 字段或 evidence 槽位。
- 执行窗口进入实现前，必须先完成当前批次相关核心文档与测试同步。

## 方案摘要

- 新建一个独立 skill，专门定义单次实施任务的修复闭环闸门。
- 该 skill 负责回答六个核心问题：
  - 是否存在 `minimal_repro`
  - 是否定义了 `hit_proof`
  - 哪些检查属于 `diagnostic_checks`
  - 哪些检查属于 `acceptance_checks`
  - 本轮明确的 `non_goals` 是什么
  - 审查前必须收齐哪些 `review_evidence`
- 规则层负责定义触发条件，确保这套流程不是“可选建议”，而是命中指定场景时的默认闸门。
- `global-task-orchestrator` 只负责在长任务里读取 `verification_contract`、阻断未闭环批次进入实现或复审，不复制整套 skill 逻辑。
- `verification_contract` 以 `state.json` 根层对象承载，实际 `review_evidence` 回写到执行型或测试型 `subtasks[].result.review_evidence`，避免双真源。
- 任务文档三件套与 `validate-plan-docs.ps1`、`validate-doc-routing.ps1` 已经收口，后续重点转向 verification contract 与复审前 evidence 槽位。

## 风险与回退

- 风险一：新 skill 与 `pre-dev-benchmark` 或 `global-task-orchestrator` 的边界描述不清，导致职责再次混叠。
  - 回退口径：先冻结边界，不进入实施；必要时缩小首版范围，只保留最小字段和最小闸门。
- 风险二：把 verification contract 的声明字段和实际 review evidence 一起塞进根层，会制造根层与 `subtasks[].result` 双真源。
  - 回退口径：根层只保留 contract 声明与 required slot；实际 evidence 只回写到执行型或测试型子任务结果。
- 风险三：试图一次性把所有验证、审查、模板和自动化做满，导致首版过重。
  - 回退口径：首版只收敛 skill 边界、触发规则、最小字段和最小校验。

## 验收标准

- 新 skill 的职责、非职责、输入输出合同和最小工作流被定稿并落盘，且不污染 `pre-dev-benchmark` 与 `global-task-orchestrator` 的原定位。
- 触发条件被定稿并落盘，能够明确说明哪些任务必须先走修复闭环闸门。
- `global-task-orchestrator` 的接入方式被定稿并落盘，能够在进入实现前与进入复审前检查 verification contract 是否齐备。
- 长任务控制面中明确出现 `verification_contract` 根对象，并至少包含 `minimal_repro`、`hit_proof`、`diagnostic_checks`、`acceptance_checks`、`non_goals`、`review_evidence`。
- 任务文档真源固定在 `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/`，并与 `validate-plan-docs.ps1`、`validate-doc-routing.ps1` 的三件套闸门保持一致。
- 计划窗口生成可直接交给执行窗口起步的子任务清单、边界摘要与停止条件。

## 阶段划分

- 阶段一：边界梳理
  - 读取现有 skills、规则、脚本与目录真源，冻结边界冲突清单。
- 阶段二：合同设计
  - 定稿并落盘新 skill、触发规则、verification contract 字段与审查证据链。
- 阶段三：执行窗口实施
  - 先同步核心文档与测试，再落盘 skill、规则、schema、模板与校验。
- 阶段四：复审与回收
  - 复查闸门是否真的阻断“只有结果通过、没有命中证明”的任务进入送审。

## 需先同步的核心文档与测试

- 核心文档：
  - `skills/global-task-orchestrator/SKILL.md`
  - `skills/pre-dev-benchmark/SKILL.md`
  - `rules/items/architecture/通用文件存储位置.md`
  - `rules/items/policy/文件存储位置强制约束.md`
  - `rules/items/workflow/文档分流与实现前闸门.md`
  - `rules/items/workflow/长任务实施顺序.md`
  - `rules/items/quality/提交与验证.md`
- 核心测试与校验：
  - `scripts/validate-doc-routing.ps1`
  - `scripts/validate-plan-docs.ps1`
  - `tests/harness/plan-docs.integration.ps1`
