# GTO-evidence-receipts

Task ID: `20260920-101849-507587-gto-evidence-receipts`

## 施工目标

修复GTO验收证据登记与关闭脱节：受控追加终态证据引用、提前检查、单一证据真源，并发布后恢复原聊天任务。

## 前置条件

- 用户已确认施工摘要、完整要求、流程和任务表。
- 写入前已冻结范围、验收和风险。

## 执行顺序

独立文档和测试先行，原实现者最小修复及整合，独立完整审查后只发布GTO；真实CLI验证合法补录与拒绝边界，保留原任务同一state与真实身份。

## 文档先行清单

- 先同步长期真源和任务施工文档。

## 测试同步清单

- 先建立最小 Red，再实施 Green 和相关回归。

## 实施批次

- skills/global-task-orchestrator/scripts/orchestrator_ctl.py
- skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json
- tests/harness/test_gto_verification_evidence.py
- tests/harness/test_gto_verification_evidence_acceptance.py
- skills/global-task-orchestrator/SKILL.md
- skills/global-task-orchestrator/references/state-schema.md
- skills/global-task-orchestrator/references/usage-modes.md
- skills/global-task-orchestrator/references/revision-3-results.example.json

## 每批写入范围

- skills/global-task-orchestrator/scripts/orchestrator_ctl.py
- skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json
- tests/harness/test_gto_verification_evidence.py
- tests/harness/test_gto_verification_evidence_acceptance.py
- skills/global-task-orchestrator/SKILL.md
- skills/global-task-orchestrator/references/state-schema.md
- skills/global-task-orchestrator/references/usage-modes.md
- skills/global-task-orchestrator/references/revision-3-results.example.json

## 验证命令

- EVIDENCE-01：原作者可追加合同要求的缺失证据引用，原终态结果和历史保持不变；来源、身份、哈希、候选、引用错误均拒绝且零修改。
- GATE-01：验收登记时核对所属证据关联，CLOSE前汇总所有必需证据；引用已登记证据，无业务键硬编码或第二份事实。
- RELEASE-01：独立测试和审查通过，受控同步GTO安装副本与receipt一致，安装版CLI验收与幂等同步通过。

## 回退方案

- 保护harness既有dirty基线；只修改获批GTO范围。
- 不能把补录当作重验或授权失败结果通过；非法请求不得改变六工件。

## 审查与返工路径

遵循已加载 GTO 包的 references/usage-modes.md 唯一流程真源。

## 要求分工

- REQ-01｜落实：DOC-001、TEST-001、WORK-001、INTEGRATE-001｜验收：EVIDENCE-01
- REQ-02｜落实：DOC-001、TEST-001、WORK-001、INTEGRATE-001｜验收：GATE-01
- REQ-03｜落实：INTEGRATE-001、REVIEW-001、ACCEPT-001、CLOSE-001｜验收：RELEASE-01

## 2026-09-20 测试夹具纠正与补充证明

TEST-001 原终态回执和最初两个预期 Red 保持不变。WORK-001 首轮完整 12 节点为 9 通过、3 失败，首轮 tee 日志曾被后续 Green 覆盖；现从原实现者持久执行记录的 CommandExecution.aggregated_output 逐字恢复于 `.artifacts/20260920-101849-507587-gto-evidence-receipts/WORK-001/first-full-failure.log`（SHA256 `5eaccce53310fbebe085355182af7aa4516ba2d6c3c9c9009c25b730f0be37dd`），恢复来源见同目录 `first-full-failure-recovery.json`。这是执行输出恢复件，不是原 tee 文件，也不是重跑或拼凑。两项实现问题由原实现者处理；纯文档收尾场景在进入目标逻辑前被既有 write_paths 门禁拒绝，原因是临时 DOC-FINAL 合同未声明自己写入的 docs/contract.md。

