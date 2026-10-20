# 独立审查记录

## 首次全局准备审查

2026-09-10，独立 reviewer：`/root/pre06_reviewer`，由主协调以 `fork_turns=none` 派发，不继承对话、不再委派。reviewer 只读；未运行测试、doctor、验收、恢复、发布或配置修改，未调用 GTO 或读取 GTO schema。主协调将返回报告记录于此。

审查范围：AGENTS/规则索引与三条固定规则；全部人工任务控制面；bootstrap/sync 维护检查和前后写入路径；两个指定测试文件；模板、生效全局 AGENTS、drugsale 环境段；三条环境规则/生成索引；三份长期文档维护通知；snapshot.py、apply-config.py、check-restore.py；恢复包 manifest/脱敏报告及非敏感文件前后像。未读取配置原文或配置副本、认证文件、密钥。

本批归属：bootstrap 新增 3 行 hold、sync 新增 2 行 hold；模板/生效入口和 drugsale 仅环境段；三条环境规则及索引 fingerprint；长期文档仅维护通知。其余 runtime、doctor、桥接、GTO dirty 不属于本批发布。reviewer 完整覆盖目标、非目标、修改范围、实施、验收、风险六要点，未发现维护闸门生产代码阻断问题。

首次结论：PRE-06 暂不关闭。原解除顺序已修订，但 reviewer 首次读取的验收账本仍含失效当前事实；需文档同步与范围复审。准备审查不等于完整迁移候选首次审查。

| Finding | 级别与位置 | 独立发现 | 主协调处理，待复审 |
|---|---|---|---|
| PRE06-001 | P2；plan.md 原 29 行、handoff-prompt.md 原 48 行 | hold 阻止正式同步，却先要求真实 receipt 收口才解除，形成循环前提。 | plan/handoff 明确隔离闭环→冻结候选/前像→无并行发布→受控解除→正式定向同步及真实 receipt→失败恢复 hold；ACC-07 分清隔离与真实机器。未解除真实标志。 |
| PRE06-002 | P2；acceptance.md 原 15/25 行 | 旧 23 项封存匹配、恢复通过、插件未知、本轮 8/8 等被写成当前事实，与新证据冲突。 | 旧表明确标为历史，新表记录配置漂移与恢复拒绝、三插件范围、当前测试和 doctor，state/inventory/execution 对齐。Windows→WSL doctor 后续由主协调重新执行，仍须明确这份新证据。 |
| PRE06-003 | P3；tests/harness/test_windows_native_transition.py 原 30 行 | snapshot 仅普通文件内容/mtime，无法捕获新增空目录，窄于“目录树不变”。 | 新增最小空目录断言，先观察预期 AssertionError，再增强 snapshot 记录目录项与对象类型。目标回归结果由主协调补入 execution/acceptance。 |
| PRE06-004 | P3；.tmp/windows-native-transition/snapshot.py 原 64 行 | verify 不检查 after_copy 完整性，不能把它泛称全部前后像完整验证。 | 不改私有原始快照工具。主协调另行只读核验 manifest 所有 before 及存在的 after_copy 与 hash，23 项材料完整；明确此证据独立于 snapshot.py verify，后者仍不检查 after_copy、ok=false 也不非零退出。 |

## 需要保留的风险

- computer-use 和 unified-computer-use 为启用，browser 配置/标准缓存未发现；Windows 新宿主是否实际加载未知，ACC-01/02 pending。
- config.toml 仅 model_reasoning_effort 漂移，保留原状；拒绝整体恢复正确。恢复先建当前私有前像，只合并迁移 enabled 键，恢复缺省键时删除本次新增键而不是用显式 true 代替；保留其他设置及宿主新字段。
- hold 不是跨进程事务锁；受控发布前需确保无并行发布，失败恢复标志并记录部分写入。
- 源/安装/receipt 尚未收口，后继必须完整迁移首次 review；不允许全量发布 dirty。
- 新附件、GUI 用户路径、窗口生命周期、代表性测试/构建、Docker 保全、重复发布和恢复演练均仍待主协调验收。

## 范围复审

2026-09-10，同一独立 reviewer `/root/pre06_reviewer` 完成范围复审，结论：通过，四项 finding 均已得到可接受处置，PRE-06 可以关闭。reviewer 重读任务文档/状态/事件，审查测试 delta 和证据映射；未执行验收或写入。

