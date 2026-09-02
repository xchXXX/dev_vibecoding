# Windows 联网代理、显式 WSL 优先：方案

> MIXED-SCOPE-CORRECTION-001：当前混合模式最终口径（2026-09-01）。Windows原生是智能体与默认命令后端，WSL只配置为集成终端；WSL优先来自全局规则要求智能体显式调用wsl.exe，不是UI自动调度。末尾历史保持。

## 任务目标

沿用任务 `20260831-144630-wsl-first-legacy-preserved-16fc6f`，以Windows原生智能体保持联网，并在项目和依赖支持时由智能体显式调用 `wsl.exe -d Ubuntu-24.04` 执行日常Linux命令为当前效果。旧Windows脚本保留原实现和Windows后端；不要求整个桌面代理迁入WSL。

## 背景与问题

用户截图确认智能体环境为Windows原生、集成终端为WSL。两项设置含义不同：前者决定代理及默认命令后端，后者只决定用户打开的集成终端；界面没有把智能体后续命令自动调度到WSL。完整WSL代理曾出现连接/cwd错误，用户已回退Windows。当前合同接受此状态，由已部署全局规则指导智能体按任务显式路由，不再要求切换或重启。

## 范围

MIXED-SCOPE-CORRECTION-001仅更新本目录plan.md、execution.md、acceptance.md当前段，纠正设置含义、显式路由机制及Hook边界。后续执行与审查继续由唯一任务控制面派发；本批不改源码、配置、Hook定义或全局网络。

## 非目标

不要求完整代理迁WSL，不另装CLI，不搬仓库或创建副本/worktree，不全量同步skills或`.codex`，不复制认证信息，不迁移/清理/扩容记忆，不改代理、防火墙、Docker、权限或全局PATH，不增加自动重试、通用wrapper或逐命令preflight。

## 约束与依赖

当前默认home为 `C:/Users/Laptop/.codex`，配置为 `desktop.runCodexInWindowsSubsystemForLinux=false`、`desktop.integratedTerminalShell=wsl`。智能体必须依据全局AGENTS及项目支持，在执行前选择Windows或显式WSL，给出发行版、Linux cwd、解释器和路径；集成终端设置本身不完成这项选择。旧`.ps1`/`.cmd`继续使用已确认Windows后端，不因普通非零自动换平台重跑；Linux/Windows的node_modules、venv和原生依赖不混用。原CFM 1024容量与旧PS fallback限制保留。

## 方案摘要

由Windows智能体承担联网交互。全局运行时AGENTS明确：项目与依赖支持时，智能体应显式调用已确认Ubuntu及Linux cwd，让文件、Git、Python、Node、测试和构建优先在WSL运行；涉及WSL当前不可达网络时先按依赖选择环境。该机制依赖规则加载和智能体执行行为，不是UI级调度器，也不保证每个未来项目或命令自动进入WSL。Hook仅是独立安全门禁，不选择命令平台。

## 风险与回退

Windows经显式HTTP代理取得TLS及403只证明传输到达，不证明认证、模型调用或所有任务联网成功；WSL直连和localhost端口失败也不授权自动改网络。先前完整WSL切换出现Windows路径被拼到应用resources目录后的cwd错误，禁止继续把该路径形式当Linux cwd。当前Windows回退状态应保持，不为满足历史门槛再次自动切换；本批文档改动可独立回退，历史正文保留。

## 验收标准

1. Windows原生智能体联网正常，界面保持Windows智能体与WSL集成终端；文档不得把两者误写为自动路由。
2. Ubuntu-24.04 uid1000混合边界主路线exit0，Linux原生工具、Linux cwd、原仓库挂载路径和真实退出码已命中，且无自动跨平台重跑。
3. 选定旧Windows脚本保持原实现，Windows后端的路径、参数、cwd、UTF-8和exit23边界通过；旧PS fallback限制单列。
4. `C:/Users/Laptop/.codex` 的全局AGENTS包含WSL优先/Windows旧入口规则，并与模板和部署回执哈希吻合；这是显式路由规则加载证据，不宣称UI自动调度。
5. 三文档和用户导航说明机制、适用边界与Hook解耦，并由原reviewer按最终内容哈希复核；Hook待信任风险另行保留，不阻塞WSL优先核心目标。
6. 现有dirty内容、记忆与Docker边界保持，列出未覆盖项目/依赖；不要求完整代理迁WSL。

