---
name: command-failure-memory
description: 在 Codex 里，当 shell、terminal、PowerShell、test、build、install、script、toolchain 或其他命令刚执行完却没有成功完成，或你正准备重试同一条失败链路时使用此 skill。触发依据是执行结果和重试意图，而不是枚举具体错误词：非 0 退出、超时、工具调用失败，或输出/上下文已经表明该命令并未成功完成，都视为失败。自动先 `record-failure`，在任何 retry/rerun/重试前先 `query-before-retry`，修复验证通过后立刻 `record-success`；even if the user did not mention the skill，也要自动使用。
---

# Command Failure Memory

在命令失败后执行固定闭环：记录失败、先查历史、再重试、成功后回写。

## Trigger Checklist / 自动触发检查

- 你刚运行了命令、测试、构建、安装或脚本，结果没有成功完成，例如退出码非 0、超时、工具调用失败，或输出明确表明执行未完成。
- 你准备再次执行同一个命令、等价命令，或继续重试同一条失败链路。
- 你需要先查历史修复方案再决定如何重试，或在修复验证成功后把新方案沉淀回经验库。
- 你是在自己调试时主动复现失败，不是用户显式点名这个 skill；这种情况下也照样自动使用。

## 默认行为

- 在任何 shell、terminal、PowerShell、bash 命令、测试、构建、安装、脚本或工具链命令失败后，立即执行 `record-failure`。
- 在再次运行同一命令或等价命令前，先执行 `query-before-retry`，不要盲目重试。
- 在确认修复方案生效后，立即执行 `record-success`，把解决方案和作用范围写回经验库。
- 在需要排查经验库状态、核对 case 数量或查看 pending failure event 时，执行 `inspect`。
- 把 `ProjectId` 设为稳定仓库标识，例如仓库目录名；不要在同一仓库里随意切换不同值。
- 把 `CommandText` 保持为实际执行的命令；把 `ErrorText` 的第一行写成最能区分问题的报错摘要，因为签名去重主要依赖命令文本和错误首行。

## 适用场景

- 使用 `git`、`npm`、`pnpm`、`yarn`、`node`、`python`、`pip`、`uv`、`pytest`、`cargo`、`go`、`docker` 等命令时失败。
- 出现 `command not found`、`module not found`、`permission denied`、`network timeout`、`SSL/TLS`、`registry`、`ENOENT`、路径缺失、`toolchain missing`、依赖安装失败或权限/环境问题。
- 同一命令刚刚失败，准备再次执行，且希望先看是否已有历史修复方案。
- 一个修复方案刚验证成功，需要沉淀为未来可复用的经验。
- 需要确认当前经验库里有哪些 case、有哪些 pending failures、以及某类问题是否已经有记录。

## 不适用场景

- 还没有任何命令执行失败，只是在做纯代码推理。
- 失败完全是当前业务逻辑的一次性断言变化，且没有可复用的命令层修复经验。
- 只想保存完整大日志原文；此 skill 只适合保存脱敏后的问题特征和解决方案。

## Usage / 使用方式

1. 优先使用跟随当前 runtime 的兼容 launcher。

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$runner = Join-Path $codexHome 'skills\command-failure-memory\scripts\command-failure-memory.cmd'
```

说明：
- 在 Codex shell 里优先走 `.cmd` launcher；它会自动选择兼容 backend，避免在受限 PowerShell 会话里直接调用 `.ps1` 失败。
- 如果当前会话设置了 `CODEX_HOME`，launcher 与 memory 默认都应跟随该 runtime；只有在 `CODEX_HOME` 未设置时才回退到 `%USERPROFILE%\.codex`。
- `command-failure-memory.py` 是当前首选 backend；`command-failure-memory.ps1` 保留为兼容回退与现有 harness 集成入口。

2. 失败后先记录。

```powershell
& $runner `
  -Action record-failure `
  -ProjectId ai-harness `
  -CommandText 'pnpm install' `
  -ErrorText 'ERR_PNPM_FETCH_500 registry request failed' `
  -Json
```

3. 重试前先查询。

```powershell
& $runner `
  -Action query-before-retry `
  -ProjectId ai-harness `
  -CommandText 'pnpm install' `
  -ErrorText 'ERR_PNPM_FETCH_500 registry request failed' `
  -Json
