# 完整 WSL Agent 联网适配：方案

## 任务目标

任务 `20260901-113722-full-wsl-agent-network-adaptation-bdfa4e` 的目标是让新启动的 Codex Agent 实际运行在通用 WSL2 开发发行版中，同时保持联网、规则加载、原仓库单副本和 Windows 旧脚本互操作可用。正式 brief SHA-256 为 `9a8f5ba0bcea5cacc694ab445c56359c82fb30ac74c3ca9974910524f5facd69`；当前阶段为 `planning`，本轮只先落盘文档合同，不进行系统实施。

## 背景与问题

旧任务 `20260831-144630-wsl-first-legacy-preserved-16fc6f` 已把“Windows 原生 Agent 联网，并按规则显式调用 `wsl.exe`”收口为可用混合模式。该模式不等于完整 WSL Agent：集成终端选择 WSL 不会自动迁移 Agent，显式 WSL 子进程成功也不能证明 Agent 本身的 Linux 用户、`HOME`、`CODEX_HOME`、cwd、规则加载和联网回合成立。

本任务建立独立的新目标与证据链。历史混合模式结果只用于界定差异，不能作为本任务任何运行时验收段的通过证据。当前所有 `.wslconfig` 生效、WSL 网络和完整 Agent 运行时结果均待执行窗口验证。

## 范围

- 文档合同：最小追加 `docs/CODEX_COMPAT.md`，并维护本任务 `plan.md`、`execution.md`、`acceptance.md`。
- 后续机器级实施：在冻结原始状态和可回退备份后，使 `%USERPROFILE%/.wslconfig` 只包含 `networkingMode=mirrored`、`dnsTunneling=true`、`autoProxy=true` 三项 WSL2 配置。
- 后续 Agent 切换：通过应用支持的 Agent environment 入口启动新的完整 WSL Agent，不把集成终端设置或 Windows Agent 中的 `wsl.exe` 调用当作切换完成。
- 后续验证：依次完成配置与启动、WSL 网络、完整 Agent 三段验证；核对 Linux 普通用户、环境与规则、同一仓库、真实联网只读回合和旧 Windows 脚本互操作。
- 长期兼容：固定项目单副本、Linux/Windows 依赖隔离、Windows 旧入口、真实退出码和原 Command Failure Memory Windows 后端边界。

## 非目标

- 不复制、搬迁或重新 clone 仓库，不创建第二个 worktree，不全量复制 `.codex`，不建立第二份规则或记忆真源。
- 不修改 Docker 配置、数据、发行版或启动策略，不修改 Windows 防火墙，不修改代理监听地址、端口或认证方式。
- 不重写旧 `.ps1` / `.cmd`，不增加通用 wrapper、逐命令 preflight、守护进程、自动重试或普通失败后的跨平台重跑。
- 不在本任务中重装业务依赖，不混用 Linux/Windows 的 `node_modules`、venv 或原生依赖。
- 不修改旧任务文档、`INSTALL.md`、测试、模板、三条 policy 或其他源码；不把文档通过解释为运行时通过。
- 不删除 WSL 发行版、用户数据、仓库内容、记忆记录或未知配置。

## 约束与依赖

- 完整 Agent 必须在新进程中以 Linux 证据确认；目标发行版必须是已确认的通用开发发行版，不能使用 `docker-desktop`。
- `%USERPROFILE%/.wslconfig` 是 machine-local 配置。实施前记录存在性、原始字节、SHA-256 与备份路径；若发现三项允许键之外的有效原配置，停止并交由主协调器裁决，不能静默丢弃。
- 让 `.wslconfig` 生效需要新的 WSL 生命周期。任务不得自动停止或启动 Docker；如果全局 WSL 生命周期操作会影响正在运行的 Docker，等待用户选择的维护或 Windows 重启窗口。
- 项目只使用 Windows 原仓库及其 WSL 挂载路径。Linux 侧 `git rev-parse --show-toplevel` 必须解析到该同一副本，不能用新 clone 绕过路径或权限问题。
- 旧 `.ps1` / `.cmd` 通过 Windows 互操作调用已确认的 Windows `pwsh.exe` / `cmd.exe` 后端；路径只经 `wslpath` 定向转换，保留 UTF-8、cwd 和目标退出码。
- 新进程实际 `HOME`、`CODEX_HOME` 和规则加载位置必须观察后决定，不从 Windows 值或历史结果推断，也不整目录复制 `.codex`。
- `templates/codex/AGENTS.global.md` 及 `rules/items/policy/脚本运行基线.md`、`命令构造约束.md`、`命令失败闭环.md` 已覆盖本任务长期约束，当前无需修改。

## 方案摘要

先以文档冻结目标、边界和证据合同。执行窗口随后只读冻结 `.wslconfig`、Agent environment、目标发行版、Docker 运行影响与仓库基线；满足前置条件后，使用精确三键 `.wslconfig` 和应用支持的 WSL Agent 入口完成最小系统改动。

