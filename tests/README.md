# tests

本目录存放 harness 自身回归测试与 control-plane 集成测试。

## 统一回归入口

- 文档入口：`docs/EVALS.md`
- 套件索引：`tests/harness/README.md`
- 当前冻结执行方式：
  - `Get-ChildItem -LiteralPath .\tests\harness -Filter *.ps1 | Sort-Object Name | ForEach-Object { pwsh -NoProfile -ExecutionPolicy Bypass -File $_.FullName }`
- 当前入口按文件名顺序执行 `tests/harness/*.ps1`，因此 `tests/harness/command-failure-case.schema.ps1` 已纳入统一回归集

## 当前冻结套件

- `tests/harness/claude-hooks-phase5.hook-behavior.ps1`：HookCommon 字段兼容解析与 canonical payload 归一化
- `tests/harness/claude-hooks-phase5.integration.ps1`：Claude hooks phase5 的 sync / install / doctor / guard 闭环
- `tests/harness/codex-failure-memory.integration.ps1`：Codex 侧失败记忆规则、收敛、脱敏、容量与并发回归；黑盒入口改为独立 skill
- `tests/harness/command-failure-memory.skill-doc.ps1`：`command-failure-memory` skill 的 frontmatter 触发描述、使用说明与 `agents/openai.yaml` 合同回归
- `tests/harness/global-task-orchestrator.skill-doc.ps1`：`global-task-orchestrator` 的 `SKILL.md / governance-essentials.md / agents/openai.yaml / current_phase` 合同回归
- `tests/harness/fix-closure-gate.skill-doc.ps1`：`fix-closure-gate` 的 frontmatter 触发描述、边界、字段合同与 `agents/openai.yaml` 回归
- `tests/harness/codex-sync.integration.ps1`：`sync-codex.ps1` 与最小 doctor / receipt 闭环回归；覆盖固定白名单四 skill 托管，其中 `pre-dev-benchmark` 与 `fix-closure-gate` 的真源位于 `skills/`
- `tests/harness/command-failure-case.schema.ps1`：`schemas/command-failure-case.schema.json` 的 schema 合同回归
- `tests/harness/control-plane.integration.ps1`：control-plane 新模型黑盒 `new-task / init-task / sync-task-md / append-event / build-subtask-brief / build-execute-handoff / validate` 闭环
- `tests/harness/windows-command-guardrails.contract.ps1`：Windows 命令构造约束、`pwsh7` 基线与全局长期偏好层合同回归
- `tests/harness/test-temp-cleanup.contract.ps1`：测试临时目录清理规则与 harness/benchmark 退出清理钩子合同回归

## opt-in benchmark

- `tests/benchmarks/command-failure-memory.autotrigger.ps1`：真实调用 `codex exec --json`，用自动 prompt 与显式 `$command-failure-memory` prompt 的输入 token 差分判定 skill 是否被自动装载。
- `tests/benchmarks/command-failure-memory.forward.ps1`：真实调用 `codex exec --full-auto` 跑失败命令、编辑脚本并检查 memory 落盘；用于直接暴露 CLI 链路是否能穿过失败 shell 回合。
- `tests/fixtures/command-failure-memory.autotrigger.cases.json`：自动触发 benchmark 的失败场景集。
- `tests/fixtures/command-failure-memory.forward.cases.json`：forward benchmark 的真实失败命令样例集。
- 当前 runtime 兼容入口优先使用 `skills/command-failure-memory/scripts/command-failure-memory.cmd`，由其转发到 `.py` backend；`.ps1` 保留为兼容回退与现有 harness 回归入口。
- 该 benchmark 需要本机可调用 `codex.exe` 且具备网络访问；它不属于默认 `tests/harness/*.ps1` 统一回归入口。
- `command-failure-memory` 的最终验收口径不是 token 差分，而是盲测 forward-test：
  - 使用新的子代理窗口或 fresh thread，不提示 `command-failure-memory` skill 信息。
  - 只给正常的“先运行失败命令，再把同一命令修到退出 0 且输出指定 PASS 标记”的任务。
  - 仅当 case 同时满足“复验通过”和“能在 `~/.codex/memories/command-failure-memory` 或任务目录本地 `.codex/memories/command-failure-memory` 找到对应 marker 留痕”时才计为自动触发成功。
  - 目标门槛为 `>= 90%`。
