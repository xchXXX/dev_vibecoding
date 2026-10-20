# Windows 联网代理、显式 WSL 优先：施工记录

> MIXED-SCOPE-CORRECTION-001：当前混合模式最终口径（2026-09-01）。Windows原生是智能体与默认命令后端，WSL只控制集成终端；显式WSL路由由全局规则和智能体执行实现。Hook独立记录，不阻塞核心目标；历史保持。

## 施工目标

沿用 `20260831-144630-wsl-first-legacy-preserved-16fc6f`，纠正Windows智能体、WSL集成终端和显式命令路由的关系。本轮只更新三文档当前段，历史、源码、配置和Hook不变，不重新初始化任务。

## 前置条件

用户在完整WSL代理连接失败后已回退Windows。当前默认home为 `C:/Users/Laptop/.codex`；doc-curator只读精确配置投影确认代理开关为false、集成终端为wsl。主协调已正式更新任务验收，原20项workspace overlap仍resolved；源码、配置和网络改动不在本批范围。

## 执行顺序

消费MIXED-SCOPE-CORRECTION-001正式brief并回传实际hash，依据用户截图、更新后的任务合同和已通过主路线更新三文档当前段；再运行文档结构、分流、限定diff与历史核对，短结果由主协调记录。不要求用户切换/重启或信任Hook来完成WSL核心目标。

## 文档先行清单

仅本目录plan.md、execution.md、acceptance.md当前段；三文档历史正文保持字节不变。旧源码审查PASS不由本批重写或推翻。

## 测试同步清单

纯文档调整不新增镜像测试、不重做网络实验。本批运行既有文档结构、分流和范围检查，核对三文档历史不变。混合主路线及Windows普通认证CLI单次回合已有真实结果；Hook仍未激活，普通命令执行成功不能算Hook allow，Get-Content自身报错也不能算Hook deny。

## 实施批次

此前初始化/overlap恢复、Ubuntu普通用户工具、规则与限定AGENTS部署、选定WindowsPython主路线、Hook源码及隔离命令验证已有记录与限定PASS。本轮回填已完成的混合主路线与待信任的真实Hook诊断；完整WSL代理尝试的连接/cwd错误继续保留，不再作为必须修复的验收路线。

## 每批写入范围

只写本目录三文档当前段。沙箱外写入使用已授权用户上下文；不修改历史、原始state、事件、其他任务、源码、配置、Hook、认证、memory或全局网络，不建立第二报告。失败闭环由主协调处理，doc-curator不越过三文件边界。

## 验证命令

使用Windows PowerShell 7执行已有 `scripts/validate-plan-docs.ps1 -RepoRoot <repo-root> -Json` 和 `scripts/validate-doc-routing.ps1 -RepoRoot <repo-root> -Json`；在已确认用户上下文检查三文档当前段diff，并核对三文档历史未变。只读配置投影结果为 `desktop.runCodexInWindowsSubsystemForLinux=false`、`desktop.integratedTerminalShell=wsl`，未输出其他配置内容。WSL只读调用在受限沙箱因Wsl/Service/E_ACCESSDENIED被拒绝后，经主协调record/query，原调用在已授权用户上下文exit0；未换平台、改权限或改safe.directory。

## 回退方案

保持用户当前Windows回退状态，不为旧历史门槛再把代理切入WSL。文档若需返工，仅由原作者按原reviewer finding修改获批两文件当前段；历史正文保留。不得以联网失败为由改代理、复制认证、安装CLI、清理经验库或自动重跑另一平台。

## 审查与返工路径

短result交主协调记录，原reviewer审三文档及用户导航与最终合同一致性。真实Hook信任及allow/deny仍未验收，作为独立安全风险保留，但不是命令路由器，也不阻塞WSL优先核心验收。原CFM容量1024及旧PS fallback限制继续列入已知限制。

## 回退与网络前置证据（MIXED-DOC-001）

以下网络、切换日志和MCP证据由主协调本轮提供，本doc-curator未重做网络实验，也未读取凭据：