## 阶段划分

当前doc_sync纠正UI含义、显式路由和Hook解耦；混合边界主路线已经验证，随后由原reviewer核对最终三文档与用户导航。Hook信任/allow-deny作为独立安全遗留另行处理，不阻塞本任务WSL优先核心验收；无需用户再次切换、重启或信任Hook。

## 需先同步的核心文档与测试

本批仅同步本目录三文档。使用既有validate-plan-docs.ps1、validate-doc-routing.ps1、限定diff及历史完整性检查；纯文档调整不新增实现镜像测试、不重做网络实验。Hook安全遗留留在原控制面，不与WSL路由验收捆绑，也不建立第二报告或状态。

## 历史记录（截至RESTART-DOC-001）

以下全部内容均为历史，包括原必填章节、旧“最新”结论及其操作建议；当前合同仅以上方当前段为准。正文未删除，仅调整历史标题。

### 历史：WSL 优先、旧脚本保留：方案

#### 历史：任务目标

日常文件操作、Git、Python、Node、测试和构建在具备对应工具及项目支持时优先使用 WSL。已有 Windows 脚本尽量原样保留，明确调用 Windows 端执行。任务标识：`20260831-144630-wsl-first-legacy-preserved-16fc6f`。

#### 历史：背景与问题

用户已批准本方案范围，并表示切换 WSL、重启应用。2026-08-31 初检时，默认执行环境仍为 Windows PowerShell 7.6.4；当时账户的 WSL 列表和独立注册表核查只发现 `docker-desktop`，版本 2。该历史缺口现已通过用户授权安装 Ubuntu 并创建普通用户解决；默认代理进程仍待再次重启后实测。没有检查其他账户、未注册镜像或远程机器，不判断用户操作是否错误。

初检时 GTO `new-task` 已分配上述标识，但 `init-task` 因初始化 `subtasks=[]` 与 schema 的 `minItems=1` 不一致而失败，仅生成 draft task.md 和 events.jsonl。现已通过授权的最小修复、独立审查和同 task_id 恢复建立有效 state.json，原草稿逐项核对后归档。人读文档记录合同与证据，不替代唯一状态。

#### 历史：范围

后续候选范围是全局规则的 Shell/平台/路径条目、全局入口模板、必要旧脚本调用入口、对应文档和针对性验证；实际文件清单须在有效任务合同中冻结。真源使用用户指定的现有 harness，不扫描其他 clone。

初始诊断批次仅新增本任务 plan.md、execution.md、acceptance.md 和项目外的用户交付摘要；不修改已有规则、脚本和系统配置。

#### 历史：非目标

不搬仓库，不创建业务副本或 worktree，不改业务代码，不全量重写 .ps1/.cmd，不迁移或清理记忆数据，不整目录覆盖 .codex，不改代理、防火墙或权限，不增加常驻服务、自动重试或逐命令预检，不修改或启动 Docker 专用发行版。

2026-08-31 用户回复“同意”，新增授权已取得：安装独立 Ubuntu WSL2（本次选择在线目录中的 Ubuntu-24.04），必要时设为默认；最小修复 GTO 初始化不一致并恢复本任务，不放宽安全校验、不修改既有任务。用户密码不由代理读取或代填。

新增前置修复的写入范围：skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1、对应 skills/global-task-orchestrator/SKILL.md 和 references/state-schema.md（仅必要初始化说明）、tests/harness/control-plane.integration.ps1 或独立最小初始化合同测试，以及本任务文档/唯一状态。先备份重叠的既有 dirty 文件到本任务 .artifacts 子目录，不改 schema 安全约束或其他任务状态。

