# 接续导航

当前全面扫描已完成，结论为仍需整改，不能宣称全部环境产物已扫净。新的独立reviewer Fermat发现11项：P1=0、P2=6、P3=5，详见environment-scan-review.md。上一轮P6-001..012关闭仅保留为当时范围的历史证据，不覆盖此次新发现。

已证明的内容继续成立：Windows原生宿主与三插件正常配置；正式安装中的旧WSL GUI桥运行时/技能已删除，10个环境文件源/安装/receipt一致；限定环境doctor通过，五容器ID/StartedAt/healthy不变。维护hold当前已解除。

需要整改：默认Codex home/CFM目标可能误落WSL home；strict合同错误拒绝合法Windows PowerShell；健康测试夹具缺原生插件；架构/附件/Browser/药品项目长期文档旧分工与当前事实冲突；遗留一个旧桥测试bytecode；测试临时父目录及导航未收口。所有ENV-SCAN-001..011仍开放，尚未实施新修复。

Windows负责Agent文件、Browser、截图、Computer Use；WSL保留Git/开发命令/Python/Node/测试构建/Linux依赖和服务。当前Ubuntu CODEX_HOME未设置、HOME=/home/laptop，与C:/Users/Laptop/.codex不同；不得靠删除Linux用户目录掩盖目标选择问题。

继续按既有迁移授权定向修复、验证并由同一reviewer做影响范围复审。禁止GTO/orchestrator_ctl/GTO schema、全量发布、覆盖混合dirty、改原生插件transport、误删历史/恢复包/业务依赖数据。GUI与新附件证据仍pending，migration_accepted=false。

## ENV-SCAN 整改中：当前事实
用户已授权删除旧环境残留、不增加兼容。11项扫描发现已有修复候选，等待原reviewer范围复审。维护hold现已重新启用，覆盖之前‘已解除’的历史描述。28项native测试、12项CFM测试、4项hold与2项合同fixture测试通过；26条规则校验无错误警告。隔离定向发布两轮通过，第二轮无变化，17文件恢复通过。实际环境runtime及CFM技能尚未发布新候选；不把源码通过当作安装通过。GUI/新附件证据仍pending，migration_accepted=false。


## ENV-SCAN 整改最终事实（覆盖此前整改中状态）

同一独立reviewer Fermat两轮范围复审关闭ENV-SCAN-001..011：首次关闭10项，最后四文件入口/metadata delta复审关闭001。未新增兼容桥；旧运行时、技能及孤立测试bytecode已不在活跃路径，测试不再遗留固定任务父目录。Windows负责Agent文件与GUI，WSL保留开发命令、依赖和服务。

主协调验证：native28项、CFM12项、hold4项、合同fixture2项通过；26条规则元数据校验通过。最终候选隔离和实际正式发布均限定environment-only与CFM-only，各两轮、第二轮无变化；源码/安装/receipt真实hash一致，插件config及AGENTS字节未改、无关receipt行未改。两个项目doctor及限定环境doctor通过，5容器ID/StartedAt不变且healthy。17文件隔离恢复通过，29份源快照校验完好。维护hold已解除。详细证据见envscan-isolated-publication.json、envscan-live-publication.json、envscan-postpublish-verification.json、envscan-final-audit.json。

本次审查与验证边界排除GTO实现/schema/专项测试、全局strict及真实GUI验收；没有全量发布。ACC-05..08通过，ACC-01..04保留主协调GUI/新附件证据缺口，用户插件可用事实保留，migration_accepted=false。这些证据缺口不表示插件不可用，也不表示环境清理仍未施工。历史记录及私有恢复包仅作证据，不作为活跃兼容实现。
