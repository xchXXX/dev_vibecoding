# skills

本目录保存 Codex skills 真源。

## 真源与运行时映射

- 真源：`<harness-root>/skills/*`
- 运行时：`~/.codex/skills/*`

## 当前最小托管范围

当前固定白名单托管目标为：

- `global-task-orchestrator`
- `command-failure-memory`
- `pre-dev-benchmark`
- `fix-closure-gate`

## 规则

- 每个 skill 使用独立目录
- 运行时投放目标为 `~/.codex/skills/`
- 不直接在运行时目录做长期维护
- 当前不托管：
  - `.system/*`
  - 其他第三方 runtime skill
  - 插件或任意目录同步

## 同步与校验

- `python3 scripts/sync-codex.py` 只把上述四个受管 skill 投放到 `~/.codex/skills/<skill>/`。
- `python3 scripts/doctor-core.py --audit-target codex_minimal` 校验四个 skill 的真源、运行时与 receipt 一致性。
