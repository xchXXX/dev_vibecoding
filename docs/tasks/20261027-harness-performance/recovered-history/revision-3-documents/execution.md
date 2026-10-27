# GTO revision 3 施工记录

## 当前状态

用户于 2026-09-05 明确批准：施工文档写清楚详细，并严格基于此施工。独立 worktree 已建立，源码修改尚未开始。本次不启用 GTO 控制面。

## 已完成基线

- 基础提交 c79d58cb0345a0cb879b2be06073a1ef04962c36；继承 45 个源码文件并记录 SHA-256。
- 主工作区源码、index 和 status 核对未变。
- 两项 schema 基线测试通过；未宣称全套基线通过。
- 已落盘 plan.md 与 acceptance.md，按阶段维护执行记录。

## 施工和返工日志

后续按阶段记录真实派发身份、写入范围、命令、退出结果、证据路径、问题编号和修订原因。失败记录追加保留。

## 施工目标

严格实现 plan.md 第 3—7 节合同，以 A01—A16 为完成标准。

## 前置条件

用户明确授权；独立 worktree 与继承快照已就绪；普通子代理派发，不初始化本次真实 GTO 状态。

## 执行顺序

P1 文档已冻结。P2 实现者与黑盒负责人并行准备；P3 实现整合完成后再派独立 reviewer；随后范围返工、正式黑盒、最终全套及收尾。

## 文档先行清单

plan.md、acceptance.md 已创建。GTO skill/references、治理、workflow 规则、架构/兼容/总纲和运行说明由实现者在完整 review 前同步。

## 测试同步清单

实现者维护 tests/harness/test_gto_workflow.py 与必要既有相关测试；验收者维护冻结黑盒夹具和 runner。reviewer 或验收者发现的问题由各自补证明，修复者不得削弱断言。

## 实施批次

第一批控制器/schema 和真实 Red/Green；第二批指令、模板、规则、正式文档整合；第三批独立 review 的批量修复；第四批黑盒失败按根因返工。每批完成后追加实际结果。

## 每批写入范围

实现者 /root/gto_implementer：plan 第 5 节源码与正式文档、harness 测试；验收者 /root/gto_blackbox_evaluator：tests/fixtures/gto-workflow、必要 tests/benchmarks、自己 .artifacts/.tmp 子目录。主协调器独占本任务三文档。真实平台派发采用 fork_turns=none；工具返回的 canonical task name 如上，身份以平台记录为准。

## 验证命令

范围：PYTHONPATH=tests/harness python3 -m unittest test_gto_workflow -v。最终：python3 -m unittest discover -s tests/harness -p 'test_*.py' -v。规则/文档使用已有 generate_rules_index.py、validate_rules.py、validate_plan_docs.py、validate_doc_routing.py 的实际 CLI 参数。禁止反复全套取代问题定位。

## 回退方案

用 worktree-baseline/manifest.json 与 files/ 区分本次 delta；未进入基线的 tracked 文件对比基础提交。禁止 reset/clean 覆盖继承改动；仅清理本次拥有的临时运行目录。

## 审查与返工路径

实现交付 → 独立 reviewer 一轮尽量列全 → 发现者证明 → 实现/整合修复 → 原 reviewer 范围复审；黑盒失败由验收者先归因再汇报建议修复层与负责人，协调器核定并派发。通过后只同步事实，不追加完整 review。

### P1/P2：方案冻结及派发

- 既有任务文档校验通过：13 个任务目录；路由校验通过：44 个 Markdown 文件。证据：`.artifacts/gto-workflow/coordination/document-preflight.json` 与相邻原始 JSON。
- 唯一实现兼整合者采用 revision3 复用既有候选/attempt 门禁，新增整合、结构化测试结果及发现者证据；未开始全局发布。
- 黑盒负责人验证现有 bwrap 可创建独立 user/pid/mount namespace，隐藏宿主 `/mnt/d` 和 `/mnt/c`，尚未证明完整模型/子代理通路。已授权一次最小通路探针；此探针不是正式新版验收。
- 本任务三文档归主协调器独占，源码与黑盒夹具写入范围分离；正式完整 review 等待实现整合完成。