- Windows侧 `127.0.0.1:15236` 可达；访问ChatGPT经显式HTTP代理完成TLS并收到403，只证明传输到达，不能证明认证成功或模型/应用请求成功。
- 显式WSL内无代理变量，localhost对应端口拒绝，直连ChatGPT网络不可达；不能把Windows代理端口在WSL NAT中直接视为同一可用服务。
- 完整代理切换失败日志出现 `error_is_connect=true`；cwd错误把Windows路径拼到 `/mnt/c/Program Files/WindowsApps/.../resources` 后。前轮MCP/node_repl另有ENOENT；这些是已观察到的连接、路径与工具启动症状，不归并为未经验证的单一根因。
- 用户已回退Windows并要求继续直到最终效果；主协调正式验收改为Windows联网代理加显式Ubuntu命令优先。本批配置投影独立确认代理开关false、终端wsl，当前默认home采用已核对的Windows `C:/Users/Laptop/.codex`。
- 后续不要求完整代理迁WSL。现已进一步确认真实Windows CLI的PreToolUse为Installed 2、Active 0、Review 2；指定用户Hook等待精确信任，后续证据见下节。任何安装或网络更改仍须落在另行明确的授权范围。

## 本轮主路线与真实Hook结果（MIXED-CLOSE-DOC-001）

以下执行结果来自主协调已记录的验证/运行时结果及其只读交互检查，本doc-curator不冒充独立重跑：

- MIXED-VERIFY-001已completed：主路线exit0；Ubuntu uid1000与原生工具、Windows旧入口、参数/cwd/UTF-8、真实exit23、18份文档校验均通过；隔离CFM为1 case、0 pending，finally清理通过。Windows home按USERPROFILE默认解析为 `C:/Users/Laptop/.codex`，原AGENTS、模板及receipt哈希全部匹配。
- Windows CLI `0.151.0-alpha.7.2` 使用普通认证完成一次ephemeral JSON只读回合，thread为 `01a0577e-dea5-7bc3-b0dd-f0c475104a9a`，观察到thread.started、command_execution及turn.completed。这是本次实际Windows代理回合证据，不能外推所有网络任务。
- 回合内Windows Node绝对路径执行 `--version` 返回exit0、v24.19.0；对缺失LiteralPath实际执行Get-Content返回exit1、ItemNotFound，未被Hook deny。probe文件仍不存在，hooks文件原SHA不变。普通命令成功及命令自身报错都不能冒充Hook生命周期通过，原MIXED-RUNTIME保持blocked。
- 主协调随后只读确认 `features list` 为 `hooks stable true`；同一Windows CLI进入Review hooks，session为 `01a05781-441b-79c3-a8fd-f3e58c5dbc3e`。PreToolUse显示Installed 2、Active 0、Review 2。这是独立安全遗留，不选择Windows/WSL平台，也不是WSL核心完成门槛。
- 目标Hook来自 `User config ~/.codex/hooks.json`，matcher为 `^(Bash|apply_patch)$`，命令为界面展示的Windows Node加原 `pre-tool-use-hook.mjs`，timeout为5s，Trust明确显示 `New hook - review required`。应审查界面里的当前完整定义，不把文件SHA当作Hook定义hash。
- 另一条Hook来自 `D:/prj/harnesss/dev_vibecoding/.codex/config.toml`，是旧pwsh `PreToolUse.ps1`，timeout为30s；它不在本次信任范围，因此不能使用Trust all。主协调未按t或执行信任，未输入模型prompt，TUI正常退出0。

用户无需为完成WSL优先目标再次切换、重启或信任Hook。若以后单独处理安全遗留，可在同一Windows CLI的 `/hooks` 或Review hooks中，仅审查 `User config ~/.codex/hooks.json` 这一条，核对来源、matcher、完整命令、5s超时和待审状态；不要Trust all或顺带信任范围外项目Hook。该可选操作及后续allow/deny复验属于独立安全工作，不反向改变已验证的显式WSL路由结论。

本轮事件信封错误由主协调保留原字节备份后，仅修正自身唯一未过校验末行，既有有效历史不动且validate通过；原reviewer独立确认旧有效字节完整。备份及其完整SHA保留于既有控制面留痕，本doc-curator不编辑事件、不扩controller、不另建报告。

## 设置含义、显式路由与局限（MIXED-SCOPE-CORRECTION-001）