控制面尚不能初始化时，先执行用户已明确批准的控制器恢复批次；在原事件流记录真实派发身份和范围，不伪造 build-subtask-brief 或 state。控制器修复后立即恢复同一 task_id，再恢复标准投影、派发绑定和阶段门禁。

#### 历史：约束与依赖

必须先有通用 WSL2 开发发行版并验证本任务代理实际进入 WSL。检查实际 CODEX_HOME 和规则加载位置，不假定 Linux CLI 与桌面代理共用配置。保留全部既有未提交改动，修改前冻结目标文件基线。

现有 Command Failure Memory 继续经 Windows 后端访问原数据目录，不切换到 Linux Python；原 Python 后端的非 Windows 锁分支不能提供同等互斥保证。不得通过关闭安全检查或 Hook 信任要求完成验收。

#### 历史：方案摘要

执行前按依赖选择环境：可用日常开发操作使用 WSL，旧 Windows 脚本明确走 Windows 后端。若已有入口足够就不新增；必须新增时仅集中处理路径、参数、工作目录和退出码，不复制核心逻辑。不得根据普通非零退出码自动改用 Windows 重跑。

规则保持单一真源，按平台适用；生成索引和运行时内容只能通过既有生成/同步机制更新，并先检查变更范围。命令失败按既有失败闭环处理，不进行数据库迁移。

#### 历史：风险与回退

风险包括 WSL 环境未生效、缺少发行版、Windows 互操作不可达、跨系统参数和工作目录错误、依赖混用、既有 dirty 文件重叠、安全机制未实际触发。

回退只恢复本任务修改前备份及任务改动；不 reset/clean 现有 checkout。用户可将代理切回 Windows native 并重启；设置回退与文件回退分开。初始诊断批次未修改运行配置；后续已安装Ubuntu和工具，回退应单独列出，不能删除用户后来写入的Linux数据。

#### 历史：验收标准

1. 实际代理及常用工具运行在通用 WSL2 开发环境。
2. 选定日常操作在 WSL 成功，且未混用 Windows 依赖环境。
3. 选定旧脚本在 Windows 后端执行，中文/空格路径、工作目录、退出码验证通过。
4. 新进程加载正确规则；相关 Hook 和失败闭环有真实命中证据。
5. 对本次入口改动完成针对性验证与独立审查，返工后复审通过。
6. 保留现有未提交内容、记忆数据和 Docker 专用环境；列明未覆盖旧脚本，不能宣称全量兼容。

#### 历史：阶段划分

A：只读核对与前置条件处理。B：恢复有效单一任务控制面，冻结文件基线及文档。C：文档和规则说明同步。D：必要测试先行、最小入口适配。E：真实验收、独立审查、原实施者返工及同一审查者复审。

A/B 的发行版安装、初始化恢复与另外明确授权的overlap接口恢复已完成；正式裁决resolved，规则部署与Hook可选入口隔离验证也已完成。当前进行全部增量独立审查，之后等待重启后的真实代理/配置home/Hook安装信任与生命周期验收。文档或隔离测试不等于全部运行时验收。

##### 历史：初始化修复 verification contract

- minimal_repro：在仓库 .tmp 的创建者自清理隔离 fixture 中包含真实 v2 schema，调用当前 init-task，确认空 subtasks 被拒绝。
- hit_proof：修复后相同 fixture 的 init-task 通过真实 schema 和控制器 validate，且仍拒绝无效状态/重复初始化。
- diagnostic_checks：校验 schema、初始化产物完整性、失败残留和同 task_id 安全恢复条件。
- acceptance_checks：最小正反合同测试、相关控制面回归、真实本任务恢复和独立 reviewer 审查。
- non_goals：不放宽 schema、不改既有任务、不重构控制器、不绕过校验写 state、不删除未知文件。
- review_evidence：repro_before_fix、pass_after_fix、hit_proof_observed、relevant_regression_ok、independent_final_review。