### P2：黑盒装配与清理回归

- 首次真实平台探针因只挂载 codex 主程序而缺少同版本 codex-code-mode-host，父子工具调用均失败。验收者完成归因，获准补同版本伴随二进制并进行一次范围平台重试；不计新版正式业务验收。
- 主协调器发现 runner 原 finally 在 TERM 后 wait 超时时缺少 KILL/reap，已由主协调器编写 `test_gto_blackbox_runner.py` 两项真实子进程测试，由入口负责人修改 `stop_owned_process`。首次测试运行时并行修复已写入，因此记录为修复后 Green（2/2，0.175 秒），不声称该文件有修复前 Red。证据 `.artifacts/gto-workflow/coordination/runner-cleanup-current.log`。
- GTO 合同实现另有独立真实 Red/Green：旧 schema 拒绝 revision3 合同，新 schema 的初始化用例通过；prose-only completion 漏洞已由实现者失败测试复现。完整闭环尚在实现，不能标记完成。

### P2/P3：平台通路成功与控制器闭环进展

- 范围平台重试通过：父 session `01a0709e-9324-7472-8e45-0d5ea0a9a62e` 实际 shell exit 0，真实 `spawn_agent(fork_turns=none)` 派出 child `01a0709e-d90c-7f10-8adb-f6d366efeac3`，子 session 保存独立 exec 轨迹。证据 `.artifacts/gto-workflow/blackbox/20260905-161017-probe/`。仍只属于平台探针，不是业务验收。
- 回收新增“拒绝调用者共享进程组”用例，三项通过；证据 `.artifacts/gto-workflow/coordination/runner-cleanup-green.log`。
- 控制器真实CLI链已走到验收失败后的复审来源分支，暴露旧分支假设；正在修复，不通过手改 state 绕过。修复后追加整合子任务与范围证据，保持终态不可重开。
- 决定复用既有 sync 安装到空隔离 CODEX_HOME，不扩展真实全局同步，本次不改实际全局安装。已在 plan 修订段明确。

- P3 范围修订：确认两条相关 workflow 规则有固定返工/终审冲突，已将文件加入 plan，第5节由同一实现者同步，随后通过已有生成器刷新索引。

- 实现者报告首批 6 项测试通过（90.876 秒），真实 CLI 串通两 review finding、复审新增 finding、验收业务失败、验收身份归因 finding、修复后新整合、新候选验收与无后置 final 的 finalize。主协调器尚待独立审查，不据此提前判验收通过。
- 黑盒静态安装已改为 namespace 内正常 bootstrap；真实非 strict doctor 返回 ok=true，receipt 使用 /harness 和隔离 CODEX_HOME，未手改。PID namespace 孙进程自然退出回收证明已记录。证据 `.artifacts/gto-workflow/blackbox/20260905-161309-inspect/`。

### P2 完成：黑盒准备交付

- 准备报告 `.artifacts/gto-workflow/blackbox/preparation/feasibility.md`；冻结四个普通业务场景、20 个夹具文件及评分矩阵，评分材料不挂载给被测代理。
- 最新静态链 `20260905-162123-inspect` 完成 bootstrap、doctor、初始历史隔离、空只读 memory 防另建、fixture HEAD、可见 prompt、namespace 回收和 cleanup。五项种子问题探针符合预设；全部只属准备证据。
- 准备者报告两个自有 project-config 夹具一度落错目录，已精确移回授权范围并删除自建空目录；未覆盖其他文件。最终仍需主协调器复核主工作区边界。
- 正式业务黑盒尚未启动；等整合结果独立 review 通过后，先运行 normal，其余仅补明确未触发条目。验收者继续负责各轮归因与集中报告。

### 证据计数更正

验收负责人交叉核对发现，协调器此前称 runner-cleanup-green.log 为“三项”不准确：当次编辑遗漏独立方法定义，将自然退出断言并入共享组 case，日志实际为两项、覆盖三种行为。已恢复独立方法并运行三项测试，真实结果 3/3、0.308 秒，新增日志 `.artifacts/gto-workflow/coordination/runner-cleanup-3cases.log`。先前日志保留；此记录纠正上文用例数，不把旧日志改写为三项。