- 用户截图显示“智能体环境：Windows原生”和“集成终端：WSL”。前者决定当前智能体及默认命令后端；后者只影响打开的集成终端。不能说UI已经自动把智能体命令切入WSL。
- 当前效果来自已部署全局AGENTS：Windows智能体在项目和依赖支持时，应显式调用已确认的 `wsl.exe -d Ubuntu-24.04`，同时指定Linux cwd、解释器和路径；旧`.ps1`/`.cmd`明确走Windows后端。智能体在每条相关任务中执行该规则，UI不提供通用逐命令调度器。
- MIXED-VERIFY-001已证明该主路线可命中Ubuntu uid1000原生工具、Linux cwd和原仓库路径，并调用未改Windows旧入口，保持参数、UTF-8、单次exit23、隔离CFM及finally清理；全局AGENTS、模板和部署回执哈希吻合。这是机制与当前样例的命中证据，不保证每个未来项目/依赖都支持WSL，也不允许失败后自动换平台重跑。
- Hook是独立PreToolUse安全门禁：它可以在激活并命中时审查/拒绝工具输入，但不决定命令运行在Windows还是WSL。Installed 2、Active 0、Review 2仍是安全风险记录；不要求用户处理它来完成本任务WSL核心目标，也不把未信任状态解释为显式路由失败。

## 历史记录（截至RESTART-DOC-001）

以下全部内容均为历史，包括原必填章节、旧“最新”结论及其操作建议；当前合同仅以上方当前段为准。正文未删除，仅调整历史标题。

### 历史：WSL 优先、旧脚本保留：施工记录

#### 历史：施工目标

执行已批准 plan.md，不扩大为脚本重写或系统迁移。沿用任务标识 `20260831-144630-wsl-first-legacy-preserved-16fc6f`。

#### 历史：前置条件

初检代理实际为 Windows PowerShell，当时当前账户仅注册 docker-desktop。必须确认或经新增授权安装通用开发发行版，并验证代理进入 WSL。初检 GTO init-task 未成功；后文记录获授权修复及同task_id恢复，禁止另造第二控制面。

#### 历史：执行顺序

先只读确认环境和写入边界，再修复经授权的前置问题；恢复同一 task_id 的有效控制面后冻结合同与基线。随后文档同步、测试同步、最小适配、运行时验收、独立审查。任何需要用户密码、重启或超出原范围的操作单独说明。

2026-08-31 用户明确批准新增发行版安装及控制器最小修复。恢复批次：安装 Ubuntu-24.04 --no-launch（不触碰 docker-desktop）；控制器修改前保存既有 dirty 文件 SHA-256/备份，先测试后实现，再恢复同一 task_id。安装期间不读取或设置用户密码，不自动启用免密 sudo。原 schema 安全约束保持不变。

#### 历史：文档先行清单

本批新增 plan.md、execution.md、acceptance.md；工作区 outputs 中交付摘要仅导航至这些文档，不形成另一套状态。后续实现前同步实际涉及的规则及长期入口说明，并先审阅既有 dirty 内容。

#### 历史：测试同步清单

当前使用既有文档结构校验，不新写业务测试。后续入口代码只测试必要行为：Linux/Windows 路由、含中文及空格路径、工作目录、真实退出码、无失败后自动重跑。失败闭环测试使用隔离数据，不制造正式经验库测试记录。

#### 历史：实施批次

批次 A：初检、授权和前置恢复已完成。批次 B：规则文档适配进行中，运行时最小部署待门禁。批次 C：显式WSL/Windows互操作已有部分证据，用户普通账户、新进程实际代理、Hook信任和最终验收未完成。

#### 历史：每批写入范围

本批：docs/tasks/20260831-144630-wsl-first-legacy-preserved-16fc6f/ 下三份文档；init-task 已生成同 task_id 下的 task.md、events.jsonl 草稿但没有 state.json；用户交付摘要放当前对话 outputs。

命令失败闭环已按现有规则新增本次真实命令失败记录，不是记忆迁移、合并或清理。其他既有规则、脚本、配置及数据库不作本任务适配写入。后续批次须由控制器冻结精确 write_paths。

#### 历史：验证命令

已执行：默认 shell 的 pwd；RuntimeInformation.OSDescription；当前进程路径；PSVersionTable.PSVersion；仅检查 CODEX_HOME/WSL_DISTRO_NAME；wsl.exe --list --verbose；针对当前账户 Lxss 的 DistributionName/Version 独立核查；git status --short（只读）。

实测：Windows 10.0.26100，PowerShell 7.6.4，CODEX_HOME 与 WSL_DISTRO_NAME 未设置；WSL 当前账户仅 docker-desktop / Stopped / 2。CODEX_HOME 未设置不能单独证明应用实际配置目录，后续仍需核对。

