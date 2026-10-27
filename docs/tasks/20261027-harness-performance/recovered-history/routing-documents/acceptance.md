## 最终文档查漏后的当前事实

外层同一验收者已判范围复验通过，本次唯一文档查漏已完成，等待主协调器最终核对；根任务仍为 active，不标 completed。下方阻塞、待投放、待复验和运行中记录均为各阶段历史，当前结论以本节及最终证据为准。

新顶层 thread `01a085b9-1dee-79e3-93aa-3063ed9c04f2` 使用新 fixture 和当前默认候选，3 次 `fork_turns="none"` 成功返回身份并正确绑定；完整首审、唯一首次 full acceptance 和内部单文档角色收尾已实际完成，外部 8 项业务检查通过。该场景是正常显式 skill 选择、无流程答案、共享文件系统的原生上下文隔离测试，不证明严格物理隔离或隐式自动触发。旧同顶层续轮为 excluded，不计入通过证据。

ACC-ISO-001 已关闭；ACC-DOC-OWNER-002 依据默认安装 9 项机械保护验证及全新正常流程回归关闭。新行为场景中的 finding 返工、验收失败后直接复验仍为 untriggered，不将正常实现分工冒充失败分支覆盖。旧失败 trace 和裁定保留。Computer Use 对本 CLI 产品不适用；CLI 证据不代表 GUI 操作通过。全局黑盒测试原则已发布并校验通过。

最终验收证据：`.artifacts/review-acceptance-routing/acceptance/repair-component-fresh/adjudication.md`。最终默认 skill/schema 子集：`5ebba5d5ebd4251db1bbf24d290c0128a9b2c773ab572ad38a47a91bebe8f38c`；投放证据为 `deployment/doc-owner/verification.json`（本轮13个非选中受管文件有前后对照，113个历史清单仅与当前作历史对照）。本次文档查漏证据：`.artifacts/review-acceptance-routing/final-doc-sweep/handoff.md`。

# 验收目标

验证新版规范及机械门禁，并由默认安装入口的全新被测进程自动遵守。

## 验收标准

- 初始测试委派写入隔离、全部work后整合送审
- 发现者定位根因给方案补失败证明及同步文档，整合者独占代码返工
- 完整首审和范围复审，首次验收始终全范围
- 验收失败修复后直接复验，不回review；有效覆盖全部验收项
- review和验收实际使用证据，WSL网页Browser、Windows GUI仅native
- 源码review后投放默认区并校验同候选，fresh无流程提示黑盒真实轨迹验证
- 单文档子代理验收后查漏同步，实质变化返回验收

## 必备证据

真实Red/Green、独立review、默认安装hash、普通业务prompt、新进程真实代理工具轨迹、Browser操作证据、各分支覆盖及清理回执。证据放.artifacts/review-acceptance-routing/。

## 未决项

既有运行时漂移待发布前核对；真实黑盒尚未执行。

## 最终结论

同一验收者已判最终范围复验通过，唯一文档查漏完成；根任务等待主协调器最终核对，尚未标completed。

## 黑盒隔离与覆盖合同

被测输入只包含普通业务目标、业务验收条件及已授权范围，不点名GTO、不提示测试代理/整合/review/验收顺序，不包含评分表、预期finding、修复建议或本任务施工文档。允许正常加载默认已安装skill和规则。评分者与被测者使用独立上下文；必须证明历史、评分和施工材料对被测进程不可读。

验收先核对投放后默认区域hash，再由新进程实际消费该安装内容；仅复制源码重装到临时区域不算默认安装证明。隔离环境若映射默认安装，须保留来源与逐文件hash映射。真实行为检查含：初始测试真实委派与文件隔离、全部work后整合、首次review完整独立检查、发现者问题合同与固定整合修复、首次全量验收、验收失败直接复验、单文档子代理查漏同步。未触发分支单独列明并追加独立场景，不能以controller模拟测试替代行为覆盖。

本产品GTO为CLI/skill流程，验收须真实调用CLI及真实代理，不虚构GUI。UI证据门禁通过针对性合同测试验证；如黑盒业务场景含网页则必须实际Browser操作并单独留证。无Browser能力时该UI场景不得判通过，也不在WSL调用Computer Use。

保留完整输入、候选和安装hash、真实派发身份/隔离参数、每次命令结果、finding及修复/复核关联、验收条目覆盖、未执行原因及本轮进程/临时数据清理记录。独立检查逐项记录，单个可隔离失败不跳过后续检查。

## 本轮实际验收结论：blocked

源码范围复审通过后已限定投放默认GTO/schema，9份默认文件hash一致；独立默认machine doctor和隔离namespace doctor通过。默认controller/schema上37项测试、117次真实CLI动作通过；真实GUI不适用于本CLI产品，UI只验证结构门禁。fresh普通退款输入已真实发起，但5次WebSocket超时和HTTPS回退后仍等待网络，0模型内容/工具执行，因此所有模型自发流程覆盖仍blocked，不能以确定性测试代替。

只回收本轮runner及其拥有的进程组，cleanup三项均true；保留完整原始输入、安装来源、网络事件和会话证据。验收发现者修正ACC-DOC-001纯文档残留并刷新仅README对应的fixture manifest。未启动验收通过后的单文档收尾。恢复同等隔离模型连接后，需重新运行普通业务场景及必要补充场景，按既定直接复验路径继续。详见 `.artifacts/review-acceptance-routing/acceptance/handoff.md`。

## 用户调整黑盒方式：原生上下文隔离子代理

用户明确指出可直接派遣上下文隔离子代理消费默认skill，因此新增原生 `fork_turns=none` 普通业务任务，不继承父对话、不提供GTO/角色/流程顺序指令。默认GTO8文件及schema再次与获审候选hash一致。新测试使用独立临时订单项目和git根，测试对象只收到退款业务需求、项目路径和实施授权；项目AGENTS只含普通入口与全局规则真源。当前平台仍共享文件系统，此方式不宣称OS文件系统隔离。此前CLI传输失败保留为独立历史，不阻断此原生模型行为验证。

## 原生行为验收发现 ACC-ISO-001

默认skill被正常选择后，已观察实际TEST Red→WORK Green→原实现者INTEGRATE。独立reviewer创建因平台线程数限制失败，后续流程blocked。另经同一验收者独立确认：两个成功新代理实际fork_turns=all，TEST/WORK/INTEGRATE三条却宣称isolated，违反现有治理契约。发现者已写真实trace可执行Red与2项默认入口合同Red，补根因、方案及正式文档。已统一交原整合者修默认skill载荷，完成后直接fresh复验，不重进review。完整证据在 `.artifacts/review-acceptance-routing/acceptance/native-isolation-finding.md`。

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

## 文档查漏验证边界

计划文档校验及26条规则校验通过；routing输出中本任务及全部13个task文件检查通过。全仓routing唯一失败为范围外wsl-environment模块缺contract/design/delivery骨架，已记录CFM `d0237898c83ddcbd72cebda6bb31b838bac52edf113b13dd3d1070028d94a4f5`；未扩范围补其他模块，不能将全仓文档校验报告为通过。详见final-doc-sweep/routing-validation.json。
