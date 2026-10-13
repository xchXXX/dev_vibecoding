# WSL 环境分层合同

## 模块边界

`wsl-environment` 负责在项目测试或构建开始前，明确“当前 WSL 环境是否具备运行条件、问题属于哪一层、下一步由谁处理”。它不替代项目依赖清单，不代替 Windows 或 Docker 的设置界面。正常 WSL 链保持只读；经用户单独授权安装的 Docker Desktop 安全启动器属于 Windows 外部能力，不进入普通命令链。

Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；项目 Git/Python/Node/测试/构建继续通过指定发行版的 wsl.exe --exec 执行。外部能力声明 v3 只列 windows_native 与 required_plugins；bootstrap/doctor 不写插件配置或官方 transport，不创建 WSL GUI 桥。磁盘 enabled 不等于 GUI 验收。

## 四层所有权

| 层级 | 负责的对象 | 声明或证据 | 允许的处理 | 不负责 |
| --- | --- | --- | --- | --- |
| 机器公共工具 | WSL 发行版共享的命令、Linux 原生 Node 工具链和基础构建工具 | `config/ai/wsl-tool-baseline.json`、`schemas/wsl-tool-baseline.schema.json` | `provision-wsl.py` 先给出计划；只有显式 `apply` 才执行已声明的最小安装 | 安装项目库、升级整套发行版或变更 Windows 设置 |
| 项目依赖隔离 | 某项目的 Python 虚拟环境、Node `node_modules`、锁文件恢复结果 | 项目自己的 manifest/lock，及 `environment.example.json` 对应的项目声明 | `project-env-doctor.py` 只读分类和报告；项目维护者按 manifest/lock 恢复 | 将项目依赖提升为系统包、跨项目复用 `.venv` 或 `node_modules` |
| 可选能力 | Playwright 浏览器、Docker、数据库、云 CLI、硬件或其他项目选择的能力 | 项目环境声明中的 capability | 仅在项目明确声明且本次任务实际需要时检查或安装；缺失时给出分类结果 | 把可选能力变成所有机器的必装项 |
| Windows 外部能力 | 官方 Browser、Computer Use、Desktop 运行时 | v3 原生插件声明与真实 GUI 证据 | Windows Agent 使用官方工具；harness 只读检查 | 不改 transport、安全设置、插件开关或注册 WSL GUI 桥 |

Linux 与 Windows 的原生依赖必须隔离。Windows 产生的 `.venv`、`node_modules`、二进制缓存或命令路径不是 WSL 项目运行时的替代品。

## 运行时安全边界

- 不引入 hook、daemon、通用逐命令 wrapper、平台自动回退或自动重试。外部能力通过声明选择受支持的执行环境或标准 MCP transport，不接管普通命令。
- machine doctor、project doctor 和 path resolver 默认只读；它们输出稳定的 JSON 分类结果，而不修复环境。
- `provision-wsl.py` 的默认行为是计划/检查。执行变更必须使用明确的 apply 意图，并且只针对基线中已声明、来源明确的包；不做 broad upgrade、卸载、发行版切换或未知来源安装。
- 不自动删除、覆盖或重建 `.venv`、`node_modules`、仓库、`CODEX_HOME` 或 Windows 用户目录。诊断结果只说明负责层和下一步。
- Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；项目 Git/Python/Node/测试/构建继续通过指定发行版的 wsl.exe --exec 执行。外部能力声明 v3 只列 windows_native 与 required_plugins；bootstrap/doctor 不写插件配置或官方 transport，不创建 WSL GUI 桥。磁盘 enabled 不等于 GUI 验收。

## Windows 原生外部能力

`config/ai/windows-external-capabilities.json` 使用 schema_version=3，每项只包含 id、kind=windows_native、provider、required_plugins。Browser 要求 browser 与 unified-computer-use；Computer Use 要求 computer-use。旧 WSL bridge 和未使用的通用路由类型已退役，不保留自动兼容分支。