### P3 完成 / P4 独立完整审查

- 实现者正式冻结控制器 SHA-256 `83bd72e848a2272c8b63ba554b2ab8527eab9565fa9bd9e9f1de54a885d51e19`，最后真实CLI完整闭环 1/1、56.490 秒通过，无后续源码改动。
- 实现交付 23 文件 delta，新增14项确定性行为用例，旧revision2/legacy范围8/8通过。详细报告与逐批失败/通过证据位于 `.artifacts/gto-workflow/implementation/`。
- 主协调器独立汇总本次源码、黑盒入口/夹具及回收测试共46文件，生成 `.artifacts/gto-workflow/review/round-1-input-manifest.json` 和 `round-1-input.diff`；与继承45文件基线区分，不将全部HEAD差异算本次修改。
- 独立 reviewer `/root/gto_reviewer`，真实 `fork_turns=none` 派发；读取合同和基线后对全部本次delta及任务文档集中审查。它独占 `tests/harness/test_gto_review_regressions.py` 写发现证明，不能代修产品实现。
- 整合交付不等于验收通过：完整harness、真实业务黑盒及独立review结论仍未完成。

### P4 首轮结论 / P5 第一次集中返工

- 独立完整 review 为 fail，报告 `.artifacts/gto-workflow/review/round-1-report.md`。46项输入在审查前后无漂移，未启动模型或完整harness。
- R3-001/P1：另一个独立必需 work 未完成也能绑定 integration；独立真实Red成立。
- R3-002/P1：reviewer可执行测试未进入候选；完整CLI证明修改该测试后仍可finalize completed。永久准入回归保留，完整失效证明另存快照，避免互斥断言。
- R3-003/P2：跨项目照用相对控制器路径失败，使用实际skill路径成功；属于继承问题延续到本次新示例，不推断真实模型一定会失败。
- reviewer最终永久新增2项case，另外的完整失效证明存 `round-1-proof-tests.py`，不是第三个永久discover用例。所有Red/等价命令结果已保留。
- 已将完整报告原样交原实现兼整合者，统一修复三项；reviewer独占发现者回归断言，原实现者不得削弱。修复后同一reviewer只复审相关delta与必要范围。昂贵验收继续等待。

### P5 第一次集中返工交付与范围复审

- 原实现者一批修复R3-001/R3-002/R3-003，相对首轮冻结候选9文件delta，未改reviewer断言、runner或夹具。
- R3-001在整合绑定、完成登记和后续门禁检查全部声明work完成；R3-002扩展所有角色写入范围检查，日志仅明确.log普通文件豁免，目录/符号链接/可执行证明不豁免；R3-003从实际加载skill目录定义控制器，与业务root分开。
- 聚焦5/5（20.560秒），最终关联范围11/11（94.480秒），包含原reviewer回归、关联边界、完整失败闭环与legacy；原始日志位于 `.artifacts/gto-workflow/implementation/rework-1/`，主协调器已直接核对输出末尾OK。
- 冻结控制器SHA `774ddb398e72040b2106a087d8593ceea2916d0f69e944cc417b9f3dd501e7e1`；同一 `/root/gto_reviewer` 已收到完整修复报告、delta和manifest进行范围复审。尚未判review通过，正式黑盒和full harness仍未运行。

### P5 第一次范围复审结论 / 第二次范围返工

- 同一 reviewer 独立确认 R3-001/R3-002/R3-003 全部关闭，原问题范围 3/3（8.066 秒），证据 `review/rework-1-original-findings-green.log`。
- 新增 R3-004/P2：普通日志豁免的文件类型限制错误地作用于已显式纳入候选的安全仓库内符号链接。新发现者回归 `test_explicit_candidate_log_symlink_remains_supported` 实际 Red（1 项，0.850 秒）；不重开或重编号前 3 项。
- 已交原实现者仅修复豁免条件，保留未声明目录/链接不可绕过候选的约束。reviewer 回归文件现为 3 项，修复者不得修改。正式验收继续等待范围复审通过。

