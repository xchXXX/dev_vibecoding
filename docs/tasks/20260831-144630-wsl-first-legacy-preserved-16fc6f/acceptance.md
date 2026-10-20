# Windows 联网代理、显式 WSL 优先：验收记录

> MIXED-SCOPE-CORRECTION-001：当前混合模式最终口径（2026-09-01）。Windows原生是智能体/默认命令后端，WSL只控制集成终端；显式WSL路由依赖全局规则和智能体执行。Hook独立保留，不阻塞核心目标；历史保持。

## 验收目标

以Windows智能体正常联网，在项目与依赖支持时由智能体依全局规则显式调用Ubuntu-24.04执行日常Linux命令，旧Windows脚本保留为最终效果。Windows智能体保持Windows、集成终端设置WSL是当前预期状态；UI不负责自动逐命令调度。

## 验收标准

核对Windows智能体与WSL集成终端的独立含义；验证全局规则已加载，显式WSL普通用户、Linux工具/cwd、原仓库路径、真实退出码和旧Windows入口主路线命中；说明项目/依赖适用边界并完成原reviewer复审。Hook仅记录独立安全风险，不作为平台路由或WSL核心完成条件。

## 必备证据

| 项目 | 当前证据及界限 |
| --- | --- |
| 设置含义 | 用户截图及配置投影均为Windows原生智能体（`runCodexInWindowsSubsystemForLinux=false`）和WSL集成终端（`integratedTerminalShell=wsl`）。前者决定智能体/默认命令后端，后者只影响集成终端；界面不自动调度后续命令。 |
| Windows实际回合 | 普通认证Windows CLI 0.151.0-alpha.7.2的单次ephemeral JSON只读回合已出现thread.started、command_execution、turn.completed，thread为01a0577e-dea5-7bc3-b0dd-f0c475104a9a。此前TLS+403仍仅是传输证据；单次真实回合不外推所有网络任务。 |
| WSL网络与路径 | 已观察无代理变量、localhost端口拒绝、直连ChatGPT不可达；完整代理切换日志有 `error_is_connect=true` 和错误cwd拼接，前轮MCP/node_repl有ENOENT。本批不复现网络、不改全局设置。 |
| 显式WSL与旧入口 | MIXED-VERIFY-001主路线本轮exit0；Ubuntu uid1000/native工具、Windows旧入口/参数/cwd/UTF-8/exit23、18docs、隔离CFM 1 case/0 pending及finally清理通过。不外推全部旧PS后端兼容。 |
| 显式路由规则 | 当前Windows home为C:/Users/Laptop/.codex，原AGENTS、模板、receipt哈希完全匹配。全局AGENTS要求支持时显式wsl.exe路由并保留Windows旧入口；不另建Linux home，也不把规则加载证据说成UI自动调度。 |
| 已审实施 | 原源码、生成物和限定部署的PASS保留；旧16文件审查hash仅是此前冻结证据，本批不修改该源码集合，也不以其替代当前运行时验收。 |
| Hook解耦 | PreToolUse为Installed 2、Active 0、Review 2，真实allow/deny未验收；这是独立安全风险。Hook不选择Windows/WSL平台，也不阻塞显式WSL核心目标；普通命令结果不能冒充Hook生命周期。 |

## 未决项

1. 原reviewer按最终三文档和用户导航的内容哈希复核：必须一致说明Windows智能体、WSL集成终端、显式wsl.exe规则路由及适用边界，不把UI写成自动调度器。
2. Hook Installed 2/Active 0/Review 2、真实allow/deny未验收作为独立安全遗留保留；用户无需为完成WSL目标切换、重启或信任Hook。若以后处理，不能Trust all或越过原安全边界。
3. 原CFM 1024容量、旧PS fallback限制及未来项目/依赖可能不支持WSL继续列明；不清理、扩容、迁移或宣称所有命令自动进入WSL。

## 最终结论

Windows智能体联网、显式WSL主路线和全局规则加载已有命中证据；Windows原生智能体加WSL集成终端是当前正确配置。该效果依赖智能体遵守全局规则显式调用wsl.exe，不是UI自动调度，也不保证所有未来项目/依赖。Hook未信任风险已解耦，不阻塞WSL核心目标；当前仅待原reviewer按最终文档/导航内容哈希复核，用户无需切换、重启或信任Hook。

## 历史记录（截至RESTART-DOC-001）

以下全部内容均为历史，包括原必填章节、旧“最新”结论及其操作建议；当前合同仅以上方当前段为准。正文未删除，仅调整历史标题。

