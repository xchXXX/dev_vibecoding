# 独立全面环境扫描报告

任务：20260910-windows-native-transition

独立 reviewer：Fermat（01a08a95-b269-7c73-9567-f8f3ec9bec24）；无对话继承，只读，不再委派。下文为独立报告原文。主协调确认源文件、关键旧断言、实际未设置的 WSL CODEX_HOME 和 12,966 字节残留文件证据；未运行全局 strict doctor 或 GTO 套件，不把静态发现记作实际测试失败。

**独立静态审查结论：不通过“源码、文档、测试和环境产物已经全部扫净”的收口判断。** 本次记录 **11 项发现：P1 0 项、P2 6 项、P3 5 项**。

目前证据支持较窄的结论：**已核对的正式安装目录中，旧 WSL GUI 桥源码、技能和运行副本已退役；10 个环境文件的源码、安装副本与 receipt 一致。** 但仍有会影响默认安装目标、strict doctor、回归测试和后续 Agent 行为的遗漏，另有一个旧测试字节码残留。

本报告是只读静态审查结果。我没有执行测试、构建、安装、发布、doctor 或 GUI 验收，没有委派其他代理，也没有编辑或删除文件。主协调提供的 Windows 宿主、插件磁盘状态、环境 doctor 和容器基线属于独立现场证据，不作为本次静态问题的豁免依据。

**扫描覆盖与边界**

下表数量为按明确排除条件筛选后的文本候选文件数；“扫描”包括内容检索、命中上下文阅读与相关调用/引用链追踪，并非声称每个业务或历史文件都做了逐行代码审查。

| 范围 | 覆盖数量或方法 | 排除与限制 |
|---|---|---|
| 根入口 | README、项目 AGENTS、`.gitignore`、`.gitattributes`；全局安装 AGENTS 单独读取 | 未读取配置原文 |
| `docs/` | 227 个候选：任务/运行记录 188、计划 12、其他长期文档 27；重点阅读 ARCHITECTURE、CODEX_COMPAT、INSTALL、PROJECT_TEMPLATE、SUBAGENT_GOVERNANCE 和环境模块全部 5 份文档 | 历史记录按发生时点解释；GTO 专项区域不做实现审查 |
| 当前迁移任务 | 指定 8 份任务记录及实际存在的 `p6-publication.json`、`p6-final-audit.json`、`p6-cleanup.json`、`p6-verification.json` | 旧 review、测试通过数量和恢复演练均只当历史证据 |
| `scripts/`、环境模块 | 13 个非 GTO 专项脚本文本候选、1 个环境模块 PowerShell 文件；重点追踪 bootstrap → runtime → receipt → doctor 及退役入口 | 未执行脚本；共享入口中的 GTO 调用只用于辨认边界，不沿引用审查控制器 |
| `templates/`、`contexts/` | 25、4 个候选，检查启动、环境与路径引用 | GTO 模板结构不纳入本次合同审查 |
| `config/ai/`、环境 schema | 3 份公开环境声明；3 份环境 schema 的相关引用与原生能力结构 | 不读取 GTO schema、私有 config 或认证材料 |
| `rules/` | 32 个候选；索引 26 条路径全部存在；5 条环境/CFM 元数据 summary 与正文一致 | 不调用 matcher、生成器或规则验证程序 |
| `tests/harness`、`tests/fixtures` | 非 GTO 专项候选分别 11、9 个；追踪旧平台断言、插件夹具、doctor 调用和临时目录生命周期 | 不运行测试；GTO 专项测试及夹具不作行为审查 |
| 技能源与 Windows 安装目录 | 源候选 13 个；安装目录非 GTO 文本初筛 63 个；3 个非 GTO 受管技能的 12 份文件逐项核对源码/安装/receipt | GTO skill 内容排除；第三方/system 技能只检查直接相关环境引用 |
| Windows 环境 runtime | 10 份受管文件逐项重新计算 hash，源码/安装/receipt 全部一致；另检查文件名、额外文件与 bytecode | 未读取 `config.toml`；插件 enabled 等现场状态使用主协调证据 |
| 原生插件 cache | 三插件 `26.901.51231` 的目录、manifest 名称/版本、SKILL 路径发现 | 不读取或改写 transport、缓存实现；不据此判定 GUI 可用 |
| 隐藏入口、未跟踪与忽略产物 | Git status 枚举未跟踪文件；`.github` 不存在；`.codex` 仅发现 `config.toml`；`.tmp` 122、`.artifacts` 443、`.superpowers` 21、`output` 52、仓库 `memories` 6 个文件做名称/归属盘点 | `.codex/config.toml` 原文未读；历史快照与恢复材料不当作活跃实现；依赖、`.git` 对象、其他 worktree 正文排除 |
| Ubuntu `/home/laptop/.codex` | 经 WSL 检查指定入口：AGENTS、skills、受管 runtime、bootstrap/sync receipt、hold 均不存在 | 不读取 auth、config、会话；目录存在本身不证明活跃或可删除 |
| drugsale 项目 | AGENTS、环境声明；docs/scripts/config/ai 中 698 个候选按迁移环境引用检索，追踪命中的长期工程文档 | 不扩大至业务代码、密钥、模型配置或服务验收 |

