# 完整 WSL Agent 联网适配：验收记录

## 验收目标

验证新启动的 Codex Agent 实际运行在通用 WSL2 开发发行版中，并在精确三键 `.wslconfig` 下完成联网、历史连续性、规则加载、同一仓库访问和 Windows 旧脚本互操作。验收必须区分配置与启动、WSL 网络、任务索引/分页历史、完整 Agent 四类证据。

## 验收标准

1. `.wslconfig` 只有 `[wsl2]` 下 `networkingMode=mirrored`、`dnsTunneling=true`、`autoProxy=true`，原状态、SHA-256、备份和回退路径可追溯。
2. 新 WSL 生命周期确认目标通用发行版为 WSL2、普通用户非 root、实际 networking mode 为 mirrored；未使用 Docker 专用发行版。
3. 目标发行版的 DNS、TLS/HTTPS、自动代理投影和必要主机互通通过脱敏验证，且没有修改 Docker、防火墙或代理监听。
4. 新 Codex Agent 进程由 Linux、UID、`HOME`、实际 `CODEX_HOME`、规则加载位置和 cwd 证据确认，并完成真实联网只读回合。
5. Agent 使用 Windows 原仓库的 WSL 挂载路径，`git` 解析为同一副本；没有创建 clone/worktree，也没有混用 Linux/Windows 依赖。
6. 选定旧 `.ps1` / `.cmd` 通过 Windows 互操作命中原后端，路径、参数、cwd、UTF-8 和目标退出码可观察，没有普通失败后的自动跨平台重跑。
7. 模板和 `脚本运行基线.md`、`命令构造约束.md`、`命令失败闭环.md` 三条 policy 保持不变；旧任务、`INSTALL.md`、测试和其他源码无修改。
8. 独立 reviewer 覆盖最终内容哈希、三段运行时证据、回退材料和零范围外修改声明；任一段未闭合时不得 final/pass。
9. 既有 Windows 任务切换到 WSL 后，当前任务必须指向同一主 rollout、正确 Linux cwd，并在分页历史中显示切换前今天的消息；仅共享 `CODEX_HOME` 或文件计数一致不能计通过。

## 必备证据

| 验收段 | 必备证据 | 当前状态 |
| --- | --- | --- |
| 文档先行 | `docs/CODEX_COMPAT.md` 最小追加；本任务三文档章节齐全；`validate-plan-docs`、`validate-doc-routing`、指定文件 `git diff --check` 输出 | `DOC-FINAL-001` 已复核：21 documents、0 modules / 7 task directories，三文件 `git diff --check` exit `0` |
| 原状态与回退 | 原 `.wslconfig` 存在性、原始字节 SHA-256、内容寻址备份路径；原 Agent environment；原仓库与进程基线 | 已记录；WSL 两个运行时 DB 另有 SQLite 一致性备份 |
| 第一段：配置与启动 | 精确 `.wslconfig` 内容与 SHA-256；新的 WSL 生命周期；`wsl.exe --version/status/list --verbose`；目标发行版、UID、`HOME`；实际 mirrored networking mode | 已通过 |
| 第二段：WSL 网络 | DNS 解析、TLS/HTTPS、非 `000` HTTP 传输结果；脱敏自动代理来源/端点；必要 Windows 主机互通；Docker、防火墙、代理监听零修改声明 | 已通过 |
| 索引与分页历史 | Windows/WSL 实际 SQLite home、主 rollout、Linux cwd、当前任务分页记录计数、修复前后 app-server 最近回合、备份与回退 | 返工后真实同步与 app-server 探针通过；用户重启 WSL Agent 后确认今天记录可见，通过 |
| 第三段：完整 Agent | 新 Agent 的 `uname`、UID、`HOME`、实际 `CODEX_HOME`、规则加载位置、Linux cwd、同一仓库根；真实联网只读回合；Windows 旧脚本互操作的 UTF-8/cwd/退出码 | 通过；重启后无临时前缀的最终脚本 exit `0`、`ok=true`，持久 `PATHEXT`、Linux 原生工具、原仓库、联网、Windows Python 和原 `.cmd` 全部命中 |
| 单副本与依赖边界 | Windows 原仓库与 WSL 挂载路径对应关系；无新 clone/worktree；无跨系统 `node_modules`/venv/原生依赖混用 | 通过；使用 `/mnt/d` 原仓库与 Linux 原生工具，无项目副本或依赖迁移 |
| 独立审查 | 最终 changed-files manifest、内容哈希、三段证据、回退材料、finding/复审结果与 independent final verdict | 清理后 `PRE-FINAL PASS`，无 actionable finding；本次定点状态文案由同一 reviewer 复审，正式 `final/pass` 以 GTO state 为准 |

HTTP 状态、配置文本、历史混合模式、WSL 集成终端、显式 `wsl.exe` 子进程和文档校验分别只能证明自身层次，不能代替完整 Agent 的真实联网回合。

## 未决项

1. 重启后的持久 `shell_environment_policy.set.PATHEXT` 已通过：新 Agent 精确继承标准值，原 `.cmd` 经 Windows 后端输出合法 JSON 并以 `0` 退出；用户再次确认今天记录可见。
2. 长期文档已同步最终运行态。`config.toml` 整体 SHA-256 `d08cd5958fc8431a39cdb5ded08017c0d9218a1a1d06c2ba9c679f6ae5e382ca` 只作时点快照；computer-use 命名管道会随重启变化，回退必须新鲜读取并只定点处理本任务的 `PATHEXT` 键，不能覆盖并发配置。
3. 一次性产物已按 reviewer 预审通过的精确清单完成清理，`work` 只保留 shell 配置回退材料，五个 WSL 数据库回退目录保持完整。清理后的第一阶段终审为 `PRE-FINAL PASS`、无 actionable finding；同一 reviewer 对本次定点状态文案完成复审后，由 GTO state 保存正式 verdict。模板和三条 policy 当前无需修改；只有发现与已冻结合同直接冲突的真源证据时，才退回主协调器重新裁决范围。

## 最终结论

精确三键网络配置、新 WSL 生命周期网络、真实库最终同步、用户可见历史、完整 WSL Agent 身份/规则/仓库/联网、持久 shell policy、Windows 旧入口、文档校验和一次性产物清理均已有通过证据。Doctor 的完整 Agent 时点验收为 `18 ok`、`0 fail`、`1` 个 thread inventory warning；受限 reviewer 上下文另得 `17 ok`、`0 fail`、`2` 个 warning，其中新增项仅为该审查沙箱的 filesystem restricted 提示。清理后 `PRE-FINAL PASS` 无 actionable finding；正式完成状态由同一 reviewer 对本次定点文案复审后写入 GTO state，本文件不预先冒充该 verdict。
