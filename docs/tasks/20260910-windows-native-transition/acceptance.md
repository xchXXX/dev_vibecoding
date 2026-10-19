# 验收记录

## 验收目标

本轮证明 ready_to_switch；重启后由主协调完成全部 ACC 项，才能证明迁移完成。

## 验收标准

完整编号与含义见 plan.md PRE-01..07 和 ACC-01..08。

## 必备证据

备份/前后像、最小 Red/Green、独立全局 review、配置无越界差异、Windows 调用 WSL 的真实结果、重启后实际插件/Browser/附件/项目/Docker证据。

## 未决项

PRE-06 独立首次准备审查、修复与同 reviewer 范围复审已完成。全部 ACC pending。用户明确急用 computer-use、browser 和配套 unified-computer-use；附件验收需要用户新附件。

## 切换前检查结果

以下为接手前历史验证，最新结果见下方“主协调当前复核”，不得直接继承：

| 编号 | 结果 | 证据与边界 |
|---|---|---|
| PRE-01 | pass | snapshot.py verify：23 项备份及封存匹配；check-restore.py：15 个修改目标恢复前置检查通过。既有 verification-result.json 记录 14 个原文件隔离字节恢复；不是整机或业务恢复演练。 |
| PRE-02 | pass | test_windows_native_transition + test_sync_codex_scope 共 8/8，9.693 秒；两入口维护停止及文件内容/mtime 不变断言通过。真实入口既有脱敏报告同时保留。 |
| PRE-03 | pass | 当前 config 与封存 hash 一致；脱敏 preparation-result/verification-result 记录仅两个 enabled 变化，官方 MCP transport 未改。不是新进程加载证明。 |
| PRE-04 | pass | 源模板、生效 AGENTS、项目环境入口与封存匹配；模板渲染一致证据在 verification-result。首次独立审查仍另列 PRE-06。 |
| PRE-05 | pass | 本轮通过 Windows wsl.exe 指定 Ubuntu-24.04 再运行两个项目 project-env-doctor，均 ok=true、findings=[]、errors=[]。不代替代表性构建或 Docker 运行验收。 |
| PRE-06 | blocked | 尚未取得完整独立 review 报告，须由主会话补齐。 |
| PRE-07 | pass | 六份人工记录、处置清单及接手提示词已对齐 P3；明确未切换、未验收、review 阻塞。 |

可复核命令及私有证据位置见 execution.md、inventory.md。所有运行期 ACC-01..08 仍未执行，不继承 PRE 的通过状态。

## 切换前主协调最终复核（历史 PRE 证据）

| 编号 | 当前结果 | 本次事实 |
|---|---|---|
| PRE-01 | pass with restore restriction | 23 项 before 与存在的 after 副本 hash 均匹配；22/23 当前文件匹配封存。config.toml 仅 model_reasoning_effort 漂移；整文件恢复前检仍 exit 2，恢复仅可保存当前私有前像后合并迁移 enabled 键，不允许整份恢复或重新 seal。 |
| PRE-02 | pass | 本次范围修复后 test_windows_native_transition 4/4，5.841 秒；新增空目录最小 Red 已命中，Green 后守卫比较覆盖目录项与文件类型/内容/mtime。历史 scoped suite 未重跑，不调用 GTO/schema 夹具。 |
| PRE-03 | pass for preparation only | 本次只读结构比对，封存后唯一变化为 model_reasoning_effort；computer-use 与 unified-computer-use 为 true、computer_use_wsl 为 false。browser 配置/标准缓存未发现，留待新 Windows 宿主核对。未改变官方 transport。 |
| PRE-04 | pass | 模板、规则、两项目入口与封存一致；未重新渲染、安装或发布。 |
| PRE-05 | pass | 本次 Windows wsl.exe 指定 Ubuntu-24.04 对两个项目运行已安装 doctor，均 exit 0、ok=true、findings=[]、errors=[]；当前进程仍 WSL。 |
| PRE-06 | pass | review.md 已记录同 reviewer 首次报告和范围复审，四项 finding 均关闭，无新增阻断。仅准备候选。 |
| PRE-07 | pass | 主协调复核候选 hash、恢复材料、配置已知漂移与 hold；state/task/handoff/execution/review/acceptance/events 对齐 P4 待用户切换。 |

## 切换前结论（历史）

ready_to_switch=true、migration_accepted=false。PRE-01..07 准备检查已完成，可通知用户切换 Agent environment 到 Windows native 并完全退出重启。Windows 新宿主启动以及 ACC-01..08 尚未发生，当前进程仍 WSL。配置漂移的安全拒绝不改写成“整文件恢复通过”。

## Windows 新宿主早期记录（已被下方 P6 事实更新）

已切换原生宿主，P5；三个插件 enabled=true，Browser 缓存现已存在。本会话官方 GUI 操作工具缺失，ACC-01/02/04 blocked；ACC-03/05/06/07/08 pending。切换后仅 harness doctor 通过，不能判 ACC-05 通过。当前 task cwd 错误，但真实 D:/ 项目可读且已登记。migration_accepted=false，维护标志保留；不需要再做准备审查或再次切换。

