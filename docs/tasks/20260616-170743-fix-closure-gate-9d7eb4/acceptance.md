# 验收目标

- 验证本任务是否成功为实施类任务建立了首版“修复闭环闸门”，并将“结果通过”和“修复点命中证明”明确分离。
- 验证该机制是否能同时服务普通修复任务与长任务编排接入，而不污染 `pre-dev-benchmark` 与 `global-task-orchestrator` 的既有定位。

## 验收标准

- 新 skill 的职责、非职责、输入输出合同和最小工作流已经定稿，并有对应真源落点。
- 规则触发条件已经定稿，能够明确说明哪些任务必须先走修复闭环闸门。
- `global-task-orchestrator` 的接入方式已经定稿，能够在进入实现前和进入复审前检查 verification contract。
- verification contract 的最小字段定义已经定稿，至少覆盖：
  - `minimal_repro`
  - `hit_proof`
  - `diagnostic_checks`
  - `acceptance_checks`
  - `non_goals`
  - `review_evidence`
- `verification_contract` 已作为根层对象进入 `state.json` / schema / 示例模板；实际 `review_evidence` 只回写到执行型或测试型 `subtasks[].result.review_evidence`，不制造双真源。
- 任务期文档真源与可执行校验口径已经统一收口到 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md`。

## 必备证据

- 任务合同真源：
  - `docs/ai/tasks/20260616-170743-fix-closure-gate-9d7eb4/state.json`
  - `docs/ai/tasks/20260616-170743-fix-closure-gate-9d7eb4/task.md`
- 人类任务文档：
  - `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/plan.md`
  - `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/execution.md`
  - `docs/tasks/20260616-170743-fix-closure-gate-9d7eb4/acceptance.md`
- 执行与复审证据：
  - verification contract 字段落地证据
  - `verification_contract.review_evidence` required slot 落地证据
  - 规则触发口径落地证据
  - `global-task-orchestrator` 接入口径落地证据
  - 审查前证据链字段与复审路径落地证据

## 未决项

- 首版规则触发范围是否先缩到 bugfix、fallback 或 catch 分支修复、高成本集成测试链路三类场景，需结合实施复杂度最终裁决。
- 复审前 evidence slot 的最小数据结构是否只保留 `summary/refs`，还是需要更强 schema，需结合实现成本最终裁决。

## 最终结论

- 当前状态：任务文档三件套及其双脚本闸门已完成收口，当前执行窗口正在落盘 skill、规则、schema、orchestrator validate 与相关测试。
- 回填要求：由 `Execute Window` 在实现完成并经过复审后，补写最终通过/未通过结论、偏差说明与后续行动，并给出 evidence slot 覆盖情况。
