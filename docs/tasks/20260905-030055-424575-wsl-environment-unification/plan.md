# WSL 环境统一治理

Task ID: `20260905-030055-424575-wsl-environment-unification`

## 任务目标

Deliver the repository-side WSL environment unification system approved by the user so recurring cross-platform failures are prevented or stopped at task start.

## 背景与问题

当前任务已由用户确认六要点，需要以文档、测试、实现和审查证据保持同一目标。

## 范围

- config/ai
- schemas/wsl-tool-baseline.schema.json
- schemas/project-environment.schema.json
- scripts/provision-wsl.py
- scripts/doctor-core.py
- scripts/project-env-doctor.py
- scripts/resolve-wsl-path.py
- scripts/bootstrap-local.py
- templates/project
- templates/codex/AGENTS.global.md
- rules/items
- rules/registry/RULES_INDEX.json
- docs/modules/wsl-environment
- docs/CODEX_COMPAT.md
- docs/INSTALL.md
- scripts/README.md
- tests/harness
- tests/fixtures/wsl-environment

## 非目标

- /etc/wsl.conf
- Docker Desktop UI settings
- <CODEX_HOME>/config.toml live mutation
- system package installation
- mass project migration
- automatic deletion of .venv or node_modules
- hooks, daemons, per-command wrappers, platform fallbacks, and automatic retries

## 约束与依赖

- Stop before any system-level mutation not already represented as repository code or documentation.
- Stop if a scoped write path overlaps unrelated dirty content and cannot be isolated without user direction.
- Stop if implementation would require guessing an undocumented Codex Local Environment file format.
- Stop if the same blocking condition recurs three goal turns without a safe in-scope alternative.

## 方案摘要

Use layered WSL-native tooling rather than globally installing project packages.

## 风险与回退

- Stop before any system-level mutation not already represented as repository code or documentation.
- Stop if a scoped write path overlaps unrelated dirty content and cannot be isolated without user direction.
- Stop if implementation would require guessing an undocumented Codex Local Environment file format.
- Stop if the same blocking condition recurs three goal turns without a safe in-scope alternative.

## 验收标准

- A clean fixture can load and validate the baseline and project declarations.
- Wrong-platform command paths, TEMP values, Python environments, Node artifacts, and Docker fallbacks are diagnosed before project tests run.
- Provisioning and doctor commands are idempotent, JSON-capable, and safe in read-only mode.
- Managed runtime sync is hash-verified and existing unrelated Codex files are preserved.
- The Windows path resolver handles drive paths, spaces, Unicode, malformed input, and missing files deterministically.
- Focused suites and one final full harness pass; independent review covers the latest scoped diff.

## 阶段划分

1. 文档与测试先行。
2. 按互斥写入范围实施。
3. 统一验证并进入 review / fix / re-review。

## 需先同步的核心文档与测试

- 同步任务涉及的长期真源文档。
- 建立能直接命中目标问题的最小测试。

## 2026-09-09 Windows 外部能力纠偏

### 缺陷声明

重启黑盒验收证明，Codex Desktop 会在启动时重新装配官方 `computer-use` 插件的 `node_repl` MCP。bootstrap 在任务开始后覆盖该表只能修改磁盘，不能替换已经启动的 MCP 进程；再次重启又会恢复官方配置，因此“doctor 报漂移 → bootstrap 改写 → 要求重启”形成循环，不能达到无感防复发。

### 目标方案

- 不再接管插件自带 `node_repl` 的 transport command，也不修改 Codex Desktop 运行时缓存。
- WSL 中的网页检查优先路由到 Codex 内置 Browser。
- 真正的 Windows GUI 自动化声明为 `windows_native_only`，交给官方 Computer Use 所在的 Windows-native 环境。
- 第三方 Windows 外部能力优先使用标准 `http_mcp`；machine doctor 只读检查声明和显式 HTTP MCP 配置，不自动改写。
- bootstrap 只同步 harness 自己的 runtime、规则和文档入口；不再因官方插件配置产生重启原因。

### 修改范围