#### 历史：需先同步的核心文档与测试

后续仅同步与默认 Shell、Windows 旧脚本入口及规则发现相关的长期说明和规则；不追溯改写历史任务文档。若修改入口代码，先冻结 minimal_repro、hit_proof、diagnostic_checks、acceptance_checks、non_goals、review_evidence，并补相应合同测试。静态规则改动不新增实现镜像测试；已授权初始化修复执行真实schema TDD与回归。

#### 历史：已批准实施文件与最新环境（2026-08-31）

Ubuntu-24.04 WSL2 安装、设为默认及基础工具补齐已完成。本任务未向 docker-desktop 发送启动、停止或修改命令；观察到的状态变化未归因。Linux Git 2.43.0、Python 3.12.3、rg 14.1.0、Node v24.19.0、npm 11.17.0 路径已实测。Node 官方 Linux x64 包 SHA-256 已校验；安装位于 /opt/node-v24.19.0-linux-x64，/usr/local/bin 仅新增 node/npm/npx 三个链接。用户现已创建 laptop，DefaultUid=1000、HOME=/home/laptop，边界主路线在该用户下复验通过。

后续精确真源改动：templates/codex/AGENTS.global.md；rules/items/policy/脚本运行基线.md、命令构造约束.md、命令失败闭环.md；docs/CODEX_COMPAT.md；必要的 tests/harness/wsl-boundary.integration.ps1。初始化修复另含 tests/harness/README.md 的一行调用说明同步。rules/registry/RULES_INDEX.json、RULES_INDEX.md 和 RULES_RESOLVED.json 仅由既有生成脚本刷新；Windows CODEX_HOME 的托管 AGENTS 与 bootstrap receipt 仅由既有 bootstrap 最小刷新。不新增通用路由 wrapper，不改旧脚本实现，不全量同步 skills 或 .codex。

规则先明确：在 WSL 可用且项目依赖支持时，Linux 操作使用 Linux 路径与解释器；当前宿主若仍为 Windows，可显式通过 wsl.exe 调用已确认发行版。旧 .ps1 和 .cmd 保留在 Windows 后端，Windows 参数路径显式转换。失败不触发跨平台自动重跑。Linux/Windows node_modules、venv 不混用，不因本任务擅自重装业务项目依赖。故障记忆沿用现有 Windows 后端及数据/锁，不迁移记忆。

普通 Linux 用户门禁已解除；仍需新进程实际代理环境/规则加载、适用 Hook 信任/真实命中。不因显式 wsl.exe 命令成功而宣称桌面代理已切换成功。

#### 历史：已批准的 overlap 裁决接口恢复批次

用户最新回复“确认”，明确同意最小未提交改动裁决接口；不再等待重复授权。仅修改现有 GTO controller、SKILL.md、references/state-schema.md、control-plane.integration.ps1 和必要 tests/harness/README.md。不修改 schema、不覆盖原 dirty 内容、不自动批准重叠、不直接编辑 state。保存新的批次基线，保留初始备份。

接口要求：显式裁决说明及冻结 HEAD、重叠路径集合和每文件 SHA-256；与已捕获基线及当前仓库核对，缺项、未知字段、漂移或不安全路径必须拒绝且不改状态。通过既有互斥锁和原子验证写入 resolved 裁决。capture 仍只捕获，不成为授权；裁决后范围变化须重新核对。该接口自身是用户单独批准的前置恢复，控制面保持 blocked，不声称已越过 code_impl 门禁；恢复通过独立审查后才正式裁决并恢复常规实施。

