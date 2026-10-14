# Portable Harness 执行记录

## 授权与范围
2026-10-14 用户批准按方案实施，要求文档/测试先行、TDD、真实子代理 review 和验收循环，根代理持续自检。只在 javirs 指定隔离工作区推进；父会话必要核验及最终复查。本工程不使用 GTO 编排。
## 当前阶段
P0–P4实现及P6固定包Review完成；当前交付候选为bb17b02f54fe。旧全量31条失败记录均已有对应目标Green，原全量失败事实保留。Windows/WSL普通Python最终验收完成，原验收者签署部分验收；根复查完成并交付复审。独立Linux、新会话、云端、真实GTO流程、许可及父会话最终复查尚无通过证据。
2026-10-14 当前续接聊天从既有计划、规格和实际 javirs 工作区找回任务。用户在本聊天再次明确确认“按原计划使用独立子代理”；没有重建 GTO 控制面。当前公共接口唯一真源为 ../../modules/portable-harness/contract/README.md。
## 执行连接证据
此前终端创建报 exec-server initialize handshake timeout；后续一次文件读取成功，其后报 transport disconnected。WSL 核查未取得成功输出；不得称权限拒绝、审批安全拒绝或产品 Red。

本轮已核实 C:/Windows/System32/wsl.exe、Ubuntu-24.04 与同一路径映射，连接恢复。独立工作区原缺 .venv，按原 requirements.txt 建立本工作区 Linux venv（Python 3.12.3，jsonschema 4.26.0）；已安装 project-env-doctor 返回 ok=true。机器 environment-only doctor 返回 ok=true、runtime_verified=false，不能推导 GUI 或会话通过。原 checkout 未作交付写入。Git start 检查器因既有 config/ai/git-policy.json 缺失返回 CONFIG_INVALID，未新造项目策略；人工核实分支 javirs、HEAD=87d7255、原有 design 修改与任务文档。
## 责任与身份
- 实现及跟进：/root。
- 旧独立测试契约设计：/root/portable_test_contract，当前进程无此活跃代理，不沿用未取得的测试结果。
- 本轮独立测试：/root/portable_tests，fork_turns=none，只写 tests/portable，PRV-09 另获准同步两项旧 hooks 测试。
- 文档同步：/root/portable_docs，fork_turns=none，只写明确文档范围。
- GTO 比较及单真源实施：/root/gto_convergence，fork_turns=none，限定 GTO 真源/生成物/专门测试范围；不担任正式 Reviewer。
- 独立 Reviewer：/root/portable_reviewer，fork_turns=none，未参与实现。已独立发现、复验关闭 PRV-01–09，完成固定候选 6aec84bcbce0 的源码与包整体 Review；后续修复仍由同一身份复验。
- 独立验收者：/root/portable_acceptance，fork_turns=none，未参与实现、测试设计或 Review；按 acceptance-plan.md 实际执行隔离接收者验收，不能以 Review 代替验收。
## 变更与裁决
最新批准替代规格中的待确认条款；GTO 是被测产品而非工程编排器。原 checkout 不写入；不修改全局安全配置或凭据，不 push/publish/merge。
## TDD 与回归证据
原始输出在 .artifacts/portable-harness/20261014/：p2-red.log 为15项缺失接口失败；p3-red.log 为27项缺失接口/CLI失败；p3-recovery-red.log 为4项缺失恢复接口失败，均为提前声明的最小对应目标批次。p2-boundary-red.log 虽按预期名保存，实际6项首次即Green，仅算补充合同测试，不能记作Red。

首轮 config + bundle 实现后 17项通过（26.551秒）。portable-green-1.log 完整52项通过（161.420秒）。追加测试及组合回归继续单列。GTO 定向差异与生成一致性由 gto_* 日志单列。

环境路径、缺失可选目录和项目环境失败已记录；Git策略缺失未伪称修复或通过。首次CFM记录发生在环境路径核实之后，属于补记，不能倒称先查询后重试。
## Review、返工与复验
PRV-01 卸载后的空目录重装、PRV-02 嵌套未列出 manifest、PRV-03 AGENTS 备份外部正文篡改、PRV-04 Windows 硬链接锁、PRV-05 doctor 依赖影响，由 /root/portable_reviewer 发现，/root/portable_tests 独立补测，/root 修复，原 Reviewer 已逐项实际复验关闭。PRV-03 的 install/update/uninstall 中断恢复与 PRV-04 两种锁四种硬链接场景另有 Reviewer 直接实验。

