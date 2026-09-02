# 完整 WSL Agent 联网适配：施工说明

## 施工目标

按任务 `20260901-113722-full-wsl-agent-network-adaptation-bdfa4e` 的单一合同，先完成文档同步，再以最小 machine-local 配置把 Codex Agent 切换到完整 WSL 环境，并用三段证据证明配置生效、WSL 网络可用和 Agent 自身可用。当前 `DOC-001` 只写文档；所有系统和运行时结果均待后续执行窗口回填。

## 前置条件

- 主协调器继续使用现有 task ID 和正式 brief，不重新初始化任务；普通执行者不读取完整 `state.json`。
- 系统写入前确认用户对 `.wslconfig` 与 Agent environment 变更的授权，并确认不会由任务自动停止或启动 Docker；若需要全局 WSL 生命周期重启，使用用户选择的维护或 Windows 重启窗口。
- 只读记录 `%USERPROFILE%/.wslconfig` 是否存在、原始字节 SHA-256、目标发行版、`wsl.exe --version` / `wsl.exe --status`、发行版 WSL 版本、Agent environment、当前 Agent 平台和仓库根。
- 若原 `.wslconfig` 含本任务三项之外的有效配置，停止实施并由主协调器裁决；不得静默覆盖。
- 确认目标是通用开发发行版，普通用户已经存在；`docker-desktop` 不可作为目标发行版。
- 冻结项目单副本：Windows 原仓库与预期 `/mnt/<drive>/...` 挂载路径指向同一工作区，不创建 clone 或 worktree。

## 执行顺序

1. 完成 `DOC-001`：追加长期兼容合同，写齐三份任务文档，运行文档校验。
2. 完成只读机器基线：记录 `.wslconfig`、WSL/发行版、Docker 影响、Agent environment、当前进程和仓库信息；不读取认证信息。
3. 创建 machine-local 内容寻址备份；若原文件不存在，明确记录 `absent`，回退时只删除本任务创建的文件。
4. 把 `%USERPROFILE%/.wslconfig` 原子写为精确三键内容，并复读内容与 SHA-256；不写任何额外 WSL2 键。
5. 在不由任务停止或启动 Docker 的前提下进入新的 WSL 生命周期。若当前条件不允许，停在生命周期门禁，等待用户选择的维护窗口。
6. 完成第一段“配置与启动”验证；未通过时不进入网络或 Agent 验收。
7. 完成第二段“WSL 网络”验证；只输出脱敏网络证据，未通过时不改防火墙、代理监听或 Docker。
8. 通过应用支持的 Agent environment 入口启动新的 WSL Agent，完成第三段“完整 Agent”验证。
9. 回收变更清单、三段证据和回退材料，交独立 reviewer；finding 回到原实施者，最多按控制面约定返工并由原 reviewer 复审。

## 文档先行清单

- `docs/CODEX_COMPAT.md`：追加完整 WSL 目标、精确 `.wslconfig`、三段验证、长期兼容和回退合同，保留全部既有内容。
- `docs/tasks/20260901-113722-full-wsl-agent-network-adaptation-bdfa4e/plan.md`：冻结目标、范围、非目标、风险、阶段和验收。
- `docs/tasks/20260901-113722-full-wsl-agent-network-adaptation-bdfa4e/execution.md`：冻结执行顺序、批次写入、命令、停止条件和复审路径。
- `docs/tasks/20260901-113722-full-wsl-agent-network-adaptation-bdfa4e/acceptance.md`：冻结三段证据表和 planning 阶段的未决结论。
- `templates/codex/AGENTS.global.md` 与 `rules/items/policy/脚本运行基线.md`、`命令构造约束.md`、`命令失败闭环.md` 当前无需修改；它们已有长期平台、互操作和失败闭环口径。

## 测试同步清单

- `DOC-001` 不新增或修改测试；运行现有 `scripts/validate-plan-docs.ps1` 和 `scripts/validate-doc-routing.ps1`。
- `SYS-001` 不以仓库测试替代机器级证据；配置复读、哈希和新的 WSL 生命周期是第一段真源。
- `VERIFY-001` 使用只读或可回退的诊断命令分别验证三个阶段，不输出 token、cookie、代理凭据或完整认证配置。
- 选定 Windows 旧脚本的互操作验证必须使用安全 fixture 或只读入口，并显式观察预期非零退出码，不能对业务数据执行写操作。

## 实施批次

### 批次一：DOC-001 文档合同

依赖：正式 brief 与允许读取的旧任务文档。写入四个允许文件，运行文档校验。收口条件是章节完整、现有兼容文档内容保留、模板/三条 policy 无需修改得到明确记录，且没有系统写入。

### 批次二：SYS-001 最小机器配置

依赖：`DOC-001` 通过、系统写入授权、原 `.wslconfig` 基线与可恢复备份、Docker 影响已裁决。只允许写 machine-local `%USERPROFILE%/.wslconfig` 的三键内容和应用支持的 Agent environment 值。收口条件是配置复读与哈希一致，且可以在不由任务停止/启动 Docker 的维护窗口进入新 WSL 生命周期。

精确配置为：

```ini
[wsl2]
networkingMode=mirrored
dnsTunneling=true
autoProxy=true
```

### 批次三：VERIFY-001 三段验证

依赖：`SYS-001` 生效。

1. 配置与启动段：确认精确文件内容、目标发行版为 WSL2、普通用户非 root，并在新生命周期通过 `wslinfo --networking-mode` 或同等系统真源观察 `mirrored`。诊断入口缺失时记录阻塞，不能只凭配置文本宣称生效。
2. WSL 网络段：在目标发行版内验证 DNS 解析、HTTPS/TLS 返回、自动代理投影与必要主机互通。代理输出必须移除 userinfo、token、query 和其他凭据；HTTP 状态非 `000` 仅证明传输到达，不能替代认证回合。
3. 完整 Agent 段：在新 Agent 回合中确认 Linux、普通 UID、`HOME`、实际 `CODEX_HOME`、规则加载位置、Linux cwd 与同一仓库根；完成真实联网只读回合，并经 `wslpath` 定向转换运行一条选定 Windows 旧脚本边界，观察 UTF-8、cwd 和目标退出码。

收口条件是三段都具备当前新进程证据；历史任务、文档验证、显式 `wsl.exe` 子进程或单纯网络 403 均不能补位。