- minimal_repro：真实 schema fixture 中捕获 dirty overlap 为 pending，原控制器没有合法 resolved 入口。
- hit_proof：新接口校验冻结证据后正式写入 resolved，同一 fixture 可通过 code_impl 门禁；原 pending 路径仍拒绝。
- diagnostic_checks：未知字段、缺失/错误 hash、HEAD/路径集合/文件漂移、越界路径和拒绝时状态完整性。
- acceptance_checks：最小正反测试、完整控制面回归、实际任务裁决、原独立 reviewer 复审。
- non_goals：不放宽 schema、锁和原子写，不改其他任务，不自动批准，不清理工作区，不迁移任何记忆。
- review_evidence：保存预期红、修复命中、回归输出摘要及独立审查；真实代理与 Hook 门禁继续单独保留。

#### 历史：必要 Hook 入口适配（原范围内，不重写旧脚本）

只读 HOOK-READ-001 确认现有安装器把 Windows 命令同时写入 command 与 commandWindows，无法作为 Linux 通用命令。最小改动限定 scripts/install-command-safety-gateway.ps1、hooks/codex/README.md、tests/harness/command-safety-gateway.integration.ps1。保留 Windows 安装器和默认行为，增加显式配对的 WSL 发行版/Node 路径参数，用 wslpath 转换同一 Hook 源文件路径并正确引用。保留原 managed id、matcher、timeout、锁、备份、合并、回执，不改网关分类或信任机制，不新增 wrapper、不安装 Linux PowerShell。

接口裁决恢复后才实施；先冻结三文件批次基线。minimal_repro 是原安装器不能生成 Linux 通用命令；hit_proof 必须执行实际生成的命令串，而非绕开命令串直接跑 mjs。隔离测试覆盖未启用WSL时Windows行为不变、配对参数缺失/错误路径拒绝且目标不变、两平台allow/deny、stdin、中文空格路径、非仓库cwd、合并/备份/幂等。原reviewer独立复审。本批只做源码与隔离测试，真实安装要等新桌面代理实际CODEX_HOME确定后；如home在Linux文件系统，再先验证同文件系统隔离目录的锁/原子写，不从挂载盘结果推断。用户精确信任与真实生命周期验收不可替代。

#### 历史：最新重启验收（2026-08-31，RESTART-DOC-001）

本节更新当前验收边界；此前“等待用户重启”的描述保留为历史，不再作为最新阻塞。用户已真实重启：主协调观察并由doc-curator复核，ChatGPT.exe PID9324于17:10:44启动，子进程codex.exe PID7448于17:10:47启动；重启后的默认exec仍为Windows PowerShell 7.6.4。

当前差异在设置层：Windows `config.toml` 的 `desktop.integratedTerminalShell` 为 `wsl`，但 `desktop.runCodexInWindowsSubsystemForLinux` 缺失；`.codex-global-state.json` 顶层及 `electron-persisted-atom-state` 内的对应旧键也均缺失。主协调对本机26.825.6671.0版app.asar的静态核对确认：代理开关缺失时使用默认false，集成终端选择不能代替代理开关。因此最新阻塞是代理WSL设置未启用、实际界面尚待核对，不是“没有重启”。具体进程、源码和哈希证据见execution.md同名章节。

最小用户操作先收集当前设置界面中Agent environment的截图，确认是否存在WSL选项或弃用提示；本机前端存在依赖feature条件的 `legacyWsl.deprecation` 提示，不能仅据静态代码断言用户必然看到，也不能据此要求另装CLI。先根据实际界面确定下一步，不盲目再次重启。本批不修改配置、不安装Hook、不安装CLI，也不复制`.codex`。

本轮只诊断设置差异并追加三份任务文档，不改变已审源码、生成物与限定部署的PASS结论。主协调复核累计16文件ordinal manifest仍为 `6248a9bcc1a9b83bd9ce3e1e4e8cc7591ad9c7ee5352d1c8255fb91fad9eac70`。显式Ubuntu普通用户可用不等于桌面代理已进入WSL；实际WSL代理的活动home、规则加载、Hook安装后的精确信任与真实生命周期仍需后续证据，整任务继续未完成。