recipient-packaging-green.log 两项补测通过；legacy-scope-green 结果为5项通过。review-prv-05-green.log 1项通过；windows-native-final.log 61项执行，58项通过、3项因当前宿主无法创建符号链接而跳过（20.345秒）。硬链接与锁占用已原生实测，不推导 junction 通过。

固定本地候选：8afd4f2ccc6aed1d505ca08e2fd750661fef74ae，临时 Git index + commit-tree 构造；javirs 的 HEAD/index 保持原状。产物 release-8afd4f2ccc6a，build-8afd4f2ccc6a.log 退出0。该候选用于审查验收，不是远端交付或部署。

WSL portable-final.log：65项中1项ERROR，checked对临时根的目录枚举返回路径歧义，原输出保留。串行单项复验通过，随后 portable-final-2.log 69项全部通过（226.807秒）；没有放宽路径检查。跨Windows/WSL并行目录枚举是未证实假设，不作为已修根因。windows-native-final-2.log 63项，60项通过、3项符号链接权限跳过（20.295秒）。

GTO独立实施回归：主版17、receipt/runtime22、分发24、继承64项（1326.568秒）分别通过，覆盖有重叠不能相加；gto-results.json及原始日志保留。生成23文件 --check 无缺失/额外/漂移。

完整Review新增 PRV-06 清单元数据、PRV-07 安装态引用闭合、PRV-08 旧sync父路径链接，独立Red后修复，8项定向回归通过；原Reviewer源码delta复验通过，待新包核对。PRV-09 旧doctor将用户hooks列为受管错误，由组合旧回归发现、独立测试取得Red；现改为managed=false/observations，原Reviewer实际复验确认其它受管缺失仍失败。

旧harness全量回归仍运行，已经出现失败，待结束取得完整trace后分类；不能先记为通过。规则旧测试已同步跨平台ID与授权边界，hooks旧测试已同步用户配置保全；第一次同步时一项文字断言写错，原失败保留，现按实际规则修正。

## 固定包核对与增量
候选 6aec84bcbce0e5e557822c887940c876fea4da08，版本 0.3.0-candidate，manifest SHA-256 为 fb985d22cad72d3f84f04e30ff3a35cece24aca641975f631f6f00712fca8b94。release-6aec84bcbce0 与 repeat 包共88个文件，逐文件比较零差异；78个安装文件、9个payload文件及manifest经原Reviewer核对固定Git对象、哈希和规则导出转换。25条全局规则不含项目scope。详细结论见 review-6aec84bcbce0.md；该包的源码/分发Review通过，未代表整体交付验收。

三个旧GTO测试仍断言固定WSL/Windows平台限制，与批准的跨平台合同不符。gto-old-platform-assertions-diagnostic.log 留存2失败1错误；仅同步环境及文档断言，保留实际工具、角色、证据与非UI说明约束，gto-platform-contract-sync-green.log 的相关11项通过（0.131秒），原Reviewer复核该测试差异通过。

PRV-10由根代理自检发现：只有Git缺失、jsonschema实际可用时，doctor漏列gto为受阻能力。独立测试者使用WSL真实jsonschema和空PATH取得Red（review-prv-10-red.log），根代理修复依赖判断并同步公共合同；review-prv-10-cli-green.log 的8项CLI回归通过（36.364秒），原Reviewer增量复核中。此修复及上述三个旧测试尚未包含在6aec候选中，需要后续冻结包与原身份复核。

PRV-10原Reviewer已独立实际复验通过：真实jsonschema可用、PATH为空，已装GTO与未装GTO两个对照均正确，诊断不修改文件、不误提示安装jsonschema。源级关闭，需绑定下一固定包。

独立验收者发现PAC-01：JSON重复字段被json.loads静默取末值，违反R05。独立测试者对JSON三字段及CLI四配置项取得3测试16子例Red（acceptance-pac-01-red.log，44.878秒）；公共合同先明确每项只出现一次，根代理再加JSON重复键检测和CLI配置参数重复检查。WSL配置+CLI20项通过（acceptance-pac-01-green.log，42.498秒），Windows同组20项中18通过、2跳过（符号链接权限、未安装真实jsonschema，5.629秒）；PAC-01用例在两个环境均实际通过。原Reviewer复验含Unicode转义重复键、两种CLI参数写法、不同来源正常优先级及零写入通过；仍须原验收者在新固定包上关闭PAC-01。

