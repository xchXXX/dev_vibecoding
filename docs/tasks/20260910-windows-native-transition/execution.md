# 施工记录

## 施工目标

完成 Windows 切换前准备，保留 Linux 开发能力及可恢复性，将后续清理/验收交给新 Windows 主协调。

## 前置条件

用户已授权本轮准备和控制记录落盘；不调用 GTO；当前 Agent 仍在 WSL。Ubuntu-24.04 与 docker-desktop 已通过 wsl.exe --list --quiet 核实。

## 执行顺序

遵循 plan.md P0-P8。本轮止于 P3；切换设置与重启属于用户动作。

## 文档先行清单

plan.md、execution.md、acceptance.md、state.json、task.md、events.jsonl；接手提示词与 inventory.md 在交付前补齐。

## 测试同步清单

维护标志必须阻止 bootstrap 与 sync 写入；同步 API 也必须拒绝。fixture 内创建维护标志并以文件树比较验证。

## 实施批次

- P0：建立合同；安装版 machine doctor baseline fail 已记录 CFM；harness project doctor pass。
- P1：两个最小 Red 命中缺少维护前置检查（bootstrap 在夹具中已经写入 AGENTS）；补充两入口的存在性闸门后目标 3/3 Green，无标志旧校验保持。
- P2：备份原文件；启用已安装原生 computer-use，停用已存在 computer_use_wsl；browser_use_wsl 本机不存在未创建；node_repl/cua_repl 与全部非目标配置结构不变。只调用 AGENTS 所属生成函数进行定向渲染，不执行 bootstrap/sync 发布流程、不发布当前 Browser 候选或 GTO。
- P2：更新三条环境规则并用正式生成器刷新索引；为当前安装/兼容/脚本入口补维护通知；drugsale 只修正环境段和浏览器分工，保留业务指令。
- P3：Windows wsl.exe 实际指定 Ubuntu-24.04 返回 Linux、正确项目 cwd、/usr/bin/python3、/usr/local/bin/node、/usr/bin/git、/usr/bin/docker；两个项目已安装 project-env-doctor 均为 ok=true、findings=[]、errors=[]。
- P3：26 条规则、19 个任务文档和 65 份文档路由校验通过。准备候选进入首次独立全局 review；重启后 ACC 均未执行。
- P3 接续：重新运行 8 项维护/定向同步测试全部通过（9.693 秒）；通过 Windows wsl.exe 重新运行两个 project doctor 均通过；23 项 snapshot verify 与 15 个修改目标只读恢复前检通过，限定文件 git diff --check 通过。
- P3 接续：未获得完整独立 review 报告；侧会话不允许调度或联系子代理，因此 PRE-06=blocked，ready_to_switch=false。将六份记录与交接提示词更新为真实状态，由主会话补齐审查，不修改运行配置、不切换、不重启。

## 每批写入范围

仅 plan.md 明确的入口、环境指令、配置布尔值及任务记录。当前 runtime_common.py、桥接实现和外部能力 schema 是其他进行中候选，不在本轮发布或覆盖。

## 验证命令

`PYTHONPATH=tests/harness python3 -m unittest test_windows_native_transition -v`；使用指定发行版运行两个已安装 project-env-doctor；两个入口维护停止检查；任务文档校验。后继不得无条件重跑旧 machine doctor 以触发 bootstrap。

接续复核：`PYTHONPATH=tests/harness python3 -m unittest test_windows_native_transition test_sync_codex_scope -v`；`python3 .tmp/windows-native-transition/snapshot.py verify`；私有恢复包 `check-restore.py` 为只读检查，不执行恢复。两个项目 doctor 的完整 Windows→WSL 命令见 handoff-prompt.md。

关键过程记录、恢复包和任务脚本暂留原位；任务未完成，不执行最终清理。测试 TemporaryDirectory 夹具由测试自身回收，任务脚本不是残留运行服务。

## 回退方案