- `config/ai/windows-external-capabilities.json`
- `schemas/windows-external-capabilities.schema.json`
- `scripts/runtime_common.py`
- `scripts/bootstrap-local.py`
- `scripts/doctor-core.py`
- `templates/codex/AGENTS.global.md`
- `rules/items/policy/缺失工具分层与依赖处理.md`
- `docs/modules/wsl-environment/**`
- `docs/CODEX_COMPAT.md`、`docs/INSTALL.md`、`scripts/README.md`、`schemas/README.md`
- `tests/harness/test_windows_external_capabilities.py`、必要的相关 runtime 测试

### 非目标

- 不修改 `WindowsApps`、`%LOCALAPPDATA%/OpenAI/Codex/runtimes` 或官方插件缓存。
- 不创建 watcher、daemon、启动竞态脚本或逐命令 wrapper。
- 不承诺同一个 WSL Agent 进程无缝控制所有 Windows 桌面软件。
- 不为尚未存在的第三方 MCP 自动安装或启动服务。
- 不删除既有备份、CFM 记录或本任务过程证据。

### Verification contract

```yaml
minimal_repro: "隔离 CODEX_HOME 中放入 Desktop 生成的官方 node_repl 表；运行 bootstrap 后证明旧实现会改写该表并要求重启"
hit_proof: "同一夹具中 bootstrap 保持 config.toml 逐字节不变、restart_reasons 不含 Windows 外部能力；doctor 返回 ok 且把 computer-use 分类为 windows_native_only"
diagnostic_checks:
  - "test_bootstrap_preserves_host_managed_node_repl"
  - "test_machine_doctor_routes_computer_use_without_bridge_drift"
  - "test_global_agents_routes_web_and_windows_gui_without_repair_loop"
acceptance_checks:
  - "相关 unittest 全绿"
  - "完整 harness 全绿"
  - "规则、文档、schema 和 diff 校验全绿"
  - "全新 Codex 黑盒任务在无桥接提示下选择正确能力且不触发旧错误"
non_goals:
  - "patch Codex proprietary runtime"
  - "background watcher or automatic restart"
  - "silent installation of Windows software"
review_evidence:
  - "repro_before_fix"
  - "pass_after_fix"
  - "hit_proof_observed"
  - "relevant_regression_ok"
```

## 2026-09-10 重启后架构纠偏：独立 Browser WSL 桥

完整重启证明上一轮“把 app-managed `cua_repl.enabled` 改成 `true`”并不是稳定方案：Codex Desktop 在 WSL 模式下会重新生成该表并恢复为 `false`，新进程仍不暴露 Browser 工具。对当前安装版代码的只读核对进一步确认，Desktop 在 `shouldUseWslPaths=true` 时不会把 Browser `node_repl` 交给 `cua_repl`，Browser 运行资格也显式要求 `!shouldUseWslPaths`。因此继续修改该开关只会制造假绿和重复重启。

纠偏后的方案复用已验证的 Windows runtime 透明代理，但把 Browser 作为独立 `browser_use_wsl` MCP surface 暴露；它动态解析当前 Desktop 自带的 `node_repl.exe` 与 Browser trusted service，只补充 Browser 所需的受限环境字段，不修改官方插件缓存、应用二进制、Browser 权限或 Windows 安全设置。