### 并行任务边界复核

主工作区的 scripts/bootstrap-local.py、scripts/doctor-core.py、templates/codex/AGENTS.global.md、tests/harness/test_wsl_runtime.py 相比起始基线出现后续变化；main index 保持原hash。本worktree这4项均仍与继承基线一致，未同步或覆盖主工作区。记录 `.artifacts/gto-workflow/coordination/main-concurrent-drift.json`；此次验收绑定本worktree候选，最终跨任务合并由用户完成。

### P5 第二次范围返工交付

R3-004仅修改controller候选覆盖判断，hash `09eadd8b1397991e44355a1ac102b94176235313b1684578693ae4214954a39d`。发现者Red 1项（0.769秒），指定Green 4/4（14.160秒），补充两项日志链接边界2/2（1.892秒）；永久reviewer测试未改。补充探针曾误发现导入TestCase，额外案例运行后中断exit130，不计通过批次，原日志和CFM修正保留。原reviewer已接手范围复审。证据 `.artifacts/gto-workflow/implementation/rework-2/`。

### P5通过 / P6开始正式验收

- 同一reviewer关闭R3-004，整体review=pass，四项finding全部关闭，无新增。本轮独立2/2（4.500秒），47项当前文件无漂移，完整审查与两轮范围复审关联保留。证据 `review/rework-2-verdict.json` 与 `rework-2-covered-candidate-manifest.json`。
- 候选冻结后由验收者启动一次normal真实业务黑盒；主协调器同时启动 `python3 -m unittest discover -s tests/harness -p 'test_*.py' -v`，输出 `.artifacts/gto-workflow/final-suite/full-harness.log`，完整源码输入另存candidate-hashes.json。两者独立读取相同候选，不写产品源码。尚未产生最终通过结论。

### P6首次全量：185/186，继承误报VAL-001

完整运行186项739.107秒，1失败；进程总耗时741.370秒，候选无漂移。唯一失败是继承的WSL命令检测把路径片段误报；doctor与测试均与起始基线一致。发现者主协调器补充同一case的真实命令正例/路径反例，最小预期Red已复现，待原实现者修正表达式。保留 full-harness.log、result.json、failure-diagnosis.json、VAL-001-red.log。未称完整验收通过，不重跑full取代定位。

### VAL-001修复与范围复审通过

原实现者仅调整测试正则的后向路径边界，保留发现者两断言；本类2/2（0.039秒）和24个命令形式/8个目录形式核对通过。同一reviewer独立2/2（0.048秒）及24/8边界核对通过，VAL-001关闭，无新增。产品23项及原审查47项无漂移，新审查清单为48项 `review/validation-1-covered-candidate-manifest.json`。这不把原185/186改称通过；待黑盒归因返工收敛后统一最终全量。

### P6 normal自然终态，待独立综合评分

首个正式run `20260905-171719-run` 自然exit0，任务20260905-091911-838082-refund-preview状态completed。runner的cleanup确认temp_removed/process_reaped=true，无强制终止。验收者初步真实轨迹统计：3个子代理（实现兼整合、reviewer、验收兼收尾），1次完整review、1次通过candidate/attempt、无后置完整review。主任务09:18:03.702–09:40:09.154 UTC，22分05秒；业务验收104次CLI合计9.83秒，说明流程/交互成本仍需评估。异常合同/结果填写和CFM边界待验收者集中归因；此处不凭completed判整体验收通过。

### P6 normal集中验收fail与返工派发

验收者完成report.md/findings.json/coverage.json（run/evaluation），BBX-001/P1规则阻塞处理、BBX-002/P2调用说明与控制面试错、BBX-003/P2继承消费CLI入口缺陷。A11 blocked且有不合规继续行为，A03/06—10/14本轮untriggered，其余仅限定范围pass；不以业务completed消除规范失败。两项真实Red/轨迹证明保留。主协调器核定三项批量返工，验收者补消费入口永久测试，原实现兼整合者修复公开约定与入口；不改runner、冻结业务prompt、CFM物理边界或主工作区。