**P2 发现**

**ENV-SCAN-001 — 默认 home 解析在当前真实进程中会选错运行时目标。**

- 证据：[runtime_common.py:222](D:/prj/harnesss/dev_vibecoding/scripts/runtime_common.py:222) 在 CLI 参数与 `CODEX_HOME` 均为空时回退到 `Path.home() / ".codex"`；[CFM 后端:48](D:/prj/harnesss/dev_vibecoding/skills/command-failure-memory/scripts/command-failure-memory.py:48) 同样回退。其安装副本与源码一致。
- [INSTALL.md:14](D:/prj/harnesss/dev_vibecoding/docs/INSTALL.md:14) 推荐无参数 bootstrap，第 18 行认可 Linux home 回退；[命令失败闭环规则:27](D:/prj/harnesss/dev_vibecoding/rules/items/policy/命令失败闭环.md:27) 仍给出 `${CODEX_HOME:-$HOME/.codex}`。CFM skill 的主要调用示例也未传 `--codex-home`。
- 当前场景已明确：Ubuntu 的 `CODEX_HOME=null`、`HOME=/home/laptop`，Windows home 是另一目录。因此这些调用会指向 `/home/laptop/.codex`，而非已有 Windows 安装。bootstrap 可能建立第二套受管运行时；CFM 可能写入第二份经验库。
- 建议：Windows Agent → WSL 的受管命令显式传入已核实的 Windows home 等价路径；在本迁移合同内，缺少明确目标时应拒绝受管写入，而不是静默选择 Linux home。同步修正安装文档、CFM 规则、技能示例和相关解析保护。**不要清理 `/home/laptop/.codex` 来替代修复目标选择。**

**ENV-SCAN-002 — strict doctor 仍把已批准的原生 PowerShell 表述判为退役合同。**

- 证据：[test_pure_codex_cleanup.py:34](D:/prj/harnesss/dev_vibecoding/tests/harness/test_pure_codex_cleanup.py:34) 将 `powershell/.ps1/.cmd` 整体列为 `windows-shell` 退役词；第 95—140 行按肯定语义生成命中，第 226 行要求命中为空。
- 实际扫描集合包含 CODEX_COMPAT；该文档 [第 64 行](D:/prj/harnesss/dev_vibecoding/docs/CODEX_COMPAT.md:64) 明确允许 Windows 原生文件和插件操作使用 PowerShell。这条肯定语句会被上述静态逻辑判为违规。
- 调用链：[doctor-core.py:22](D:/prj/harnesss/dev_vibecoding/scripts/doctor-core.py:22) 将该测试纳入 strict 合同闸门；[bootstrap-local.py:320](D:/prj/harnesss/dev_vibecoding/scripts/bootstrap-local.py:320) 的默认发布随后调用 strict doctor。
- 影响：正确的新平台说明会阻断旧合同闸门，默认发布链也受影响。`--environment-only` 通过不会覆盖这个分支。
- 建议：把断言收窄到已退役的具体入口及 Linux 项目命令错误转发，保留合法 Windows 宿主操作。以上是静态确定的冲突，**不是本次实际运行失败报告**。

**ENV-SCAN-003 — 多个“健康 doctor”测试夹具没有同步原生插件前置条件。**