GTO：new-task 成功；init-task 非零退出，schema 校验失败。静态核查 New-InitialState 的空 subtasks 与 schema minItems=1 不一致；state.json 不存在。已 record-failure、query-before-retry，无历史建议；未重试初始化，未修改控制器或 schema，不记录成功。

可选命令探测 Get-Command pwsh,python,python3 结束为非零；已记录，未据此安装或替换工具链。

文档校验命令：pwsh -NoProfile -File scripts/validate-plan-docs.ps1 -RepoRoot <repo-root> -Json；pwsh -NoProfile -File scripts/validate-doc-routing.ps1 -RepoRoot <repo-root> -Json。实际结果由验收文档记录。

#### 历史：回退方案

初始诊断阶段未改运行配置。初始化失败草稿现已核对归档并成功恢复，禁止再次 init-task。恢复时先检查这些创建者已知产物，再走获批的原控制器最小修复/恢复路径；不删除未知文件、不手工绕过 schema 写 state、不重新分配 task_id。

#### 历史：审查与返工路径

已由无历史只读子代理 /root/verify_wsl_prerequisite 独立确认当前账户的发行版情况。另派专门 reviewer 仅审本批三份文档和阻塞证据；它的通过不能计作适配实施的 final/pass。后续正式实现按原实施者返工、同一 reviewer 复审，最多三轮，完成必须有有效控制面和真实运行时证据。

#### 历史：2026-08-31 实施进展补记

- Ubuntu-24.04 安装与设默认 exit=0；apt-get update、ripgrep/python3-venv 安装 exit=0。安装 Python venv 引入五项 Python 依赖升级，不执行全系统升级。
- 官方 Node v24.19.0 Linux x64 tar.xz SHA-256：14b342e71204f811bde6153be8e04b62aef63c236fef92b55f9c83154b409647。下载校验、安装、node/npm Linux 路径验证均 exit=0。临时安装脚本与下载目录已清理。
- WSL 到 /mnt/d 原仓库、/mnt/c Windows 规则入口及 cmd.exe ver 验证成功。WSL NAT localhost proxy 警告仍存在，但上述网络与命令成功；未改代理设置。
- 已异步请用户完成 Ubuntu 首次普通用户创建；不处理用户密码。目前 default exec 工具仍在 Windows PowerShell，不等同于 WSL 代理验收。
- 控制器原实施者 /root/repair_gto_initialization：真实 schema 预期红命中；初始化正反测试4项通过；完整 control-plane 回归101项通过。原 reviewer /root/review_wsl_plan_blockers 已接收恢复增量审查，尚不作为最终验收。
- 新发现独立控制器缺口：dirty overlap 捕获后为 pending，但无正式裁决接口。已向用户单独请求最小接口授权，未擅自实现，也不绕过写 state。此事项不阻止文档同步阶段。
- 本批长期规则只改说明及模板；不新增路由代码，TDD 实现测试不适用该静态规则变更。新增边界验证若需要，覆盖真实 Linux/Windows 进程、路径、退出码与原后端隔离数据；已有 bootstrap/规则校验沿用。

#### 历史：恢复、互操作与尚未闭合门槛

同 task_id 的 init-task 已恢复成功；正式 schema validate 返回 ok=true、errors=[]、warnings=[]。原失败 task.md/events.jsonl 逐项核对后移动至 docs/ai/runs/20260831-144630-wsl-first-legacy-preserved-16fc6f-initialization-recovery/failed-draft，保留内容、原事件顺序与 residue-hashes.json。新事件流追加归档引用，未把原先虚假的 task_initialized 当作成功，未伪造历史派发。原实施者完成独立恢复核对。

初始化修复五文件独立审查 PASS；reviewer 独立重跑 Initialization 4/4 和真实schema happy path 1/1，未冒充重跑全部101项。后续规则及部署仍需审查。

WSL原生 Git识别同一 /mnt/d 原仓库成功；从WSL经Windows pwsh.exe、wslpath -w 显式转换脚本和RepoRoot，运行旧 validate-plan-docs.ps1 成功，18docs/0errors/0warnings。stdout中文字存在编码显示问题，须由边界测试核对和在调用层处理，不重写旧脚本。

未改动的 pre-tool-use-hook.mjs 直接在Linux Node下验证：已存在路径的rg输入 stdout为空且exit0；原始state写入输入返回permissionDecision=deny且exit0。输入只分类，不实际执行删除或状态写入。这仅证明原代码的两例Linux行为，不证明Codex生命周期已命中或已信任。

