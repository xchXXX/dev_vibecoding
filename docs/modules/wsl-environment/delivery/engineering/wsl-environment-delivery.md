# WSL 环境工程交付说明

## 本地运行

在目标仓库根的 WSL shell 中运行所有入口；不要在 Docker 专用发行版、PowerShell 或 batch 中替代正常链。具体 CLI 参数以各脚本的 `--help` 为准，JSON 模式用于机器可读验收。

```bash
python3 scripts/provision-wsl.py --help
python3 scripts/doctor-core.py --help
python3 scripts/project-env-doctor.py --help
python3 scripts/resolve-wsl-path.py --help
```

首次创建 worktree 后，先运行 machine doctor。任务第一次需要实际项目运行时时，再运行该项目的 project doctor；检查通过后才开始对应 Linux 项目的测试、构建或 Playwright 回归。Windows 原生 Agent 的官方 Browser/Computer Use 操作不以 machine/project doctor 为前置条件。 若迁移 hold 存在，暂停全局 bootstrap/sync 与旧 machine doctor 修复链，按任务记录继续；项目 doctor 和正常插件请求仍可运行。

## Docker Desktop 安全启动器

这是 Windows 外部能力的单独安装项，不属于每个项目都要执行的 WSL 脚本。只有已经确认本机存在 Docker Desktop 残留 socket 复发问题，并得到用户明确授权后，才从 Windows PowerShell 执行一次：

```powershell
& "D:\prj\harnesss\dev_vibecoding\modules\wsl-environment\tooling\docker-desktop-safe-start.ps1" -Action Install -CodexHome "$env:USERPROFILE\.codex" -Json
```

安装后有两个启动入口：当前用户登录时由 HKCU Run 执行的 `AI Harness Docker Safe Start`，以及开始菜单中的 `Docker Desktop Safe Start`。后续手工重启 Docker 时应使用开始菜单的安全入口；原始 Docker Desktop 快捷方式不会被替换。按用户安装缺少官方 `InstallLocation` 时会补齐该 HKCU 值，已有冲突值则停止安装。

状态和限定环境诊断如下；此诊断不调用 GTO 或读取其 schema，不代表全局 doctor 或 GUI 验收通过。迁移 hold 期间按任务阶段执行，不用诊断结果触发全量修复：

```powershell
& "$env:USERPROFILE\.codex\.ai-harness\runtime\windows-external\docker-desktop-safe-start.ps1" -Action Status -Json
```

```bash
# 先查实 Windows 实际 CODEX_HOME 的 WSL 等价路径；本机核实值如下。
python3 scripts/doctor-core.py --environment-only --root /mnt/d/prj/harnesss/dev_vibecoding --codex-home /mnt/c/Users/Laptop/.codex --json
```

运行记录保存在 `<CODEX_HOME>/.ai-harness/runtime/windows-external/logs/docker-safe-start.jsonl`。被轮换的目录保留在原目录旁的 `*.stale-<timestamp>` 中，不自动清理。

## 依赖与环境

- WSL 机器公共工具来自基线，不从项目 manifest 推断。
- Python 和 Node 项目依赖只按当前项目的 manifest/lock 在 WSL 侧恢复；不能复用 Windows 安装产物。
- Playwright、Docker 等可选能力必须由项目声明；Windows 人工浏览不等于 WSL 自动化浏览器已安装。
- `CODEX_HOME` 由 bootstrap/doctor 的受管 runtime 合同处理；它不是项目依赖目录，也不能整目录复制。
- Windows 原生文件/附件读取使用已核实Windows路径；仅具体Linux命令需要文件时使用resolver转换单个路径，initial banner仍是上游限制。
- Windows 原生 Agent 使用官方 Browser 和 Computer Use；WSL 保留项目命令与 Linux 依赖。harness 只读检查原生插件配置，不改写官方 transport、插件开关或注册 WSL GUI 桥；磁盘配置不等于真实 GUI 验收。
- 第三方 Windows 服务不属于当前原生插件声明和发布范围；按其官方安装与接入合同单独处理。

## 验证方式

验证按本次变更的实际范围执行：原生声明、只读诊断、隔离环境重复发布、受管旧桥退役及影响范围回归。迁移维护期间不运行 GTO 或读取其 schema，不全量发布 harness；文档改动检查定向 diff。

```bash
python3 scripts/validate_doc_routing.py --repo-root "$PWD" --json
python3 scripts/validate_plan_docs.py --repo-root "$PWD" --json
git diff --check -- docs/modules/wsl-environment docs/CODEX_COMPAT.md docs/INSTALL.md scripts/README.md \
  rules/items/policy/缺失工具分层与依赖处理.md rules/items/policy/脚本运行基线.md \
  rules/items/policy/窗口系统附件路径桥接.md templates/codex/AGENTS.global.md
```

## 排障说明

| 症状 | 归属 | 正确下一步 |
| --- | --- | --- |
| 命令解析到 `/mnt/c` 或 Windows Program Files | 机器公共工具 | 记录分类，按明确基线修正 WSL 工具；不跨平台自动重跑 |
| `TEMP`、`.venv`、`node_modules` 来自 Windows | 项目依赖隔离 | 按项目 manifest/lock 在 WSL 恢复；不自动删除旧目录 |
| Playwright/Docker/云 CLI 缺失 | 可选能力 | 先检查项目声明和任务需要，再经明确权限处理 |
| 附件初始 banner 或 UI 上传失败 | Windows 外部能力/上游产品 | 先用原生文件工具核对用户明确给出的Windows路径及存在性；保留上游证据，勿声称仓库可消除 banner |
| managed runtime hash 不匹配 | Codex runtime | 查看 receipt 和受管真源，运行明确的 bootstrap/sync 流程；必要时新建任务或重启会话 |
| Docker 第二次启动报 `sailor-ingest.sock` 无法访问 | Windows 外部能力 | 使用已安装的安全启动入口；它只备份已知零字节 socket，遇到陌生内容会停止并保留现场 |
| 需要检查本地网页 | 浏览器能力 | Windows 原生 Agent 使用官方 Browser；项目服务继续运行于 WSL |
| 需要操作原生 Windows GUI | Windows 原生能力 | 使用官方 Computer Use；只关闭本任务自建且无未保存内容的窗口，工具未加载则记录对应验收项 pending |
| 第三方 Windows MCP 接入 | 其他外部能力 | 按官方合同单独处理；不复用已退役的 WSL GUI 桥 |

## 不适用项

不适用：本模块不提供后台持续监控、命令重试服务或通用环境“自动修复”按钮。Docker 安全启动器只在 Windows 用户登录或用户显式入口触发，并只处理已冻结的残留 socket 故障。