### 历史：WSL 优先、旧脚本保留：验收记录

#### 历史：验收目标

验证 plan.md 六项标准。区分已完成的安装、控制器恢复、规则部署与Hook入口隔离验证，和未完成的桌面代理真实切换/活动配置home/Hook真实安装信任及命中。

#### 历史：验收标准

代理和常用工具在通用 WSL2 中运行；选定开发命令成功；旧脚本在 Windows 后端正确执行；新进程规则与治理机制有命中证据；针对性验证和独立实现审查通过；现有工作区、记忆数据和 Docker 内部环境边界得到保护。

#### 历史：必备证据

- 初检默认命令环境为 Windows PowerShell 7.6.4，当前账户仅注册 docker-desktop；主代理与独立只读代理结论一致。它是历史基线，不是安装后现状。
- 经用户后续授权，Ubuntu-24.04 已安装为 WSL2并设默认；本任务未向Docker发启动/修改命令；末次只读状态为Running，与初检Stopped不同，启动来源未归因。Linux内核、Ubuntu24.04.4、原生Git/Python/rg/Node/npm路径均已实测；具体版本与安装哈希见 execution.md。
- 从WSL访问原 /mnt/d 仓库，原生Git识别根目录成功；通过Windows pwsh.exe/wslpath执行未修改的 validate-plan-docs.ps1 exit0，18文档/0error/0warning。中文stdout已通过临时调用进程设置UTF-8后验证，旧脚本未修改。
- 控制器原缺陷通过真实schema最小Red命中，修复后Initialization 4/4、完整控制面101/101、skill-doc检查通过。正式schema、安全边界、旧任务均未改。
- 独立reviewer对初始化修复五文件增量PASS，并独立重跑Initialization 4/4及真实schema happy path 1/1；没有把该PASS当作整项WSL验收。
- 同task_id真实恢复init和validate通过，无错误/警告。原失败草稿、事件字节与顺序保留于任务运行留痕，原实施者已核对哈希。
- 未修改的Hook源文件直接用Linux Node测试：安全输入exit0且无拒绝输出；原始state写入分类返回deny。没有实际执行该写入，也未宣称Codex Hook生命周期已命中。
- 原有文档校验：validate-doc-routing.ps1 exit0（6tasks/18docs/0error）；git diff --check exit0。后续最新改动仍需复核。

#### 历史：未决项

1. 普通用户前置条件已通过：用户创建laptop后实测DefaultUid=1000、HOME=/home/laptop，跨系统主路线在uid1000下exit0；未读取或处理用户密码。
2. 当前默认exec仍为Windows；应用的Agent environment、真实WSL新进程与实际CODEX_HOME须验收，不假定只改集成终端就生效。
3. 已解除：最新“确认”授权的dirty overlap接口已完成，106/106控制面回归、原reviewer独立5组通过。主协调核对17个重叠路径、最新HEAD/哈希和原备份后，正式capture/resolve成功；未直接改state或放松门禁。
4. 已解除：托管AGENTS与两份有内容变化的JSON索引已部署；INDEX.md正常处理但未变。原reviewer独立确认生成内容、模板渲染、回执、备份及WSL uid1000读取hash一致。F001仍closed/round1。
5. Hook可选WSL安装入口源码及隔离验证已完成：新增WSL组2/2、原完整套件27/27通过；原reviewer独立重跑WSL两组2/2通过，三文件hash与送审一致，源码检查暂未发现可行动问题。真实配置仍保留Windows通用命令，未安装新定义；重启后确认活动home再最小部署、用户精确信任及真实allow/deny验收。不得关闭Hook或绕过信任。
6. CFM成功回写因原库case容量1024失败，已记录容量错误；不删旧记录、扩容或迁移。隔离测试不得污染正式经验库。

#### 历史：最终结论

实施和验收分开：Ubuntu普通用户/原生工具、初始化及overlap接口恢复、真实resolved裁决、规则源码/索引/托管入口部署、选定WindowsPython跨平台主路线和Hook可选入口隔离验证均已完成。当前汇总原reviewer对全部增量的审查；真实桌面代理/活动home/Hook实际安装信任与生命周期仍未闭合。不得标记任务completed/final-pass，也不宣称所有旧脚本兼容。继续沿用原task_id。

#### 历史：前轮独立收尾结论（历史）

原reviewer覆盖11个实施文件与3份任务文档，源文件限定PASS、无新可行动finding。F001由原doc-curator返工并原reviewer关闭（round1）。reviewer独立主路线exit0，fixture清理通过；未将旧fallback诊断或用户门禁计通过。任务status/current_phase均为blocked，review.verdict=needs_more_evidence，控制器validate 0errors/0warnings；不调用finalize-task。