当前Windows hooks.json 的 command 与 commandWindows 均为Windows绝对路径。Linux agent实际加载目录、generic command的WSL适配、精确hash信任与真实事件仍未确认。不得关闭Hook或用bypass参数代替用户信任。

CFM成功回写：第一次query误用了ai-harness标识返回retry_gate_not_met；随后按原事件的dev_vibecoding标识查询返回retry_gate_passed后才恢复初始化。恢复后record-success真实失败：case capacity limit reached: 1024；已record-failure记录容量错误。未删旧记录、调高容量、迁移数据或虚报成功回写；此遗留容量问题与WSL互操作区分。

官方依据（2026-08-31核对）：https://learn.chatgpt.com/docs/windows/windows-app 明确 Agent environment 与 Integrated terminal shell 独立且agent切换需重启；https://learn.chatgpt.com/docs/hooks 明确 commandWindows 仅Windows覆盖、changed hooks需精确hash重新信任。Windows应用home与WSL独立CLI默认home不可混淆。

#### 历史：独立审查返工与边界测试补记

F001：独立reviewer发现新增CFM简单参数说明遗漏现有WindowsPS fallback。已交回原doc-curator，以ADAPT-FIX-001仅修改兼容说明/模板/命令失败闭环三文件；23规则与8项bootstrap复验通过。原reviewer复审认为F001可以关闭，不等于整体final/pass。

新增最小wsl-boundary.integration.ps1在Windows宿主上显式指定发行版和WindowsPython。默认主路线在执行前选择该WindowsPython供旧.cmd使用，不修改机器PATH或旧脚本，不按失败退出自动切换。默认主路线已通过Linux工具、中文空格路径与字面参数、WindowsPS平台/工作目录/UTF-8/真实exit23且仅调用一次、旧validate18文档与WindowsCFM隔离闭环。严格继承原.cmd后端模式独立保留，不把原PS fallback差异放宽为通过。

已诊断原PS fallback计数限制：相同显式隔离CodexHome、case_count=1，但Python inspect pending=0而原.cmd在无Python PATH时PS inspect pending=1；不是丢路径。原脚本未修改，该模式不计通过。本任务使用既有WindowsPython主路线，不能据此宣称所有旧backend互换。

测试开发出现嵌入JS字符串转义和诊断输出捕获错误，已在隔离CFM记录/查询并修复验证，未写入正式经验库。默认套件内fixture在创建者finally正常清理。另根协调创建的 .tmp/wsl-first/cfm-diagnostics 诊断目录，即使绝对路径已核对，独立递归清理命令仍被平台在创建进程前拒绝；已记录该工具层阻塞，不改TEMP、不换语言或包装脚本绕过。目录暂留允许.tmp位置，待受支持清理或用户处理。

#### 历史：收尾只读复核

原bootstrap/path-resolution脚本、三份rules registry产物与Windows runtime AGENTS.md均与任务前备份hash一致，证实本轮尚未部署/生成这些文件。Ubuntu仍DefaultUid0。末次wsl列表中Ubuntu为Stopped、docker-desktop为Running（初检为Stopped）；本任务没有对Docker发送启动、停止、修改命令，状态变化来源未归因，不以“未执行Docker命令”推断“Docker持续停止”。未为查该变化扫描其他项目或修改Docker。

验证代理独立诊断目录 .tmp/wsl-verifier-cfm-01a055974368 也因同类平台拒绝而保留；suite自身成功/失败fixture均已清理。两处诊断目录在允许.tmp落点，未通过改TEMP或换shell规避策略。测试脚本的默认主路线exit0，可选-CheckInheritedCmdBackend严格诊断exit1，后者仍是旧PS后端已知限制。

#### 历史：用户创建完成后的复核

用户告知已创建账户后，只读确认Ubuntu-24.04 DefaultUid=1000；id输出uid=1000(laptop)，HOME=/home/laptop。Linux bash/Git/Python/rg/Node/npm可用，原harness及Windows规则入口可读。

使用原wsl-boundary.integration.ps1、显式Ubuntu-24.04与既有WindowsPython重跑，exit0，输出明确uid1000。Linux原生工具、中文/空格/字面参数、WindowsPS平台/cwd/UTF8/一次exit23、旧validate18文档、CFM隔离主路线与fixture清理均通过。未重跑已知旧PS fallback严格诊断，未修改任何旧脚本、工具配置或全局PATH。

