# Command Failure Memory Blind Benchmark

日期：`2026-04-21`

## 目标

验证 `command-failure-memory` 在“不提示 skill 名称”的 blind 子代理窗口里，遇到失败命令后是否会自动处理、修复并把解决方案写入 memory。

## 本次口径

- 不使用 hooks 作为触发前提。
- 自动触发判定基于真实前向 blind run，而不是 token 差分。
- 成功标准：
  - 子代理按原命令复跑后退出码为 `0` 且输出目标 `CFM-FWD-PASS-*`
  - `~/.codex/memories/command-failure-memory/cases/*.json` 中存在对应 case 命中

## 关键实现调整

- `command-failure-memory.py` / `command-failure-memory.ps1`：省略 `-CodexHome` 时优先读取 `CODEX_HOME`，未设置时回退到 `~/.codex`
- `AGENTS.md` / `SKILL.md` / `agents/openai.yaml`：launcher 路径改为“优先跟随 `CODEX_HOME`，否则回退到 `%USERPROFILE%\\.codex`”
- 新增 `tests/benchmarks/command-failure-memory.forward.ps1` 与 `tests/fixtures/command-failure-memory.forward.cases.json`

## 真实 blind 子代理 benchmark

- 工作目录：`C:\Users\72385\dev\ai-harness`
- 样例目录：`C:\Users\72385\dev\ai-harness\.tmp\command-failure-memory-forward-bench-run1\cases`
- memory 快照：`C:\Users\72385\dev\ai-harness\.tmp\command-failure-memory-forward-bench-run1\memory-snapshot`
- 真实 runtime skill 已先用仓库版本覆盖到 `C:\Users\72385\.codex\skills\command-failure-memory`
- 跑完后已把原始 `C:\Users\72385\.codex\memories\command-failure-memory` 恢复

## 结果

- blind 子代理窗口前向测试：`10 / 10` 通过，实际通过率 `1.00`
- 覆盖样例：
  - 缺失命令
  - 显式非零退出
  - `exit 0` 但输出明确失败
  - 缺失 label / 缺失文件 / 缺失脚本
  - timeout-like 非零退出
  - 缺失目录 / 缺失工具

## 额外发现

- `codex exec --full-auto` 的 Windows CLI blind forward-test 仍可能在首个失败 `shell_command` 后卡住。
- 因此当前仓库把 `tests/benchmarks/command-failure-memory.forward.ps1` 视为 CLI 诊断入口，而不是最终自动触发验收口径。
- 真正的自动触发验收，当前以新的子代理窗口 blind benchmark 为准。