私有备份位置与逐文件清单交付时记录在 inventory.md。当前仅做切换准备；恢复须比较 post hash，漂移停止。不能用整库 reset 或整份旧配置覆盖后续工作。

## 审查与返工路径

独立子代理只读 review；首次覆盖整个准备候选及后继迁移计划，列出全部发现。主协调修复并测试，后续 reviewer 按 finding 和影响面复审。主协调自己执行验收。急用插件通过只表示该路径可用，不能结束全部迁移。

## 主会话接续（独立审查进行中）

已以 fork_turns=none 委派只读 pre06_reviewer，不继承整段对话、不再委派。主协调核实进程为 Linux WSL、CODEX_HOME 实际路径如 inventory；工具发现有 node_repl，未把它作为 Windows GUI 证明。用户已明确三个急用插件，ACC 保持 pending。

本次 harness 与 drugsale 已安装 project doctor 均 ok=true、findings=[]、errors=[]；在当前 WSL 直接运行。最小维护测试 test_windows_native_transition 3/3，3.073 秒。未重跑包含 GTO 发布夹具的 test_sync_codex_scope；旧 8/8 仅保留历史记录。

快照脚本返回 ok=false（退出码仍为 0），恢复前检 exit 2；原因仅 config.toml 的 model_reasoning_effort 漂移。CFM 已 record-failure/query-before-retry：d7c261908c5d6b333c0bff3ac217d2a37388ca417d64def81f435001702860a7、5eee284143d30d17e9d00193adb4e8c6dbf298b42787419660ea6e511792403f。未修复或重封存配置，不能回写原检查成功。技能路径误读已记 CASE-7895f2025fc440a7，明确补记晚于首次纠正读取，不倒填合规顺序。

采用 receiving-code-review 核对 reviewer 指出的真实 receipt/解除维护循环前提；仅修订任务计划与交接顺序，未解除标志或发布。待完整报告后由同一 reviewer 范围复审。

## PRE-06 首次报告与范围修复

独立完整报告由主协调记录在 review.md：2 项 P2、2 项 P3，首次结论暂不关闭。主协调已修订 PRE06-001 的 ACC-07 隔离/真实同步措辞，PRE06-002 的历史/当前证据分表。后续再次从 Windows wsl.exe 指定 Ubuntu-24.04 调用两个项目 doctor，均 exit 0、ok=true，无 findings/errors。

PRE06-003 最小 Red：只运行 test_snapshot_detects_empty_directory_creation，1 test / failures=1，0.278 秒；AssertionError 为新增空目录后旧 snapshot 仍相等，与事先声明一致，不触发 CFM。随后 snapshot 增加目录项及对象类型，生产入口未变。

PRE06-004：主协调独立只读 hash 核验 before 和 after_copy 全部匹配，共 23 项；snapshot.py verify 本身的检查缺口未被伪称已修复。恢复策略保留 model_reasoning_effort 与缺省 enabled 语义。

PRE06-003 Green/回归：`PYTHONPATH=tests/harness python3 -m unittest test_windows_native_transition -v`，4/4，5.841 秒；目录检测命中，bootstrap CLI/sync API 维护停止与无标志既有校验通过。测试 TemporaryDirectory 自动回收。

## 主协调准备收口

同 reviewer 范围复审通过，PRE06-001..004 全部关闭。主协调最终只读核验：测试候选 hash 9299cc7d97b9af25175793f3452334e2cbb4d1ae70b1aacf66fcce5d71c97b0f 不变；23 项 before/after 副本完整；22 项非配置当前内容匹配；配置已知 model_reasoning_effort 漂移未再变化；维护标志保留；实际进程仍 WSL。PRE-07 纯状态收口后 P4/ready_to_switch=true，等待用户切换重启。所有 ACC pending、migration_accepted=false。

本次只改任务记录和测试快照覆盖，未修改运行配置/生产入口、未全量发布、未解除标志。测试夹具已清理，.tmp/windows-native-transition 只保留原任务 snapshot.py/apply-config.py，任务与私有恢复证据留待迁移结束。

## Windows 原生接续实时结果（2026-09-10）