普通Linux用户前置条件已解除；此前review记录中的uid0是上一轮历史证据。桌面代理exec仍在Windows，控制器最小overlap接口仍待明确授权，AGENTS/index尚未部署，Hook真实信任与生命周期证据仍待续接。不将“用户已创建”理解为额外控制器变更授权。

#### 历史：用户确认后的裁决接口恢复批次

最新“确认”明确批准最小未提交改动裁决接口。已同步方案并保存 .artifacts/wsl-first-20260831/overlap-api-baseline 五文件hash备份；原备份不覆盖。正式建立 GTO-OVERLAP-001，原实施者 /root/repair_gto_initialization 通过实际brief续接。保持前置恢复blocked身份，不绕过原code_impl门禁，待接口审查通过后正式裁决；普通用户已通过，旧review中对应阻塞是历史记录。

本批部署前只读复核：原bootstrap/path-resolution、三份registry、Windows托管AGENTS仍与任务前基线一致。普通WSL shell实测uid1000，未设置CODEX_HOME且/home/laptop/.codex不存在；Windows挂载目录中的AGENTS/hooks可读。这仅是独立WSL shell的事实，不推断重启后桌面代理的配置home，也不因此创建或复制Linux .codex。官方说明再次核对：Agent environment与Integrated terminal shell独立；Hook commandWindows仅Windows覆盖，变更定义需要用户核对精确信任。

#### 历史：最小overlap接口实现与回归

原实施者先同步GTO文档与最小真实Git/schema测试，Red明确命中原Unsupported action；实现resolve-workspace-overlap -DecisionJson后Green。显式summary/head/write_overlap/baseline_hashes三方核对，保留pending gate，拒绝未知/缺失字段、陈旧基线和链接路径；范围改变使裁决失效并要求新capture，code_impl中拒绝该范围变化而非放松门禁。

五文件相对overlap-api-baseline增量为controller91行、SKILL2行、state-schema说明20行、测试181行、README2行。新增5组覆盖19种无效payload、6种漂移、两个范围入口/阶段拒绝/fresh capture及真实junction。完整control-plane106/106、skill-doc、AST、diffcheck均exit0。原reviewer已接收实际brief和冻结hash作独立复核；主协调尚未执行真实裁决，不把实现结果当作审查已过。

原reviewer独立Overlap decision:*五组通过后，主协调检查最新capture的17个overlap路径，均属于已冻结范围；显式resolve-workspace-overlap返回resolved，HEAD未变，随后经正式transition恢复doc_sync。原备份、接口批基线、Hook批基线保持独立。裁决输入在.artifacts/wsl-first-20260831/overlap-decision.json，不作为第二任务状态。旧GTO-OVERLAP-001结果的筛选命令摘要更正：用GTO_TEST_NAME_PATTERN环境变量，而非-TestNamePattern参数，已写正式更正事件。

#### 历史：Registry生成与核对修正

既有generator处理三份registry成功、23条规则；实际仅RULES_INDEX.json和RULES_RESOLVED.json内容变化，RULES_INDEX.md保持原内容。实施者后置检查误要求三个目标必须都变化而抛错；主协调经原WindowsPython/原CodexHome完成record-failure和query-before-retry（61f8eb2da70705f1e59ec9fa368aed35cd7397c08b50b9b53136947e158a2bec）。修正为实际changed集合属于allowlist，且三目标存在、其他registry未变；不重跑已成功generator、不强制产生diff。修正核对exit0。

按原容量失败先查询后尝试本条record-success，仍因case capacity limit reached: 1024失败；该容量失败已另记录。不清理/扩容/迁移原记忆，也不虚报成功回写。本批备份deploy-baseline-20260831-164902保留原3registry和2runtime及hash。Hook最小Red两例命中并正式validate通过后，任务已正式进入code_impl，开始最小安装入口实现与bootstrap部署。

#### 历史：最小运行时部署已完成

DEPLOY-001按显式HarnessRoot/CodexHome及-SkipSync -SkipRules -SkipDoctor调用原bootstrap，exit0/updated=true/issues=[]，仅完成global_agents/receipt。没有全量skills同步、没有再运行generator、未改Hook/config/auth。Windows托管AGENTS6093bytes、SHA256 5dcca14592c635f966e41ac44c629abf0965d761380ac4056e90ad26e16493a2；bootstrap receipt610bytes、SHA256 6686c63f94edff51b9ca41c530daba3d0463e64a3f8f4dc03dbd1534ecb1103e；模板hash d53dd3df3cc607232ccd9378c93d37c1f85919972cc0098e0e66b1adcffd58d7。fresh Windows PID24680与WSL PID403(uid1000)读取两文件hash一致，渲染字节与receipt匹配，WSL转路径后规则入口可读。原五文件批次备份事后仍匹配。