原独立测试者 `/root/test_001` 仅纠正临时合同范围，未放宽产品门禁或既有断言；另补实际候选源漂移、dispatch/result 双作者匹配、额外 review_evidence 的合同键与真实引用三条既定边界。纠正目标 1 passed，新增目标 3 passed；新增证明是当前实现 Green，不宣称旧版 Red。测试集合由 12 增至 15 节点，待原实现者整体验证后送审。

纠正及 before/after SHA 的独立作者回执：`.tmp/gto/20260920-101849-507587-gto-evidence-receipts/test-fixture-correction.json`，SHA256 `80710845040ca9d7b5935996e84c83c1c23b7d6f0838fe671ec25ab9dba64ab8`。新测试 SHA：主测试 `e31c168cab76c19208b53150ef435e46cd64541454b215a6d59726deb498f32f`；CLI 测试 `aa0a541b66aa2ff954a716778d9fb318016e9cee9154239bc3cc63cdfbd0e208`。后续 integration 引用本纠正事实，不覆盖旧测试回执。


## 2026-09-20 独立审查与归属返工

原实现者 `/root/implementer` 完成 WORK-001 与只读 INTEGRATE-001，三个 pre-final evidence 项完整。源码验证为 15 节点通过，最后来源过滤后受影响 7 节点通过，5 项关键旧流程回归通过；旧 CoordinatorBlocking 夹具在新旧 controller 上均因合同输入不在消费者 .tmp 而初始化失败，作为既有测试债务保留，不放宽安全规则。整合覆盖批准的 8 个文件，候选指纹 `b782a24282b788af97b299eff93a45cec9e1681772a91ddbcd32be2d8558b5d4`。

独立 reviewer `/root/gto_reviewer` 以 fork_turns=none 创建并绑定 REVIEW-001，完整审查后登记 fail。唯一 high finding `REVIEW-EVIDENCE-OWNER-001`：直接结果与 receipt 两入口均能接受其他 kind 或 template 专属 key。reviewer 亲自新增四条最小真实 CLI Red，另有三条独立合法/拒绝/blocked/CLOSE 检查通过。证据位于 `.artifacts/20260920-101849-507587-gto-evidence-receipts/REVIEW-001/`；完整回执 `.tmp/gto/20260920-101849-507587-gto-evidence-receipts/result-REVIEW-001.json`，SHA256 `5f3326d29a2e2b95254f211e192ea27e993ac0be5df522111468b253891ac4a8`。

finding 已由控制器派回原整合者 round 1；测试不得由返工者修改。修复后追加 integration，并交同一 reviewer 复审，不能提前发布。原业务 RAG 任务的 state、47 个终态结果及既有 AI/FUNC 原始验收证据保持不变，仍等待依赖工具修复。

## 2026-09-20 归属问题修复与重新整合

- `REVIEW-EVIDENCE-OWNER-001` 由原整合者 `/root/implementer` 完成 round1 修复，控制器已记录为 `awaiting_re_review`。Fix delta SHA256：`bdfb9eac5fcafa3088b21c2f638be7ebecf3ec9055d5aa8ce7262385671c6022`。
- 当前合同测试19/19、发现者四条目标4/4、相关回归5/5通过，原始日志在 `.artifacts/20260920-101849-507587-gto-evidence-receipts/WORK-001-owner-fix/`；这些为原实现者实跑，后续复审/验收另记独立操作。
- 原整合者只读完成 `INTEGRATE-001-integration-2`，结果已正式记录。当前8路径candidate fingerprint：`54d2d55b2f6ba2ea9ea4c89bcda8d1114e74392ce83301f454555a49b7658469`。本阶段没有改代码或重复全量测试。
- 同一独立审查者 `/root/gto_reviewer` 已绑定 `REVIEW-001-rereview-1`，复审正在进行，尚未宣称通过或发布。
- 平台曾拒绝接续原tester，错误为 `agent thread limit reached`；待整合完成后通过 `followup_task` 成功恢复同一 `/root/test_001`，随后 `send_message` 成功，CFM已闭环。未替换身份或修改平台配置，观察记录见 `.artifacts/20260920-101849-507587-gto-evidence-receipts/agent-capacity-observation.log`。

