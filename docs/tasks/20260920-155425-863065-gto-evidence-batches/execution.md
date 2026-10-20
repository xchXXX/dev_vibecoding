# GTO分批验收证据登记与汇总

Task ID: `20260920-155425-863065-gto-evidence-batches`

## 施工目标

修复GTO无法登记分批真实验收证据的问题：保留历史终态，登记已执行且独立评分的局部结果，核验当前适用性，汇总完整覆盖并用于正常关闭。

## 前置条件

- 用户已确认施工摘要、完整要求、流程和任务表。
- 写入前已冻结范围、验收和风险。

## 执行顺序

独立文档与测试先行；新增追加式局部证据登记及当前候选覆盖汇总，来源身份/原始输出/独立评分/输入/候选适用性哈希可重验，执行单元集合不能缩小或重复计数；现有full/scoped保留。源码独立Review后仅发布GTO，安装版真实CLI正反例验收，随后由原业务验收者恢复原同一任务并补真正失效的最小功能证据。

## 文档先行清单

- 先同步长期真源和任务施工文档。

## 测试同步清单

- 先建立最小 Red，再实施 Green 和相关回归。

## 实施批次

- skills/global-task-orchestrator/scripts/orchestrator_ctl.py
- skills/global-task-orchestrator/scripts/acceptance_batches.py
- tests/harness/test_gto_acceptance_batches.py
- tests/harness/test_gto_acceptance_batches_cli.py
- skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json
- skills/global-task-orchestrator/SKILL.md
- skills/global-task-orchestrator/references/state-schema.md
- skills/global-task-orchestrator/references/usage-modes.md
- skills/global-task-orchestrator/references/revision-3-results.example.json

## 每批写入范围

- skills/global-task-orchestrator/scripts/orchestrator_ctl.py
- skills/global-task-orchestrator/scripts/acceptance_batches.py
- tests/harness/test_gto_acceptance_batches.py
- tests/harness/test_gto_acceptance_batches_cli.py
- skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json
- skills/global-task-orchestrator/SKILL.md
- skills/global-task-orchestrator/references/state-schema.md
- skills/global-task-orchestrator/references/usage-modes.md
- skills/global-task-orchestrator/references/revision-3-results.example.json

## 验证命令

- BATCH-01：历史environment_failure保留不变，可登记其中确已执行且独立通过的局部单元；新定向attempt诚实记录partial而非full，调用只记一次。
- COVERAGE-01：依据冻结完整单元集合汇总当前候选覆盖，真实代码/输入失效、假身份、篡改、未执行、漏项、重复和冲突均拒绝；登记、validate与finalize重验。
- RELEASE-01：独立源码审查及安装版CLI验收通过，仅发布GTO且source/install/receipt一致，旧full/scoped及预算和证据归属行为保持。

## 回退方案

- 现有harness未提交内容须采集基线并保留，只有获批范围允许增量修改。
- 旧证据当前适用性必须有可核验来源与独立审查，不能通过缩小依赖路径继承失效输出。
- 原业务功能验收仍独立核对；实际缺失证据不能以AI评分或GTO结构校验代替。

## 审查与返工路径

遵循已加载 GTO 包的 references/usage-modes.md 唯一流程真源。

## 要求分工

### 本轮执行记录