仓库生成增量仅两JSON；INDEX.json19033bytes/A2FB11957A7992FC949B5F7C04B978B384F9D1AB478D32B30388B0170ADB0E77，INDEX.md4114bytes/A89F57A1F1BF2CC68A236554E1C2269C809133CBF1BACDD96613F00ED328BE38（未变），RESOLVED.json54191bytes/E2FD7D9CAB7B6F0C08CB15AF2E6E009266B66A344D573E4FA685D8D73FF71D4E。23条规则校验0error（原sibling warning保留），18文档0error/0warning，diffcheck通过。这些证明部署与读取，不替代真实桌面代理加载。

#### 历史：Hook最小入口红绿与测试边界

HOOK-ADAPT-001按README先行、最小两例Red确认缺口后，正式code_impl才修改安装器。最小WSL组已2/2 exit0：实际生成的Windows/Linux命令串分别运行allow/deny，stdin含中文、源路径含空格/单引号，cwd不依赖仓库。6类坏参数/路径在目标写入前拒绝，原hooks hash不变、无metadata；原Windows命令保留，备份/幂等通过。

测试驱动两次意外错误在既有隔离.tmp/wsl-first/cfm-diagnostics完成CFM记录/查询/成功回写：cmd.exe整段/c参数被ArgumentList重复引用，改为该调用专用正确ArgumentLine；另WSL NAT启动stderr被合并进空stdout断言，改为stdout协议与stderr诊断分离，仍严格拒绝真实非0并解析deny输出。stderr提示显式保留，不改代理、不吞错误、不改Hook判断。完整旧套件回归和独立审查尚待回收；没有部署真实hooks.json。

#### 历史：Hook入口回归与最终运行时边界

原完整command-safety-gateway.integration.ps1回归27/27 exit0；最小WSL组2/2、AST及diffcheck通过。最终送审hash：installer9627E64D5FC21AA152FE2CF22FC4EC156D88F3073645A17B11E5AF960B2876AF；README2B4226F4D2B362877CB46B62D3C6E9C84C4377B24E3B72570D19A142DC3F0F14；testsFEBE5A635B9A8EDF3E77D7A54B1F1062EBA0AAA1F9C5DE5793C9523058E821B6。原reviewer接收新brief继续独立审查；前一批部署已独立限定PASS。

主协调末次只读确认默认exec仍Windows/PowerShell7.6.4；真实hooks.json仍只有一个本任务managed id，generic仍等于commandWindows，文件SHA256 B4A4E0DB9CE8AB4749779AF4B8AA4E578CA2F2FF8C299921423A7F1FC69456DE。没有安装新WSL定义，不把隔离命令验证当真实生命周期。下一步用户核对Agent environment=WSL并重启；之后在同任务读取真实平台/UID/CODEX_HOME/规则来源，选择已核对的活动home最小安装，再由用户按实际/hooks精确信任，最后真实运行时验收。若home位于Linux文件系统，先补同文件系统隔离锁/原子写验证。不得复制auth、迁移记忆、自动信任或绕过Hook。

原reviewer已独立重跑Hook最小WSL2组exit0，三文件hash与冻结值一致、AST0error，暂未发现可行动源码问题。当前统一收尾只核对累计16个实际实施增量和任务文档的一致性；INDEX.md属于已生成但未变化目标。任务仍不具备运行时final/pass条件。施工文档、方案及验收文档已更新到该边界，后续状态由唯一控制面记录，不另建任务。

最终审查回执：原reviewer统一结论为“已实施源码、生成物与限定部署证据PASS；整任务needs_more_evidence，不得finalize；无新增可行动finding”。累计16文件ordinal内容SHA256为6248a9bcc1a9b83bd9ce3e1e4e8cc7591ad9c7ee5352d1c8255fb91fad9eac70，与主协调独立值相同。F001保持closed/round1。正式REVIEW-001结果及事件已记录，任务status/current_phase均blocked，仅等待上述用户重启及真实Hook运行时门禁。本段为审查结束后的结论回执，不改变已审源码或实施范围。

#### 历史：最新重启验收（2026-08-31，RESTART-DOC-001）

