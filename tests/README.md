# tests

本目录存放 harness 自身回归测试与 control-plane 集成测试。

## 统一回归入口

- 文档入口：`docs/EVALS.md`
- 套件索引：`tests/harness/README.md`
- 当前冻结执行方式：
  - `Get-ChildItem -LiteralPath .\tests\harness -Filter *.ps1 | Sort-Object Name | ForEach-Object { powershell -NoProfile -ExecutionPolicy Bypass -File $_.FullName }`
- 当前入口按文件名顺序执行 `tests/harness/*.ps1`，因此 `tests/harness/command-failure-case.schema.ps1` 已纳入统一回归集

## 当前冻结套件

- `tests/harness/claude-hooks-phase5.hook-behavior.ps1`：HookCommon 字段兼容解析与 canonical payload 归一化
- `tests/harness/claude-hooks-phase5.integration.ps1`：Claude hooks phase5 的 sync / install / doctor / guard 闭环
- `tests/harness/codex-failure-memory.integration.ps1`：Codex 侧失败记忆规则、收敛、脱敏、容量与并发回归；黑盒入口改为独立 skill
- `tests/harness/command-failure-memory.skill-doc.ps1`：`command-failure-memory` skill 的 frontmatter 触发描述、使用说明与 `agents/openai.yaml` 合同回归
- `tests/harness/codex-sync.integration.ps1`：`sync-codex.ps1` 与最小 doctor / receipt 闭环回归；覆盖固定白名单三 skill 托管，其中 `pre-dev-benchmark` 的真源位于 `skills/`
- `tests/harness/command-failure-case.schema.ps1`：`schemas/command-failure-case.schema.json` 的 schema 合同回归
- `tests/harness/control-plane.integration.ps1`：control-plane 黑盒 validate / bootstrap / hydrate / compile-dispatch-message 闭环

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
- happy path：当前冻结 run 可通过 `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate -TaskId <task_id> -Json`
- happy path：`hydrate` 会重编译陈旧 `dispatch_message_raw`，并回填 `expected_written_role / expected_written_by_patterns / dispatch_packet_required`
- bad path：`validate` 缺 `-TaskId`
- bad path：`plan.json.status != frozen`
- bad path：`bootstrap` 拒绝 `draft` source plan 与 existing run draft plan
- bad path：`codex-role-map` 存在非法 `agent_type` 或缺少必需角色
- bad path：缺 `work_orders` 目录或当前 run 下没有任何 `work_order`
- bad path：缺 `read_paths_mandatory`
- bad path：弱化 `required_return_fields` 也不能绕过仓库最低回执字段集合
- bad path：`dispatch_message_raw` 与合同编译结果不一致
- bad path：复杂任务缺 `dispatch_packet`
- bad path：`return_packet_required=true` 但缺 `return_packet`
- bad path：删除 `work_order_id` 后仍不能绕过缺失 `return_packet`
- bad path：`return_packet_path` 指向他人工单回执
- bad path：`return_packet_required=false` 绕过尝试
- bad path：`return_packet.written_role / written_by` 与 `expected_written_role / expected_written_by / expected_written_by_patterns` 合同不一致
- bad path：`expected_written_by_patterns` 含非法正则，或被弱化为不受限的通配/正则转义模式
- bad path：`dispatch_packet_path` 越出当前 task run、穿过 reparse point、或伪造 `task_id + dispatch_packet_path`
- bad path：显式 `dispatch_packet_required=true` 可覆盖数量启发式
- bad path：`hydrate` 在目标路径不存在、目标 task 缺 `work_orders`、JSON 不可解析、编译前置字段缺失、`dispatch_packet_path` 越界、或施工图关键字段缺失时必须非零退出
- bad path：`compile-dispatch-message.ps1` 目标目录为空时必须非零退出，不能把空目标集当成功

## 说明

本批测试优先验证黑盒行为与合同闸门，不对私有 helper 名称、临时目录名或内部执行顺序做过拟合断言。