### 批次四：REVIEW-001 独立审查

依赖：三段验证及最终变更清单完整。reviewer 检查最终内容哈希、机器配置与备份、Docker/防火墙/代理零修改、项目单副本、旧脚本互操作和回退可执行性。存在 finding 时回到原实施者；返工后复用原 reviewer，不扩大范围静默修复。

## 每批写入范围

| 批次 | 允许写入 | 明确禁止 |
| --- | --- | --- |
| `DOC-001` | `docs/CODEX_COMPAT.md`；本任务 `plan.md`、`execution.md`、`acceptance.md` | 旧任务、模板、三条 policy、`INSTALL.md`、测试、源码、系统配置、完整 `state.json` |
| `SYS-001` | `%USERPROFILE%/.wslconfig`；应用支持的 Agent environment machine-local 值；经批准的 machine-local 回退备份 | Docker、防火墙、代理监听、仓库、`.codex` 整目录、认证信息 |
| `VERIFY-001` | 无业务或系统配置写入；仅由主协调器按控制面回收结果 | clone/worktree、依赖重装、跨平台自动重跑、第二份记忆库 |
| `REVIEW-001` | reviewer 只回填允许的审查结果 | 代替原实施者修复、直接扩展实施范围 |

## 验证命令

`DOC-001` 在仓库根运行：

```powershell
pwsh.exe -NoProfile -File scripts/validate-plan-docs.ps1
pwsh.exe -NoProfile -File scripts/validate-doc-routing.ps1
git diff --check -- docs/CODEX_COMPAT.md docs/tasks/20260901-113722-full-wsl-agent-network-adaptation-bdfa4e/plan.md docs/tasks/20260901-113722-full-wsl-agent-network-adaptation-bdfa4e/execution.md docs/tasks/20260901-113722-full-wsl-agent-network-adaptation-bdfa4e/acceptance.md
```

后续第一段使用实际目标发行版替换 `<distro>`，并逐项保存退出码与脱敏输出：

```powershell
Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig') -Raw
Get-FileHash -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig') -Algorithm SHA256
wsl.exe --version
wsl.exe --status
wsl.exe --list --verbose
wsl.exe -d <distro> -- sh -lc 'id -u; printf "%s\n" "$HOME"; wslinfo --networking-mode'
```

第二段必须在目标发行版的普通用户上下文运行，网络端点由执行窗口根据当前真源冻结；命令只输出 DNS/TLS/HTTP 结果及脱敏代理摘要，不写配置。第三段必须从新的完整 WSL Agent 回合采集 `uname -s`、`id -u`、`HOME`、实际 `CODEX_HOME`、`pwd`、`git rev-parse --show-toplevel`、规则加载证据、真实联网回合结果和选定 Windows 互操作结果。尖括号只表示执行窗口必须从只读基线取得真实值，禁止猜测发行版或端点。

## 回退方案

1. 停止继续验证，保存失败阶段、命令、退出码与脱敏诊断；不自动切换平台重跑。
2. 把 Agent environment 恢复到实施前记录的值，不复制或清理任何 `.codex`。
3. 原 `.wslconfig` 存在时，从内容寻址备份恢复原始字节并核对 SHA-256；原文件不存在时，只删除本任务创建的 `.wslconfig`。
4. 在用户选择的生命周期窗口启动新进程并复验原 Windows Agent 路线。若 Docker 正在运行且会受全局 WSL 生命周期影响，等待用户处理，不由任务停止或启动 Docker。
5. 核对仓库、发行版、用户数据、Docker、防火墙、代理监听和旧脚本均未被回退流程修改；不执行 `git reset`、`git clean` 或发行版删除。

## 审查与返工路径

完成三段验证后派专门 reviewer，范围覆盖本任务全部实际 changed files、machine-local 配置哈希/备份、三段证据和零范围外修改声明。每个 finding 保持稳定 ID，并回到原实施者；修复后由原 reviewer 复审。若第三轮仍未闭合，或需要改 Docker、防火墙、代理监听、仓库布局、模板、policy、测试或旧脚本，实现停止并交主协调器裁决，不能在本任务内静默扩张。只有独立 final/pass 覆盖最新内容与运行时证据后，任务才可完成。

## TEST-001 修复前网络与跨平台基线

`repro_before_fix`：Windows `127.0.0.1:15235/15236` 均为 TCP connected，分别经 SOCKS5h/HTTP 代理访问 `chatgpt.com` 得到 `curl exit 0 / HTTP 403`；同一时刻 Ubuntu-24.04 处于 NAT 路由 `default via 172.30.96.1`，同两 loopback 端口均 `Connection refused`，显式代理 HTTPS 为 `curl exit 7 / HTTP 000`。WSL DNS 解析成功，但代理环境未投影，当前环境和清除代理后的 HTTPS 均为 `curl exit 28 / HTTP 000`。诊断包装命令及 WSL 包装均 `exit 0`，因此不可达是被成功采集的修复前症状，不是包装命令失败；HTTP 403 只证明 Windows 代理传输到达，不代表认证成功。

现有 `tests/harness/wsl-boundary.integration.ps1` 使用 Ubuntu-24.04、显式 Windows Python 与 Windows `pwsh.exe` 运行通过：覆盖 Linux 原生 Git/Python/rg/Node/npm、中文与空格路径、WSL 到 Windows PowerShell 的平台/cwd/UTF-8/参数/真实非零退出码且不重试、只读 `validate-plan-docs`、隔离 Windows Command Failure Memory 主路线和 fixture 清理。它不覆盖 NAT/mirrored 模式、localhost 代理可达、`autoProxy` 投影、DNS/HTTPS、真实 Codex Agent 平台、Agent `HOME`/`CODEX_HOME` 或规则加载，不能替代后续网络与完整 Agent 验收；严格 inherited `.cmd` backend parity 本轮未检查。

套件结束后 `wsl_boundary_fixture_leftovers=0`。本批未修改 `.wslconfig`、系统配置、规则、测试、旧任务或完整 `state.json`。

## NET-001 machine-local 配置实施证据

