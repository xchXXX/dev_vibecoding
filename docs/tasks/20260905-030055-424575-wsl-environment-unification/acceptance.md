# WSL 环境统一治理

Task ID: `20260905-030055-424575-wsl-environment-unification`

## 验收目标

Deliver the repository-side WSL environment unification system approved by the user so recurring cross-platform failures are prevented or stopped at task start.

## 验收标准

- A clean fixture can load and validate the baseline and project declarations.
- Wrong-platform command paths, TEMP values, Python environments, Node artifacts, and Docker fallbacks are diagnosed before project tests run.
- Provisioning and doctor commands are idempotent, JSON-capable, and safe in read-only mode.
- Managed runtime sync is hash-verified and existing unrelated Codex files are preserved.
- The Windows path resolver handles drive paths, spaces, Unicode, malformed input, and missing files deterministically.
- Focused suites and one final full harness pass; independent review covers the latest scoped diff.

## 必备证据

- 初始最小 Red、每轮复审反例、Green 命中证明、61 项相关 WSL 回归、161 项完整 harness、规则/文档验证和 scoped diff-check 均有实际命令证据。
- 最新同一 reviewer re-review hash 为 `9b1f0adbfa117c07181ed65cd39a6e6fb3b7da9e384d7a4881230bf44658f488`，所有已登记 finding 已关闭。

## 未决项

- 本仓库不会自动修改 `/etc/wsl.conf`、Docker Desktop WSL Integration、Codex GUI/Local Environment 或 live `<CODEX_HOME>/config.toml`；这些属于后续经用户授权的机器侧交接。
- 本仓库不会替用户执行 apt、pnpm 或项目依赖安装；doctor 发现缺口后 fail-closed，并给出所属层级和下一步。
- Codex 会话开头的 `Files mentioned by the user` / 本地临时附件 banner 属于上游产品输入链，本实现只提供显式路径桥接，不能保证 UI 上传成功或隐藏 banner。

## 最终结论

独立 final/pass 已覆盖最新 scoped source manifest，任务完成。

## 2026-09-09 验收重开

上面的最终结论只覆盖最初 WSL 分层治理，不再代表 Windows Computer Use 桥的当前结论。重启黑盒已观察到 Desktop 恢复官方 `node_repl.exe`，旧 bootstrap 随后再次改写配置并要求重启；因此该扩展方案验收失败，任务重新进入纠偏施工。

新的最终闸门必须同时满足：

- 官方插件生成的 MCP 表不被 bootstrap 改写。
- machine doctor 不把官方 Computer Use 配置当作 WSL 环境错误。
- WSL 网页任务自动选择内置 Browser；Windows GUI 在 WSL 中必须在调用 Computer Use 前停止，并明确交接到应用的 Windows-native Agent environment，不暴露底层 transport 错误。
- 全新 Codex 黑盒任务没有收到桥接实现提示，也不出现 `sandboxCwd`、`windows_external_bridge_required` 或重启循环。
- 首次 review 已穷举本轮范围问题，后续 findings 均有 Red/Green、范围复审和范围验收记录。

当前结论：`pending`。在新黑盒证据产生前，不恢复 `pass`。

首轮全新黑盒结果：网页任务和项目测试任务通过；Windows GUI 任务失败并复现 `sandboxCwd is not a local file URI`。已进入 `REV-WEC-011` 迭代，当前结论继续为 `pending`。

## 2026-09-09 最新候选验收状态

- 外部能力模块 14/14、受影响范围 69/69、完整 harness 224/224 通过；规则、文档路由和任务文档闸门通过。
- 真实 bootstrap 已定点关闭两个声明内 WSL 不兼容插件；原配置内容寻址备份存在且哈希一致，官方 `node_repl` 的 `command/args/env` 未被接管。
- 第二次真实 bootstrap 为零改动、零重启原因，已证明机器侧配置幂等。
- 第三轮无提示黑盒运行在施工前已启动的旧宿主内，仍持有旧的插件 skill 并复现 `sandboxCwd`。这是宿主不热加载配置的直接证据，不算最终通过。

重启后最终黑盒结果：新进程 machine doctor 为 green，当前 skill 清单不再包含 Computer Use；隔离黑盒只收到自然记事本请求，未调用 Computer Use、未出现 `node_repl/sandboxCwd`，直接给出 Windows-native Agent environment 交接，且未触碰用户文件。

最终结论：`pass`。WSL 中的 Windows GUI 请求现在会在插件初始化前自动停止并给出受支持的环境切换方式；不会再先撞到底层 `sandboxCwd` 错误。该结论不声称 WSL 能直接控制 Windows GUI，也不声称同一任务可自动迁移到 Windows native。

最终记录更新后完整 harness 再验：224/224 通过（709.051 秒）；规则、文档路由、任务文档与 scoped diff-check 均通过。

