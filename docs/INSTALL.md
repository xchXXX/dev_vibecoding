# INSTALL

## 目标

本文冻结 `ai-harness` 的最小安装 / 同步合同。

当前已冻结：

- Claude agents install / sync
- Claude hooks / doctor 边界

本批次新增冻结：

- Codex 最小兼容闭环的 install / sync / doctor 文档口径

## Claude 现有口径

### hooks / doctor

- doctor 只读审计 `agents/manifest.json`、`hooks/claude/manifest.json`、`hooks/claude/settings.json`、`hooks/claude/scripts/<Event>.ps1`
- install / sync 只负责把冻结模板投放到用户级 Claude 运行时
- 不做自动修复
- 不设计 user / project / local 三层 settings merge / override
- 不触碰项目 `.claude/settings.json` 或 `.claude/settings.local.json`

## Codex 最小闭环口径

### 1. 真源与运行时映射

- 真源：`C:/Users/72385/dev/ai-harness/skills/*`
- 运行时：`C:/Users/72385/.codex/skills/*`
- 当前最小目标：
  - `global-task-orchestrator`
  - `command-failure-memory`
  - `pre-dev-benchmark`

### 2. `sync-codex.ps1` 最小合同

- 负责固定白名单源路径到 `~/.codex/skills/*` 的 install / sync
- 最小支持 install / sync 语义
- 默认不接管未托管运行时目录
- 当前只托管固定白名单：
  - `skills/global-task-orchestrator -> ~/.codex/skills/global-task-orchestrator`
  - `skills/command-failure-memory -> ~/.codex/skills/command-failure-memory`
  - `skills/pre-dev-benchmark -> ~/.codex/skills/pre-dev-benchmark`
- 不扩展到：
  - `.system/*`
  - 插件
  - 通用任意目录同步
  - 项目级清理

### 3. Codex doctor / validate 最小合同

未来最小 doctor / validate 只校验：

- 真源 skill 存在
- 运行时 skill 存在
- 关键文件已同步
- 真源与运行时基本一致

不扩展到：

- 更广范围项目 doctor
- Claude settings merge / override
- 项目接入清理

## 非目标

- 不做项目接入清理
- 不做 `.claude/settings.local.json` 收敛
- 不做更大范围 evals
- 不做 `.system/*` 或第三方 runtime skill 托管

## 最小验收项

- Codex 真源与运行时映射已冻结
- `sync-codex.ps1` 最小职责与非目标已冻结
- Codex doctor / validate 最小边界已冻结
- 当前最小托管目标明确为：
  - `global-task-orchestrator`
  - `command-failure-memory`
  - `pre-dev-benchmark`
- `sync-codex.ps1` 与 `doctor-core.ps1 -AuditTarget codex_minimal` 已覆盖上述固定白名单