- 写前把目标解析并严格核对为 `C:\Users\Laptop\.wslconfig`；基线为 `absent`。写入使用 `FileMode.CreateNew`，因此若文件在核对后突然出现则会失败而不会覆盖。
- 最终文件为 UTF-8 无 BOM、LF、末尾保留 LF，共 `64` bytes；逐字匹配冻结内容，SHA-256 为 `7e39e5e217df4d0edaa97664cf4c29644932e22e9cd67f6bc0fd60d33c6ec2a8`。
- INI 复读只解析出 `[wsl2]` 下三个键：`networkingMode=mirrored`、`dnsTunneling=true`、`autoProxy=true`；无额外键。
- 只读复核显示 `docker-desktop` 仍为 `Running` / WSL `2`；未执行 `wsl --shutdown`、`wsl --terminate`，未停止或启动 Docker。
- `C:\Users\Laptop\.codex\hooks.json` 的 SHA-256 仍为基线 `b4a4e0db9ce8ab4749779af4b8aa4e578ca2f2ff8c299921423a7f1fc69456de`。
- `rollback_preserved=true`：原文件不存在，回退只删除本任务新建且哈希仍匹配的精确目标；不恢复或改动其他文件。精确回退命令如下，当前未执行：

```powershell
$target = [System.IO.Path]::GetFullPath('C:\Users\Laptop\.wslconfig')
$expectedSha256 = '7e39e5e217df4d0edaa97664cf4c29644932e22e9cd67f6bc0fd60d33c6ec2a8'
if ($target -cne 'C:\Users\Laptop\.wslconfig') { throw "Unexpected rollback target: $target" }
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Rollback target is absent: $target" }
$actualSha256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -cne $expectedSha256) { throw "Rollback refused because SHA-256 drifted: $actualSha256" }
Remove-Item -LiteralPath $target
```

本批仓库写入仅为本节所在的 `execution.md`；系统目标仅为 `C:\Users\Laptop\.wslconfig`。未修改 Docker、防火墙、代理监听、端口转发、shell 启动文件、Codex 配置、`AGENTS.md`、hooks、测试、旧任务或完整 `state.json`。

## NETWORK-VERIFY-001 新 WSL 生命周期网络命中证据

- 子任务 brief SHA-256：`f25b0a40a15d3ccaec73940d62745af1b245872a4de21d2d7a2d7d98ef41ae96`。执行前 `Ubuntu-24.04` 与 `docker-desktop` 均为 `Stopped` / WSL `2`；随后 `wsl.exe --shutdown` 返回 `0`，因此本任务没有停止、启动或修改 Docker。
- 新启动的 `Ubuntu-24.04` 没有出现旧 `localhost proxy configuration ... not mirrored ... NAT mode` 警告；启动诊断包装返回 `0`。身份为 `Linux`、`uid=1000`、`HOME=/home/laptop`。
- `wslinfo --networking-mode` 返回 `mirrored` / exit `0`。接口为 `lo=127.0.0.1/8,10.255.255.254/32`、`eth1=192.168.31.221/24`，主路由为 `default via 192.168.31.1 dev eth1`；没有修复前 `default via 172.30.96.1` 的 NAT 路由，系统真源、接口与路由三者一致支持 mirrored 判断。
- `autoProxy` 在新实例投影 `HTTP_PROXY`、`HTTPS_PROXY`、`http_proxy`、`https_proxy`，脱敏值均为 `http://localhost:15236`；`ALL_PROXY` 与 `NO_PROXY` 未设置。
- WSL 内 `127.0.0.1:15235` 与 `127.0.0.1:15236` TCP 均为 `connected`。按实际代理类型，显式 SOCKS5h `15235` 与显式 HTTP `15236` 访问 `https://chatgpt.com` 均为 `curl exit 0 / HTTP 403 / TLS verify 0 / remote_ip 127.0.0.1`。
- `/etc/resolv.conf` 的 nameserver 为 `10.255.255.254`；Python `socket.getaddrinfo` 对 `chatgpt.com` 与 `example.com` 均解析成功，`dns_python_exit=0`，共同证明 DNS tunneling 入口可用。
- 使用新实例当前代理环境访问 `https://chatgpt.com` 为 `curl exit 0 / HTTP 403 / TLS verify 0 / remote_ip 127.0.0.1`。`403` 仅作为 HTTPS transport 到达证据，不代表认证成功，也不作为真实 Codex 会话或完整 Agent 验收。
- 验证后 `.wslconfig` 仍为精确三键、`64` bytes、SHA-256 `7e39e5e217df4d0edaa97664cf4c29644932e22e9cd67f6bc0fd60d33c6ec2a8`。主验证结束后的只读快照显示两发行版均为 `Stopped` / WSL `2`；完成闸门复验再次启动目标发行版后，立即快照为 `Ubuntu-24.04=Running`、`docker-desktop=Stopped`。未修改 Docker、防火墙、代理监听、端口转发、Codex 设置或其他系统配置。
- 诊断偏差：初版 Bash heredoc 被 PowerShell 外层解析拒绝，且首轮 DNS 状态字段与 curl `%{proxy_used}` 格式不兼容；均先走 Command Failure Memory 的 `record-failure -> query-before-retry`，再分别以 Base64 脚本载荷、Python DNS 与受支持的 curl 字段补证。修复后成功回写被现有 Command Failure Memory `case capacity limit reached: 1024` 阻塞；未删除、清理或改写经验库。

`review_evidence`：

- `repro_before_fix`：`TEST-001` 已记录 NAT 路由、WSL loopback 两端口 `Connection refused`，以及显式代理 `curl exit 7 / HTTP 000`。
- `pass_after_fix`：完整 shutdown 后的新 `Ubuntu-24.04` 中，mirrored、代理投影、DNS、两端口 TCP 与三条 HTTPS 传输检查全部取得 exit `0` 证据。
- `hit_proof_observed`：`wslinfo=mirrored`，接口/路由从修复前 NAT `172.30.96.1` 切为宿主 LAN `192.168.31.221/24` / `192.168.31.1`，且原先拒绝的 `127.0.0.1:15235/15236` 均连接并完成对应代理传输。
- `relevant_regression_ok`：新实例无旧 NAT 代理未镜像警告；`.wslconfig` 哈希未漂移；`docker-desktop` 验证前后均未运行，且任务未启动或修改 Docker。

## HISTORY-001 共享 CODEX_HOME 与任务历史连续性适配

