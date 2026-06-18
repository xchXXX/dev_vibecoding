# EVALS

本文件说明 ai-harness 自身的评估与回归测试入口。

## 当前统一回归入口

- 入口文档：`tests/README.md`
- 套件索引：`tests/harness/README.md`
- 当前冻结执行方式：
  - `Get-ChildItem -LiteralPath .\tests\harness -Filter *.ps1 | Sort-Object Name | ForEach-Object { pwsh -NoProfile -ExecutionPolicy Bypass -File $_.FullName }`

本阶段仅冻结：
- harness 测试目录：`tests/harness/`
- fixtures 目录：`tests/fixtures/`
- 当前 harness 统一入口覆盖：
  - `tests/harness/claude-hooks-phase5.hook-behavior.ps1`
  - `tests/harness/claude-hooks-phase5.integration.ps1`
  - `tests/harness/codex-failure-memory.integration.ps1`
  - `tests/harness/codex-sync.integration.ps1`
  - `tests/harness/command-failure-case.schema.ps1`
  - `tests/harness/control-plane.integration.ps1`
- 真实回归测试延后到 Phase 8 实现