### BBX批量返工进展

BBX-003发现者4项Red为2fail/2pass（1.288秒），证实两个文档CLI同根缺陷；原实现者只修显式消费目录解析，4项Green，未改runtime_common。BBX-001发现既有set-phase blocked入口无法使用，已核定同action的blocked登记/显式原phase恢复与下游拒绝，避免永久死端；发现者补可执行阻塞/恢复回归，原实现者并行完善BBX-002公开示例。

### BBX第一次批量返工整合交付

原实现者冻结controller `41fec694182994deed02b40a73989f6633fcaba58652c7dab3257889913f2c53`，本批15项delta，包含两个消费CLI和新增公开结果JSON参考。BBX-001发现者4/4初步Green（16.291秒），BBX-003发现者4/4（1.332秒），公开示例真实完整CLI链2/2（26.423秒），最终关联8/8（28.515秒，含4项阻塞+4项不同旧版/模板检查）。发现者测试hash未改；文档结构/路由校验通过。结果与全部真实日志在implementation/blackbox-rework-1。原reviewer已收到集中报告及冻结delta范围复审；未跑新模型或第二次full，BBX-001实际行为仍待fresh重验。

### BBX批次范围复审：新增R3-005

原reviewer集中复审fail，仅新增R3-005/P2：根级阻塞白名单遗漏record-acceptance-findings及record-finding-fix，误拒已派发任务的证据回传。两项独立Red（26.135秒）保存于review；永久reviewer测试SHA be725adffe1e1dc77880da346933e13cfd7d2d51c4b6db9245cbc316408cfdde。其余批次delta无独立问题，消费CLI独立4/4（1.406秒），53项覆盖清单无实现漂移。已交原实现者仅修回执保留入口，保持blocked/human_adjudication与新执行拒绝，原reviewer后续范围复核。BBX-001行为仍不据CLI Green关闭。

### R3-005最小修复交付

控制器仅一行白名单补齐两类已有回执，hash `705212eaded595f13a188a5cfffe2d7ec08f03ac2f66a10217d2192ddb1fb056`。发现者2项预期Red（26.152秒），两个新case+4项阻塞范围6/6 Green（45.418秒）。53项中其余52项无漂移，reviewer断言未改。原reviewer已接手最小范围复核，不跑新黑盒或full直到source通过。证据implementation/blackbox-rework-2。

### P6第二次正式验收启动

原reviewer独立2/2（29.046秒）关闭R3-005，53项当前候选无漂移，source ready for fresh blackbox。冻结清单review/blackbox-rework-2-covered-candidate-manifest.json。验收者获准执行原冻结review-boundaries普通业务场景，兼顾正常链与首轮未触发分支；不更改prompt、不传失败提示。主协调器同时执行第二次完整harness，证据final-suite-2，复用本任务已有临时编译缓存而不动共享环境。此次运行针对BBX源码修复后的新候选；首次失败记录不覆盖。BBX-001真实行为未提前判通过。

### 第二轮黑盒：准确blocked，预初始化停链行为通过

run 20260905-183323-run，143.189秒，owner=/root唯一init被identifier格式拒绝；CFM不可达后只保存证据并正确blocked，没有后续控制器动作/子代理/业务改动/state。BBX-001预init分支真实通过；已初始化root blocker/恢复及A06—08未触发，BBX-003公共CLI本轮未调用。53项候选无漂移、进程temp清理。BBX-002新增关联owner值域说明遗漏，已交原实现者只准备两文档补丁，待第二次full结束应用，不放宽schema。完整报告与preinit-blocked-proof位于该run/evaluation。

### 第二次full通过198/198

`final-suite-2/full-harness.log` 实际198项763.796秒全部OK，进程765.681秒，candidate_drift=[]。这覆盖全部代码、schema、测试与当时53项源码候选，含旧revision2和所有发现者回归。全量结束后才授权应用两份owner公开说明，另做实际公开init smoke和文案范围复核；controller/schema/tests不变，因此不重复完整harness，仅后续新鲜模型验收绑定更新后的skill说明。此前185/186失败记录与VAL-001闭环保留。