用户报告已切换；实际 Win32NT / Windows PowerShell 路径已确认，Windows codex.exe PID 27720、28412 均来自 C:/Users/Laptop/AppData/Local/OpenAI/Codex/bin/8e5b6932251c2c1c/codex.exe。未借助 CIM 获取父进程；该检查被环境拒绝，没有伪称进程父子关系已证明。

CODEX_HOME 环境变量为空；Windows 用户目录 C:/Users/Laptop/.codex 的任务 hold、恢复包及 config 存在。只输出允许字段的结构核对显示：computer-use、browser、unified-computer-use enabled=true；computer_use_wsl=false。node_repl/cua_repl 的 enabled 键不存在，此结果不能解释成禁用。Browser 标准缓存现已存在。

当前所有可调用工具中不存在 node_repl/cua_repl/Browser/Computer Use 操作工具。已读 Computer Use 技能，要求通过官方 node_repl 导入 @oai/sky；当前缺少该入口，不能启动自造客户端代替。Browser manifest 要求使用内置 Browser，未通过 shell 或 web.run 冒充点击。

当前任务 cwd=C:/mnt/d/prj/harnesss/dev_vibecoding 不存在；真实 D:/prj/harnesss/dev_vibecoding 存在，应用项目登记也指向 D:/。之后所有命令显式指定真实 workdir，未创建镜像或搬库。

裸 wsl.exe 不在当前 PowerShell PATH。C:/Windows/System32/wsl.exe 确实存在；受限沙箱首次调用返回 Wsl/EnumerateDistros/Service/E_ACCESSDENIED，只读提权调用成功；随后用户将权限设为完全访问，重新列举成功。Ubuntu-24.04 和 docker-desktop 均存在。切换后 harness 已安装 project doctor 通过（ok=true/findings=[]/errors=[]），不代表 ACC-05 的两项目代表性测试/构建通过。

CFM：CASE-7bd1e169f71a4672（错误 cwd，显式真实路径验证）、CASE-f5efc1124c7bd74e（WSL 绝对路径）、CASE-4550f51e4ef2a7df（沙箱服务访问边界）已记录查询与成功。首次纠正读取/沙箱回退早于补记，未倒填合规顺序。CIM 失败 signature b8757d3031d6b54c9e16c53184f042812edb37ee88917138663c85cff3810f97 已记录/查询，未重试或伪称修复。

本批仅更新任务事实；不改 config/transport、不全量发布、不解除 hold。P5 GUI 能力缺失阻塞优先插件验收，ACC-01/02/04 blocked；其余 pending，migration_accepted=false。
## P6 实施期间事实（历史）

当前 P6：已完成 Windows 原生切换，用户确认 Computer Use、Browser 和 unified-computer-use 正常使用。PRE-01..07 已通过，不重做。主协调继续定向清理；GUI 工具在本会话未暴露，仅对应证据 pending，不阻塞其余实施。

实际项目 D:/prj/harnesss/dev_vibecoding；WSL /mnt/d/prj/harnesss/dev_vibecoding。应用携带的 C:/mnt/d 路径无效，不复制仓库。命令指定真实 workdir，并使用 C:/Windows/System32/wsl.exe -d Ubuntu-24.04 --cd <Linux项目> --exec <命令>；复杂内容先写脚本，禁止将 Markdown 反引号嵌入默认 shell 的 python -c。

原生声明 v3、只读诊断、environment-only 发布与 receipt 驱动的旧技能退役已实现，尚未发布。独立 Carver 正在做完整迁移首次 review；有修复则同 reviewer 范围复审。维护 hold 仍存在；发布前先冻结私有 installed 前像和候选 hash。仅正式 environment-only 与 retire-legacy-gui 入口可用于本任务，不全量发布、不调用 GTO/schema、不改正在使用的插件配置。

