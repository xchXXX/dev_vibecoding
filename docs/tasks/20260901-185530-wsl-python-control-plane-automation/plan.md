# 任务目标

将当前 PowerShell 为主的 ai-harness Codex 控制面迁移为 WSL 原生 Python，并将任务六要点、六工件一致性、按 `finding_id` 的 review 循环、规则机械匹配和共享 Command Failure Memory 变成可执行、可验证、可恢复的自动化。

# 背景与问题

当前本机实施任务存在规则正文加载过重、长任务合同分散、review 循环依赖协调器临时判断、PowerShell/Windows 命令链复杂，以及 CFM 容量和 Linux 并发不足等问题。用户已明确：语义判断仍由 Codex 完成；Python 只承担机械工作；Codex command-safety hook 退出开发环境；CFM 保持 Windows 与 WSL 可见的同一物理目录。

# 范围

- 规则索引、结构化 profile 匹配和文档校验 Python 化。
- GTO schema、控制器、投影、六工件和 review 状态机 Python 化。
- CFM WSL 锁、容量、active/archive、跨会话共享和原地格式升级。
- bootstrap、sync、doctor、session 与正式 Codex 测试入口 Python 化。
- Codex command-safety hook 运行面安全移除。
- 长期真源文档、模板、规则和验收 benchmark 同步。

# 非目标

- 不迁移 Claude hooks。
- 不建立自然语言任务分类脚本。
- 不新增 Codex hook、command runner、守护进程或第二状态库。
- 不移动 CFM 物理目录。
- 不改写历史任务和运行审计记录。

# 约束与依赖

- 当前工作区存在大量未提交改动，必须保留并基于实时哈希增量施工。
- 正式运行使用 WSL Python 3.12 标准库和 Linux 原生命令。
- 语义分类由 Codex 输出结构化 task profile，Python 只做 schema 校验与索引匹配。
- 子代理最多三路并行，写入路径必须互斥。
- 实施前先同步核心文档和目标 Red 测试。

# 方案摘要

以 Python 作为控制面唯一实现，保持现有目录职责和 JSON 合同风格。GTO 新控制器负责六工件、阶段门禁、`next_action` 与 finding lifecycle；规则脚本只对 Codex 提供的结构化 profile 查表；CFM 继续写 `/mnt/c/Users/Laptop/.codex/memories/command-failure-memory`，通过 WSL 锁和原子写保护；Codex hook 整体退出开发运行面。

# 风险与回退

- 任何实时文件哈希与派发基线不一致时停止该子任务并重新裁决。
- Python 等价行为未通过目标测试前不退出旧入口。
- CFM 原地升级先生成内容寻址备份和迁移 manifest；计数或哈希不一致即不安装新格式。
- review 同一 finding 三轮仍未关闭时任务进入 blocked，不降低验收标准。

# 验收标准

- 六工件一致、六要点可投影、合同改变使批准失效。
- 问答、小任务、大型任务 blind behavior 分流正确。
- 同一 finding 跨 subtask 循环合法，不同 finding 独立计轮，R3 后自动 blocked。
- 正式 Codex 控制面正常链不运行 Windows 命令且不依赖 Codex hook。
- CFM 跨 WSL 进程/会话共享并与 Windows 主机看到同一物理文件。
- 全部相关测试和独立 final review 通过。

# 阶段划分

1. bootstrap 与文档合同。
2. 三路目标 Red 测试。
3. GTO、CFM、Rules 三路并行实现。
4. Ops 迁移和 Codex hook 移除。
5. 统一 WSL 与理想行为验收。
6. reviewer 循环至 final/pass。

# 需先同步的核心文档与测试

- 文档：`AGENTS.md`、规则入口、`ARCHITECTURE`、`CODEX_COMPAT`、`HOOKS`、`INSTALL`、`SUBAGENT_GOVERNANCE`、GTO/CFM skill 与模板。
- 测试：GTO same-finding lifecycle、CFM capacity/lock/store、规则结构化 profile、无 Codex hook 和 WSL-only 正常链。