### owner文档补充已应用

完整198/198后应用两文档合法owner说明，其余51项不变；从当前公开SKILL提取一次init，exit0/oktrue/state.owner=coordinator，consumer已清理。证据implementation/owner-guidance。原reviewer只核对文案与schema，不重复CLI。复核后按plan执行两个互相隔离的必要补场景，重验review-boundaries及首次project-config；无需另一次完整harness，代码/schema/tests未变。

### 最后两项fresh场景并行执行

owner文案范围复核pass，无新增；53项候选除两文档外51项不变。验收者启动review-boundaries=20260905-184952-run，project-config=20260905-185004-run，两次间隔12秒，各有全新隔离项目/state/home/证据目录；fixture未改、没有附加提示。各run独立判定，未自动追加其他场景。完整harness自有node-compile-cache已清理，证据delivery/suite-cache-cleanup.json；未碰正在运行的blackbox临时目录。最新源码相对起始基线的53项delta在delivery/source-task-delta.patch 和 delivery/source-task-delta-manifest.json，不混入继承的无关改动。


### 项目配置黑盒发现根协调器身份兼容缺口

project-config 的真实父级 developer 指令和 list_agents 返回均明确身份为 `/root`。父级按此身份提交 set-phase blocked 的 written_by，被 writerIdentity schema 拒绝；最终文字准确报告受阻，但任务根状态仍 active/doc_sync、next_action=dispatch_ready_subtask，coordinator_blocker 缺失。验收者将其独立登记为 BBX-004，负责最小实际 CLI 证明、身份来源和后续停链核验；不以伪造 UUID 消除问题。review-boundaries 尚未自然结束，当前不修改冻结候选，待两场集中归因后返工。


### 两场自然收口，统一发现者回归阶段

验收者核定 review-boundaries/project-config 两场均自然结束，各53项候选无漂移，自有临时目录清空。review-boundaries真实reviewer记录 REVIEW-001-F001、补测试并两次范围扩展Red，随后协调补丁失败/CFM不可达；project-config完成默认策略恢复及17项业务测试，WORK-001记录blocked。两者没有completed冒报，但根阻塞登记均因BBX-004失败而分别留active/review及active/doc_sync。验收者负责把最小证明追加到原有独占test_gto_coordinator_blocking.py；产品源等待Red和集中报告后修改。


### BBX-004集中返工已放行

验收者完整核定两场新增需修复的GTO源码问题只有BBX-004；review-boundaries的REVIEW-001-F001为被测业务缺陷，保留原ID及修复路由，不扩展本次GTO源码范围。其他命令异常与CFM边界均保留，没有原失败链重试或completed冒报。发现者永久新增2项case，实际预期Red exit1，测试SHA `390ea481a1e2b3365e91597665999951f8fef0cd0bfb6b8e0deadb2f12957f5d`；证据project-config run/evaluation/bbx-004-permanent-red.json及.log。原实现者获准只修改schema两pattern及两份身份说明，保留finder断言与controller不变，执行范围Green后交原reviewer。


### BBX-004修复交付与有限重验决定

原实现者仅修改schema两pattern及SKILL/state-schema说明共3文件，schema SHA `ad6bf68cf176bc7190899748657411d63055ab61fc12b7805da805514fb64a71`，controller不变。发现者2项Green（4.467秒），原block4项+legacy revision2派发/回执1项共5/5（21.114秒）；原Red保留，53项候选中相对此轮输入另外50项不变。原reviewer正在范围复核。

验收者指出，前两场由偶发命令错误触发CFM阻塞；再次运行任一普通场景不能保证覆盖root阻塞，反复重跑会成为随机挑样。主协调器接受其有限重验建议：不再为命中BBX-004追加模型轮；身份修复使用真实来源证据、永久CLI阻塞/同身份恢复和范围复审验证。真实模型成功登记/恢复仍列覆盖受限，不把旧候选的模型轨迹冒充最新schema的完整行为通过。最终全量仍按plan对最新源执行。CFM外部不可达和未走完的业务验收如实保留，不放开宿主历史、另建库或引入新桥接。