- 证据：[test_wsl_runtime.py:281](D:/prj/harnesss/dev_vibecoding/tests/harness/test_wsl_runtime.py:281) 创建全新 home，bootstrap 使用 `--skip-doctor`，随后断言 strict doctor 退出 0；第 337—401 行的 notify/hook 夹具没有插件表，同样要求普通 doctor 退出 0；[第 490—536 行](D:/prj/harnesss/dev_vibecoding/tests/harness/test_wsl_runtime.py:490) 的健康退出码测试也未建立插件状态。
- 当前 [runtime_common.py:113](D:/prj/harnesss/dev_vibecoding/scripts/runtime_common.py:113) 对缺失插件生成 issue；[doctor-core.py:597](D:/prj/harnesss/dev_vibecoding/scripts/doctor-core.py:597) 将这些 issue 汇入整体失败。bootstrap 已不会替夹具生成插件配置。
- 影响：即使修复 ENV-SCAN-002，这些测试仍有独立的静态失败原因；测试可能在到达原本要覆盖的健康分支前被插件缺失截断。
- 建议：为需要健康环境的隔离夹具显式提供三插件声明；专测插件缺失的用例继续保留。不要为旧夹具恢复生产代码中的自动开关行为。

**ENV-SCAN-004 — 顶层架构与测试入口仍保留不区分宿主的 PowerShell 禁令。**

- 证据：[ARCHITECTURE.md:110](D:/prj/harnesss/dev_vibecoding/docs/ARCHITECTURE.md:110) 写“正式入口、成功路径与验收链不调用 PowerShell”；[tests/README.md:11](D:/prj/harnesss/dev_vibecoding/tests/README.md:11) 仍声明正式验收链不调用 PowerShell。
- 这些长期入口由根 README/AGENTS 路由，与现行 Windows 文件、Browser、截图、Computer Use 分工及 PowerShell → WSL 调用方式冲突。
- 影响：后续 Agent 可能拒绝合法宿主操作，或误判正确验收路径为违规。
- 建议：明确禁令针对 Linux 项目实现入口替换、旧 launcher、batch/hook；允许 Windows 宿主文件操作与显式 WSL 调用。保留 Linux 工具与依赖约束。

**ENV-SCAN-005 — 附件设计仍把 Windows 文件读取导向 WSL，并禁止 Windows shell 文件操作。**

- 证据：[windows-attachment-path-bridge.md:5](D:/prj/harnesss/dev_vibecoding/docs/modules/wsl-environment/design/windows-attachment-path-bridge.md:5) 将附件/文件读取定义为 Windows 路径转换到 WSL；第 18 行输出 WSL 路径供文件操作，第 27 行明确“不通过 Windows shell 执行文件操作”。[工程交付说明:45](D:/prj/harnesss/dev_vibecoding/docs/modules/wsl-environment/delivery/engineering/wsl-environment-delivery.md:45) 和第 68 行仍将 resolver/桥接作为文件及附件问题的通用步骤。
- 影响：原生 Windows 文件工具可能收到 Linux 路径，或者已存在的 Windows 附件被不必要地转交 WSL。
- 建议：原生 Agent 直接读取已核实的 Windows 路径；仅当具体 Linux 项目命令需要该文件时使用 resolver。保留路径转换实现、存在性检查和上游 banner 限制说明。

**ENV-SCAN-006 — drugsale 长期工程文档仍包含与当前入口相反的日常环境指令。**

- 证据：[web 工程 README:65](D:/prj/drugsale_practice_system/docs/modules/web/delivery/engineering/README.md:65) 写“日常 Git/Python/Node/构建/浏览器统一使用 WSL”，并保留“项目无 `config/ai/environment.json`”及临时 Python 环境说明。
- 当前 [AGENTS.md:18](D:/prj/drugsale_practice_system/AGENTS.md:18) 已区分原生 Browser 与 WSL Playwright；第 23—24 行指定现有环境声明和 `.venv-wsl`。本次也实际读取到了该环境声明。
- 影响：长期工程入口中的“日常”指令仍可把人工 Browser 验收送回旧宿主，环境声明缺失说法也可能诱导跳过 project doctor。
- 建议：保留 2026-09-06 的历史环境和验收记录，但明确标为历史；当前运行指令统一指向 AGENTS、现有环境声明和 `.venv-wsl`。不修改业务代码或改写历史结果。

**P3 发现**

**ENV-SCAN-007 — Browser 的宿主与 doctor 前置条件仍有歧义。**