- PRE06-001 closed：隔离 receipt 与真实正式同步顺序明确，循环前提消除。
- PRE06-002 closed：旧表标历史，当前表与 state/inventory/execution 对齐；最新 Windows→WSL doctor 证据已区分。
- PRE06-003 closed：新增空目录最小 Red 命中，snapshot 记录目录类型，目标 4/4 通过；生产代码未变。
- PRE06-004 closed：主协调独立 before/after hash 补证据充分；原工具限制保留并明示，未伪称修复。

没有新增阻断发现。首次报告反映 reviewer 当时读取版本，当前过期账本问题已解决，不能根据报告提交时间推断修订先后。此复审仅覆盖切换前候选，迁移运行验收仍 pending。reviewer 明确允许主协调纯状态收口，无须再次全局审查；实质性代码/配置/验收条件变化仍需按影响范围审查。

主协调随后核对候选 hash 不变、23 项 before/after 副本完整、22 项非配置封存匹配、已知配置漂移不变、hold 保留且当前仍 WSL；完成 PRE-07。

## P6 完整迁移首次审查与范围复审

独立只读 reviewer Carver（01a08a71-4fe0-7a11-aca1-61e997448bc7），未继承对话、未委派、未跑验收或发布。首次发现 P6-001..010：runtime退役/恢复、安装归属与额外记录、锁/hold、Windows命令漏报、旧测试夹具、畸形输入、schema元数据、文档列/入口、插件doctor前置、错误home示例。共7项P2、3项P3。

首次修复后19项回归通过15.895s；同reviewer复审关闭003..010，保留001/002并新增011（额外记录与doctor合同）。主协调继续修正正常ExitStack异常传播/逐项恢复错误报告、既有receipt显式归属及source字段、范围外receipt保留并限定审计。两项最小Red均为预期AssertionError，修复后22项通过24.617s。默认路径中断及恢复失败有独立故障注入断言，不执行其GTO子流程。

当前001/002/011和追加配置删除脚本等待同reviewer复审，不能标可发布。一次性配置脚本dry-run仅命中停用computer_use_wsl，未写真实配置；5组夹具验证保留原生字段、CRLF/子表、重复无变、拒绝启用或缺省enabled。

## P6 最终范围复审通过

同一独立 reviewer Carver 明确确认 P6-001、002、011 均已关闭，配置删除脚本 P6-012 修复后复审通过；P6-001..012全部关闭，无未关闭finding。主协调回归22/22、维护守卫4/4（2.615s）、配置成功/失败边界4/4。隔离正式重复发布及16文件恢复已通过。此结论允许主协调进入真实定向发布，不等于ACC全通过。

最后5处长期文档删除原则的轻量范围复审通过，P6-001..012保持全部关闭。主协调随后按报告完成真实清理与非GUI验收；reviewer未替主协调跑验收。一次性脚本现已归档私有process-materials，不再作为工作区运行入口。

## 全面扫描后的当前结论（覆盖此前清理完结表述）
当前全面扫描已完成，结论为仍需整改，不能宣称全部环境产物已扫净。新的独立reviewer Fermat发现11项：P1=0、P2=6、P3=5，详见environment-scan-review.md。上一轮P6-001..012关闭仅保留为当时范围的历史证据，不覆盖此次新发现。

已证明的内容继续成立：Windows原生宿主与三插件正常配置；正式安装中的旧WSL GUI桥运行时/技能已删除，10个环境文件源/安装/receipt一致；限定环境doctor通过，五容器ID/StartedAt/healthy不变。维护hold当前已解除。

需要整改：默认Codex home/CFM目标可能误落WSL home；strict合同错误拒绝合法Windows PowerShell；健康测试夹具缺原生插件；架构/附件/Browser/药品项目长期文档旧分工与当前事实冲突；遗留一个旧桥测试bytecode；测试临时父目录及导航未收口。所有ENV-SCAN-001..011仍开放，尚未实施新修复。

Windows负责Agent文件、Browser、截图、Computer Use；WSL保留Git/开发命令/Python/Node/测试构建/Linux依赖和服务。当前Ubuntu CODEX_HOME未设置、HOME=/home/laptop，与C:/Users/Laptop/.codex不同；不得靠删除Linux用户目录掩盖目标选择问题。

继续按既有迁移授权定向修复、验证并由同一reviewer做影响范围复审。禁止GTO/orchestrator_ctl/GTO schema、全量发布、覆盖混合dirty、改原生插件transport、误删历史/恢复包/业务依赖数据。GUI与新附件证据仍pending，migration_accepted=false。