## 2026-09-09 能力验收再次重开

上面的 `pass` 只证明 WSL 会话不会再撞到 `sandboxCwd`，但其做法是移除 Computer Use 能力并要求用户切换环境，未满足“保持 WSL、直接调用 Windows GUI、无需逐次设置和重启”的实际目标。该结论现已撤销。

当前结论：`pending`。

新的通过条件是：独立兼容入口保留 Desktop 官方 `node_repl` 真源，只转换可证明等价的 WSL 挂载盘 `sandboxCwd`；真实协议通过该入口执行 `sky.list_apps()`；最终全新无提示黑盒必须实际打开、读取并关闭 Windows 记事本。仅返回交接说明、仅无报错或仅单元测试通过均判失败。

安装候选状态：4 轮范围复审的全部 Critical / Important / Minor findings 已关闭，最终复审允许安装；43 项桥接/外部能力测试、42 项 WSL 环境测试和真实 `sky.list_apps()` 协议 smoke 已通过。尚缺本机 bootstrap 后的新进程无提示记事本黑盒，以及该次真实 Windows `node_repl.exe` 子进程无遗留证明，因此结论仍为 `pending`，不能提前写成 `pass`。

机器安装状态：本机窄 bootstrap、备份/所有权核对、已安装代理真实协议 smoke 和第二次零改动幂等复跑均通过；GTO 未被同步。安装后在当前旧 Desktop 宿主内创建的无提示子代理仍继承旧工具清单，未实际打开记事本，因此该轮黑盒明确判失败。当前仅剩一次安装后宿主重启，以及重启后真正无提示的“打开、读标题、关闭、无新增 PID 遗留”黑盒；当前结论继续为 `pending`。

## 2026-09-10 重启后验收迭代

重启后首个真正无提示黑盒已实际打开、读取并只关闭本任务新建的记事本窗口；原窗口集合保持不变，精确 `argv[0]` PID 基线和结束结果均无 `node_repl.exe` 遗留。该轮已证明桥接能自动使用且无需切换设置。

但现场还发现 skill 示例错误地假设 `list_apps.id == list_windows.app`。黑盒代理自行使用全窗口差集完成了安全操作，不能用这次自适应掩盖指引缺陷。因此已按 TDD 把指引改为“复合窗口身份全量前后差集必须唯一，再用标题或可访问性确认应用”，并只同步该 skill；30 项外部能力、5 项同步范围、14 项兼容代理、42 项 WSL 环境回归及 doctor 均通过。

当前结论继续为 `pending`：等待这次修复的独立 review 和同步后第二次无提示黑盒，失败则继续迭代。

首次独立 review 发现 1 个 Important：状态读取返回对象可能覆盖由差集证明的初始窗口身份。该 finding 已以不可变 `targetWindowIdentity` 修复，目标用例与外部能力 30/30 再次通过并已同步本机；当前等待同一 reviewer 范围复审和最终无提示黑盒，结论仍为 `pending`。

同一 reviewer 已确认该 Important 关闭且无新增 finding。随后无提示黑盒完成真实记事本生命周期，但关闭后的首个即时窗口快照仍看见旧窗口，第二次只读快照才消失；能力结果成功，但过程产生了可避免的异步假失败记录。已新增有界条件检查指引并同步本机，当前等待该最小变更复审与第三次无提示黑盒；在此之前结论保持 `pending`。

## 2026-09-10 最终结论

- 异步条件检查修订经独立复审，唯一 Minor 测试缺口已关闭；最终无 Critical、Important 或 Minor finding，verdict 为 `Ready`。
- 第三次完全无提示黑盒实际打开并识别唯一任务记事本窗口 `28249748`，确认标题与空白状态，只发送一次关闭，首次独立只读条件检查即确认窗口消失；未触碰用户原窗口或文件。
- 黑盒前后按 NUL 分隔 `argv[0]` 精确匹配的 `node_repl.exe` 基线均为空；没有遗留 runtime 子进程。
- 本轮没有出现 `sandboxCwd`、插件、权限、窗口归属或异步假失败；machine doctor、受管安装 hash、skill validator 和受影响测试均为 green。

最终结论：`pass`。在后续新 Codex WSL 任务中，Windows GUI 请求会自动发现 `windows-computer-use-wsl`，通过独立 `computer_use_wsl` 兼容入口使用官方运行时，只转换可证明等价的挂载盘 `sandboxCwd`；无需切换 Agent environment、无需为每次插件调用修改设置或重启。窗口操作仍 fail closed：无法唯一证明任务归属、应用不匹配或检查超限时会停止并报告，而不会猜测或重复 mutation。

## 2026-09-10 Browser 回归验收重开