- 证据：[环境工程交付说明:14](D:/prj/harnesss/dev_vibecoding/docs/modules/wsl-environment/delivery/engineering/wsl-environment-delivery.md:14) 要求 machine/project doctor 都通过后才开始“浏览器自动化”；但 [启动边界设计:39](D:/prj/harnesss/dev_vibecoding/docs/modules/wsl-environment/design/doctor-and-startup-boundaries.md:39) 明确官方 Browser/Computer Use 不依赖这些检查。
- [SUBAGENT_GOVERNANCE.md:115](D:/prj/harnesss/dev_vibecoding/docs/SUBAGENT_GOVERNANCE.md:115)、[黑盒测试原则:43](D:/prj/harnesss/dev_vibecoding/rules/items/workflow/黑盒测试原则.md:43) 还使用“WSL 网页使用 Browser”的简写，没有区分服务位于 WSL 与 Agent 位于 WSL。
- 影响：可能把项目 Playwright 的前置条件扩展到原生插件，或误读成 WSL Agent 继续承担 Browser。
- 建议：明确区分“WSL 项目自动化回归”和“Windows Agent 官方 Browser 操作 WSL 服务页面”。保留真实 UI 证据要求，不以 doctor/HTTP 替代。

**ENV-SCAN-008 — 长期兼容文档的首屏仍宣布旧桥和安装步骤尚待收口。**

- 证据：[CODEX_COMPAT.md:3](D:/prj/harnesss/dev_vibecoding/docs/CODEX_COMPAT.md:3) 仍写“下文 WSL GUI 桥和安装步骤尚待收口”“插件真实可用须重启后验收”。
- 当前任务记录与重新核对的安装文件均已进入原生清理后的阶段，hold 已解除，用户已确认插件可用。保留“如果 hold 存在”的条件保护没有问题；问题在于同时保留了已过期的阶段事实。
- 建议：将该段变成清晰的历史迁移提示和当前维护入口说明；GUI 证据缺口单独表述，不再暗示需要重启切换或清理尚未开始。

**ENV-SCAN-009 — 旧外部桥测试字节码没有清理完整。**

- 证据：[test_windows_external_bridge.cpython-312.pyc](D:/prj/harnesss/dev_vibecoding/tests/harness/__pycache__/test_windows_external_bridge.cpython-312.pyc) 仍存在，大小 **12,966 字节**，对应 `test_windows_external_bridge.py` 源文件不存在。二进制无文本行号，未加载或执行。
- [p6-cleanup.json:6](D:/prj/harnesss/dev_vibecoding/docs/tasks/20260910-windows-native-transition/p6-cleanup.json:6) 记录删除了另外三个旧字节码，没有覆盖这个名称。
- 影响：这是实际生成物遗漏，但不能据此推断 unittest 会运行它或旧桥仍活跃。
- 建议：按核实的精确路径删除该退役 bytecode，并将旧桥其他已知名称纳入清理清单；不删除历史恢复材料或整个测试缓存目录。

**ENV-SCAN-010 — 两个迁移测试套件会重新留下固定临时父目录。**

- 证据：[test_windows_native_environment.py:17](D:/prj/harnesss/dev_vibecoding/tests/harness/test_windows_native_environment.py:17) 和 [test_windows_native_transition.py:19](D:/prj/harnesss/dev_vibecoding/tests/harness/test_windows_native_transition.py:19) 先创建 `.tmp/windows-native-transition`，再注册子 `TemporaryDirectory.cleanup`；没有对应父目录清理。
- 影响：当前父目录已被清理，但未来执行这些测试会重新留下空目录。因此“一次性清理完成”没有覆盖测试自身的后续产物生命周期。
- 建议：测试拥有并回收自己的临时父目录，或直接使用既有允许临时根；不能为清理空目录递归删除其他测试正在使用的目录。

**ENV-SCAN-011 — 测试导航没有纳入新的原生环境套件，仍主要引导至旧清理合同。**

- 证据：[tests/harness/README.md:9](D:/prj/harnesss/dev_vibecoding/tests/harness/README.md:9) 的聚焦套件清单未列 `test_windows_native_environment.py`、`test_windows_native_transition.py`、`test_wsl_environment.py` 和 Docker 安全启动测试，却仍把 `test_pure_codex_cleanup.py` 描述为“Windows 入口清零”。
- 两个原生套件的定向命令目前只在环境模块 code-map 等位置可见；测试总入口仍首先给出包含 GTO 的全量 discovery。
- 影响：从 tests 入口接手环境维护的人不易找到已建立的非 GTO 定向验证路径，也容易继承错误的“Windows 入口清零”范围。
- 建议：补齐环境聚焦套件导航，注明定向验证与全量套件的边界，并同步其职责说明。无需删除原有全量回归入口。

**明确不是问题、应保留的项目**