```yaml
minimal_repro: "新 Desktop WSL 进程中工具清单没有 Browser/cua_repl；Desktop 已把 cua_repl.enabled 恢复为 false；安装版代码在 shouldUseWslPaths=true 时省略 Browser nodeRepl"
hit_proof: "新进程自动取得 browser_use_wsl；通过内置 Browser 的 iab 后端点击 example.com 的 More information，并回报跳转后的标题和 URL；同一候选下 computer_use_wsl 记事本生命周期仍通过且无 node_repl.exe 遗留"
diagnostic_checks:
  - "Browser bridge 动态解析现有 node_repl 与当前 Desktop 自带 Browser service，缺失、越界或版本漂移时 fail closed"
  - "bootstrap 注册 browser_use_wsl 与 computer_use_wsl 两个独立 surface，不再修改 app-managed cua_repl"
  - "doctor 接受 WSL 下 cua_repl=false 的宿主事实，但缺失或漂移的 Browser bridge/source 必须报错"
  - "代理除挂载盘 sandboxCwd 转换和 Browser allow-list 环境补充外，保持 JSON-RPC 字段与权限对象不变"
acceptance_checks:
  - "focused tests、受影响范围测试、规则/文档/schema validator 与 scoped diff-check 通过"
  - "真实 bootstrap 有内容寻址备份、配置定点 diff，并且第二次运行零变化"
  - "实际 Browser native pipe 协议 smoke 命中当前打包 Browser service"
  - "新 Desktop 进程完成 Browser 点击黑盒与 Windows 记事本非回归黑盒"
non_goals:
  - "修改 Codex Desktop/app.asar、官方插件缓存、官方 node_repl 真源或 app-managed cua_repl"
  - "启用完整 CDP、绕过 Browser 安全策略、扩大网站权限或操作 Codex 自身界面"
  - "切换 Agent environment、后台 watcher、每次调用前修改设置或要求重启"
review_evidence:
  - "repro_before_fix"
  - "pass_after_fix"
  - "browser_pipe_hit_proof"
  - "fresh_browser_blackbox"
  - "native_gui_non_regression"
```

TDD 顺序固定为：先锁定声明/生成/doctor/代理行为的最小 Red，再实现双 surface；首次 review 穷举协议、安全、更新漂移、进程生命周期、配置保真、自动发现、文档与测试问题；每个 finding 先 Red 后修复并做范围复审。真实黑盒失败则继续迭代，不能退回“强开 `cua_repl`”或用 doctor 绿灯代替页面点击。

### 实施与复审顺序

1. 先同步长期文档、任务文档和测试合同。
2. 写最小失败测试并确认失败类型正好命中旧的改写/漂移逻辑。
3. 只做让测试转绿的最小实现，再清理失去职责的代码和 runtime 投放项。
4. 首次 review 按合同、数据流、异常、兼容、安全、测试和文档七个面完整扫描；不因发现首个问题停止。
5. review 每发现一项缺陷，先补最小 Red，再修复并做对应范围 review 与范围验收。
6. 最后运行全新 Codex 黑盒验收；失败则按同一循环迭代，不用单测替代黑盒结论。

### 黑盒失败后的支持边界纠正

首轮全新黑盒中，网页与项目测试任务通过；Windows 记事本任务虽然先运行 doctor 且选择了官方 Computer Use，仍在执行任何 JavaScript 前收到 `sandboxCwd is not a local file URI: file:///mnt/d/...`。这证明 `windows_native_only` 不能只作为说明性标签，必须在 WSL 进程调用插件前形成明确停止条件。

OpenAI Windows 文档说明 Agent environment 是应用级 `Windows native` / `WSL` 二选一设置，切换后需要重启；Computer Use 文档只承诺在 Windows 活动桌面工作，没有同一任务自动跨环境迁移接口。因此本轮不伪造自动迁移：doctor 对 Windows GUI 返回 `unavailable_in_wsl` 与 `start_windows_native_agent`；全局入口要求 WSL 任务在调用 Computer Use 前停止，并给出 `Settings > Agent environment > Windows native` 的受支持交接。只有存在等价网页入口时才可改用 Browser。

第二轮黑盒证明提示词仍无法覆盖插件 skill 自身的强制初始化合同。第三轮采用受支持的插件开关，而不是 transport 改写：声明列出在 WSL 必须禁用的官方插件 ID；bootstrap 只把这些已存在插件表的 `enabled` 改为 `false`，修改前创建内容寻址备份，其他 TOML 字节和所有 MCP transport 字段保持不变；doctor 对重新启用的冲突插件 fail closed。切换到 Windows-native 后，由用户在插件界面显式启用 Computer Use。

## 2026-09-09 WSL 直连 Computer Use 修订方案

### 缺陷声明

