## 最终文档查漏后的当前事实

外层同一验收者已判范围复验通过，本次唯一文档查漏已完成，等待主协调器最终核对；根任务仍为 active，不标 completed。下方阻塞、待投放、待复验和运行中记录均为各阶段历史，当前结论以本节及最终证据为准。

新顶层 thread `01a085b9-1dee-79e3-93aa-3063ed9c04f2` 使用新 fixture 和当前默认候选，3 次 `fork_turns="none"` 成功返回身份并正确绑定；完整首审、唯一首次 full acceptance 和内部单文档角色收尾已实际完成，外部 8 项业务检查通过。该场景是正常显式 skill 选择、无流程答案、共享文件系统的原生上下文隔离测试，不证明严格物理隔离或隐式自动触发。旧同顶层续轮为 excluded，不计入通过证据。

ACC-ISO-001 已关闭；ACC-DOC-OWNER-002 依据默认安装 9 项机械保护验证及全新正常流程回归关闭。新行为场景中的 finding 返工、验收失败后直接复验仍为 untriggered，不将正常实现分工冒充失败分支覆盖。旧失败 trace 和裁定保留。Computer Use 对本 CLI 产品不适用；CLI 证据不代表 GUI 操作通过。全局黑盒测试原则已发布并校验通过。

最终验收证据：`.artifacts/review-acceptance-routing/acceptance/repair-component-fresh/adjudication.md`。最终默认 skill/schema 子集：`5ebba5d5ebd4251db1bbf24d290c0128a9b2c773ab572ad38a47a91bebe8f38c`；投放证据为 `deployment/doc-owner/verification.json`（本轮13个非选中受管文件有前后对照，113个历史清单仅与当前作历史对照）。本次文档查漏证据：`.artifacts/review-acceptance-routing/final-doc-sweep/handoff.md`。

# 施工目标

统一初始测试委派、发现者根因与测试文档责任、整合返工、review与验收独立闭环，并验证默认安装的无提示实际行为。

# 前置条件

用户已批准。项目doctor通过；现有安装漂移记录在CFM，未绕过为通过。

# 执行顺序

文档先行和六工件；并行测试子代理；唯一整合实施；完整首审与范围复审；通过后统一投放；新进程无提示完整黑盒；验收失败直接整合返工与范围复验；单文档子代理收尾。

# 文档先行清单

docs_contract子代理先同步规范；主协调器先写六工件。独立测试先按需求冻结行为合同并交付Red；随后由整合者实施并统一核对JSON合同示例与schema，未将提前字段设计作为测试答案。

# 测试同步清单

测试A负责测试委派/整合路由；测试B负责发现者合同/验收独立循环和证据；文件不重叠，共享fixture单写入者。

# 实施批次

文档 -> 测试 Red -> 整合 Green -> 完整review及范围返工 -> 默认投放 -> 黑盒 -> 单人文档收尾。

# 每批写入范围

文档子代理仅规范Markdown；测试A/B各自新文件；整合子代理controller/schema/JSON及必要测试适配；主协调器仅本次控制工件与证据、获审后的投放。

# 验证命令

先运行独立新增unittest最小目标并声明预期Red；随后tests/harness相关GTO套件、validate_plan_docs.py、validate_doc_routing.py、validate_rules.py；实际命令与证据随后追加。黑盒按已核对runner能力冻结后执行，不预报通过。

# 回退方案

既有差异保留在.artifacts/review-acceptance-routing/baseline/preexisting.patch；不回滚他人内容；投放备份按文件核验恢复。

# 审查与返工路径

reviewer完整首审，发现者复现根因方案测试文档->同整合者->范围复审；首次验收全量；验收失败同样发现者交付->同整合者->重新投放->同验收者范围复验，不回review。所有独立检查尽可能执行；未触发必须标记。

# 阶段事实

文档子代理完成18个相关规范文件的同步；主协调器核对格式检查通过。初始测试A/B各写独立测试文件，整合子代理暂停，待全部真实Red交付后恢复。控制器/schema/JSON示例修改前hash核对未变。

测试阶段已交付：A 13项，13个失败断言（含subTest）且0 errors；B 23项，20个独立Red目标和3个现有正向/安全对照。A七项CLI在新字段门禁先失败，其后续路径须Green后实测；B验收返工全链在旧门禁下尚不可达，不能以函数证据代替端到端验收。全部交付后才于控制events记录并启动整合实施。