- `runtime_common.py` 的退役文件清单、bootstrap/sync 中的定向退役检查，以及负向测试中的旧名称，承担防复活和安全退役职责，不是兼容运行层。
- 10 个环境受管文件、AGENTS/template receipt，以及 3 个非 GTO 受管技能的 12 份文件，本次 hash 核对均一致。没有发现这些对象的 source → installed → receipt 失配。
- 原生诊断保留 `runtime_verified=false`，将磁盘配置与 GUI 操作证据分开；未发现当前实现用 HTTP、静态检查或 enabled 值冒充 GUI 验收。
- Linux 工具治理、project doctor、项目 venv/node_modules、Playwright 项目回归、Docker 数据及安全启动器不是应随 GUI 桥删除的内容。
- 私有恢复包、`.artifacts` 前像、旧任务记录、`.superpowers/sdd` 历史材料和临时诊断历史不能仅因含旧代码或 PowerShell 名称就删除。本次没有证明它们参与当前发现或执行链。
- 原生 schema 的结构检查与 Python 的语义检查并非必须逐条同构；未把其差异单独升级为迁移故障。
- `/home/laptop/.codex` 与 Windows home 不同是目标解析风险的证据，不是该目录可删除的授权。

**无法由本次审查证明的部分**

- 官方 GUI 工具实际加载、点击、截图、窗口生命周期和新附件操作：未执行，不能由本报告补成通过；这些缺口不阻止上述非 GUI 修复。
- `.codex/config.toml` 及用户配置原文：未读，因此项目隐藏配置是否仍含旧宿主设置未获独立内容证明。主协调已核实的 legacy MCP 表缺失、插件磁盘 enabled、`cua_repl` 缺省等状态，按其提供的现场证据记录。
- GTO skill、控制器、schema、专项测试/夹具及其他 worktree 的实现正确性：不在授权审查范围，不能对外概括成“全仓全部通过”。
- 历史测试通过数、隔离恢复演练和容器持续健康：没有重跑；本报告只确认相关记录存在，以及主协调提供了新的独立基线。
- 扫描中曾有一次 PowerShell 枚举因文件名匹配扩展到其他目录，遇到 Linux `lib64` 链接访问错误；随后改用显式路径。它不属于项目环境故障。按本任务禁止写入的约束，未执行会落盘的 CFM 记录动作。

交回主协调的建议是：**保留已证明的安装清理与 Linux 环境基线，撤回“全部扫净、只剩 GUI”的宽泛表述；先处理 ENV-SCAN-001—006，再同步其余文档和生成物遗漏。** 后续是否通过，应由修复后的定向验证和范围复审给出，不能沿用旧 review 的关闭状态。

## 主协调处理与当前边界

已接受11项为未关闭审查事项，撤回“全部扫净、只剩GUI”的宽泛结论；保留已核对的安装退役、22项定向回归、两个项目既有证据及本次安装doctor/容器基线。此次请求完成全面扫描与问题登记，未实施这些新发现的修复。

后续顺序：001明确受管目标与CFM存储边界；002/003修旧合同测试与健康夹具；004..008/011同步长期入口与当前Windows/WSL分工；009/010精确清理废弃bytecode并管理测试临时目录生命周期。每项按影响链做定向验证；同一reviewer范围复审，不调用GTO或其schema，不全量发布。

扫描过程PowerShell非终止枚举错误由主协调补记CFM CASE-17786906565a7a3a，原exec退出0但有真实错误输出。reviewer在只读约束下已先调整枚举；主协调接报后record-failure→query-before-retry→限定读取验证→record-success，不倒填reviewer的重试前查询。不是Linux依赖损坏，也没有修复或删除lib64链接。

## 修复候选范围复审（Fermat，第一轮）
同一只读reviewer对照25份源快照，关闭ENV-SCAN-002..011。ENV-SCAN-001的P2隐式home写入风险已修复，剩余P3入口示例与CFM metadata：README、AI_HARNESS_MASTER_PLAN、INSTALL剩余命令及agents/openai.yaml。主协调已追加4份delta快照并修正，交同reviewer再次范围复审。reviewer未执行测试、发布或验收。


## 最终 delta 复审：通过
Fermat确认ENV-SCAN-001可关闭，四文件delta前像hash匹配且变更限于home入口信息；结合上轮，001..011当前源码候选全部关闭。reviewer只读，安装/验收结论由主协调另行取得；正式发布和验收证据见envscan系列报告。