“禁用官方插件并要求切换 Windows-native”只消除了错误提示，没有恢复用户要求的 Windows GUI 能力。真实协议探针进一步证明：Desktop 生成的 Windows `node_repl.exe` 能从当前 WSL 进程连接 native pipe 并执行 `@oai/sky`；失败发生在 Codex 将 `file:///mnt/d/...` 作为 Windows 本地 `sandboxCwd` 传给运行时的边界。

### 已批准架构

- 保留官方 `mcp_servers.node_repl` 及其动态 `command/env` 为 Desktop 真源，不覆盖、不缓存版本路径或 pipe 值。
- 新增独立 `computer_use_wsl` MCP 兼容入口。它每次启动读取当前 `config.toml` 中的官方 `node_repl` 条目，启动同一官方运行时并透明转发 MCP JSONL。
- 只在 `tools/call.params._meta["codex/sandbox-state-meta"].sandboxCwd` 为 `file:///mnt/<drive>/...` 时转换为对应 Windows file URI；其他请求、响应和权限字段原样保留。无法确定映射时 fail closed。
- 官方 Computer Use 插件在 WSL 继续禁用，避免其 skill 调用错误的 `node_repl` namespace；新增受管全局 skill 只为 Windows GUI 请求选择 `computer_use_wsl`。
- bootstrap 只管理独立 MCP 表和受管 runtime/skill；doctor 验证声明、配置、官方真源引用和兼容入口，不把官方条目改成私有 transport。

### 修改范围

- Create: `modules/wsl-environment/tooling/node-repl-wsl-compat.py`
- Create: `skills/windows-computer-use-wsl/SKILL.md`
- Modify: `config/ai/windows-external-capabilities.json`
- Modify: `schemas/windows-external-capabilities.schema.json`
- Modify: `scripts/runtime_common.py`
- Modify: `scripts/bootstrap-local.py`
- Modify: `scripts/doctor-core.py`
- Modify: `scripts/sync-codex.py`（仅受管 skill allow-list）
- Modify: `templates/codex/AGENTS.global.md`
- Modify: `rules/items/policy/缺失工具分层与依赖处理.md`
- Modify: `docs/modules/wsl-environment/**`、相关入口文档和任务记录
- Modify/Create: `tests/harness/test_windows_external_capabilities.py` 及最小兼容入口测试

### Verification contract

```yaml
minimal_repro: "向官方 node_repl 发送带 file:///mnt/d/... sandboxCwd 的无害 js 调用，稳定返回 not a local file URI；同进程使用 Windows URI 后 sky.list_apps 成功"
hit_proof: "兼容入口的协议测试证明只重写 sandboxCwd，随后真实官方 node_repl 通过兼容入口执行 sky.list_apps；最终黑盒实际打开、读出标题并关闭记事本"
diagnostic_checks:
  - "test_translate_sandbox_cwd_maps_mounted_windows_drive"
  - "test_translate_sandbox_cwd_rejects_non_windows_wsl_path"
  - "test_proxy_rewrites_only_sandbox_cwd_and_preserves_permission_profile"
  - "test_bootstrap_registers_independent_compat_server_without_overwriting_node_repl"
  - "real protocol smoke: sky.list_apps through compat server"
acceptance_checks:
  - "focused unittest and full harness pass"
  - "doctor reports computer-use configured_for_wsl through computer_use_wsl"
  - "fresh no-hint black box opens Notepad, reads title, closes it, and touches no user file"
  - "restart and second-project smoke require no settings change or additional restart"
non_goals:
  - "patch or replace Codex proprietary runtime/plugin cache"
  - "background watcher, daemon, automatic restart, Windows software installation, or security-setting changes"
  - "translate Linux-only /home paths into invented Windows locations"
review_evidence:
  - "repro_before_fix"
  - "pass_after_fix"
  - "hit_proof_observed"
  - "relevant_regression_ok"
```

### TDD 与验收顺序