```

4. 修复成功后回写。

```powershell
& $runner `
  -Action record-success `
  -ProjectId ai-harness `
  -CommandText 'pnpm install' `
  -ErrorText 'ERR_PNPM_FETCH_500 registry request failed' `
  -Resolution 'Switch to the approved registry mirror and rerun install.' `
  -ScopeKind candidate_global `
  -ScopeReason 'Registry outage affected multiple repos.' `
  -Json
```

5. 审计经验库。

```powershell
& $runner -Action inspect -Json
```

## Standard Loop / 标准闭环

1. 在命令首次失败后执行 `record-failure`。
2. 在再次执行相同或相近命令前执行 `query-before-retry`。
3. 优先尝试返回结果中的高置信度 `suggestions`。
4. 方案生效后执行 `record-success`。
5. 需要看整体状态时执行 `inspect`。

## Actions / 动作说明

### `record-failure`

- 必填：`-Action record-failure -ProjectId -CommandText -ErrorText`
- 用途：登记一次待处理失败，并开启“先查再重试”闸门。
- 关键输出：`query_should_happen_before_retry=true`、`failure_count`、`signature`

### `query-before-retry`

- 必填：`-Action query-before-retry -ProjectId -CommandText -ErrorText`
- 用途：在重复执行前查询等价历史 case。
- 关键输出：
  - `query_permitted=false` + `reason=retry_gate_not_met`：当前签名还没有先前 failure 记录。
  - `query_permitted=true`：允许查询，并返回 `suggestions`。

### `record-success`

- 必填：`-Action record-success -ProjectId -CommandText -ErrorText -Resolution`
- 当不存在等价 case 时还必须提供 `-ScopeKind`
- 可选：`-ScopeConfidence -ScopeReason -ProjectSpecific`
- 用途：把确认有效的修复方案写入经验库，并驱动 scope 收敛。
- 关键输出：`created_new_case`、`case_id`、`scope_kind`、`projects_seen`

### `inspect`

- 必填：`-Action inspect`
- 用途：查看经验库索引、case 数量和 pending failure 数量。
- 关键输出：`case_count`、`pending_failure_count`、`index_path`、`failure_events_path`

## `ScopeKind` 选择

- `candidate_global`：看起来像环境、工具链、网络、权限、registry、系统依赖之类的跨项目问题，但还没有充分验证。
- `candidate_project`：看起来依赖当前仓库配置、私有脚本、特定目录结构或项目私有依赖。
- `global`：已经跨项目验证为稳定通用解法。
- `project`：已经确认只在当前项目成立，或有明确项目特异证据。
- 当新的证据表明“原本像全局问题其实是项目私有问题”时，对 `record-success` 增加 `-ProjectSpecific`。

## 参数约束

- 允许省略 `-CodexHome`；默认优先使用 `CODEX_HOME`，未设置时回退到 `~/.codex`。
- 默认把数据写到 `~/.codex/memories/command-failure-memory`。
- 脚本会对敏感信息脱敏，并对超长文本截断；不要刻意传入整份原始日志、token 或私钥。
- 新建 case 时如果不给 `-ScopeKind`，脚本会失败；不要省略。
- 把真正执行过的命令和真正看到的错误摘要传进去，不要改写成模糊描述，否则会降低召回率。

## 结果判读

- `record-failure` 成功：说明失败已进入待查询队列。
- `query-before-retry` 返回 `suggestions`：优先按 `scope_confidence` 和 `scope_kind` 选择最匹配方案。
- `record-success` 返回 `created_new_case=false`：说明命中了已有等价 case，只更新统计和收敛信息。
- `inspect` 可以用来确认经验库是否在增长、是否存在未消费的 pending failures。

## 维护要求

- 触发本 skill 后，通过显式脚本动作完成记录与查询；不要依赖 hooks、事件桥接或平台协议改造。
- 修改 `command-failure-memory.cmd`、`command-failure-memory.py`、`command-failure-memory.ps1` 的参数、输出字段、脱敏规则或 case schema 时，同步更新 `tests/harness/codex-failure-memory.integration.ps1` 与相关文档。
- 保持说明性文本默认中文；字段名、路径、脚本参数、代码标识符保持原样。