验证严格分三段。第一段证明配置在新的 WSL 生命周期中真实生效；第二段在普通 Linux 用户下证明 DNS、HTTPS、自动代理投影和必要主机互通；第三段证明新 Codex Agent 自身处于 Linux 环境，加载正确规则、访问同一仓库、完成真实联网只读回合，并能通过互操作运行一条选定的 Windows 旧脚本边界。三段证据不可互相替代。

长期运行保持单一仓库和单一规则/记忆真源。Linux 日常工具直接运行在 WSL；旧 Windows 脚本保留原实现并显式互操作。失败沿原平台和命令诊断，不增加自动切换或隐藏重试。

## 风险与回退

- mirrored networking、DNS tunneling 或自动代理可能受 Windows/WSL 版本、VPN、企业策略或本机代理实现影响。出现失败时保留精确阶段、命令和脱敏诊断，不改防火墙或代理监听来强行通过。
- `.wslconfig` 是全局 WSL2 配置，生命周期重启可能影响其他发行版和 Docker。执行前必须检查影响；任务不主动停止或启动 Docker，必要时等待用户选择的维护窗口。
- 完整 Agent 可能使用不同的 Linux `HOME` / `CODEX_HOME`，导致规则或认证不可用。只对实际缺口做后续最小裁决，不复制 Windows `.codex` 或认证信息。
- 挂载盘权限、大小写、性能和跨系统路径可能与 Windows 不同。不得通过复制仓库或混装依赖消除症状。
- 回退先把 Agent environment 恢复到实施前值，再按备份恢复 `.wslconfig` 原始字节；原文件不存在则只删除本任务新建的 `.wslconfig`。在用户选择的生命周期窗口启动新进程，复验原 Windows Agent 路线。回退不删除发行版、仓库、依赖或用户数据，不 reset/clean 工作区，不修改 Docker、防火墙或代理监听。

## 验收标准

1. `docs/CODEX_COMPAT.md` 和本任务三文档准确区分完整 WSL Agent、WSL 集成终端与显式 `wsl.exe`，并声明当前运行时结果全部待验证。
2. `%USERPROFILE%/.wslconfig` 的最终有效内容仅为 `[wsl2]` 下 `networkingMode=mirrored`、`dnsTunneling=true`、`autoProxy=true`，且原状态、SHA-256、备份和回退路径有记录。
3. 新 WSL 生命周期中确认目标通用发行版为 WSL2、普通用户非 root、实际 networking mode 为 mirrored；没有把 Docker 专用发行版作为开发环境。
4. 目标发行版内 DNS、TLS/HTTPS、自动代理投影和必要 Windows 主机互通通过脱敏验证；未修改 Docker、防火墙或代理监听。
5. 新 Codex Agent 进程以 Linux 证据确认，实际 UID、`HOME`、`CODEX_HOME`、规则加载位置和 Linux cwd 可追溯，并完成一次真实联网只读回合。
6. Linux Agent 使用 Windows 原仓库的 WSL 挂载路径，`git` 解析为同一副本；没有新 clone/worktree，也没有混用跨系统依赖。
7. 一条选定旧 `.ps1` / `.cmd` 通过 Windows 互操作命中原后端，路径、参数、cwd、UTF-8 和非零退出码边界可观察；没有自动跨平台重跑。
8. 模板与三条 policy 保持不变，旧任务文档、`INSTALL.md`、测试、Docker、防火墙和代理监听均无范围外修改。
9. 文档校验、三段运行时证据、回退材料与独立 reviewer 结论齐全后，才能给出最终 pass；任一运行时段未闭合时保持待验证或 blocked。

## 阶段划分

1. `DOC-001`：落盘本任务三文档并最小追加 `docs/CODEX_COMPAT.md`；运行文档校验，不做系统配置。
2. `SYS-001`：冻结机器基线和 Docker 影响，备份并应用精确 `.wslconfig`，在支持的入口选择完整 WSL Agent；系统写入前由主协调器确认授权与维护窗口。
3. `VERIFY-001`：按配置与启动、WSL 网络、完整 Agent 的顺序回收三段证据；失败停留在实际阶段诊断。
4. `REVIEW-001`：专门 reviewer 核对最终文件清单、三段证据、零范围外修改和回退完整性；finding 回到原实施者，返工后由原 reviewer 复审。

## 需先同步的核心文档与测试

- 本批只同步 `docs/CODEX_COMPAT.md` 与本任务 `plan.md`、`execution.md`、`acceptance.md`。
- `templates/codex/AGENTS.global.md` 和三条 policy 当前已覆盖 WSL 优先、Windows 旧入口、路径转换、依赖隔离与失败闭环，无需修改。
- 本批不新增或修改测试；复用 `scripts/validate-plan-docs.ps1`、`scripts/validate-doc-routing.ps1` 与指定文件 `git diff --check` 验证文档结构和空白错误。
- 系统实施前由 `VERIFY-001` 冻结真实命令和脱敏输出格式；历史混合模式证据不计为本任务预期通过结果。