Desktop 管理 node_repl/cua_repl 的 transport 和工具装配。诊断只读 enabled；缺省字段不等于禁用，缺插件或异常开关只提示 check_desktop_plugin。runtime_verified 保持 false，GUI 证据另行取得。

## Docker Desktop 安全启动例外

`modules/wsl-environment/tooling/docker-desktop-safe-start.ps1` 是一个显式安装、用户级的 Windows 外部入口，用于处理 Docker Desktop 停止后遗留的 AF_UNIX socket 目录。它不是 hook、daemon、逐命令 wrapper 或通用重试器。

- 安装动作复制固定脚本、注册当前用户的 HKCU Run 登录入口，并创建“Docker Desktop Safe Start”开始菜单入口；不会接管 WSL 的 `docker` 命令。旧的同名计划任务会被移除，避免非交互任务上下文重复启动。
- 对按用户安装的 Docker Desktop，安装动作只在确认真实 Launcher 位于 `%LOCALAPPDATA%\Programs\DockerDesktop` 时补齐官方安装模式应有的 HKCU `InstallLocation`；已有不同值时拒绝覆盖。
- 启动前先检查 Docker 是否已经健康；健康时不做任何修复。检测到已有启动进程时先给它 30 秒完成启动，避免和正常初始化竞争。
- 只有 `Docker/run` 与 `docker-secrets-engine` 中的已知零字节 socket 名全部符合白名单时，才把整个目录改名为带时间戳的备份并重建空目录。
- 发现陌生文件、非零字节内容或子目录时立即失败，原目录保持不动。备份和 JSONL 运行记录不会由脚本自动删除。
- `doctor-core.py` 只校验安装 receipt 及源文件/安装副本 hash；不调用 Windows 命令，也不把“receipt 正常”冒充 Docker 引擎在线。

## 配置契约

机器公共工具的单一机器可读真源为 `config/ai/wsl-tool-baseline.json`，其结构由 `schemas/wsl-tool-baseline.schema.json` 约束。项目环境声明使用 `schemas/project-environment.schema.json`；Python 项目在 `requirements_file` 与 `pyproject_file` 中二选一，后者可用 `extras` 指定需要一起核对的可选依赖组。doctor 只解析依赖并执行离线 dry-run，不构建项目。新项目从 `templates/project/config/ai/environment.example.json` 复制后再填写项目实际依赖和 capability。

项目声明必须是声明式数据：描述依赖层、期望的 Linux 运行时、可选能力和诊断入口。它不能携带任意 shell、任意下载 URL、密钥或“发现问题就执行”的修复命令。

## 不适用项

不适用：本模块不修改 /etc/wsl.conf、Docker UI、Agent environment 或插件 transport。bootstrap/doctor 不写 config.toml；Docker 安全启动器仅处理显式授权的启动故障。

## Windows 原生迁移的限定维护入口

维护标志存在时发布入口拒绝写入。先在隔离目标验证，再冻结候选、受控解除、正式定向发布，失败恢复标志。

- `python3 scripts/bootstrap-local.py --environment-only --harness-root <root> --codex-home <home> --json`：只投放环境 runtime 并更新其真实 receipt；不改动 AGENTS、hooks、插件 config、其他技能和 schema。
- `python3 scripts/sync-codex.py --retire-legacy-gui --harness-root <root> --codex-home <home> --json`：旧桥 MCP 已明确停用且技能符合既有 receipt 时，仅将旧技能移入私有恢复目录并更新该技能记录；未知改动拒绝退役。
- `python3 scripts/doctor-core.py --environment-only --root <root> --codex-home <home> --json`：只审计环境 runtime/receipt、Linux 工具和原生插件配置；不执行 GTO 或其 schema，不等价于全局 doctor 通过。

bootstrap/doctor 不修改原生插件配置。一次性迁移在私有备份和定点核对后删除旧 WSL GUI 桥配置、代码与技能；完成后不保留旧运行或发现入口。Windows 调用 WSL 时使用 `wsl.exe -d <distro> --cd <project> --exec python3 <script>`；复杂内容先写脚本文件，避免默认 shell 解释反引号、重定向或变量。