## 2026-09-20 复审通过与限定发布

- 原独立 reviewer 完成 `REVIEW-001-rereview-1/pass`，本人4条原Red均Green（63.018秒），另以真实CLI核对新字段与旧attempt兼容，八路径指纹一致。控制器正式登记并关闭 `REVIEW-EVIDENCE-OWNER-001`。
- 冻结候选 `candidate-54d2d55b2f6ba2ea`，完整指纹 `54d2d55b2f6ba2ea9ea4c89bcda8d1114e74392ce83301f454555a49b7658469`。
- 正式执行 `sync-codex.py --skill global-task-orchestrator`；source/install/receipt的11个GTO文件一致，12条其他技能发布记录未变，宿主config.toml与AGENTS.md哈希未变。scope doctor strict通过（9项合同检查），第二次同步 `runtime_changed=false`。证据为任务artifact根目录 `scoped-publication.log`、`publication-hashes.log`、`scoped-doctor.log`、`scoped-publication-idempotent.log`。
- 原独立tester `/root/test_001` 已正式绑定 `ACCEPT-001-attempt-1` 执行安装版CLI验收；尚未登记验收结果，不以发布检查替代独立验收。
- 业务原任务47份终态结果canonical哈希、findings、acceptance_gate及历史events字节前缀保持不变，见 `original-immutable-before-restore.log`。原AI/FUNC不重跑，等待本工具验收和收尾后使用原作者已形成的补录载荷恢复。


## 安装版独立验收已登记

ACCEPT-001-attempt-1由原tester完成并正式record为completed/pass。实际15项定向检查310.836秒全通过，261次调用全部为installed entry；三验收项均映射，0模型。原始结构化audit/summary和发布核验完整保存；外层tee日志目录时序错误已披露并CFM闭环，未重跑。CLOSE-001已绑定原doc-curator，仅执行四正式文档事实收敛，root随后重新限定同步并完成最终校验。

## 原业务任务恢复尝试：真实后续改动触发候选保护

安装版独立验收通过后，root在GTO文档收尾并行期间尝试原作者既有FUNC15 receipt。控制器正确拒绝candidate stale，未追加receipt；旧AI17补录和finalize均未执行。只读核实另一个用户授权的同工作区任务“优化右侧聊天助手界面”（01a0bcc4-bbcf-7051-97fa-a878962adf30）已改聊天界面、回答展示、检索预热、后端代码及依赖/测试/文档，因此不能把旧候选PASS直接用于新版。这是当前内容变化触发的正确保护，不是本次工具修复失败。

原任务保留同一state、47份终态结果、findings、验收历史和events旧前缀；拒绝后receipt=0，比较日志为本任务 `original-immutable-after-stale-rejection.log`。完整诊断在业务项目 `.artifacts/20260918-102642-605274-training-assistant-rag/RESUME-20260919/receipt-candidate-diagnostic.log` 和 `concurrent-candidate-change.log`。本工具任务三验收项已通过；原业务新版是否形成新候选并补做受影响验收，已作为重要范围决定询问用户。未回退另一任务改动，未新增AI调用，未越过保护门禁。

## 工具最终文档与发布完成

原doc-curator CLOSE-001正式登记completed，恰为4份正式文档纯文字事实同步；18个相对链接全部有效，示例JSON、完整result schema、实际_document_delta及_documentation_sync验证通过。root完成收尾后的限定发布、11个GTO文件source/install/receipt核对、12条其他技能发布记录和宿主配置/AGENTS哈希不变检查；strict doctor 9项合同检查全部通过，无errors/warnings，第二次同步runtime_changed=false。证据为closeout-scoped-publication.log、closeout-publication-hashes.log、closeout-scoped-doctor.log、closeout-scoped-idempotent.log。

本工具修复合同已履行，独立验收3项均pass，finding全部closed。原业务候选被另一授权任务修改造成的待验收状态单独记录，不将该任务视为已关闭，也不把旧AI/FUNC结果宣称为新版验证。控制器最终完成标记由validate/finalize生成，不手工写入。