上述 `pass` 对 Windows 原生 GUI 桥仍然成立，但后续真实 Browser 请求证明旧插件策略同时关闭了 `unified-computer-use`，使内置 Browser 只能由用户打开，代理无法操作。该问题属于同一外部能力分流方案的回归，因此整体状态重新标记为 `pending`。

新的最终通过条件是：磁盘策略稳定保持 `unified-computer-use@openai-bundled=true`、`computer-use@openai-bundled=false` 和 `computer_use_wsl` 就绪；重启后的全新任务能实际操作内置 Browser；Windows 记事本无提示黑盒仍通过。

当前静态与安装证据：首轮为 32/32 外部能力测试及 106/106 受影响范围；review 修复后的最新结果为 34/34 focused、108/108 受影响范围。规则、文档、任务文档校验与 scoped diff-check 通过；真实 bootstrap 的内容寻址备份匹配施工前哈希，只改变 `unified-computer-use` 的布尔值，`node_repl`/`cua_repl` transport 未变；静态修复重新同步后的第二次 bootstrap 零改动；doctor 两路均为 `configured_for_wsl`。独立 review 的 TOML 行内注释保真、schema/runtime parity、缺失可选 Browser 直接测试和路由文档冲突均已修正，TOML 测试也已加强为整文件 exact-bytes 断言；最终静态复审确认所有 Critical / Important / Minor 均关闭，静态候选为 `Ready`。

当前结论仍为 `pending`，原因只剩当前任务不会热加载新工具。需要在新 Desktop 进程中完成 Browser 与 Windows GUI 双黑盒，不能用磁盘 doctor 或单元测试替代。

### 重启后 Browser 黑盒结果

首次重启后的 Browser 黑盒为 `fail`：标签页可以打开，明确自然语言请求和 `@Browser` 请求仍没有获得 Browser 控制工具。现场确认插件开关已为 `true`，但 app-managed `cua_repl` MCP 仍为 `enabled=false`；doctor 未检查这一层而假绿。整体继续为 `pending`，必须先修复 MCP 开关声明与 doctor，再重新进入新进程双黑盒。

### `cua_repl` 修正静态候选

- TDD 首轮 3/3、外部能力整文件最初 35/35、受影响范围最初 109/109 通过；首次 review 的 3 个 Important 与 1 个 Minor、范围复审新增的 1 个 Important 与 1 个 Minor 均已用 Red/Green 修复。最终外部能力 43/43、受影响范围 117/117；第二次范围复审无 Critical/Important，代码 verdict 为 `Ready`。
- 已证明标准和 quoted `cua_repl` 表只修改目标 `enabled`，保留 BOM、CRLF、注释、`command/args/env/timeout` 和相邻表；无法安全定点改写、非布尔开关或非 table 目标均明确 fail closed。
- 当前状态仍为 `pending`：尚缺真实本机 bootstrap 的内容寻址备份与二次幂等、安装版 doctor，以及重启后 Browser 点击和 Windows 记事本非回归双黑盒。静态测试不得替代这些证据。

### `cua_repl` 安装态验收

- `pass`：施工前哈希与内容寻址备份一致；整份配置只有现有 `cua_repl.enabled` 从 false 改为 true，Browser/Computer Use 插件状态和三个 MCP transport 均保持所有权边界。
- `pass`：第二次相同 bootstrap 零变化、零重启原因；安装版 doctor 对 Browser 与 Windows GUI 均为 `configured_for_wsl`，无 findings/errors。
- `pending`：当前 Desktop 进程不会热加载本轮开关，尚未取得 Browser 工具出现并实际点击 `More information` 的黑盒证据。
- `pending`：尚未在同一新宿主下复验 Windows 记事本完整生命周期与 `node_repl.exe` 无遗留。

当前总体结论继续为 `pending`。下一步只有一次 Codex Desktop 重启和重启后的双黑盒，不再需要切换设置或重复执行 bootstrap。

## 2026-09-10 重启后纠偏状态

- `fail`：重启后的新进程仍未获得 Browser 控制工具；`cua_repl.enabled=true` 没有跨 Desktop 启动保持，不能作为根治方案。
- `pass`：根因已定位到当前 Desktop 的 WSL 分支，而不是用户没有正确重启或没有正确打开 Browser。
- `pending`：独立 `browser_use_wsl` 尚未完成 TDD、review、真实协议 smoke 和新进程页面点击黑盒。
- `not accepted`：不得再以“配置中暂时为 true”、doctor 绿灯、Browser 标签页可打开、HTTP 访问成功或 Windows GUI 黑盒通过，代替 Browser 实际点击证据。

当前总体结论：`pending`。最终必须在完全不提示桥接细节的新任务中自动点击 `More information`，读出跳转后的标题与 URL，并在同一候选下复验记事本；失败继续迭代，测试夹具清理、任务记录和 CFM 证据保留。