旧回归最小诊断定位到测试准备失配（legacy-fixtures-diagnostic.log、legacy-schema-diagnostic.log）：审计目录未创建；合同输入位于consumer外；无checkout_binding历史副本错误期待继续；schema-only回执漏run_evidence。仅四测试文件同步，控制器/schema及冻结历史fixture/provenance不改，拒绝复制活动状态及全文件字节保全仍强制。gto-legacy-fixtures-green.log 4项通过（15.957秒）、neighbors日志9项通过（75.705秒），原Reviewer静态复核通过。尚未取得完整全量trace，不将这些诊断扩大解释全部失败。

## 独立验收进展
Windows实际两次CLI接入共6.817557秒（install 5.908008秒、doctor 0.909549秒）；WSL fresh home 共135.336189秒（install 105.213567秒、doctor 30.122622秒）。均只需一项必填home，五模块已安装，用户AGENTS外部正文、配置、hooks、MCP、无关技能及数据字节保留，session_verified=false。依赖准备单列，不计为新会话验收。Windows真实锁占用、中断恢复、外部更改保全、普通权限NTFS junction拒绝均已取得独立证据；正式逐项结论待验收者报告。

验收失败历史单列：验收器曾误把自己的wrapper当作者依赖、误比较AGENTS块哈希与整文件，修正验证器后保留原日志；第一次WSL安装遭验收器自行设置的60秒subprocess期限中断，未取得产品异常证据，现场无journal/receipt，公开recover返回recovered=false（0.721563秒）。验收者随后在新自有接收目录按600秒单命令期限继续，未重复启动已有旧全量回归。这些尝试不计为产品通过，也不隐去成本。

## 原文命令验收缺口与PRV-11
根代理核对INSTALL原命令时发现：此前CLI单测及验收使用-B或PYTHONDONTWRITEBYTECODE，实际文档未要求该参数。独立测试者在970e包的副本上使用普通Python、清除禁写缓存环境变量，真实复现import产生6个__pycache__文件，install因未列文件退出1/BUNDLE_INVALID；doctor虽退出0但installed=false。原包未改，失败副本独立，证据review-prv-11-fixed-release-red.log。正式单项Red为1测试3失败（4.530秒，review-prv-11-red.log）。此前两CLI时长只能作为禁写缓存变体数据，不再认作完整原文接收者流程通过。

根代理在harness入口导入本地modules之前禁止写字节码，保持严格清单检查；原Reviewer与验收者继续原身份复验，同时检查已安装工具的普通运行是否产生相同所有权问题。970e包已取得的源码/哈希Review及其它场景证据保留，但不将其宣称为最终可接入包。后续新固定包必须使用不带-B、清除相关继承环境的真实文档命令验收。

PRV-11进一步覆盖两个GTO入口：普通controller帮助命令留下3个pyc，卸载保留这些未知文件后重装正确拒绝UNMANAGED_CONFLICT；start_session实际命中snapshot越界拒绝路径时也会懒导入并写缓存。独立Red分别留在review-prv-11-gto-red.log和review-prv-11-start-session-red.log。修复仅在三个入口本地导入前设置sys.dont_write_bytecode，未放宽清单/所有权/snapshot检查；两个GTO入口从canonical生成，23文件生成检查通过。review-prv-11-all-entrypoints-green.log共13项通过（63.670秒）。原Reviewer在Windows普通CLI与WSL真实GTO拒绝/卸载/重装链独立复验通过，未知用户文件仍阻止接管；这是修复副本证据，仍需绑定新固定包。

## 旧回归最终输出与定向收口
harness-regression-1.log已结束：472项、4796.346秒、24失败/7错误。该进程在后续夹具和旧规则断言修正前已加载测试，不能把它改记为全绿，也不重复启动全套。逐项关联当前失败与最小复验；重复收集的同一测试不算独立故障。