- 已验证 Ubuntu-24.04 项目环境；已安装 GTO 完成 validate、prepare-workspace 和首次 preflight，允许交付写入。既有 dirty 工作区按已批准范围保留。
- 发布前基线通过 scoped strict doctor，9 项现有合同检查通过；安装版六份受影响文件保存于 `.artifacts/20260920-155425-863065-gto-evidence-batches/baseline/`，宿主配置仅保存哈希。
- DOC-001 由真实隔离代理 `/root/gto_batch_tester` 以 doc-curator 身份完成并正式登记；TEST-001 已以 tester 身份绑定同一代理，独立冻结行为测试。尚未声明新接口实现通过。
- 独立预审发现同文件 JSON pointer 错配风险；测试合同细化为 reviewer 的 `units_sha256` 绑定完整批次单元载荷，评分 ID 与 outcome 选择器必须来自所选评分对象，作者允许对象本身或真实祖先元数据。该细化落实既有“同一单元真实来源”要求；正式字段文档在整合阶段同步。
- 预审发生一次只读路径错误：误读 `docs/tasks/.../task.md`，正确路径为 `docs/ai/tasks/.../task.md`。预审者先纠正后回报，主协调者补记 CFM 并核验成功；保留先重试后查询的顺序偏差，不将其描述为完整合规的首次闭环。CFM signature 为 `92352f5d39fddd3c46328da476040ffe67e2508c604d12a69573c98b3d696362`。
- TEST-001 已正式登记：15 个公开 CLI 顶层用例冻结，最小 Red 17.351 秒准确命中新 action 未实现，AST 检查通过。WORK-001 已绑定原实现/整合者 `/root/implementer`，code_impl preflight 通过；产品写入限定三个已声明文件。
- 后续只读预审指出需增加 blackbox 专属链、效果失败禁绕过、真实跨候选 delta 和排除缺少 DOC-FINAL 所致 finalize 假红的证明。恢复原测试代理时平台返回 `agent thread limit reached`；已记录/查询 CFM `d4978ce1cb055c389263fa7bf2395ce1d48a1541e2b452592d54a2a2cff56709`，完成代理暂停后的一次重试仍失败。该失败未解决，不伪造原代理结果；产品实现继续，补证明测试留正式独立 Review 处理，后续独立验收身份依实际可用能力如实绑定。

- REQ-01｜落实：DOC-001、TEST-001、WORK-001｜验收：BATCH-01
- REQ-02｜落实：TEST-001、WORK-001、REVIEW-001｜验收：COVERAGE-01
- REQ-03｜落实：INTEGRATE-001、ACCEPT-001、CLOSE-001｜验收：RELEASE-01

### WORK 与整合交接

- WORK-001 已由控制器记录 completed：最终同版本独立测试为来源校验 8/8（180.505 秒）与覆盖检查 7/7（254.160 秒），日志位于 `.artifacts/gto/20260920-155425-863065-gto-evidence-batches/`。这不是业务模型验收，也不替代后续独立 Review。
- INTEGRATE-001 已绑定同一真实实现者 `/root/implementer`；同步四份授权文档并运行原有 full/scoped、预算、证据归属定向回归，尚未发布安装版。
- 后续首次安装验收计划使用真实独立 tester `/root/test_001`。原 GTO 初始 tester `/root/gto_batch_tester` 无法恢复的实际平台失败已保留；该人员调整是尚未绑定的 ACCEPT 首次分派偏差，不替换任何已有验收或复验责任者，不声称新人员是 TEST-001 作者。冻结六要点中的独立测试、审查与验收要求保持，历史业务证据仍只能由原作者登记。安装验收须等待独立 Review 和受控发布完成。

### 独立 Review 第一轮

- INTEGRATE-001 已记录 completed。最终整合验证包含当前覆盖关键 2/2、旧 full/scoped 2/2、预算与证据补登记 5/5；早期错误测试类名和旧调用参数错误日志保留，未计作通过。
- REVIEW-001 已正式绑定 `/root/gto_batch_reviewer`，真实 CLI 最小证明 2 项在 38.796 秒内均准确复现预期拒绝而实际放行。控制器记录 verdict=fail，追加 REVIEW-INPUT-VALUE-001 与 REVIEW-INPUT-ORIGIN-002，不发布源码候选。
- 两个 finding 第 1 轮返工均已正式派给原整合者 `/root/implementer`，只修产品输入投影比较与历史输入归属，保留独立测试和文档合同。黑盒链、跨候选 delta、finalize 篡改等未执行专项仍待原 Reviewer 复审，不因已有测试通过而省略。

