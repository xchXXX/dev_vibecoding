# Portable Harness 验收记录

状态：bb17b02f54fe源码/分发Review通过，Windows和WSL原文命令、生命周期及配置/依赖增量完成，原验收者已签署部分验收报告并关闭PAC-01。旧全量31条失败记录均已有目标Green，未重跑全套。后续Windows隔离venv真实GTO初始化/校验补验通过；用户明确本轮仅自用／内部交付，来源审核完成。完整GTO真实场景因模型容量及会话中断暴露身份恢复缺陷，用户已批准修复并续验原任务。独立Linux、新会话、云端及完整GTO尚未通过，不宣称整体完成。

证据根：`.artifacts/portable-harness/20261014/`。命令、失败历史、候选与独立身份见 [执行记录](execution.md)。

| 要求 | 验收信号 | 当前证据 |
| --- | --- | --- |
| R01–R02 简单接入 | ≤3 项参数、两次 CLI；依赖单计 | bb17普通Python原文命令通过，无-B且清缓存环境：Windows6.648422秒、WSL115.287459秒；1必填home。重复doctor、移走包后installed CLI通过；新会话/真实陌生接收者未测 |
| R03/R13 模块独立 | 无 GTO 的方法模块与模块更新隔离 | 单模块测试、Reviewer原生工具烟测通过；新会话未测 |
| R04 自包含 | 无作者仓库依赖 | installed CLI、Git/路径工具、benchmark、CFM通过；PRV-07引用缺口已修，bb17固定包核对通过；移走接收包后installed CLI实际通过 |
| R05 配置 | 优先级、未知字段、相对路径、安全边界 | 行为测试通过；PAC-01重复JSON键和CLI参数由原发现者在两平台bb17复验关闭，真实跨层优先级各2项通过 |
| R06 跨平台 | 各平台独立证据 | WSL portable74项通过、后续CLI13项通过（覆盖重叠）；Windows63项中60通过、3符号链接权限跳过，原生junction和进程树另有实际证据；独立Linux未测 |
| R07 所有权 | AGENTS/hooks/MCP/技能/数据字节保全 | 冲突/漂移、硬链接、旧sync父链测试通过；Windows独立实测用户字节保全及NTFS junction拒绝；旧doctor非受管hooks观察已修 |
| R08 恢复 | 互斥、中断恢复与外部更改保全 | 两平台真实锁、完整/部分恢复，Windows注入I/O回滚通过；Windows后续隔离venv补齐依赖，真实init-task/validate及卸载重装后重验共16检查通过，原bundled Python未改；GTO代理丢失后的身份移交缺陷正在修复；不承诺不同内核并发共享安装 |
| R09 数据与能力 | 排除作者历史，缺可选依赖不阻塞无关模块 | 私有路径/项目规则排除、CFM空数据与依赖诊断通过 |
| R10 分发 | 固定源码、白名单、哈希、依赖和支持声明 | bb17包88文件重复构建零差异，固定Git对象及哈希经原Reviewer核对；原Reviewer已审核依赖来源/许可，包不内嵌第三方依赖；用户选择本轮仅内部交付，未选择或添加对外许可证 |
| R11 诊断 | 退出码与磁盘/会话状态分开 | JSON/人读、blocked_capabilities及session_verified=false通过 |
| R12 证据 | 独立Red/Green、Review、验收与复验 | PRV-01–11及bb17源码/包经原身份复验；原472项24F/7E保留，30唯一ID/31条失败已由根与Reviewer核对到目标Green；原验收者已签署部分验收 |
| Codex/云端 | 新会话真实加载及 GTO 真身份流程，不以模拟替代 | 真实GTO同一隔离任务已通过六工件/首次preflight并绑定真实tester，但两次平台容量失败后旧代理因中断不可用；用户允许gpt-6.1-sol及可审计恢复修复，正在推进。新会话/云端仍未验收 |

## 独立检查
测试设计为 `/root/portable_tests`，Review 为未参与实现的 `/root/portable_reviewer`。验收为新建无历史代理 `/root/portable_acceptance`，持续由原身份执行及关闭问题，不能把部分场景通过记为整体验收通过。Review报告为review-bb17b02f54fe.md；根对账为root-regression-reconciliation.json；原文命令证据为acceptance-docs-windows-bb17b0.json和acceptance-docs-wsl-bb17b0.json。

正式独立结论见证据目录acceptance-final-report-bb17b02f54fe.md，由/root/portable_acceptance签名；本表仅汇总，不替代其逐项范围。后续Windows GTO执行证据见acceptance-windows-gto-execution-bb17b0.json及dependency-preparation记录。原包哈希核对通过。此前根自检仅覆盖bb17旧范围，新增修复仍需重新Review与验收；父会话最终复查尚未取得，不代签。
## 剩余限制
连接、WSL映射和Windows Python已核实。独立Linux、云端、新顶层Codex会话及真实GTO完整代理流程尚无验收证据；不以CLI或模拟抵扣。内部交付的来源审核已完成，未来对外许可另行决定。缺项目git-policy，检查器未通过，不伪造配置。只在javirs指定工作区修改，原始脏checkout未作交付写入；候选用临时Git index与commit-tree冻结，未改分支HEAD/index，未推送、合并、发布或安装portable包到真实全局环境。用户追加授权的Docker修复独立记录：已完成停机数据盘/设置备份和SHA-256一致性核验，升级与重启验收待完成。

