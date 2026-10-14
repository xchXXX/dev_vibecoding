# Portable Harness 验收记录

2026-10-14追加交付：用户要求继续剩余验收并授权Git提交推送，明确由dots云端从Git拉取。已补仓库技能发现入口、隔离venv安装/只读检查命令及[dots云接入说明](../../modules/portable-harness/delivery/engineering/dots-cloud.md)。独立新增7项测试通过，最终pip隔离/无用户缓存专项1项通过（覆盖重叠不累加）。产品提交436e52c71d9c371af0e11e3d8249460bd49d8310已推送到GitHub的javirs分支。该提交在干净Linux容器从Git bundle克隆后，9条命令和14项检查全部通过，首次真实PyPI安装、重复安装、只读检查、真实GTO doctor及7项新增测试均通过；新云任务加载与dots宿主能力仍由用户云端按交付提交验收。

状态：当前固定候选为5a0606ac6b11，已完成中断身份恢复修复、独立测试及源码/清洁分发目录Review。Windows和WSL既有原文命令、生命周期、配置及依赖证据保留，原验收者已签署部分验收报告并关闭PAC-01。新增Windows原生恢复成功链及Linux容器Python3.11完整生命周期通过。旧全量31条失败记录均已有目标Green，未重跑全套。用户明确本轮仅自用／内部交付，来源审核完成。Docker官方升级、故障恢复命中和两轮重启验收通过。完整GTO已在原任务执行到completed并最终validate通过；独立Linux主机、新会话和云端尚未通过，不宣称全部规格验收完成。

证据根：`.artifacts/portable-harness/20261014/`。命令、失败历史、候选与独立身份见 [执行记录](execution.md)。

| 要求 | 验收信号 | 当前证据 |
| --- | --- | --- |
| R01–R02 简单接入 | ≤3 项参数、两次 CLI；依赖单计 | bb17普通Python原文命令通过，无-B且清缓存环境：Windows6.648422秒、WSL115.287459秒；1必填home。重复doctor、移走包后installed CLI通过；新会话/真实陌生接收者未测 |
| R03/R13 模块独立 | 无 GTO 的方法模块与模块更新隔离 | 单模块测试、Reviewer原生工具烟测通过；新会话未测 |
| R04 自包含 | 无作者仓库依赖 | installed CLI、Git/路径工具、benchmark、CFM通过；PRV-07引用缺口已修，bb17固定包核对通过；移走接收包后installed CLI实际通过 |
| R05 配置 | 优先级、未知字段、相对路径、安全边界 | 行为测试通过；PAC-01重复JSON键和CLI参数由原发现者在两平台bb17复验关闭，真实跨层优先级各2项通过 |
| R06 跨平台 | 各平台独立证据 | WSL portable74项通过、后续CLI13项通过（覆盖重叠）；Windows63项中60通过、3符号链接权限跳过，原生junction和进程树另有实际证据；5a候选Linux容器Python3.11生命周期16检查通过，独立Linux主机未测 |
| R07 所有权 | AGENTS/hooks/MCP/技能/数据字节保全 | 冲突/漂移、硬链接、旧sync父链测试通过；Windows独立实测用户字节保全及NTFS junction拒绝；旧doctor非受管hooks观察已修 |
| R08 恢复 | 互斥、中断恢复与外部更改保全 | 两平台真实锁、完整/部分恢复，Windows注入I/O回滚通过；Windows后续隔离venv真实init-task/validate及卸载重装后重验共16检查通过，原bundled Python未改；5a新增受限身份移交已通过独立WSL及Windows测试、Review，原任务已实际恢复；不承诺不同内核并发共享安装 |
| R09 数据与能力 | 排除作者历史，缺可选依赖不阻塞无关模块 | 私有路径/项目规则排除、CFM空数据与依赖诊断通过 |
| R10 分发 | 固定源码、白名单、哈希、依赖和支持声明 | bb17包88文件重复构建零差异；5a修复包88文件完整集合、87引用哈希及Git来源经独立Reviewer核对，根已归档ZIP并核对内容；依赖来源/许可审核保留，包不内嵌第三方依赖；用户选择本轮仅内部交付，未选择或添加对外许可证 |
| R11 诊断 | 退出码与磁盘/会话状态分开 | JSON/人读、blocked_capabilities及session_verified=false通过 |
| R12 证据 | 独立Red/Green、Review、验收与复验 | PRV-01–11及bb17源码/包经原身份复验；原472项24F/7E保留，30唯一ID/31条失败已由根与Reviewer核对到目标Green；原验收者已签署部分验收 |
| Codex/云端 | 新会话真实加载及 GTO 真身份流程，不以模拟替代 | 真实GTO同一隔离任务已通过可审计身份恢复、独立Red/实现/集成/Review/验收/关闭，状态completed、最终validate通过；3真实业务身份、8派发turn、1实际验收attempt。容量失败与中断历史保留，新会话/云端仍未验收 |