文档与规则验证：generate_rules_index.py输出25条；validate_rules.py通过；validate_plan_docs.py覆盖18个任务目录通过。现有Codex CLI为0.153.4；版本信息只用于本次黑盒启动取证，不代替能力验证。

投放边界补充：现有sync-codex默认全量同步含另一任务Windows bridge。为满足本次限定GTO投放、保留无关dirty的已批准约束，由整合者先补Red后新增显式仅GTO选择并保留receipt其它记录；默认全量语义不变，此增量一并独立review后使用。

## 完整首审与第一轮返工

完整首审发现5项问题。RAR-003由发现者修正文档，其余RAR-001/002/004/005在根因、方案、独立失败测试和文档全部交齐后，统一派给原整合者返工。未投放。reviewer继续为已识别的runner隔离环境启动阻塞补充独立Red与最小修复合同，测试交付前禁止提前修改runner。

## 用户要求分支隔离

收到“再开一个分支，在其中改造”后，创建 `codex/gto-review-acceptance-routing`，工作区为 `/mnt/d/prj/harnesss/dev_vibecoding/.worktrees/gto-review-acceptance-routing`。44份任务候选、必要继承依赖与证据已按hash迁移，原工作区不回退、不再写入。两份外部sync漂移单独保留为继承基线；当前由同一reviewer在新根范围复审，未投放。新根独立标准库venv与项目doctor通过；默认安装doctor复核尚未结束，不宣称环境健康。

默认machine doctor复核exit1：GTO未投放造成预期源/安装差异，另有既有Windows能力配置/schema、doctor/runtime_common和全局AGENTS/bootstrap漂移。项目doctor通过。此次CFM查询因命令文本签名不同返回query_permitted=false，主协调误在同批执行了只读复核；已如实记录，后续须读查询结果后再决定重试，不计合规通过。默认环境未修复，禁止忽略漂移直接黑盒。

## 范围复审通过与限定投放

同reviewer的7+3+4项独立复审通过，RAR-001至006已关闭。投放前重新核对主根、分支和获审11文件hash一致，依照原“review完成后统一投放”授权，从登记主源入口仅同步GTO及schema。默认9文件与候选一致，113未选文件hash/mtime不变，其他skill receipt保留，主根源码没有写入。随后派独立验收者执行首次完整验收，默认系统既有漂移仍不等于已修复。

## 默认环境变化后继续真实黑盒

独立验收者最新默认machine doctor exit0，既有漂移已由外部状态变化解除，本任务未修无关runtime。先前“全部写入只在新根”的主协调自设限制收窄为源码施工只在分支：为使用已审且同hash登记主源runner，允许其仅在主根规则允许的 `.artifacts/gto-workflow/blackbox/<本轮runid>` 和 `.tmp/gto-workflow/blackbox/<本轮runid>` 生成测试产物，并归档到分支；不改主根源码或配置、不增加runner输出功能。首次真实无提示黑盒继续。

## 本轮停止点

新分支施工与复审、限定默认投放已完成；首次独立验收的默认CLI/环境/隔离通过，真实模型黑盒传输blocked。未提交/合并，未修改系统网络，未启动最终文档代理。后续从验收复验继续，不重新进入review循环。

## 原生上下文隔离测试观察

仅普通业务输入的小任务与跨模块任务均观察到未选择GTO，因此不能据此评价skill内部流程通过。另一次确实读取默认GTO后，由于native子代理未继承CODEX_HOME，误选HOME下运行时而阻塞；后续项目只补实际运行时目录声明，无流程提示。当前案例显式选择默认安装skill（与用户常规选择skill相同），不告知角色或流程步骤。夹具初始缺HEAD导致prepare-workspace被正确拒绝，主协调仅为7份原始输入准备人工测试仓库基线，外层仓库HEAD未变。原隔离子代理恢复同一任务、完成CFM闭环，已真实派出initial_tests；当前正在等待初始测试，尚未派实施和整合。自动选择入口与选中后执行规范分别评估。

### ACC-ISO-001 定向投放与 fresh 复验

原整合者完成两份运行时入口修复；独立入口测试 2/2 Green。登记主源原哈希保护后仅同步两份自有文件，定向投放默认 GTO；9 份安装文件全部匹配新候选，113 份非选中文件 hash/mtime 不变。真实复验已派发 `/root/merchant_fresh`，`fork_turns="none"`；只有普通业务需求和正常 skill 选择，无流程答案。初始 fixture HEAD 和 CODEX_HOME 已准备。旧失败证据保留；实际行为结论待同一验收者裁定，不返回 review。