本节是重启后的最新记录，前文等待重启及旧环境状态仅保留历史。RESTART-DOC-001沿用原task_id，只追加plan.md、execution.md、acceptance.md；不修改源码、配置、Hook安装状态或CLI环境，不自行修改控制面。

- 真实重启证据：主协调于17:12:45检查pwsh PID10832祖先链，记录ChatGPT.exe PID9324于17:10:44启动、子进程codex.exe PID7448于17:10:47启动。doc-curator随后独立复核两个进程的PID、父子关系和启动时间一致；本轮默认exec复核仍为Microsoft Windows 10.0.26100、PowerShell 7.6.4。不能继续以“用户尚未重启”解释当前平台。
- 精确配置键复核：只输出 `C:/Users/Laptop/.codex/config.toml` 的 `desktop.integratedTerminalShell=wsl`、`desktop.runCodexInWindowsSubsystemForLinux` 缺失。只读核对 `.codex-global-state.json` 顶层和 `electron-persisted-atom-state` 内同名两键，均缺失；没有输出整份配置或认证信息。
- 本机源码依据来自主协调对 `C:/Program Files/WindowsApps/OpenAI.Codex_26.825.6671.0_x64__2p2nqsd0c76g0/app/resources/app.asar` 的只读静态核查：`.vite/build/src-C2ILPx7g.js` 中 `runCodexInWsl` 映射到 `runCodexInWindowsSubsystemForLinux`，default为false；`.vite/build/window-all-closed-DCMYPAWO.js` 的 `bE` 读取 `config.toml.desktop`，仅在新键缺失时检查旧迁移键，`getEffective` 对缺失值返回default，启动路径 `jE` 据此决定 `preferWsl`。结合已复核的键值，可将当前默认Windows执行定位为代理WSL开关未启用，而不是集成终端设置未保存。
- 本机 `general-settings-BsQYJwk6.js` 存在依赖feature条件的 `legacyWsl.deprecation` 提示。这只能证明代码中有该条件分支，不能证明当前用户界面已展示该提示、已无WSL选项或必须另装CLI。官方Windows应用说明用于解释两设置独立；对本机默认值与迁移行为，以本机源码证据为准。
- 显式 `Ubuntu-24.04` 子进程复核exit0：uid=1000、HOME=/home/laptop、CODEX_HOME未设置、`/home/laptop/.codex` 不存在。这是显式WSL shell的事实，不代表桌面代理活动home，也不据此创建Linux `.codex`。既有WSL NAT localhost代理提示仍出现，目标命令exit0且JSON完整；未修改代理。
- 文件哈希复核保持上轮结果：Windows AGENTS为 `5dcca14592c635f966e41ac44c629abf0965d761380ac4056e90ad26e16493a2`，bootstrap receipt为 `6686c63f94edff51b9ca41c530daba3d0463e64a3f8f4dc03dbd1534ecb1103e`，模板为 `d53dd3df3cc607232ccd9378c93d37c1f85919972cc0098e0e66b1adcffd58d7`，hooks.json为 `b4a4e0db9ce8ab4749779af4b8aa4e578ca2f2ff8c299921423a7f1fc69456de`。没有安装新Hook定义或刷新上述文件。
- 主协调独立复核累计16个实施文件ordinal manifest仍为 `6248a9bcc1a9b83bd9ce3e1e4e8cc7591ad9c7ee5352d1c8255fb91fad9eac70`，已追加正式 `restart_acceptance_observed` 事件。原源码、生成物及限定部署PASS保持有效；本轮不复写或推翻该审查，只更新设置差异和剩余运行时门槛。

下一步先请用户提供Agent environment实际设置页截图，核对WSL选项或弃用提示，再确定对应操作；不在界面未核对时重复要求重启，不直接写代理开关，也不安装CLI。实际WSL代理、活动CODEX_HOME和规则来源尚未验收，Hook最小安装、精确信任与真实allow/deny生命周期继续单独保留。当前验证仅使用既有文档校验与diff检查，不新增镜像测试。

本轮文档验证：`validate-plan-docs.ps1` exit0，18份文档、0error、0warning；`validate-doc-routing.ps1` exit0，6个任务、0error、0warning；指定三文档的 `git diff --check` exit0。该diff命令不单独证明未跟踪文件完整性，三文档内容另由前述结构校验覆盖，并核对新增章节唯一、无尾随空白。未重跑源码套件，也未把文档验证当作代理WSL或Hook运行时验收。