## 独立检查
测试设计为 `/root/portable_tests`，Review 为未参与实现的 `/root/portable_reviewer`。验收为新建无历史代理 `/root/portable_acceptance`，持续由原身份执行及关闭问题，不能把部分场景通过记为整体验收通过。Review报告为review-bb17b02f54fe.md；根对账为root-regression-reconciliation.json；原文命令证据为acceptance-docs-windows-bb17b0.json和acceptance-docs-wsl-bb17b0.json。

正式独立结论见证据目录acceptance-final-report-bb17b02f54fe.md，由/root/portable_acceptance签名；本表仅汇总，不替代其逐项范围。后续Windows GTO执行证据见acceptance-windows-gto-execution-bb17b0.json及dependency-preparation记录。新增恢复修复由/root/gto_recovery_tests独立测试、/root/recovery_reviewer独立Review，报告为recovery-review.md；不把旧bb17验收签名扩大至新增范围。父会话最终复查尚未取得，不代签。
## 剩余限制
连接、WSL映射和Windows Python已核实。独立Linux主机、云端、新顶层Codex会话尚无验收证据；不以CLI、子代理或模拟抵扣。真实Linux容器使用WSL内核，其16项检查通过不能冒称独立Linux主机。内部交付的来源审核已完成，未来对外许可另行决定。缺项目git-policy，检查器未通过，不伪造配置。只在javirs指定工作区修改，原始脏checkout未作交付写入；早期候选用临时Git index与commit-tree冻结；用户追加Git授权后，javirs已快进到5a固定候选并正常提交云端接入增量436e52c，再推送至origin/javirs。未合并main、发布release或安装portable包到真实全局环境。用户追加授权的Docker修复已完成，具体范围与未做的登录/恢复演练见下文。

## 5a0606候选补验

新固定source为5a0606ac6b11102076adec53fac7be0dfc6169d0，manifest SHA256为59b2ab772a1b6e42d2f2e464a3b80095976cc2bece0d3907b01180acd9cc699a。清洁目录经独立Reviewer精确文件集合及哈希核验：88文件、87引用哈希全符，无额外文件。对应内部交付ZIP为portable-harness-0.3.0-candidate-5a0606ac6b11.zip，SHA256为3d0c25cc19c3779a312d29f5cb4ff442f7b19ecd35c5d690a26f3936a97e0e63；根归档脚本逐项核验ZIP与清单，独立Tester再次确认88个唯一ZIP条目、CRC、全部归档字节和Linux报告。补验为independent-final-bundle-container-supplement.json，不追认被隔离的污染包。

Windows独立Tester使用既有隔离venv执行恢复成功链，1项9.669秒通过（总10.0秒），证据interrupted-recovery-windows-success.json。首次宿主PATH缺Git导致的准备失败保留，复跑只在子进程PATH加入实际Git目录，产品和测试未改。

Linux清洁容器验收linux-container-5a0606-clean/recipient.json：Python3.11.17、只读包/根文件系统、无网络、自有接收目录；普通Python命令安装、doctor、installed CLI、同包更新、卸载、重装共6条命令全exit0，16检查全通过。用户五类资产字节保全，包无新增文件，installed runtime无缓存，session_verified=false。容器未安装Git/jsonschema，doctor正确列出受阻能力；本批不代表容器GTO执行通过。首个受检查脚本缓存污染影响的运行及坏ZIP保留在历史证据中。

Docker已升级4.95.0.242831/Engine29.8.2；官方恢复逻辑实际处理两个旧socket目录并恢复监听，两轮官方stop/start和WSL集成验证通过。恢复后32容器、77镜像ID、23卷在两轮重启间一致；停机数据盘/设置备份SHA256一致，旧safe-start安装副本及专属启动项经审查后退役，原生启动值保留。未做Windows重新登录或备份恢复演练，也不将资源ID一致声明为数据库业务内容验收。docker-recovery-result.json和recovery-review.md记录完整边界。

## 真实GTO场景完成

同一场景BB17-GTO-ADDONE-001、formal_round=1、task_id=20261014-144021-713937-portable-add-one，原consumer位于.tmp/portable-harness/real-gto-add-one-bb17/consumer。独立tester、implementer、reviewer使用实际独立身份完成全流程，原tester负责最终验收和close，共8派发turn（含两次本人回执格式修正），未冒充身份或重建任务。Review实际观察54次CLI；冻结candidate-28f79302f9921323后原tester再次fresh运行44次CLI，原生run/verify及attempt-1门禁通过。验收manifest SHA256为401c2149a327713c803953020bec91d2cb7c9e6688631edeb49b7e35108dd19e，runtime SHA256为975903df614a755dcc3e3a79a18db4123ac13913174bc5266202d18f646924e9。

原生accept-artifact-update、record CLOSE、finalize-task、最终validate均退出0；最终state.status=completed、next_action.kind=none，根独立读取state核实。ACCEPT-001是保留的模板ready，实际ACCEPT-001-attempt-1已completed/pass，不能误读模板状态。最终phase=review是控制器正常完成表示。旧容量失败、原任务、旧bb17包、恢复授权、身份移交及所有失败证据均保留；通过的是授权修复后的5a包同场景，不追认旧bb17包完整流程通过。