ACC-05：两个项目 project doctor 均通过；harness 原生环境回归12项及维护守卫4项通过；drugsale Linux pnpm typecheck 通过。ACC-06：现有五容器均 healthy，未重启或改服务。ACC-01 用户确认可用但待主协调操作证据；ACC-02/03/04 pending；ACC-07/08待定向正式发布与恢复演练。migration_accepted=false。

Docker 只读基线：worker 72a22f7b9905、api 29bca7421b41、web d36f57799fea、postgres 863919c56230、redis aa66ea23c3af，全部 healthy。后续复核相同容器与 StartedAt，不能以此替代 GUI。

P6进一步修复：22项原生回归通过24.617s，模板目标1/1；隔离正式environment-only/retire-legacy-gui各运行2次，第二次changed=false，16文件字节恢复通过且夹具清理。私有installed前像 C:/Users/Laptop/.codex/.ai-harness/backups/windows-native-transition-20260910-p6-084433。真实配置删除dry-run和5组夹具通过，尚未apply。

## P7 当前最终事实

Windows 原生迁移的源码与安装清理已完成，当前 P7，剩余 GUI/新附件证据待补。用户已确认 computer-use、browser、unified-computer-use 正常使用；无需再次切换或重复准备。

Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；Git、Python/Node、测试构建、Linux 依赖和服务继续在 Ubuntu-24.04。实际项目 D:/prj/harnesss/dev_vibecoding；WSL /mnt/d/prj/harnesss/dev_vibecoding。Windows 调用使用 C:/Windows/System32/wsl.exe 指定发行版和 --exec，工作目录用真实 D:/，不创建 C:/mnt/d 镜像。

已删除旧 GUI 桥源码/技能/旧测试、installed node-repl-wsl-compat.py、installed windows-computer-use-wsl 技能，以及 config.toml 中停用的 computer_use_wsl 表（browser_use_wsl 原本不存在）。不保留旧运行兼容层；私有恢复材料不参与技能发现。bootstrap/doctor 只读原生插件配置，所有原生插件与官方 transport、其余配置语义保持不变。

正式 environment-only 发布和 retire-legacy-gui 各执行两轮，第二轮无变；10个环境运行文件源/安装/receipt吻合，AGENTS/template receipt一致，无关sync记录保持不变。限定环境doctor通过，hold已受控解除。没有全量发布、调用GTO或读取其schema，未改业务依赖/服务/数据。

独立reviewer Carver首次完整审查与同reviewer范围复审已完成，P6-001..012全部关闭；最后5处文档原则修订复审通过。主协调22项原生回归、4项hold守卫、1项目模板测试通过；配置成功/失败边界4组通过。两项目project doctor发布后再次通过，drugsale Linux pnpm typecheck通过；五容器ID/StartedAt/healthy不变。

ACC-05/06/07/08通过。ACC-01用户确认可用、主协调实操证据待补；ACC-02 Browser真点击/title/URL、ACC-03用户新附件、ACC-04自建窗口生命周期仍pending。本会话工具清单没有官方Browser/Computer Use操作工具，不能用HTTP、doctor或用户确认替代这些证据。migration_accepted=false；这是证据缺口，不是清理实施被阻塞。

验证报告：p6-publication.json、p6-final-audit.json、p6-verification.json、p6-cleanup.json。私有恢复包：/mnt/c/Users/Laptop/.codex/.ai-harness/backups/windows-native-transition-20260910-p6-085320；原始pre-switch包保留，不能整份覆盖当前配置。过程脚本及p6-before原像已移至 process-materials；旧 .tmp 路径仅为历史位置。

恢复：先重建任务hold；对需恢复目标比较当前hash与p6-publication/最终审计的after证据，漂移则停止覆盖并定点合并。installed文件与receipt可从私有 files 前像按目标恢复；原生config只按迁移键做合并，不能用整份旧config覆盖Desktop后续字段。16文件演练仅证明隔离字节恢复，不证明整机/业务数据恢复。

## 新一轮全面环境扫描（进行中）
用户要求另一独立reviewer全面检查历史生成代码/测试/文档和环境链路。Fermat只读扫描，主协调当前核对原生宿主、限定安装doctor和五容器健康：均正常；这不证明全库无旧产物。详见environment-scan-baseline.json。扫描未结束，不继承上一轮全面清理结论。