### 最终源码范围复审通过，第三次全量启动

同一reviewer关闭BBX-004，独立2/2（5.122秒），无新增，53项覆盖清单无漂移，发现者断言未改；报告review/bbx-004-review.md，冻结清单bbx-004-covered-candidate-manifest.json。最终全量使用标准unittest discover命令，153项源码输入hash保存于final-suite-3/candidate-hashes.json，测试输出独立保存；不覆盖前两次全量记录。后续只更新本任务事实文档和交付/清理证据，不再安排后置完整review。


### 实际耗时的解释边界

四场模型任务按父任务起止时间分别为normal 1325.452秒、预初始化blocked 143.189秒、review-boundaries 1022.860秒、project-config 704.544秒。后两场并行，不能相加当作用户等待时间；提前blocked的短运行也不能当作性能改善。normal的业务验收104次CLI合计9.830036秒，而模型协调全链约22分05秒，说明代理交互/控制面仍有明显成本。本次没有同任务旧版GTO对照，不宣称耗时降低比例；各run成本文件保存累计输入/缓存/输出用量，累计上下文token不是单次窗口或货币账单。


### P6最终全量通过 / P7事实收尾

最终标准full实际200/200、798.771秒，进程800.920秒，exit0；153项输入candidate_drift为空。证据final-suite-3/full-harness.log与result.json。当前53项源码delta基于bbx-004最终review清单重建，git apply --reverse --check只读检查exit0，没有应用补丁。已清理结束的final-suite-3自有node编译缓存，四场黑盒各自进程/临时项目此前均已回收，必要原始prompt/hash/10份trace/失败证明和报告保留。

验收汇总事实链接纠正：green-lifecycle.log为历史5项1失败尝试，不能列作通过依据；成功生命周期链接改为final-candidate-loop.log（1/1、56.490秒），旧失败原文保留。当前确定性源码检查及独立review已通过，但模型未触发分支与CFM外部阻塞仍未关闭，不标完整黑盒验收通过、不发布真实全局、不提交合并。


### 最终文档、规则与边界回执

现有文档结构/路由CLI均通过：13个任务目录、44份Markdown，无错误/警告；规则校验25条通过。53项审查源码与153项全量输入最后hash复核均无漂移；继承的范围外文件未改，主仓库暂存区hash未变，其4项并行修改保持原样。`.tmp/gto-workflow/` 已为空，只回收本任务自有临时内容及空目录。最终回执 `.artifacts/gto-workflow/delivery/final-boundary.json` 汇总原始校验结果、源码边界和清理；未新增后置review、模型轮、Git提交或全局安装。


### 用户要求继续：CFM测试环境恢复

用户确认继续补验收。根只读确认实际CODEX_HOME为/mnt/c/Users/Laptop/.codex，候选CFM helper的inspect能访问原同一物理库（ok=true，index存在）；未输出case正文。阻塞来自bwrap不挂载历史，与宿主库故障不同。已追加六要点和最小受限通道方案，保留先前200/200、53项review候选及四场失败/受限结论，开始新一轮环境修复。CFM接入批次前像保存于.artifacts/gto-workflow/cfm-access/baseline.json和before，不复制CFM经验库。


### CFM发现者Red与实现派发

验收者新增test_gto_blackbox_cfm.py四个实际CLI/socket用例。原helper在显式空/非法/断链endpoint下仍走本地成功并建库，三个子例Red成立；其他三个case因新server入口尚未实现而Red，不能混称已验证服务协议缺陷。首轮4case/6失败断言、1.622秒；根核到host_home被错误列入拒绝selector，与已批准三合法selector冲突，由原测试作者更正，产品落盘前再次Red为1.705秒、同4case/6失败，原日志保留。当前测试SHA93647a31cd05419b72cfe5bdcd23485718d6b7126dacbf2ab71005393029c7b5；更正selector断言仍待Green执行，不能凭缺入口Red判其已被覆盖。实现者仅写产品及通道，不修改这些断言。

