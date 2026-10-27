## 最终文档查漏后的当前事实

外层同一验收者已判范围复验通过，本次唯一文档查漏已完成，等待主协调器最终核对；根任务仍为 active，不标 completed。下方阻塞、待投放、待复验和运行中记录均为各阶段历史，当前结论以本节及最终证据为准。

新顶层 thread `01a085b9-1dee-79e3-93aa-3063ed9c04f2` 使用新 fixture 和当前默认候选，3 次 `fork_turns="none"` 成功返回身份并正确绑定；完整首审、唯一首次 full acceptance 和内部单文档角色收尾已实际完成，外部 8 项业务检查通过。该场景是正常显式 skill 选择、无流程答案、共享文件系统的原生上下文隔离测试，不证明严格物理隔离或隐式自动触发。旧同顶层续轮为 excluded，不计入通过证据。

ACC-ISO-001 已关闭；ACC-DOC-OWNER-002 依据默认安装 9 项机械保护验证及全新正常流程回归关闭。新行为场景中的 finding 返工、验收失败后直接复验仍为 untriggered，不将正常实现分工冒充失败分支覆盖。旧失败 trace 和裁定保留。Computer Use 对本 CLI 产品不适用；CLI 证据不代表 GUI 操作通过。全局黑盒测试原则已发布并校验通过。

最终验收证据：`.artifacts/review-acceptance-routing/acceptance/repair-component-fresh/adjudication.md`。最终默认 skill/schema 子集：`5ebba5d5ebd4251db1bbf24d290c0128a9b2c773ab572ad38a47a91bebe8f38c`；投放证据为 `deployment/doc-owner/verification.json`（本轮13个非选中受管文件有前后对照，113个历史清单仅与当前作历史对照）。本次文档查漏证据：`.artifacts/review-acceptance-routing/final-doc-sweep/handoff.md`。

# 任务合同

本次为用户批准的手工协调施工，六工件记录事实，不调用GTO控制器维护本任务。

## do

统一初始测试委派、发现者根因与测试文档责任、整合返工、review与验收独立闭环，并验证默认安装的无提示实际行为。

## do_not

- 本次不调用GTO编排
- 不提交合并或覆盖既有未提交改动
- 不修改无关Windows能力实现
- 不把模拟回执当真实黑盒通过

## change_areas

- docs/SUBAGENT_GOVERNANCE.md及相关规范
- rules/items/workflow及相关policy、registry
- skills/global-task-orchestrator
- schemas/orchestrator-task-state.schema.json
- templates/orchestrator及示例
- tests/harness和必要黑盒夹具/runner
- 本次六工件和获审后默认安装区域
- scripts/sync-codex.py：仅GTO投放选项，保留其他受管内容及回执

## implementation

文档先行和六工件；并行测试子代理；唯一整合实施；完整首审与范围复审；通过后统一投放；新进程无提示完整黑盒；验收失败直接整合返工与范围复验；单文档子代理收尾。

## acceptance

- 初始测试委派写入隔离、全部work后整合送审
- 发现者定位根因给方案补失败证明及同步文档，整合者独占代码返工
- 完整首审和范围复审，首次验收始终全范围
- 验收失败修复后直接复验，不回review；有效覆盖全部验收项
- review和验收实际使用证据，WSL网页Browser、Windows GUI仅native
- 源码review后投放默认区并校验同候选，fresh无流程提示黑盒真实轨迹验证
- 单文档子代理验收后查漏同步，实质变化返回验收

## risks

- 既有dirty工作受保护，仅改授权范围
- machine doctor发现既有Windows runtime/global入口漂移，默认部署验收前需解决；项目doctor通过
- 黑盒未触发分支不得冒充已覆盖，缺失必需能力如实阻塞
- 源码候选与默认安装需hash一致，新进程消除热更新误判

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