旧GTO两项证据夹具复用错误已仅在测试修正：负向receipt不再原地污染正向输入，后续attempt使用独立真实run_evidence绑定，保留历史字节检查与错误类型命中。gto-legacy-evidence-green.log两项通过（227.786秒）、邻近3项通过（1.184秒），原Reviewer静态复核通过。IndependentReview六项补跑5通过/1失败（159.270秒，原文件gto-independent-review-six-green.log虽名含green，内容实际失败）；RAR-002跨attempt复用证据和RAR-006合成source缺canonical example正在按已确认根因修正夹具，未放宽产品校验。非GTO旧模板断言、严格doctor测试入口和合法升级/篡改区分另由独立测试者定向收口。

970e26c82ec742c594f1a47e1d5119ba7a14cd33对应manifest SHA-256为45a16918ec516dbccc6cc27e9131005f96461e6d76dea6395c22ca15b8c6eca3。与6aec相比88文件中8项变化，原Reviewer核对85直接Git blob和两项生成索引通过。独立验收者已在该包完成Windows增量21/21和优先级2/2，PAC-01实际复验通过；WSL基线28/28及补验16/16属于6aec。所有批次范围有重叠，不相加，也不以这些禁写缓存变体抵扣原文命令。

## 当前固定候选与根复查
当前source为bb17b02f54fe3883cde8608b6c560e9b46809646，tree为7c6bc3ab83386487dcd94bffabc6df1ec361176e，版本0.3.0-candidate。包release-bb17b02f54fe的manifest SHA-256为98d2c66ec1cf719ad64678e3a5975668f656939135feb657025d6655313fd2a0。构建与重复构建均退出0，88文件逐项哈希相同（repeat-build-bb17-equality.json）。原Reviewer的review-bb17b02f54fe.md确认85直接文件匹配Git blob、两生成索引不变、GTO生成真源一致；PRV-11绑定此包关闭。

RAR002/RAR006两目标通过112.259秒、邻域2项通过0.502秒；gto-legacy-failure-pass-map.json列20唯一ID/21条原失败。根代理逐项核验行号与测试ID通过（root-gto-evidence-map-verification.json），首次证据解析误把unittest跨行docstring结果当单行，修正解析并保留失败说明，不算产品缺陷。

非GTO测试同步4目标通过60.569秒。组合检查首次仍被HOOKS中“没有使用”误判肯定动作而失败（legacy-test-contract-sync-gate.log）；只把第二句改为“用户hooks不属于安装器的受管资产”，未削弱扫描器或所有权。单项扫描通过1.741秒，受影响strictdoctor固定9项门禁与bootstrap skip-sync两目标复验通过109.108秒（legacy-test-contract-sync-gate-green.log）。其余旧规则/hooks失败已有review-prv-09-contract-green.log的目标Green，不重复套件。真实Linux venv检查单项通过属于WSL进程中的Linux环境测试，不冒称独立Linux机器验收。

bb17冻结后只有HOOKS及本任务状态文档更新；HOOKS不在88文件接收者包中，原Reviewer已复核此仓库文档delta。root-final-scope.json通过临时index比较，确认产品/测试与固定候选一致，javirs仍为原HEAD、真实index为空。所有候选为本地不可变Git对象；未移动分支或建立远端交付。任务报告更新不纳入产品包，不伪称其已包含在固定source中。

原验收者在bb17普通Python、清除字节码环境变量下实测：Windows两CLI为6.648422秒（5.863372+0.78505），WSL为115.287459秒（94.996307+20.291152），均1项必填home、无源码修改、包及installed runtime不生成缓存、重复doctor和移走包后installed CLI通过。Windows缺jsonschema，GTO帮助实际失败，不能记作GTO运行通过；WSL实际GTO帮助返回0且不生成缓存。最终增量、生命周期和原身份问题关闭结论由独立验收报告负责。

## 本轮交付结论
原验收者已签署acceptance-final-report-bb17b02f54fe.md，结论为部分验收，PAC-01在acceptance-findings.md关闭。最终docs检查Windows9/9、WSL11/11，delta分别18/18和19/19，真实优先级各2/2；根代理核读六份JSON未发现failed检查，计数有范围重叠，不加成规格通过率。WSL普通GTO帮助、无缓存、卸载重装通过；WindowsGTO缺jsonschema仍单列阻塞。WSL实际Git为/usr/bin/git，报告明确修正通用验证器的Windows Git文案误标。

原包完整性由原验收者复核88文件/87清单项全部哈希匹配。根与Reviewer独立核对两份失败映射，30唯一ID覆盖原31条失败且均有目标Green（root-regression-reconciliation.json）。正式任务文档保留P5/P7/P8外部未完成项；不对外发布，不把本地候选对象当作已提交/推送的javirs分支。本轮无运行中的测试或验收进程。

