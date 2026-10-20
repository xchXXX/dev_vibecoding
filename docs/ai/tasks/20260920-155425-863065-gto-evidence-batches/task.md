# GTO分批验收证据登记与汇总

Task ID: `20260920-155425-863065-gto-evidence-batches`

## 要做什么

修复GTO无法登记分批真实验收证据的问题：保留历史终态，登记已执行且独立评分的局部结果，核验当前适用性，汇总完整覆盖并用于正常关闭。

## 不做什么

- 不改药品销售项目业务模块、测试题目、评分标准或既有原始输出。
- 不重跑完整20题、不伪造模型调用、不用局部通过改写历史整轮失败。
- 不直接编辑任务state或绕过review、候选、权限、证据、功能验收门禁。
- 不改无关harness文件、不清理既有dirty改动、不提交或推送Git。

## 改哪些地方

- skills/global-task-orchestrator/scripts/orchestrator_ctl.py
- skills/global-task-orchestrator/scripts/acceptance_batches.py
- tests/harness/test_gto_acceptance_batches.py
- tests/harness/test_gto_acceptance_batches_cli.py
- skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json
- skills/global-task-orchestrator/SKILL.md
- skills/global-task-orchestrator/references/state-schema.md
- skills/global-task-orchestrator/references/usage-modes.md
- skills/global-task-orchestrator/references/revision-3-results.example.json

## 怎么实现落地

独立文档与测试先行；新增追加式局部证据登记及当前候选覆盖汇总，来源身份/原始输出/独立评分/输入/候选适用性哈希可重验，执行单元集合不能缩小或重复计数；现有full/scoped保留。源码独立Review后仅发布GTO，安装版真实CLI正反例验收，随后由原业务验收者恢复原同一任务并补真正失效的最小功能证据。

## 怎么验收

- BATCH-01：历史environment_failure保留不变，可登记其中确已执行且独立通过的局部单元；新定向attempt诚实记录partial而非full，调用只记一次。
- COVERAGE-01：依据冻结完整单元集合汇总当前候选覆盖，真实代码/输入失效、假身份、篡改、未执行、漏项、重复和冲突均拒绝；登记、validate与finalize重验。
- RELEASE-01：独立源码审查及安装版CLI验收通过，仅发布GTO且source/install/receipt一致，旧full/scoped及预算和证据归属行为保持。

## 有什么风险

- 现有harness未提交内容须采集基线并保留，只有获批范围允许增量修改。
- 旧证据当前适用性必须有可核验来源与独立审查，不能通过缩小依赖路径继承失效输出。
- 原业务功能验收仍独立核对；实际缺失证据不能以AI评分或GTO结构校验代替。

## 当前状态

- status: `completed`
- current_phase: `review`
- next_action: `none`

## 要求导航

见 docs/tasks/20260920-155425-863065-gto-evidence-batches/plan.md 的完整要求清单。