- 触发症状：把 Agent environment 切为 WSL 并重启后，同一对话窗口只显示本周一及更早内容；恢复 Windows Agent 并重启后，今天的完整记录重新显示。任务 ID 保持 `01a05597-4368-7c60-8155-4c88a8e4f2d7`，服务端与 Windows 本地会话文件均未丢失。
- Windows 真源 `C:\Users\Laptop\.codex\sessions` 有 `151` 个会话文件；本任务文件名匹配 `2` 个。主文件位于 `sessions/2026/08/31`，在本轮对话期间继续更新。Windows `config.toml` SHA-256 为 `0dd6105c70dc29ebda4d973086dfe3a564a5f7609bb3ad53dd0e29637d9da595`。
- Ubuntu 原生默认目录 `/home/laptop/.codex` 存在，但 `sessions=0`、`archived_sessions=0`，且 `config.toml` 不存在；普通新 WSL 进程中 `HOME=/home/laptop`、`CODEX_HOME` 为空。这解释了 WSL Agent 未显式投影时读取另一套空本地状态的风险。
- Windows 真源经 `/mnt/c/Users/Laptop/.codex` 在 Ubuntu 中可见：`sessions=151`、本任务文件名匹配 `2` 个，配置哈希与 Windows 一致。未读取或输出认证文件内容。
- 非持久临时验证把当前 PowerShell 进程的 `CODEX_HOME` 设为 `C:\Users\Laptop\.codex`，并用 `WSLENV=CODEX_HOME/p` 启动单个 WSL 进程；WSL 自动得到 `CODEX_HOME=/mnt/c/Users/Laptop/.codex`，会话数、任务匹配数和配置哈希全部命中。临时进程结束后恢复调用进程原环境。
- 持久化前，Windows 用户级 `CODEX_HOME` 与 `WSLENV` 均不存在。最终仅写入：`CODEX_HOME=C:\Users\Laptop\.codex`、`WSLENV=CODEX_HOME/p`。写后新 WSL 进程再次得到 `/mnt/c/Users/Laptop/.codex`，并复验 `sessions=151`、本任务匹配 `2`、配置哈希一致。
- 一次受限沙箱 PowerShell 复读 HKCU 时两值显示为空，不能作为真实用户注册表证据；该差异先进入 Command Failure Memory 的 `record-failure -> query-before-retry`。随后在真实用户 `desktop-515kle7\laptop` 上分别通过 `Get-ItemProperty HKCU:\Environment`、`reg.exe query HKCU\Environment` 与 `[Environment]::GetEnvironmentVariable(..., 'User')` 三种入口复核，均返回 `C:\Users\Laptop\.codex` 与 `CODEX_HOME/p`，两个 `reg.exe` 查询退出码均为 `0`。
- Ubuntu 的 `codex` 当前解析为 Windows npm 启动器 `/mnt/c/Users/Laptop/AppData/Roaming/npm/codex`；`codex --version` 因缺少 `@openai/codex-linux-x64` 返回 `1`。Linux Node/npm 为 `/usr/local/bin/node`、`/usr/local/bin/npm`，全局前缀 `/opt/node-v24.19.0-linux-x64` 由 `root` 管理且普通用户不可写。本批没有使用 `sudo`、没有安装包、没有改 `PATH`；是否需要用户级 Linux CLI 由真实 WSL Agent 运行时证据决定。
- `history_continuity_restored`：共享 `CODEX_HOME` 的环境层已命中同一任务库；完整应用在 WSL Agent 重启后是否连续渲染今天历史，保留给 `RUNTIME-001` 作为必须通过的用户可见验收，不能用本节的文件计数替代。
- 本批没有复制、移动、改写或清理 `sessions`、`archived_sessions`、`memories`、认证数据、项目仓库或 `/home/laptop/.codex`；没有创建第二份 CodexHome。

守卫式回滚只在当前用户环境仍精确匹配本批写入值时执行，当前未回滚：

```powershell
$expectedHome = 'C:\Users\Laptop\.codex'
$expectedWslenv = 'CODEX_HOME/p'
$currentHome = [Environment]::GetEnvironmentVariable('CODEX_HOME', 'User')
$currentWslenv = [Environment]::GetEnvironmentVariable('WSLENV', 'User')
if ($currentHome -cne $expectedHome) { throw "CODEX_HOME drifted; refusing rollback: $currentHome" }
if ($currentWslenv -cne $expectedWslenv) { throw "WSLENV drifted; refusing rollback: $currentWslenv" }
[Environment]::SetEnvironmentVariable('CODEX_HOME', $null, 'User')
[Environment]::SetEnvironmentVariable('WSLENV', $null, 'User')
```

## RUNTIME-001 既有任务切换 WSL 的历史连续性诊断与修复

### 两次用户可见复验

- 用户两次把 Agent environment 切到 WSL 并重启；同一任务窗口均只显示本周一及更早记录。切回 Windows 后今天记录重新出现，因此正文未删除，失败位于 WSL 运行时的任务索引与分页历史层。
- 第二次复验发生在共享 `CODEX_HOME` 已通过 `WSLENV=CODEX_HOME/p` 投影之后，证明“WSL 能看到同一 `sessions` 目录”不足以保证既有 Windows 任务的 UI 历史连续性。本轮不再要求用户对当前窗口重复切换。

### 桌面端日志与实际运行时真源

- WSL 启动日志确认 `spawnCommand=wsl.exe`、Linux app-server `0.151.0-alpha.7.2` 初始化成功，认证、配置与网络请求均可用；这排除了“仍在 Windows 运行”和网络未修复。
- 同一日志记录 `Local app-server project migration failed: AbsolutePathBuf deserialized without a base path`，并持续出现混合路径 `/mnt/c/Program Files/WindowsApps/.../app/resources/C:\\Users\\Laptop\\Documents\\Codex\\...` 的 `ENOENT`。
- 桌面包内置逻辑为 WSL app-server 设置 `CODEX_SQLITE_HOME="$HOME/.codex/sqlite"`。实际 Doctor 复现也确认：共享 `CODEX_HOME=/mnt/c/Users/Laptop/.codex`，而 WSL 原生 SQLite home 为 `/home/laptop/.codex/sqlite`。因此项目、配置和 rollout 正文保持单副本，Windows 与 WSL 的运行时 SQLite 索引按平台分开。
- 未带实际 `CODEX_SQLITE_HOME` 的手工 Doctor 会在 `/mnt/c` 上访问 Windows SQLite，并对六个数据库得到 `disk I/O error (4618)`；Windows Doctor 同时报告这些数据库健康。该结果用于证明不能把 WSL SQLite 直接指向 Windows 挂载目录，不作为数据库损坏结论。
- 带桌面端实际 `CODEX_SQLITE_HOME=/home/laptop/.codex/sqlite` 的 WSL Doctor 为 `state databases healthy`、WebSocket `101`、Provider reachability 通过，但线程 parity 为 `153 active files / 133 active rows`，缺 `20` 个 active rows，并发现 `4` 个 duplicate rollout thread IDs。