## 全面扫描后的当前结论（覆盖此前清理完结表述）
当前全面扫描已完成，结论为仍需整改，不能宣称全部环境产物已扫净。新的独立reviewer Fermat发现11项：P1=0、P2=6、P3=5，详见environment-scan-review.md。上一轮P6-001..012关闭仅保留为当时范围的历史证据，不覆盖此次新发现。

已证明的内容继续成立：Windows原生宿主与三插件正常配置；正式安装中的旧WSL GUI桥运行时/技能已删除，10个环境文件源/安装/receipt一致；限定环境doctor通过，五容器ID/StartedAt/healthy不变。维护hold当前已解除。

需要整改：默认Codex home/CFM目标可能误落WSL home；strict合同错误拒绝合法Windows PowerShell；健康测试夹具缺原生插件；架构/附件/Browser/药品项目长期文档旧分工与当前事实冲突；遗留一个旧桥测试bytecode；测试临时父目录及导航未收口。所有ENV-SCAN-001..011仍开放，尚未实施新修复。

Windows负责Agent文件、Browser、截图、Computer Use；WSL保留Git/开发命令/Python/Node/测试构建/Linux依赖和服务。当前Ubuntu CODEX_HOME未设置、HOME=/home/laptop，与C:/Users/Laptop/.codex不同；不得靠删除Linux用户目录掩盖目标选择问题。

继续按既有迁移授权定向修复、验证并由同一reviewer做影响范围复审。禁止GTO/orchestrator_ctl/GTO schema、全量发布、覆盖混合dirty、改原生插件transport、误删历史/恢复包/业务依赖数据。GUI与新附件证据仍pending，migration_accepted=false。

### ENV-SCAN repair candidate
11 findings addressed in source/docs/fixtures; hold re-established. Native 28/28 (22.860s), CFM 12/12, hold and pure fixture 6/6 passed. Four planned minimal Red failures matched expected assertions. Unexpected document-contract failure recorded and closed as CASE-004807a8676e8a5e after correction. Fermat resumed for read-only scoped rereview; installed publication still pending.


隔离正式bootstrap environment-only与CFM-only sync两轮通过，第二轮无变化；config/AGENTS和无关receipt行保全；17文件隔离恢复通过。实际安装前像17文件已封存，候选hash已冻结。review尾项只有4份文档/metadata，已修正并对最终候选重跑隔离验证通过。


## ENV-SCAN 整改最终事实（覆盖此前整改中状态）

同一独立reviewer Fermat两轮范围复审关闭ENV-SCAN-001..011：首次关闭10项，最后四文件入口/metadata delta复审关闭001。未新增兼容桥；旧运行时、技能及孤立测试bytecode已不在活跃路径，测试不再遗留固定任务父目录。Windows负责Agent文件与GUI，WSL保留开发命令、依赖和服务。

主协调验证：native28项、CFM12项、hold4项、合同fixture2项通过；26条规则元数据校验通过。最终候选隔离和实际正式发布均限定environment-only与CFM-only，各两轮、第二轮无变化；源码/安装/receipt真实hash一致，插件config及AGENTS字节未改、无关receipt行未改。两个项目doctor及限定环境doctor通过，5容器ID/StartedAt不变且healthy。17文件隔离恢复通过，29份源快照校验完好。维护hold已解除。详细证据见envscan-isolated-publication.json、envscan-live-publication.json、envscan-postpublish-verification.json、envscan-final-audit.json。

本次审查与验证边界排除GTO实现/schema/专项测试、全局strict及真实GUI验收；没有全量发布。ACC-05..08通过，ACC-01..04保留主协调GUI/新附件证据缺口，用户插件可用事实保留，migration_accepted=false。这些证据缺口不表示插件不可用，也不表示环境清理仍未施工。历史记录及私有恢复包仅作证据，不作为活跃兼容实现。