## P6 实施期间事实（历史）

当前 P6：已完成 Windows 原生切换，用户确认 Computer Use、Browser 和 unified-computer-use 正常使用。PRE-01..07 已通过，不重做。主协调继续定向清理；GUI 工具在本会话未暴露，仅对应证据 pending，不阻塞其余实施。

实际项目 D:/prj/harnesss/dev_vibecoding；WSL /mnt/d/prj/harnesss/dev_vibecoding。应用携带的 C:/mnt/d 路径无效，不复制仓库。命令指定真实 workdir，并使用 C:/Windows/System32/wsl.exe -d Ubuntu-24.04 --cd <Linux项目> --exec <命令>；复杂内容先写脚本，禁止将 Markdown 反引号嵌入默认 shell 的 python -c。

原生声明 v3、只读诊断、environment-only 发布与 receipt 驱动的旧技能退役已实现，尚未发布。独立 Carver 正在做完整迁移首次 review；有修复则同 reviewer 范围复审。维护 hold 仍存在；发布前先冻结私有 installed 前像和候选 hash。仅正式 environment-only 与 retire-legacy-gui 入口可用于本任务，不全量发布、不调用 GTO/schema、不改正在使用的插件配置。

ACC-05：两个项目 project doctor 均通过；harness 原生环境回归12项及维护守卫4项通过；drugsale Linux pnpm typecheck 通过。ACC-06：现有五容器均 healthy，未重启或改服务。ACC-01 用户确认可用但待主协调操作证据；ACC-02/03/04 pending；ACC-07/08待定向正式发布与恢复演练。migration_accepted=false。

Docker 只读基线：worker 72a22f7b9905、api 29bca7421b41、web d36f57799fea、postgres 863919c56230、redis aa66ea23c3af，全部 healthy。后续复核相同容器与 StartedAt，不能以此替代 GUI。

## P7 当前最终事实

Windows 原生迁移的源码与安装清理已完成，当前 P7，剩余 GUI/新附件证据待补。用户已确认 computer-use、browser、unified-computer-use 正常使用；无需再次切换或重复准备。

Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；Git、Python/Node、测试构建、Linux 依赖和服务继续在 Ubuntu-24.04。实际项目 D:/prj/harnesss/dev_vibecoding；WSL /mnt/d/prj/harnesss/dev_vibecoding。Windows 调用使用 C:/Windows/System32/wsl.exe 指定发行版和 --exec，工作目录用真实 D:/，不创建 C:/mnt/d 镜像。

已删除旧 GUI 桥源码/技能/旧测试、installed node-repl-wsl-compat.py、installed windows-computer-use-wsl 技能，以及 config.toml 中停用的 computer_use_wsl 表（browser_use_wsl 原本不存在）。不保留旧运行兼容层；私有恢复材料不参与技能发现。bootstrap/doctor 只读原生插件配置，所有原生插件与官方 transport、其余配置语义保持不变。

正式 environment-only 发布和 retire-legacy-gui 各执行两轮，第二轮无变；10个环境运行文件源/安装/receipt吻合，AGENTS/template receipt一致，无关sync记录保持不变。限定环境doctor通过，hold已受控解除。没有全量发布、调用GTO或读取其schema，未改业务依赖/服务/数据。

独立reviewer Carver首次完整审查与同reviewer范围复审已完成，P6-001..012全部关闭；最后5处文档原则修订复审通过。主协调22项原生回归、4项hold守卫、1项目模板测试通过；配置成功/失败边界4组通过。两项目project doctor发布后再次通过，drugsale Linux pnpm typecheck通过；五容器ID/StartedAt/healthy不变。

ACC-05/06/07/08通过。ACC-01用户确认可用、主协调实操证据待补；ACC-02 Browser真点击/title/URL、ACC-03用户新附件、ACC-04自建窗口生命周期仍pending。本会话工具清单没有官方Browser/Computer Use操作工具，不能用HTTP、doctor或用户确认替代这些证据。migration_accepted=false；这是证据缺口，不是清理实施被阻塞。

验证报告：p6-publication.json、p6-final-audit.json、p6-verification.json、p6-cleanup.json。私有恢复包：/mnt/c/Users/Laptop/.codex/.ai-harness/backups/windows-native-transition-20260910-p6-085320；原始pre-switch包保留，不能整份覆盖当前配置。过程脚本及p6-before原像已移至 process-materials；旧 .tmp 路径仅为历史位置。

恢复：先重建任务hold；对需恢复目标比较当前hash与p6-publication/最终审计的after证据，漂移则停止覆盖并定点合并。installed文件与receipt可从私有 files 前像按目标恢复；原生config只按迁移键做合并，不能用整份旧config覆盖Desktop后续字段。16文件演练仅证明隔离字节恢复，不证明整机/业务数据恢复。

## 全面扫描后的当前结论（覆盖此前清理完结表述）
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