### 当前任务的精确错误指针

- 当前任务 ID `01a05597-4368-7c60-8155-4c88a8e4f2d7` 在共享 `sessions` 下存在两个同 ID rollout：
  - 主文件：`rollout-2026-08-31T10-12-51-...jsonl`，修复时约 `23 MB`，今天持续更新；
  - 旧快照：`rollout-2026-08-31T17-45-52-..._01a05736-....jsonl`，`97,795` bytes，昨晚停止更新。
- Windows `state_5.sqlite` 的当前任务行指向主文件；WSL 原生 `state_5.sqlite` 指向旧快照，并保存上述混合错误 cwd。
- 修复前的临时只读 WSL app-server 探针得到：
  - `rollout_path` 为旧快照；
  - `cwd` 为混合错误路径；
  - 最近三回合均为昨晚的 `01a057...`，最新状态为 interrupted。
- 两个 rollout 的文本级比较显示旧快照有一条主文件中没有完全相同文本的历史用户消息，因此没有移动、删除、合并或重写任一 `sessions/*.jsonl`。

### 守卫式状态指针修复

- 仅在 WSL 没有运行中 Codex 进程、两个 rollout 的首行 `session_meta.id` 均精确匹配当前任务、主文件更大且更新时间更新、WSL state DB `integrity_check=ok` 时执行。
- 使用 SQLite backup API 备份 WSL 原生 `state_5.sqlite` 到 `/home/laptop/.codex/backups/wsl-index-repair-20260901T054912Z/state_5.sqlite`，备份 SHA-256 为 `a4b91fb84474b3af457224f6e59be189e8e959d79cd7f8bd8482b3978582d90b`。
- 单事务、守卫条件只更新当前任务一行的两个字段：
  - `rollout_path` -> 仍在更新的主 rollout；
  - `cwd` -> `/mnt/c/Users/Laptop/Documents/Codex/2026-08-31/wsl-powershell-wsl-she`。
- 修改前后 `integrity_check=ok`；没有修改 Windows SQLite、`sessions/*.jsonl`、`memories_1.sqlite`、`auth.json` 或 `hooks.json`。
- 同一探针随后命中主 rollout 与正确 Linux cwd，但最近分页回合仍旧，证明路径层修复成功且还需同步分页历史，不能提前宣布 UI 连续性恢复。

### 当前任务分页历史的最小同步

- Windows 与 WSL 的 `thread_history_1.sqlite` 均为 `integrity_check=ok`，都有迁移版本 `1..6`，四张目标表的列名和顺序完全一致；跨平台 migration checksum 不同，因此同步未改写 `_sqlx_migrations`。
- 第一次同步在发现 checksum 不同后，于历史表写入前受保护中止；当时只刷新了当前任务的状态时间字段，目标数据库备份已经生成。该失败已进入 Command Failure Memory。
- 重试前增加版本、描述、成功状态和逐表列顺序检查，并保留 checksum 差异证据。源是 Windows SQLite backup API 生成的一致性快照，不直接复制活动 WAL 文件。
- 写入前再次分别备份 WSL 原生 `state_5.sqlite` 与 `thread_history_1.sqlite`：
  - `/home/laptop/.codex/backups/wsl-thread-sync-20260901T055451Z/state_5.sqlite`，SHA-256 `fd5e76b737d7b553261417b99c67b37f7caf07faf33c4f57dad303224fa5ca3d`；
  - `/home/laptop/.codex/backups/wsl-thread-sync-20260901T055451Z/thread_history_1.sqlite`，SHA-256 `5b7232f38de4e37baa7c404429b633201fe512583fece53acaac5e2d90ee8d9f`。
- 仅替换当前任务在 `thread_history_projection_state`、`thread_items`、`thread_realtime_items`、`thread_turns` 四表的记录，并同步必要时间字段；不触碰其他任务或 Memory：
  - `thread_items: 695 -> 1779`；
  - `thread_turns: 10 -> 23`；
  - projection state 保持 `1`，realtime items 保持 `0`；
  - 写后计数与源快照精确一致，两库 `integrity_check=ok`。
- 修复后同一只读 WSL app-server 探针命中：
  - 主 rollout；
  - 正确 `/mnt/c/.../wsl-powershell-wsl-she` cwd；
  - 今天的最近回合 `01a05b6f...`、`01a05b5f...`、`01a05b5d...`，不再停在昨晚 `01a057...`。

### 尚未关闭的用户可见闸门

- 上述探针证明 Linux app-server、主 rollout、Linux cwd 和今天分页历史均已命中，但完整桌面 UI 必须在最后时点再次从 Windows 生成一致性快照并同步当前任务，然后由用户切换 WSL、重启并确认本窗口显示今天记录。
- 最后时点同步仍只允许当前任务记录；随后才采集完整 Agent 的 `uname`、UID、`HOME`、`CODEX_HOME`、cwd、规则加载、真实联网和 Windows 旧脚本互操作证据。
- 用户可见复验未通过前，`RUNTIME-001`、`DOC-FINAL-001` 与 `REVIEW-001` 保持未完成。

### 第三次复验、预终审 finding 与同步工具返工