### 真实原始记录格式的合同细化

- 主协调只读核对业务原始 JSON 结构：场景使用 scenario_id/status，18 项 OUTPUT_ARCHIVED 与 DI 准备失败分开。没有读取隐藏评分标准、改写 raw 或调用模型。
- 原 Reviewer 发现固定 id/executed 不能承载既有原始记录，并在 `.tmp/gto/20260920-155425-863065-gto-evidence-batches/review-native-contract.md` 编写最小正式合同原文，SHA256 `aa3a57e4a702a7d2a8673a0facb2b95963d4026bf882e6ba2eb8804a5ce0f2c7`。
- 主协调仅把该发现者原文应用至已批准的 state-schema.md 和结果示例：显式 raw_selectors 随完整合同冻结，在所选记录内核对 ID/归档状态，whole-file 重复仍拒绝，独立 PASS 评分仍必需。文档内容作者为 `/root/gto_batch_reviewer`，应用者为 `/root`；未扩大业务范围，也未让返工者调整测试或放宽合同。
- 此时产品尚未实现 selectors，待发现者冻结独立失败证明并按正常 finding 流程返工。原两个输入 finding 已由原 Reviewer 独立复验 Green，其他专项仍未全部完成。

### 最终源码审查与受控发布

- 同一原整合者修复并追加整合，同一独立 Reviewer 完成三次范围复审；5 项 finding 均已关闭：输入值比较、历史输入归属、历史生命周期、真实 raw selectors、路径别名去重。最终 REVIEW-001-rereview-3 为 PASS，本轮独立 3/3、61.858 秒；既有专项复用范围通过精确 delta/hash 核验，未宣称重复执行。
- 已冻结 candidate-0308aa1ae36e33e6，fingerprint `0308aa1ae36e33e6728225867caa167fb013c3a10c1a1b0a137185be86a73795`。最终 helper SHA256 `0afe8fbda94361c03502caa2c1bd55d0c51988bc6ad061bf2f92170b813edf0a`。
- 已通过官方 sync-codex 仅发布 global-task-orchestrator；12 个 source/install/receipt 文件一致，其他技能 receipt 未变；strict doctor 通过，9 项合同检查 26.638 秒。二次 sync runtime_changed=false。原始证据 release-sync-first.json、release-doctor.json、release-integrity.json、release-sync-second.json 位于本任务 `.artifacts/gto/`。
- 宿主 config.toml 在任务初始与发布前快照之间哈希不同，不能声称整个时段未变化；本任务未编辑该配置，发布前后 hash 一致，AGENTS hash 也一致。未覆写或回退观察到的宿主配置变化。
- ACCEPT-001-attempt-1 已正式绑定首次独立安装验收者 `/root/test_001`，与实现和Review分离；此时尚未登记通过。安装版验收与source Review严格区分，业务模型调用仍为0。
- 主协调一次日志路径读取误把递归清单basename当根路径，CFM `CASE-663977bd5cb8ca12` 已按record/query/验证正确FullName/success闭环，未影响产品或验收结果。

### 安装版验收与文档收口完成

- ACCEPT-001-attempt-1 已正式记录 PASS，作者 `/root/test_001`，4 个冻结节点通过，214.158 秒；132 次真实调用均使用绝对安装控制器，104 次成功、28 次合同预期拒绝，业务模型调用为0。
- 初次安装fixture被源码相对路径断言阻挡，当时0次安装CLI调用，已按CFM闭环；正式运行只在进程内改入口适配以运行真实安装CLI，未改冻结测试或产品校验。
- CLOSE-001 已由 `/root/gto_batch_reviewer` 以 doc-curator 身份只读核对，四正式文档无需修改；独立重算132条trace及12文件hash吻合，已记录completed。主协调执行finalize，不将原业务Browser阻塞混入本GTO修复的完成判定。
