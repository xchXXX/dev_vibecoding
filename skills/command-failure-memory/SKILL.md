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
: "${CODEX_HOME:?set verified Windows Codex home WSL path}"
runner="skills/command-failure-memory/scripts/command-failure-memory.py"
if [[ ! -f "$runner" ]]; then
  runner="${CODEX_HOME:?CODEX_HOME must be set}/skills/command-failure-memory/scripts/command-failure-memory.py"
fi
```

- 后端使用 WSL `python3` 和 GNU 双横线 argv；Windows 原生 Agent 通过指定发行版的 wsl.exe --exec 发起调用。先核实实际 Windows CODEX_HOME 的 WSL 等价路径，每次显式传入 `--codex-home`；缺失时后端报错，不回退到 Linux HOME。
- 复杂文本直接作为 `--command-text`、`--error-text`、`--resolution` 等 argv 值传入。
- `--json` 只选择机器可读输出形式。
- 数据根始终是 `$CODEX_HOME/memories/command-failure-memory`，不移动数据根、不另建并行可编辑库；原地格式升级见下文存储合同。
- 同一数据根的存储事务与格式升级见下文性能存储合同；active 超过工作集上限时转入 archive，不丢弃 pending 或拒绝新 case 来伪装容量受控。

## 标准闭环

1. 失败后记录：

```bash
python3 "$runner" --codex-home "$CODEX_HOME" --action record-failure \
  --project-id ai-harness \
  --command-text 'pnpm install' \
  --error-text 'ERR_PNPM_FETCH_500 registry request failed' \
  --json
```

2. 重试前查询：

```bash
python3 "$runner" --codex-home "$CODEX_HOME" --action query-before-retry \
  --project-id ai-harness \
  --command-text 'pnpm install' \
  --error-text 'ERR_PNPM_FETCH_500 registry request failed' \
  --json
```

3. 修复验证成功后回写：

```bash
python3 "$runner" --codex-home "$CODEX_HOME" --action record-success \
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
python3 "$runner" --codex-home "$CODEX_HOME" --action inspect --json
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
- `inspect` 返回 case、active/archive 和 pending 计数；新版另返回 `storage_format=sqlite-v2`、当前 `database_path` 和迁移计数/哈希。旧 `index_path`、`failure_events_path` 只定位保留的升级前 JSON，不代表当前可编辑真源。

每次有效 `record-success` 只增加一次 `verify_count`，新 case 首次成功为 1；本次验证采用的非空 `resolution` 更新为当前方案。历史计数保留，不凭猜测批量减一。

签名保留参数大小写、正式路径和故障类型；只归一明确的临时目录随机段，保留其下文件名。Python traceback 取最终异常摘要，不把共同的 Traceback 标题当故障区别。旧 v1 记录按原命令/错误定位并复核留存摘要，不因旧签名曾折叠大小写或忽略异常类型就复用不同故障的方案；不迁移或覆盖真实库来伪造兼容通过。

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


## 20261027 性能改进

性能存储演进（20261027，源码已实现、待独立验收；未安装的旧 runner 仍遵守其原格式）：

- 数据根保持不变；升级完成后的 `memory.sqlite3` 是案例和 pending 的唯一可编辑真源。旧 `index.json`、`cases/`、`runtime/failure-events.json` 作为升级前证据保留，不双写、不继续参与普通查询。旧 runner 不得与新 runner 同时写同一数据根。
- 使用 Python 标准库 SQLite 事务；案例按 `signature` 索引定位，pending 以 `(project_id, signature)` 定位。旧签名兼容仍复核原始摘要，不能仅凭旧 hash 命中。查询与写入的事务只加载命中案例/事件；冷案例淘汰按索引定位，`inspect` 才允许全量列出。
- 第一次打开旧格式时，在同一数据根内完成一次受互斥保护的迁移：验证全部索引与案例对应关系、案例内容和所有 pending，保存内容寻址备份与 migration manifest；对导入前后规范化内容的哈希、案例数量、active/archive 数量和 pending 数量逐项核对。全部通过才提交格式标志；失败回滚新格式，不修改旧文件，不把损坏或漏失记录当空库。
- pending 不截断；已归档案例全部保留并仍可按签名命中。不同项目并发记录失败/查询/成功由短事务串行提交，不能因全量覆盖而丢更新。正常查询成本不随无关历史线性增加。
- 新增存储格式、并发与迁移验证只使用隔离 fixture；本次开发不迁移用户真实库，不安装到共享 CODEX_HOME。接口的实际可用状态以该 runner 与安装回执为准。