- 第三次切换 WSL 并重启后用户仍只看到本周一记录；切回 Windows 后界面一度仍停在周一。此时 Windows `state_5.sqlite` 仍指向主 rollout，`integrity_check=ok`，应用内部 `list_threads` 的更新时间继续前进，`read_thread` 能返回今天的最新回合。桌面日志同时出现连续 `ResizeObserver loop completed with undelivered notifications`。因此正文和 Windows 后端分页数据仍在，当前现象还包含桌面渲染/缓存层未按后端结果刷新；通过应用内重新导航触发可逆重载，但最终仍需用户可见确认。
- 专门 reviewer 给出 pre-final fail：旧同步脚本先提交 state、之后才检查/写 history，两个 WAL 数据库之间没有跨库原子性；失败备份目录缺 manifest；checksum 不同仅比较列名过弱；回退说明没有可执行验证合同；临时产物没有条件式清理方案。
- 返工后的任务级同步脚本先完成以下全部 guard：源快照哈希、无运行中 WSL Codex、state `threads` 与四张 history 表的 `table_xinfo`、外键、索引/索引列/唯一性、trigger、规范化建表 SQL；migration 的版本/描述/成功状态一致，且 0.151.0-alpha.7.2 的 Windows/Linux checksum 组合逐版本精确命中 allowlist。脚本不改 `_sqlx_migrations`。
- 两个目标库均先通过 SQLite backup API 生成一致性备份并核对 SHA-256/`integrity_check`，随后在任何写入前落盘 `status=prepared` manifest。提交顺序为 history 后 state，并明确 `cross_database_atomic=false`；任一步或后验验证失败，只按当前任务从备份执行补偿事务并记录 `rolled_back` 或 `rollback_failed`。WAL 数据库禁止用普通文件复制覆盖。
- `/tmp` 副本先从当前任务 `thread_items` 确定性删除一条 sentinel，明确得到目标 `1778` 条、源 `1779` 条且 SHA-256 摘要不同；随后故障注入在 history 提交源数据后抛出精确错误 `injected failure after history commit`。结果 manifest 为 `rolled_back`、`compensation.history.verified=true`，补偿后当前任务 state 投影、四表行摘要严格恢复到 sentinel 前目标状态，两库 `integrity_check=ok`。随后同一副本成功路径为 `completed`，四表摘要与源快照一致。测试临时根删除失败会使测试失败，实际测试 exit `0`，没有写真实 WSL 索引。
- 测试专用 `--skip-process-check` / `--fault-after-history-commit` 若与默认 `/home/laptop/.codex/sqlite` 或默认备份根组合会被拒绝，并要求目标和备份根都解析在 `/tmp` 下。写前还检查目标 rollout 为存在的绝对文件、首行 `session_meta.id` 精确匹配当前任务、cwd 为存在的绝对 Linux 目录，并以 `samefile` 核对 Windows source state 快照确实指向选定主 rollout 和对应 cwd。
- 返工后真实同步执行前，旧失败目录 `/home/laptop/.codex/backups/wsl-thread-sync-20260901T055253Z` 已在不覆盖任何备份的条件下补写 `manifest.json`，状态为 `legacy_aborted_partial_state_commit`；两份备份 SHA-256 分别为 `2a4e57...9479`、`5b7232...8d9f` 且 `integrity_check=ok`。该目录与正式备份保留到用户 UI 验收和最终复审，不能静默删除。工作目录中的 schema 展开文件、Windows 快照和一次性脚本也保留到最终复审，之后只按精确清单清理一次性产物；有效 WSL 回退备份在用户 UI 通过和最终审查前不删除。

### 返工后真实 WSL 索引同步与协议探针

- 第二轮独立复审对同步工具与上述文档给出 `pre-final pass`，没有新增 actionable finding；该结论不替代真实库、UI、完整 Agent 和旧脚本互操作验收。
- 通过 Windows SQLite backup API 生成新快照 `work/snapshots/20260901T063119Z`：state SHA-256 `4c9e3619763373d94c5712a49a759c99fa28c967d31c7880198644fc317f07db`，history SHA-256 `2a06762b50a536e8094efb953668f261aeabb9dd55a0f9e0ed9443623aa943b2`；源当前任务计数为 projection `1`、items `1971`、realtime `0`、turns `27`。
- 返工脚本真实执行成功，manifest 为 `/home/laptop/.codex/backups/wsl-thread-sync-20260901T063133042529Z/manifest.json` 且 `status=completed`、`cross_database_atomic=false`。写前 WSL 备份：state SHA-256 `5e46061e939a213c582ece91d67999f58ba82a5bb28f6a204d90976896d31f69`，history SHA-256 `d94fc574ef0a4cb04bbd29a3a390482bae0b4768ec475634fb8e33fb43b84bbe`，两者 `integrity_check=ok`。
- 当前任务 WSL history 从 items `1779` / turns `23` 同步到 items `1971` / turns `27`；projection 保持 `1`、realtime 保持 `0`。写后四表摘要与 Windows 快照源完全一致，state 指向主 rollout、正确 `/mnt/c/.../wsl-powershell-wsl-she` cwd 和源时间字段，两库 `integrity_check=ok`。
- 真实 WSL app-server 只读协议探针返回当前任务 ID、主 rollout、正确 Linux cwd、`next_cursor_present=true`，最近三回合为今天的 `01a05ba7-868f...`、`01a05ba7-069f...`、`01a05ba5-ae4f...`。因此最后一次用户操作前的 WSL 后端连续性已经命中；完整桌面界面仍必须由用户切换并重启后确认。

### 完整 WSL Agent 用户验收与旧脚本环境适配

