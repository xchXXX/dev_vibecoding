# skills

本目录保存 Codex skills 真源。

## 真源与运行时映射

- 真源：`C:/Users/72385/dev/ai-harness/skills/*`
- 运行时：`C:/Users/72385/.codex/skills/*`

## 当前最小托管范围

本批次冻结的最小托管目标只有：

- `global-task-orchestrator`

## 规则

- 每个 skill 使用独立目录
- 运行时投放目标为 `~/.codex/skills/`
- 不直接在运行时目录做长期维护
- 当前不托管：
  - `.system/*`
  - 其他第三方 runtime skill
  - 插件或任意目录同步

## 批次边界

本批次只冻结文档合同，后续代码批次再实现 `sync-codex.ps1` 与最小 doctor 校验。