原验收者建议本轮先运行冻结review-boundaries，完成最新候选的实际完整链，并观察此前CFM截断的finding/返工；收口后按缺口决定是否执行既有entry-precision，每个候选每场一次，遇新源码缺陷先返工再重新冻结。小任务仍允许单实现者兼整合，不能为覆盖条件分支强行增加代理或故意留错；交付核心缺口是最新源码/隔离安装的至少一条真实完整链，以及接通后的CFM真实动作和隔离证明。


### 用户简化验收条件，CFM通道已撤回

用户要求黑盒明确禁止CFM，根立即停止实现。原实现者确认6项既有文件和server新文件，finder另1新测试，无活动进程/后台写入；本批new-green为4case/1pass/3fail，均在readiness前退出。根按cfm-access/baseline恢复6文件并删除两新源文件，撤回patch与回执保留；53项原review候选无漂移。CFM helper、GTO产品源、runner均恢复上一轮通过状态。

四个普通业务prompt仅统一增加CFM禁止条件，README说明评测边界，manifest只更新README和4prompt项；业务夹具未改。新条件不透露GTO施工规范答案；新黑盒将明确标注CFM-disabled，不再以CFM不可达阻断该测试，也不声称CFM联通已验证。原库及真实全局配置均未改。


### CFM-disabled范围复核通过，真实续验放行

原reviewer最小复核pass无新增，确认4prompt去掉统一环境句后与旧原文hash一致，README明确条件、manifest正确；53项仅6个授权评测文本变化，其余47项不变。根核153项全量输入也只有这6文本变化，产品/测试/runner/业务夹具代码无漂移，200/200结果可按此范围复用，不再重复整套测试。冻结review/cfm-disabled-covered-candidate-manifest.json，证据blackbox/cfm-disabled/full-suite-reuse-binding.json。已交原验收者启动一次fresh review-boundaries，CFM动作必须为0，其他完整流程照原标准；未授权自动追加下一场。


### CFM-disabled真实返工链进展

本场 `20260905-201852-run` 已自然出现真实 review finding，随后派发修复、再整合、交回原 reviewer 复审，并冻结候选进入验收。外层未给被测代理追加分工或修复提示。期间回执结构及最新 review brief fingerprint 的拒绝由被测协调器根据当前证据处理；具体是否属于产品缺陷，由验收者在自然收口后结合父子 trace 集中判定，不凭单次非零退出码提前定性。此时尚不宣称最终验收通过。


### CFM-disabled续验最终收口

独立验收者完成本场逐项评分与五场汇总，原四场 aggregate 原样保留历史快照。本场 CFM 动作 0，初始实施、整合、一个完整 review、发现者 18 子例有效 Red、原实施者修复、再整合、原 reviewer 范围复审、一个候选的一次正式验收及事实同步均有实际轨迹。验收的 15 测试方法和 118 CLI 用例通过，119 次调用计 22.712711735992343 秒；整条业务链的小套件共执行 5 次，不能声称没有重复测试成本。模型轨迹 1779.452 秒，不能据此给出新旧提速比例。

外层发现者对保存的订单业务候选最小复现 BBX-BIZ-001：5001 位合法输入及产生 6001 位结果的合法输入被 Python 转换限制拒绝。冻结业务合同无位数上限，故业务全范围验收 fail；验收者未发现新增 GTO 源码缺陷或硬规范违反，根据此保留业务失败与条件分支覆盖限度，不扩展为订单产品修复，也不追加抽样模型。三份施工文档明确区分流程 pass 与业务 fail；完整原始报告和复现脚本保留。

最终可执行源码沿用 200/200 全量证据及六份评测文本变化的复用绑定；独立审查覆盖 53 项无漂移，继承的范围外文件无漂移。五场自有进程/临时项目已清理，保留共 14 份必要父子 trace。主仓库并行变化保留，未全局发布、提交、合并或推送。收尾只做文档结构/路由、规则校验、边界与事实检查，没有后置完整 review。