- 当前已知差异：
  - Windows 上的 `codex exec` blind forward-test 仍可能在首个失败 `shell_command` 后卡住，因此 `command-failure-memory.forward.ps1` 当前主要用于诊断 CLI 路径。
  - 面向真实自动触发率的最终验收，以新的子代理窗口 blind benchmark 为准；最新一次留痕见 `docs/ai/runs/2026-04-21-command-failure-memory-blind-benchmark.md`。

## control-plane 当前测试范围

- control-plane 集成套件：`tests/harness/control-plane.integration.ps1`
- 新控制面唯一真源：`docs/ai/tasks/<task_id>/state.json`
- 新控制面摘要文件：`docs/ai/tasks/<task_id>/task.md`
- 新控制面事件流：`docs/ai/tasks/<task_id>/events.jsonl`
- 新 orchestrator 动作约定：
  - `new-task`
  - `init-task`
  - `sync-task-md`
  - `append-event`
  - `build-subtask-brief`
  - `build-execute-handoff`
  - `validate`
- 长任务身份约定：
  - 一个正式长任务只对应一个 `task_id`
  - `Plan Window` 与 `Execute Window` 共享同一个 `task_id`
  - `Execute Window` 继续已有 `task_id` 时，不应重新 `init-task`
- happy path：`init-task` 创建 `state.json / task.md / events.jsonl`，随后 `validate` 通过
- happy path：同一 topic 连续调用 `new-task` 时应生成不同 `task_id`
- happy path：`sync-task-md` 可按 `state.json` 重写人读摘要
- happy path：`sync-task-md` 生成的摘要至少包含 `## 目标 / ## 关键决定 / ## 当前阶段 / ## 子任务` 等核心 section
- happy path：`append-event` 追加合法 JSONL 事件后，`validate` 仍通过
- happy path：`build-subtask-brief` 输出来自 `state.json.subtasks[]` 的子任务简报
- happy path：`build-execute-handoff` 输出给 `Execute Window` 的交接提示，至少包含 `task_id / current_phase / objective / scope_in / scope_out / acceptance / stop_conditions / task.md / 首批子任务摘要 / 先委派子代理`
- bad path：`validate` 缺 `-TaskId`
- bad path：对已存在 `task_id` 再次执行 `init-task` 必须失败，避免误复用与误覆盖
- bad path：`state.json` 缺必填字段（例如 `current_phase`）
- bad path：`subtasks[].subtask_id` 重复
- bad path：`pending / in_progress` 子任务缺 `read_paths` 或 `write_paths`
- bad path：`blocked` 子任务缺 `result`
- bad path：`completed` 子任务缺关键 `result` 字段（例如 `result.summary / result.written_role / result.verification`）
- bad path：`completed` 子任务 `changed_files` 越出 `subtask.write_paths`
- bad path：`result.written_role` 与 `subtask.role` 不一致
- bad path：`manifest.json` 或 `agents/codex-role-map.json` 多出未对齐角色
- bad path：schema 规定为 array 的根字段若被写成单个 string，例如 `scope_in` 或 `acceptance`，`validate` 必须失败
- bad path：schema 规定为 array 的子任务字段若被写成单个 string，例如 `read_paths / write_paths / assignment.must_include`，`validate` 必须失败
- bad path：schema 规定为 array 的结果字段若被写成单个 string，例如 `result.verification.commands` 或 `blocked_by`，`validate` 必须失败
- bad path：`events.jsonl` 含非法 JSON 行

## 说明

本批测试优先验证新控制面黑盒行为与合同闸门，不再对 `plan.json / work_orders / dispatch_packets / return_packets / .ai/session / hydrate / compile-dispatch-message` 做回归断言。