## 历史阶段：最新直接复验状态

同一验收者直接复验：默认9文件匹配ACC-ISO新候选，入口合同2/2 Green。fresh真实initial_tests调用显式fork_turns="none"，但平台返回agent thread limit reached，没有成功子代理身份；state已blocked，六子任务全部ready且dispatch为空。已证明正确参数被实际采用，未证明成功隔离身份及其绑定，ACC-ISO-001保持pending_behavioral_retest，完整验收blocked_platform_capacity。旧all派发失败证据保留；未启动新review、后续验收或文档收尾。恢复条件是平台有足够可创建独立代理的容量，再由同一验收者用普通业务输入直接复验；不得父层代评审、伪造身份或改旧证据。

### 追加授权：全局黑盒测试原则与恢复验收

用户明确要求新增一条规则后继续原任务。新增全局 model_decision 规则，说明默认安装及环境容量预检、显式/隐式分测、新顶层会话与上下文/记忆/文件隔离差异、真实轨迹评分、分项结论与范围复验。原整合者写规则并刷新索引；同一验收者先检查独立 CLI 顶层通路与代理回收能力，避免继续消耗原施工树容量。网络或容量前置失败先保存独立环境证据，不计业务通过。遵循原验收返工链，不重新开启 review，不提前文档收尾。

### 全局黑盒测试原则完成

新增 `global.workflow.黑盒测试原则`，按语义选取，不强制小任务启动GTO。原整合者编写，同一验收者独立审读通过。工作树与登记主源分别由既有生成器刷新索引；26条规则，0 errors、0 warnings。仅新增该规则，登记主源其他25条规则字节未变，默认全局AGENTS已指向该索引。规则完成不代表原GTO黑盒通过；独立CLI容量/通路预检仍在处理中。

### 历史阶段：最新恢复条件

黑盒规则已完成独立语义验收和默认全局源投放。原GTO完整验收仍未完成：原生施工树容量不足；新顶层WSL CLI在120秒内无模型内容，有界终止并清理，独立网络观察为DNS成功但TCP未建立，未到TLS/HTTP。未继续昂贵业务重跑。桌面新顶层业务prompt和干净Git fixture已准备，create_thread工具要求明确新建任务授权，等待用户该项授权后继续，由原验收者在被测树外评分。ACC-ISO-001仍pending_behavioral_retest，不返回review，不提前文档收尾。

### ACC-DOC-OWNER-002：发现者文档责任越界

桌面顶层黑盒完整运行后，外部验收者发现reviewer以文档N/A附带让整合者补说明，原整合者实际在finding返工修改正式contract；控制器沿用其历史整合宽写域而接受。它是流程责任违规，不能降为未触发。发现者负责根因、失败测试及治理文档；测试与方案齐备后才启动原整合者代码修复。原隔离修复成功证据单独保留；整体不得提前文档收尾。修复后同一验收者做范围复验，不回review，不重复全部业务链。

## 历史阶段：当前修复复验事实

桌面顶层业务主链已真实完成，4次none成功派发和绑定已独立验证，ACC-ISO-001关闭。ACC-DOC-OWNER-002责任违规保留；原整合者已完成修复，待限定投放通知后由同一验收者对默认controller直接范围复验，再进行已准备的小组件续轮。当前施工仍未完成，不进入review，不提前最终文档收尾。

## 默认安装定向验证

ACC-DOC-OWNER-002限定投放后，默认9文件独立hash一致；同一验收者运行默认controller的9项定向验证全部通过（130.952秒），含发现者文档/测试保护、点路径与symlink变体、合法产品代码和runtime Markdown、验收直接复验及文档收尾。机械修复已通过，仍待原桌面任务小组件真实续轮；不提前关闭问题，不进入最终文档收尾。

## 全新顶层最终范围复验

同一验收者已完成全新顶层quantity黑盒：独立新thread/新fixture/当前默认候选，3次真实none成功派发与身份绑定、完整首审、唯一首次全量验收、单文档角色收尾均核对；外部8项业务全部通过。ACC-DOC-OWNER-002依据默认9项机械保护Green和全新正常流程回归关闭；新场景finding返工及验收失败直复验未触发，明确不称真实分支通过。旧同对话续轮excluded，旧失败保留。当前可进入外层单文档查漏，施工仍active、未completed。
