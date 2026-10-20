# 任务摘要

## 基本信息

- `task_id`: `20260901-113722-full-wsl-agent-network-adaptation-bdfa4e`
- `title`: 完整 WSL 智能体网络与本地适配
- `status`: `completed`
- `owner`: `main-coordinator`

## 目标

- 修复完整 WSL 智能体在 Windows 本地代理环境下的联网问题，使 Codex 智能体真实运行于 Ubuntu-24.04；保留原项目单副本和 Windows 旧脚本入口，并完成规则、文档、验证与独立审查

## 范围

### Scope In

- 创建最小用户级 .wslconfig 网络配置并验证 mirrored、dnsTunneling、autoProxy
- 通过 Codex 设置页切换完整 WSL 智能体并在重启后验收真实 Linux 环境
- 适配 harness 全局规则真源、兼容和安装文档、运行时 AGENTS 与必要测试
- 保留 Windows 智能体显式 wsl.exe 混合模式作为回退
- 验证原 Windows 项目单副本、Linux 原生工具和旧 .ps1/.cmd Windows 互操作

### Scope Out

- 不搬迁或复制仓库
- 不重写旧 .ps1/.cmd
- 不迁移、复制、扩容或清理 Command Failure Memory
- 不复制整个 .codex 或迁移认证会话
- 不修改 Docker Desktop 配置或主动停止 Docker
- 不处理 Hook 信任或把 Hook 作为平台路由
- 不扫描其他 clone、worktree 或未知项目
- 不开放代理 LAN 监听、不改防火墙入站规则、不增加端口转发

## 验收标准

- 重启后的 Codex 默认命令真实运行在 Linux，普通用户 uid=1000
- 真实 Codex 会话联网成功，WSL 内 Windows localhost 代理、DNS 和 HTTPS 路径有命中证据
- 原项目仍为同一份 Windows 文件，WSL 通过 /mnt/c 或 /mnt/d 访问且 Windows/WSL Git 状态无平台幽灵差异
- Git、Python、Node、npm、rg 使用 Linux 原生路径，日常命令不嵌套 wsl.exe
- 旧 .ps1 由 Windows pwsh.exe 7 执行，旧 .cmd 由 cmd.exe /C 执行，参数、cwd、中文和退出码正确
- 实际 CODEX_HOME、全局 AGENTS 加载位置和模板/回执哈希已核对
- 文档、规则、生成物、运行时部署和相关回归通过
- 独立 reviewer 对全部最终变更及运行时证据给出 final/pass

## 停止条件

- mirrored 网络导致 Docker 或其他 WSL 发行版异常且不能用最小回滚恢复
- 需要开放 0.0.0.0、修改防火墙、端口转发或代理软件全局监听才可继续
- 实际 CodexHome 需要复制整份 .codex 或迁移认证/记忆
- 出现超出 allowlist 的未知未提交修改冲突
- 三轮修复后相同网络或运行时阻塞仍未闭合

## 关键决定

- 采用完整 WSL 智能体加原 Windows 项目单副本；不迁移到 Linux 文件系统
- 先修复并验收普通 Ubuntu 网络，再切换 Codex 智能体
- 环境感知规则同时保留 Windows 混合回退和 WSL 原生主路径
- 旧任务 20260831-144630-wsl-first-legacy-preserved-16fc6f 作为历史基线，不改写其完成结论
- 系统配置变更仅限用户确认的 .wslconfig 三项；应用开关通过设置页操作

## 当前阶段

- `current_phase`: `review`

## 子任务

### READ-001

- `title`: 只读核对完整 WSL 智能体适配范围与现有真源
- `role`: `reader`
- `status`: `completed`
- `goal`: 只读确认现有混合模式真源、完整WSL所需最小适配文件、无需修改文件及已知工作区重叠风险

### DOC-001

- `title`: 同步完整WSL任务方案与长期兼容合同
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 先于系统实现落盘完整WSL目标、三段验证、最小配置、回滚及长期兼容合同；旧混合任务保持历史
- `dependencies`: `READ-001`

### TEST-001

- `title`: 冻结并执行修复前网络与跨平台基线
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 取得修复前NAT localhost代理不可达的直接证据，并复核现有边界测试覆盖与缺口；只把短证据写入本任务施工记录
- `dependencies`: `DOC-001`

### NET-001

- `title`: 实施最小WSL mirrored与autoProxy网络配置
- `role`: `implementer`
- `status`: `completed`
- `goal`: 备份前态并在用户级.wslconfig实施networkingMode=mirrored、dnsTunneling=true、autoProxy=true；只把短证据写入本任务施工记录
- `dependencies`: `TEST-001`

### NETWORK-VERIFY-001

- `title`: 新WSL实例网络命中验证
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: WSL完整重启后证明mirrored与autoProxy命中，普通Ubuntu网络通过；失败则阻止切换Codex Agent；只把短证据写入施工记录
- `dependencies`: `NET-001`

### RUNTIME-001

- `title`: 真实Codex WSL智能体与旧入口验收
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 用户切换Agent environment并重启后，验证真实Codex回合在Linux普通用户运行、项目单副本、规则加载与Windows旧入口，并把短证据写入本任务文档
- `dependencies`: `HISTORY-001`

### DOC-FINAL-001

- `title`: 回填运行时证据并更新用户导航
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 将实际网络、Agent、CODEX_HOME、路径和旧入口证据写回正式文档，并把混合模式标为可回退前态
- `dependencies`: `RUNTIME-001`

### REVIEW-001

- `title`: 完整WSL网络与本地适配独立最终审查
- `role`: `reviewer`
- `status`: `completed`
- `goal`: 独立覆盖最终仓库变更、系统配置哈希和全部运行时证据，给出final/pass或稳定finding
- `dependencies`: `DOC-FINAL-001`

### HISTORY-001

- `title`: 共享CODEX_HOME恢复WSL任务历史连续性
- `role`: `implementer`
- `status`: `completed`
- `goal`: 证明WSL历史缺失来自未投影CODEX_HOME，并以Windows用户CODEX_HOME加WSLENV路径转换复用同一会话库；不复制或迁移数据
- `dependencies`: `NETWORK-VERIFY-001`

## 更新时间

- `09/01/2026 16:14:15`
