# 施工目标

- 按已定稿合同实现“修复闭环闸门”首版能力，并让长任务与普通修复任务都能复用最小 verification contract。
- 在不污染 `pre-dev-benchmark` 与 `global-task-orchestrator` 的前提下，补齐规则触发、模板承载、state/schema 接口与最小校验。
- 收紧任务期文档三件套的真源目录、目录骨架校验与章节校验口径，并把 verification contract 的 contract/evidence 双层口径固定下来。

## 前置条件

- `docs/ai/tasks/20260616-170743-fix-closure-gate-9d7eb4/state.json`、`docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/plan.md`、`docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/execution.md`、`docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/acceptance.md` 已定稿。
- 执行窗口必须继续复用当前 `task_id`，不得重新 `init-task`。
- 执行窗口开始前，先完整阅读 `state.json`、`task.md`、方案文档、施工文档、验收文档。
- 执行窗口不得跳过子代理直接收口；先组织子任务，再推进阶段。

## 执行顺序

1. 先完成边界梳理子任务，确认新 skill、规则、目录真源与脚本校验的冲突面。
2. 先同步当前批次相关核心文档，让新 skill 与 `global-task-orchestrator` 的边界描述先定稿。
3. 再同步测试与校验脚本设计，明确哪些是 diagnostic，哪些是 acceptance，以及 review evidence slot 在哪一层回写。
4. 之后进入 skill、规则、schema、模板与脚本实现。
5. 实施完成后再进入复审，并按审查返工路径回流。

## 文档先行清单

- `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/plan.md`
- `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/execution.md`
- `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/acceptance.md`
- `docs/ai/tasks/20260616-170743-fix-closure-gate-9d7eb4/state.json`
- `skills/global-task-orchestrator/SKILL.md`
- `skills/global-task-orchestrator/references/state-schema.md`
- `skills/pre-dev-benchmark/SKILL.md`
- `schemas/task-state.schema.json`
- `templates/task-state.example.json`
- 后续如新建 `修复闭环闸门` skill，需先补其 `SKILL.md` 真源说明、`agents/openai.yaml` 与最小样例，再扩展规则与脚本。

## 测试同步清单

- `scripts/validate-doc-routing.ps1`：校验 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md` 的目录骨架。
- `scripts/validate-plan-docs.ps1`：校验 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md` 的章节口径。
- `tests/harness/plan-docs.integration.ps1`：覆盖三件套、缺文件、缺章节和关键章节占位场景。
- `tests/harness/control-plane.integration.ps1`：覆盖 `verification_contract` 根对象、进入实现前 contract 缺失、进入复审前 evidence 缺失等闸门。
- `tests/harness/global-task-orchestrator.skill-doc.ps1`：覆盖 orchestrator skill 文档对 verification contract 与 phase gate 的约定。
- 如新增 skill 或规则校验脚本，需要为其补最小集成测试或回归测试。

## 实施批次

- 批次一：边界与字段定稿
  - 目标：冻结新 skill 的职责、触发规则与 verification contract 字段。
  - 收口条件：方案文档、施工文档与 `state.json` 的 acceptance 一致。
- 批次二：文档与校验同步
  - 目标：补齐新 skill 文档、目录真源校验、state/schema 接口与最小模板。
  - 收口条件：`plan.md / execution.md / acceptance.md` 的目录骨架、章节规则与审查口径不再互相冲突。
- 批次三：规则与实现接入
  - 目标：让 `global-task-orchestrator` 或相关流程能检查 verification contract 并阻断未闭环任务。
  - 收口条件：至少一条长任务路径和一条普通修复任务路径能复用该闸门。
- 批次四：复审闭环
  - 目标：验证“结果通过但未证明命中”的场景会被阻断或退回补证据。
  - 收口条件：审查口径与实施口径一致，不再把关键缺口留给二次审查指出。

## 每批写入范围

- 批次一：
  - `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/`
  - `docs/ai/tasks/20260616-170743-fix-closure-gate-9d7eb4/`
- 批次二：
  - `skills/`
  - `rules/`
  - `schemas/`
  - `templates/`
  - `scripts/`
  - `tests/`
  - `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/`
- 批次三：
  - `skills/`
  - `rules/`
  - `schemas/`
  - `templates/`
  - `scripts/`
  - `tests/`
  - `docs/ai/tasks/20260616-170743-fix-closure-gate-9d7eb4/`
- 批次四：
  - `docs/ai/tasks/20260616-170743-fix-closure-gate-9d7eb4/`
  - `docs/ai/runs/` 下对应 run 留痕目录

## 验证命令

- `pwsh -File .\scripts\validate-doc-routing.ps1 -RepoRoot . -Json`
- `pwsh -File .\scripts\validate-plan-docs.ps1 -RepoRoot . -Json`
- `pwsh -File .\skills\global-task-orchestrator\scripts\orchestrator_ctl.ps1 -Action validate -RepoRoot . -TaskId 20260616-170743-fix-closure-gate-9d7eb4 -Json`
- `pwsh -File .\skills\global-task-orchestrator\scripts\orchestrator_ctl.ps1 -Action sync-task-md -RepoRoot . -TaskId 20260616-170743-fix-closure-gate-9d7eb4 -Json`
- `pwsh -File .\tests\harness\plan-docs.integration.ps1`
- `pwsh -File .\tests\harness\control-plane.integration.ps1`
- `pwsh -File .\tests\harness\global-task-orchestrator.skill-doc.ps1`
- 文档三件套变更后，先通过 `validate-doc-routing.ps1` 与 `validate-plan-docs.ps1`，再进入更高成本回归与复审。

## 回退方案

- 若新 skill 边界无法稳定定义，先回退到“只冻结最小字段与最小证据链”的首版，不强行扩展复杂自动化。
- 若目录真源与校验脚本口径冲突无法在本批收敛，先保留 `docs/tasks/` 为唯一人类任务文档真源，并把旧脚本修正作为阻塞项回主协调器裁决。
- 若规则触发范围过大导致首版复杂度失控，先缩到 bugfix、fallback 或 catch 分支修复、高成本集成测试链路三类场景。
- 若 verification contract 的实际 evidence 回写需要新增第二真源，先回退到“根层只声明 required slot，实际 evidence 只回写 `subtasks[].result.review_evidence`”。

## 审查与返工路径

- 执行窗口按 `global-task-orchestrator` 的固定路由组织子代理：
  - 边界梳理优先给 `reader`
  - 文档同步优先给 `doc-curator`
  - 测试与校验同步优先给 `test-verifier`
  - 实施与接入由相应执行型子代理处理
  - 复审由专门 `reviewer` 子代理执行
- 审查重点先查证据链是否闭环，再查实现细节：
  - 是否有 `minimal_repro`
  - 是否有 `hit_proof`
  - 是否区分 `diagnostic_checks` 与 `acceptance_checks`
  - 是否具备 `review_evidence`
- 若审查发现缺口，返工必须回到原施工子代理，由其补证据、补字段或补实现；复审继续复用同一审查子代理，避免口径漂移。