## 用户要求继续后的执行（2026-10-14）
用户指出不应在部分验收处停止，要求继续剩余事项。以上“本轮交付”是此前阶段记录，不是当前停止状态。原独立身份继续：Windows依赖、许可来源、真实GTO与环境能力分开补验，不重建工程控制面。

用户直接选择“本轮仅自用／内部交付”。原Reviewer完成license-provenance-review.md/json，实际核对包文件及6个第三方依赖许可证据；源码包未捆绑这些库。本轮不新增或代选对外许可证，也不再以公开分发许可阻塞内部验证。

原验收者创建本任务独立Windows venv，按bb17 requirements从PyPI安装平台匹配依赖，pip check通过。准备命令36.672475秒；真实控制器init-task/validate、卸载重装后再validate/doctor共8条产品命令、16checks通过，18.425457秒。七类用户资产及consumer证据保全，无受管缓存；bundled Python仍无jsonschema。证据acceptance-windows-gto-dependency-preparation-bb17b0.json及acceptance-windows-gto-execution-bb17b0.json，原验收者已签追加。该夹具停planning，不冒称完整真实代理流程。

真实GTO完整流程另为单场景BB17-GTO-ADDONE-001，使用bb17固定控制器、独立consumer和真实fork_turns=none角色，合同及实际批准映射在该consumer/.tmp，当前由gto_convergence推进。root不代写角色结果；发现产品故障停止该环节并保留证据。

环境探针发现已安装Docker Desktop但引擎不就绪；官方启动命令45秒期限超时。具体路径/失败/已备容器脚本见remaining-environment-probes.md。用户追加“这个docker问题一直出现，请你顺带彻底根治”，根代理启动根因修复分支，由独立测试者只读诊断；尚未删除/重置Docker数据、修改WSL集成或全局配置。新会话工具无隔离CODEX_HOME参数，当前Windows/WSL PATH均无Codex CLI；只读项目清单仅本地主机，不据此伪造独立Linux或新profile加载证据。

### Docker恢复与中断续接（北京时间2026-10-14下午）
Docker独立诊断定位4.90后端处理遗留AF_UNIX socket时Error1920。根代理在自有临时目录做Windows socket bind/listen/close/rename对照，全部通过，不能归因所有Windows socket损坏。官方维护者指出后续版本有恢复措施；根代理固定下载4.95.0.242831，SHA256与官方一致、Docker Inc签名Valid。停机备份约19.5GB data VHDX、系统VHDX、设置与旧修复资产，每项源/备份SHA256相同。升级原位per-user，未传accept-license、数据迁移或重置参数，安装退出0。

官方4.95首次启动自行保留两个原socket目录并重建监听器，Ingest/Secrets Engine通过、Engine29.8.2就绪；没有手工轮换。后续两轮官方stop/start全退出0，32容器、77镜像ID、23卷标识相同；这是恢复后两轮之间的资源一致性，不能冒称升级前数据库业务内容已验收。Ubuntu集成返回29.8.2。独立Reviewer审核后，根代理退役旧safe-start自动启动值、专用脚本/receipt/快捷方式，所有资产有验hash备份与事前/逐项审计；原生Docker启动值保留，未做Windows重新登录验收。证据为docker-*.json/log及recovery-review.md。Docker Hub TLS失败独立记录；AWS ECR Docker官方Python镜像可拉取，固定digest的只读无网络容器输出Python3.11.17。

真实GTO旧tester两次平台容量失败后，用户允许改用gpt-6.1-sol。会话随后中断，实际旧协调/tester不可用；新协调/root/gto_resume证实bb17没有合法身份移交入口。用户明确批准“仅对尚无交付结果的中断任务进行可审计身份移交，保留旧包/原任务/全部失败记录，再用修复包续验”。按同task保留场景amendment，独立/root/gto_recovery_tests最小Red命中缺action；/root/gto_resume实现保守recover-interrupted-dispatch，独立4项Green、symlink2项、正常恢复bind/validate/preflight1项通过；这些覆盖重叠不合计。独立/root/recovery_reviewer静态无P1/P2，相关回归/新固定包和真实场景续验继续推进。旧bb17包不改写。