1. 先更新本节、长期合同和验收状态；既有无提示黑盒 `sandboxCwd` 失败作为 skill 行为基线 Red。
2. 先写路径转换、协议透明性、配置保真、doctor 路由和 skill 发现测试并观察预期 Red。
3. 按 Red 顺序实现兼容入口、独立 MCP 注册、doctor 和最小 skill；每项 Green 后才进入下一项。
4. 首次 review 一次覆盖协议、权限、安全、进程生命周期、敏感值、更新漂移、配置保真、自动发现、文档和测试，不在首个 finding 停止。
5. 每个 review finding 先补 Red，再修复并做范围复审和范围验收。
6. 候选全绿后执行真实 bootstrap；只允许一次安装所需的 Codex 重启。重启后运行无提示 GUI 黑盒，失败则继续迭代。
7. 清理临时夹具；保留任务文档、CFM、测试输出摘要和内容寻址备份。

## 2026-09-10 Browser 自动化回归修正

真实任务在内置 Browser 已打开 `https://example.com/` 时仍没有任何 Browser 操作工具。磁盘清单确认 `unified-computer-use@openai-bundled` 是应用管理的 Browser 自动化运行时，而旧策略把它与原生 Windows Computer Use 插件一并禁用，导致“能打开面板但代理不能点击”。

本次最小修正合同：

```yaml
minimal_repro: "内置 Browser 已打开，但当前任务工具清单只有 computer_use_wsl，没有 cua_repl/Browser 操作入口；磁盘中 unified-computer-use 为 enabled=false"
hit_proof: "新进程在自然 Browser 请求下取得 Browser 工具并对 example.com 完成一次只读页面状态检查或链接点击；同一候选下 Windows 记事本仍经 computer_use_wsl 完成"
diagnostic_checks:
  - "声明将 unified-computer-use 列为 codex-browser 的 wsl_enabled_plugins"
  - "bootstrap 只恢复 unified-computer-use，同时继续禁用 computer-use"
  - "doctor 对被禁用的 Browser 必需插件返回 run_bootstrap"
acceptance_checks:
  - "外部能力和 WSL 范围测试通过"
  - "真实 bootstrap 只改变目标 enabled 字段且二次运行幂等"
  - "重启后的内置 Browser 黑盒通过"
  - "重启后的 Windows 记事本黑盒仍通过"
non_goals:
  - "修改官方插件缓存或 cua_repl/node_repl transport"
  - "自动开启完整 CDP、放宽网站权限或操作 Codex 自身界面"
review_evidence:
  - "browser_plugin_red"
  - "plugin_policy_green"
  - "fresh_browser_blackbox"
  - "native_gui_non_regression"
```

### 重启黑盒后的 `cua_repl` 修正合同

首次修正只恢复了插件开关。完整重启后，明确 Browser 请求和 `@Browser` 请求均未获得控制工具；本机配置同时显示 `unified-computer-use=true`、`mcp_servers.cua_repl.enabled=false`，而 doctor 仍错误返回 Browser `configured_for_wsl`。因此本轮把 MCP 运行时开关纳入同一声明式边界：

```yaml
minimal_repro: "完整重启后的任务打开 example.com 并明确请求 Browser；工具清单无 cua_repl，磁盘 cua_repl.enabled=false，但 doctor 报 Browser configured_for_wsl"
hit_proof: "doctor 对 false 返回 run_bootstrap；bootstrap 只将现有 cua_repl.enabled 改为 true；新进程工具清单出现 Browser 并实际点击 example.com 的 More information"
diagnostic_checks:
  - "declaration binds codex-browser to the existing cua_repl MCP server"
  - "doctor rejects an explicitly disabled required Browser MCP"
  - "bootstrap preserves cua_repl command/args/other fields and changes only enabled"
acceptance_checks:
  - "focused and affected WSL suites pass"
  - "real bootstrap backup and second-run idempotence pass"
  - "fresh Browser black box clicks and reads the resulting title/URL"
  - "fresh Notepad black box still uses computer_use_wsl without sandboxCwd failure"
non_goals:
  - "create a missing app-managed MCP table"
  - "modify cua_repl command, args, env, Browser permissions, CDP, or plugin cache"
review_evidence:
  - "repro_before_fix"
  - "pass_after_fix"
  - "hit_proof_observed"
  - "relevant_regression_ok"
```