新测试12,083bytes，SHA256 F7D36950CFDD0D2331D3D287DFF473FAE5873AA797040FB2EAC1A52A02BA4B01。原PS fallback严格诊断仍exit1，主路线显式选择WindowsPython且无失败后跨平台重跑。两处独立诊断目录在.tmp暂留，路径与策略拒绝原因见execution。

普通用户复核更新：用户创建后主协调器重跑既有边界测试exit0，uid1000与全部主路线结果已观察，fixture清理通过；该更新不改变上一轮独立review的历史记录，也不关闭桌面代理/部署/Hook门禁。

#### 历史：本批验收与续接

新增overlap接口及真实裁决、规则部署已各获原reviewer限定PASS；Hook新入口独立最小WSL两组也已通过。完整控制面106项、原Hook27项及其他既有回归分别保存原实施者证据，未冒充全部由reviewer重跑。此前F001保留closed/round1；本批累计实际实施增量16文件，INDEX.md是已处理但未改变的第17个计划目标。整体不能final/pass，剩余真实代理/活动home/Hook安装信任及生命周期需要用户重启后继续。

继续使用同task_id。下一轮先只读确认平台、UID、HOME/CODEX_HOME和加载来源；不重新init、不复制.codex。由代理执行范围内最小Hook安装和验证；如实际home在Linux文件系统，先补相同文件系统的隔离验证。精确Hook信任仍由用户操作，不能由旧Windows信任外推。套件自有fixture在执行后清理，两处独立诊断库因原平台清理拒绝暂留允许.tmp；原CFM容量及PS fallback计数限制保留原样。

最终审查回执：原reviewer统一结论为“已实施源码、生成物与限定部署证据PASS；整任务needs_more_evidence，不得finalize；无新增可行动finding”。累计16文件ordinal内容SHA256为6248a9bcc1a9b83bd9ce3e1e4e8cc7591ad9c7ee5352d1c8255fb91fad9eac70，与主协调独立值相同。F001保持closed/round1。正式REVIEW-001结果及事件已记录，任务status/current_phase均blocked，仅等待上述用户重启及真实Hook运行时门禁。本段为审查结束后的结论回执，不改变已审源码或实施范围。

#### 历史：最新重启验收（2026-08-31，RESTART-DOC-001）

本节替代前文作为当前验收结论；此前“等待用户重启”仅为历史记录。用户已真实重启，ChatGPT.exe PID9324（17:10:44）与其codex.exe子进程PID7448（17:10:47）的启动时间、父子关系已由主协调和doc-curator分别核对，但默认exec仍是Windows PowerShell 7.6.4。

| 验收项 | 最新证据与结论 |
| --- | --- |
| 应用重启 | 已证实，不再是当前阻塞。 |
| 代理WSL设置 | `desktop.integratedTerminalShell=wsl`，但代理键 `desktop.runCodexInWindowsSubsystemForLinux` 及两处旧迁移键均缺失；本机源码给该代理键默认false。当前仅设置了集成终端，代理WSL开关未启用，界面状态仍待截图核对。 |
| 显式WSL开发环境 | Ubuntu-24.04 uid1000、HOME=/home/laptop可用；CODEX_HOME未设且Linux `.codex` 不存在。只证明显式子进程，不证明桌面代理或其活动home。 |
| 已部署文件与已审增量 | AGENTS、receipt、模板、hooks.json哈希均与上轮一致；主协调复核16文件manifest仍为 `6248a9bcc1a9b83bd9ce3e1e4e8cc7591ad9c7ee5352d1c8255fb91fad9eac70`。原源码、生成物及限定部署PASS不变，F001仍closed/round1。 |
| Hook运行时 | 本轮未安装新定义，实际WSL代理活动home、规则加载、Hook精确信任与真实生命周期均未验收。 |

本机静态前端源码含有依赖feature条件的旧WSL弃用提示；这不证明用户当前看到该提示，也不证明必须另装CLI。下一步先由用户截图Agent environment设置，确认WSL选项或弃用提示，再据实际界面决定操作；不盲目再次重启、不直接修改配置、不安装Hook或CLI。

当前结论：这是重启后发现的设置差异，不是新源码缺陷或已审结果失效。最新阻塞为代理WSL设置未启用及界面待核对；真实代理/home/Hook门槛继续未完成，整任务保持needs_more_evidence，不得finalize。详细证据与本轮文档校验见execution.md同名章节；历史记录保留不覆盖。