- 用户把 Agent environment 切为 WSL 并重启后明确确认“已切换，今天记录可见”。当前任务的用户可见历史连续性闸门通过；没有复制、移动、合并或重写任何 rollout JSONL，也没有迁移 Memory、认证或 Hook 数据。
- 当前 Agent 真源为 `Linux-6.18.33.2-microsoft-standard-WSL2-x86_64`、`Ubuntu-24.04`、`uid=1000`、`HOME=/home/laptop`、`CODEX_HOME=/mnt/c/Users/Laptop/.codex`、`CODEX_SQLITE_HOME=/home/laptop/.codex/sqlite`，cwd 为 `/mnt/c/Users/Laptop/Documents/Codex/2026-08-31/wsl-powershell-wsl-she`。Python、Git、Node 与 rg 均解析为 Linux 工具；harness 的 Git 根为原仓库 `/mnt/d/prj/harnesss/dev_vibecoding`，没有新增 clone/worktree 或第二份项目。
- 全局 `AGENTS.md`、项目 `AGENTS.md`、`rules/registry/RULES_ENTRY.md`、`RULES_INDEX.json` 及 always-on 条目均由原 Windows 真源的 `/mnt/c`、`/mnt/d` 挂载路径读取；没有复制规则仓库。真实会话本身完成认证联网回合；Linux Doctor 另得 `config loaded`、`auth configured`、WebSocket `101 Switching Protocols`、Provider reachability 通过，state databases healthy。
- WSL 直接调用 Windows PowerShell 7、中文/空格路径、UTF-8、参数、cwd、预期 exit `23` 且只调用一次，以及 Windows Python Command Failure Memory 隔离 `record/query/success/inspect` 均通过。旧 `.cmd` 的额外检查最初无 stdout；根因不是脚本改动或权限，而是当前 WSL 命令环境无 `PATHEXT`，WSL 启动的 Windows 进程仅得到 `.CPL`，所以 launcher 内的 extensionless `where python` 无法解析。
- Windows user `PATHEXT` 保持 absent，machine `PATHEXT` 保持标准 `.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC`；未修改注册表。当前 Codex 已注入 `WSLENV` 的 `PATHEXT/l`。只对一次 WSL 命令临时设置同一标准分号值后，原 `.cmd` 未改一行即得到 Windows `PATHEXT` 标准列表加 `.CPL`、解析到既有 Windows Python、输出合法 JSON 且 child exit `0`，构成修复点命中证明。
- 依据 Codex 官方 `shell_environment_policy.set` 配置能力，在共享 `C:\Users\Laptop\.codex\config.toml` 增加且仅增加 `PATHEXT` 显式值；写前备份位于 `work/backups/wsl-shell-env-20260901T065240Z/config.toml`，原 SHA-256 `83f9c4e443808dfe5f7a7b749300a85dbe8d3a0fd4245834c71aa434bc0716be`，manifest SHA-256 `5241ec68b1ed3467c88e6f05043298ab5e7fbc38690482ddd4d62af1e7a08b74`。写后配置 SHA-256 为 `39baec50e948a6c4a471a232650775f9021ab7828651cf9f21ac6ed80b790146`。
- Python `tomllib` 精确读回配置值；Linux Codex `--strict-config doctor --summary --no-color` exit `0`，说明配置被当前版本接受。shell environment policy 在 Agent 启动时装载，因此当前既有 Agent 子进程仍显示旧的 `PATHEXT` unset；必须最后重启一次 Codex 应用，再以真实新 Agent 复验变量和原 `.cmd`，此项通过后才能进入独立 final review。

该配置的守卫式回退只在当前配置 SHA-256 仍为 `39baec50e948a6c4a471a232650775f9021ab7828651cf9f21ac6ed80b790146`、备份 SHA-256 仍为 `83f9c4e443808dfe5f7a7b749300a85dbe8d3a0fd4245834c71aa434bc0716be` 时执行；用备份字节恢复后必须核对恢复 SHA-256。不得用回退覆盖后续用户对 `config.toml` 的其他编辑。

## RUNTIME-001 重启后最终验收

- 用户完成最后一次 Codex 应用重启、保持 Agent environment 为 WSL，并明确确认“已重启，今天记录可见”。用户界面历史连续性再次通过。
- 新 Agent 的 `PATHEXT` 精确为 `.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC`；`WSLENV` 中恰有一个 `PATHEXT/l`。`HOME=/home/laptop`、`CODEX_HOME=/mnt/c/Users/Laptop/.codex`、`CODEX_SQLITE_HOME=/home/laptop/.codex/sqlite`，没有创建第二个 CodexHome 或迁移主记忆。
- 在任务 cwd 不设置临时 `PATHEXT` 前缀运行 `python3 work/verify_final_wsl_agent.py`，exit `0`、`ok=true`。Linux 原生 Git、Python、rg、Node、npm、原 `/mnt/d/prj/harnesss/dev_vibecoding` 仓库、HTTPS 传输、Windows Python 和原 `.cmd inspect` 全部命中；`.cmd` 子进程 exit `0`，隔离临时库已清理。
- `TERM=xterm-256color codex --strict-config doctor --summary --no-color` exit `0`，汇总为 `18 ok · 1 idle · 2 notes · 1 warn · 0 fail degraded`。config、auth、state databases、WebSocket `HTTP 101` 和 provider reachability 通过；保留的 warning 是缺失 rollout 库存项和重复 thread inventory，不将其误写为全绿。
- 重启后 `config.toml` SHA-256 为 `d08cd5958fc8431a39cdb5ded08017c0d9218a1a1d06c2ba9c679f6ae5e382ca`。与重启前快照相比，目标 `shell_environment_policy.set.PATHEXT` 保持不变，另有 computer-use 启动时生成的 `SKY_CUA_NATIVE_PIPE_DIRECTORY` UUID 变化。因此整体配置哈希只作时点证据；回退必须新鲜读取并定点删除本任务新增的 `PATHEXT` 键，保留当时的命名管道与其他配置，不能用旧整文件覆盖。
- RUNTIME-001 首轮 verifier 错把两份任务文档按整文件重写。主协调器从主 rollout 与各执行 rollout 中按真实成功写操作重放，恢复写前精确字节：`execution.md` 为 `35561` bytes / SHA-256 `f616fca9605bfc2c367167a34d0b6c17c0e3689007ba74569a800ea99b85657b`，`acceptance.md` 为 `5165` bytes / SHA-256 `2406425f6d7412cf48ae7708a9a023cbfb09e1a19bda3fe03c4a48dd408c4972`；随后只追加本节和更新验收状态。系统配置、旧脚本、规则和仓库源码未受该文档返工影响。

## DOC-FINAL-001 长期文档与任务状态核对

