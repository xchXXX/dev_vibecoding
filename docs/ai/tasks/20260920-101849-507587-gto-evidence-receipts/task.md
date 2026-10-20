# GTO-evidence-receipts

Task ID: `20260920-101849-507587-gto-evidence-receipts`

## 要做什么

修复GTO验收证据登记与关闭脱节：受控追加终态证据引用、提前检查、单一证据真源，并发布后恢复原聊天任务。

## 不做什么

- 不改原任务已完成结果、候选、验收结论或失败历史，不降低关闭门槛。
- 不修改业务产品或受保护模块，不新跑AI场景，不提交推送Git。
- 不覆盖或清理当前harness既有未提交改动。

## 改哪些地方

- skills/global-task-orchestrator/scripts/orchestrator_ctl.py
- skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json
- tests/harness/test_gto_verification_evidence.py
- tests/harness/test_gto_verification_evidence_acceptance.py
- skills/global-task-orchestrator/SKILL.md
- skills/global-task-orchestrator/references/state-schema.md
- skills/global-task-orchestrator/references/usage-modes.md
- skills/global-task-orchestrator/references/revision-3-results.example.json

## 怎么实现落地

独立文档和测试先行，原实现者最小修复及整合，独立完整审查后只发布GTO；真实CLI验证合法补录与拒绝边界，保留原任务同一state与真实身份。

## 怎么验收

- EVIDENCE-01：原作者可追加合同要求的缺失证据引用，原终态结果和历史保持不变；来源、身份、哈希、候选、引用错误均拒绝且零修改。
- GATE-01：验收登记时核对所属证据关联，CLOSE前汇总所有必需证据；引用已登记证据，无业务键硬编码或第二份事实。
- RELEASE-01：独立测试和审查通过，受控同步GTO安装副本与receipt一致，安装版CLI验收与幂等同步通过。

## 有什么风险

- 保护harness既有dirty基线；只修改获批GTO范围。
- 不能把补录当作重验或授权失败结果通过；非法请求不得改变六工件。

## 当前状态

- status: `completed`
- current_phase: `review`
- next_action: `none`

## 要求导航

见 docs/tasks/20260920-101849-507587-gto-evidence-receipts/plan.md 的完整要求清单。
