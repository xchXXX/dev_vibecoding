---
name: command-failure-memory
description: 在 Codex 里，当 shell、terminal、test、build、install、script、toolchain 或其他真实命令失败，或准备重试同一失败链路时使用此 skill。执行前已明确声明、只运行最小目标测试且实际失败类型与预期一致的 TDD 预期红不触发；若出现意外的命令、环境或基础设施错误则照常触发。
---

# Command Failure Memory

真实命令失败后执行固定闭环：记录失败、先查历史、再重试、成功后回写。

## 触发边界

以下情况触发：

- 命令、测试、构建、安装或工具链真实失败。
- 准备重试同一命令或等价失败链路。
- 确认一个修复方案已生效，需要回写可复用经验。

TDD 预期 Red 仅在同时满足以下条件时零触发：

1. 执行前已明确声明这是 Red，并写明预期失败类型或缺失行为。
2. 只运行能证明该行为的最小目标测试。
3. 实际失败正是已声明的断言、缺失接口或缺失实现，没有出现另一条命令、环境或基础设施错误。

任一条不满足时进入标准闭环。预期 Red 转 Green 不为该 Red 补写成功记录。

## Runner 与数据边界

```bash
runner="skills/command-failure-memory/scripts/command-failure-memory.py"
if [[ ! -f "$runner" ]]; then
  runner="${CODEX_HOME:?CODEX_HOME must be set}/skills/command-failure-memory/scripts/command-failure-memory.py"
fi
```

- 正常链使用 WSL `python3` 和 GNU 双横线 argv。
- 复杂文本直接作为 `--command-text`、`--error-text`、`--resolution` 等 argv 值传入。
- `--json` 只选择机器可读输出形式。
- 数据根始终是 `$CODEX_HOME/memories/command-failure-memory`，不迁移、不另建库。
- 同一数据根使用跨 WSL 进程互斥锁与原子替换；active 超过工作集上限时转入 archive，不丢弃 pending 或拒绝新 case 来伪装容量受控。

## 标准闭环

1. 失败后记录：

```bash
python3 "$runner" --action record-failure \
  --project-id ai-harness \
  --command-text 'pnpm install' \
  --error-text 'ERR_PNPM_FETCH_500 registry request failed' \
  --json
```

2. 重试前查询：

```bash
python3 "$runner" --action query-before-retry \
  --project-id ai-harness \
  --command-text 'pnpm install' \
  --error-text 'ERR_PNPM_FETCH_500 registry request failed' \
  --json
```

3. 修复验证成功后回写：

```bash
python3 "$runner" --action record-success \
  --project-id ai-harness \
  --command-text 'pnpm install' \
  --error-text 'ERR_PNPM_FETCH_500 registry request failed' \
  --resolution 'Switch to the approved registry mirror and rerun install.' \
  --scope-kind candidate_global \
  --scope-reason 'Registry outage affected multiple repos.' \
  --json
```

4. 只读查看索引和 pending 数量：

```bash
python3 "$runner" --action inspect --json
```

## 真实 action 与 argv

- `record-failure`：必填 `--project-id`、`--command-text`、`--error-text`。
- `query-before-retry`：必填 `--project-id`、`--command-text`、`--error-text`。
- `record-success`：必填 `--project-id`、`--command-text`、`--error-text`、`--resolution`；新 case 还必须给 `--scope-kind`。
- `inspect`：无额外必填业务参数。

其他 parser 参数为 `--codex-home`、`--scope-confidence`、`--scope-reason`、`--project-specific`、`--json`。以 `python3 "$runner" --help` 为最终 argv 真源。

## 结果判读

- `record-failure` 返回 `query_should_happen_before_retry=true`、`failure_count` 和 `signature`。
- `query-before-retry` 在有失败记录时返回 `query_permitted=true` 与 `suggestions`。
- `record-success` 返回 `created_new_case`、`case_id`、`scope_kind` 和 `projects_seen`。
- `inspect` 返回 case、active/archive 和 pending 计数以及索引路径。

## Scope 选择

- `candidate_global`：看起来是跨项目的环境、工具链、网络、权限或 registry 问题，但证据尚不充分。
- `candidate_project`：依赖当前仓库配置、私有脚本或特定目录结构。
- `global`：已跨项目验证为稳定通用解法。
- `project`：已确认仅对当前项目成立。

如新证据显示原候选全局解法实为项目私有，在 `record-success` 时增加 `--project-specific`。

## 数据安全

- 不传入 token、私钥或未脱敏大日志；脚本仍会执行脱敏和长度截断。
- `--project-id` 使用稳定仓库标识。`--command-text` 保持真实命令，`--error-text` 首行保留最能区分问题的摘要。
- 格式升级只在原目录内执行，先做内容寻址备份和 migration manifest；计数或哈希不一致时不安装新格式。