- 本轮写前基线为：`docs/CODEX_COMPAT.md` `22843` bytes / SHA-256 `25cd78ee40aeca1dcc5f3f14a4908f1eaeea7d2927163d99dbacee2fb9a3ff87`；本文件 `37776` bytes / SHA-256 `30603de875f0a68cc8eff33a298ea76f6b3bd84d8c6fbdc7864609b22ee0494e`；`acceptance.md` `5139` bytes / SHA-256 `01d762d68269201db6d4653425ace8ffa3073abe1072a9c6e3f317ced9678a15`。
- 当前新 Agent 环境再次读得标准 `PATHEXT`，`WSLENV` 中 `PATHEXT/l` 恰出现一次；只读计算的共享 `config.toml` SHA-256 仍为 `d08cd5958fc8431a39cdb5ded08017c0d9218a1a1d06c2ba9c679f6ae5e382ca`。该整体哈希仅是时点快照；computer-use 命名管道会随重启变化，安全回退必须新鲜读取并只定点处理本任务的 `shell_environment_policy.set.PATHEXT` 键，保留并发配置。
- `docs/CODEX_COMPAT.md` 已把 planning 阶段口径保留为历史，并补入重启后今天记录可见、持久 `PATHEXT`、单个 `PATHEXT/l`、无前缀最终脚本 exit `0` / `ok=true`、Doctor `18 ok` / `0 fail` / `1` 个 thread inventory warning、Windows 旧入口、单仓库、无 Memory/认证/Hook 迁移及动态配置回退边界。旧任务历史、模板、rules、Hook 与运行时代码均未修改。
- 使用 Codex bundled Windows PowerShell 7 运行 `scripts/validate-plan-docs.ps1`，结果为 `Validation passed for 21 documents`；运行 `scripts/validate-doc-routing.ps1`，结果为 `Validation passed for 0 modules and 7 task directories`。指定 `docs/CODEX_COMPAT.md`、本文件和 `acceptance.md` 的 `git diff --check` exit `0`。由于两份任务文档当前未跟踪，补充 no-index 检查另发现本文件受保护前缀第 148–165 行已有 CRLF/尾空白提示；该区域属于必须逐字节保留的前 35561 bytes，本轮未改。`acceptance.md` 与本轮新增尾部未出现同类提示。
- `review_evidence.docs_and_rules_synced`：长期兼容说明与本任务最终运行时证据、旧入口、单仓库、无 Hook/Memory 迁移及动态回退边界已经同步，文档结构与路由校验通过；`independent_final_review` 仍由后续独立 reviewer 覆盖，本节不宣布独立终审完成。

## CLEANUP-001 一次性产物清理

- 同一 reviewer 在清理前给出 `PRE-CLEANUP PASS`，确认 `work/snapshots`、`app_server_schema`、`__pycache__` 和 15 个任务脚本/探针都不是运行时入口或唯一回退载体；两次正式同步的源 manifest 哈希已在删除前与保留的 WSL manifest 交叉核对。
- 使用精确路径删除 15 个根文件：`app_server_probe.py`、`diagnose_cfm_cmd_stdout.ps1`、`inspect_sqlite.py`、`inspect_thread_history.py`、`inspect_windows_state.py`、`probe_pathext_boundaries.ps1`、`probe_pathext_boundaries.py`、`probe_pathext_child.ps1`、`record_aborted_backup_manifest.py`、`repair_wsl_thread_index.py`、`run_wsl_boundary_with_process_env.ps1`、`snapshot_windows_thread_state.py`、`sync_current_thread_to_wsl.py`、`test_sync_current_thread_to_wsl.py`、`verify_final_wsl_agent.py`；并精确删除 `work/__pycache__`、`work/app_server_schema`、`work/snapshots` 三个目录。未使用 glob，也未触碰 `work/backups`。
- 清理后 `work` 从约 `823 MB` 降为 `8.0K`，完整递归清单只剩 `backups/wsl-shell-env-20260901T065240Z/config.toml` 与 `manifest.json`。两者 SHA-256 分别保持 `83f9c4e443808dfe5f7a7b749300a85dbe8d3a0fd4245834c71aa434bc0716be`、`5241ec68b1ed3467c88e6f05043298ab5e7fbc38690482ddd4d62af1e7a08b74`。
- `/home/laptop/.codex/backups` 中 `wsl-index-repair-20260901T054912Z`、`wsl-thread-sync-20260901T055253Z`、`wsl-thread-sync-20260901T055451Z`、`wsl-thread-sync-20260901T063133042529Z`、`wsl-thread-sync-20260901T063309761852Z` 五个回退目录全部保留。当前 `config.toml`、`.wslconfig`、Windows/WSL 数据库、sessions/rollout JSONL、Memory、认证、Hook、仓库、规则真源及旧脚本均不在删除清单。
- 保留的 shell 配置备份只用于基线取证，不能整文件覆盖当前动态 `config.toml`；实际回退仍须新鲜读取并定点处理本任务增加的 `shell_environment_policy.set.PATHEXT`。

## REVIEW-001 清理后第一阶段终审

- 同一独立 reviewer 对清理后的系统状态、五套 WSL SQLite 回退目录、两份 shell 配置回退文件、四份 GTO 变更文件、真实 WSL Agent 证据和零范围外删除声明执行只读复核，结论为 `PRE-FINAL PASS`，无 actionable finding；本轮未修改文件、配置或数据库。
- reviewer 独立复算的 scoped change SHA-256 为 `f6c53a9ed4574d416ab5b6f2cb974c7bff1e5875ccda3126d12895ae782b76e4`，与主协调器结果一致。对应文件哈希为：`docs/CODEX_COMPAT.md` `ef3cbad6fd00cb14f3c51be08f08da3c24d75563932c2c0ddf86c1aa58207c1e`、`plan.md` `ff9098cadcea8559dca77bd834ff93e7449196d95bfcd38e5297235c5bbfdcb3`、本文件 `778f0825fbc46f1a72c678b26a6f34aed6fdb0f7619777dabb1f5cc09d4dd0a4`、`acceptance.md` `445e64d3002bf8e50f9b64790f36beb354e0719efb7a5d52a09540020e407487`。
- reviewer 以 SQLite 只读 immutable 模式核对全部实际备份，`integrity_check=ok`；四个 thread-sync manifest 记录的数据库哈希与文件一致。`work` 保持 `8.0K` 且只剩两份 shell 配置回退文件；15 个根脚本和三个一次性目录已精确清理，没有触碰系统配置、活动数据库、sessions、Memory、认证、Hook、仓库、规则真源或旧脚本。
- reviewer 重跑文档结构、路由和 GTO 校验均通过。其受限审查上下文另得 Doctor `17 ok · 0 fail · 2 warn`；第二个 warning 仅为该 reviewer 沙箱的 filesystem restricted 提示，不反驳完整 Agent 时点验收的 `18 ok · 0 fail · 1` 个 thread inventory warning，也不构成本任务 finding。
- 本节和验收文档只记录已发生的 `PRE-FINAL PASS` 及终审边界，不在正式结果写入前冒充 `final/pass`。同一 reviewer 对这次定点状态文案复审后，正式 verdict 与最终 scoped change SHA-256 只写入 GTO state。
