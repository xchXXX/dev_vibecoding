# Codex Command Safety Gateway 验收合同

## 验收目标

证明本任务不仅让目标测试通过，而且确实在真实命令执行前阻止或安全路由已知高频失败族；同时证明 expected-red 不会吞掉声明外故障，安装器不破坏用户 Hook 配置，GTO 仍保持单一状态真源，fresh gateway 相对同轮 fresh bare-Node 基线的性能满足双门槛预算。

本文件当前冻结验收口径，不代表实现已经通过。正式状态、子任务结果、review evidence 与最终 verdict 只以 `docs/ai/tasks/20260828-150316-command-safety-gateway-c498ea/state.json` 为准。

## 验收标准

1. safe pass-through 对未命中错误族的命令返回 allow，并保持原 `tool_input` 不变；Hook 热路径不读 CFM、不运行 `git`、不访问网络、不扫描父目录。
2. missing path、PowerShell foreach pipeline、raw recursive cleanup、raw GTO state patch 四类最小 payload 在真实命令执行前返回 `deny` 或冻结的 `updatedInput`；被阻止的原始子进程 sentinel 不得出现。
3. expected-red 只有在实际退出码与输出同时命中事前声明的 `expected_exit_codes` 和 `expected_output_pattern` 时，才输出 `status=expected_red`；child marker 不受信任；底层退出 0 时输出 `status=unexpected_green`，模式不匹配、spawn/not-found、signal、timeout 或明确 runtime 异常保持非零。
4. 符合声明的 expected-red 与 `unexpected_green` 都不生成 CFM failure；声明外真实失败仍进入既有命令失败闭环。CFM 不进入网关热路径。
5. GTO raw patch 被拒绝或改写到结构化 action；该 action 以 `subtask_id` 为边界，拒绝未知字段和非法状态，限制 changed files 到 write paths，写后验证并原子替换，失败时原 `state.json` 不变。
6. 安装器只管理稳定 managed id 的自身条目，保留 `hooks.json` 所有非托管内容；实际变化前创建内容寻址备份，写 machine-local receipt，并在相同输入二次执行时保持目标哈希与备份数量稳定。
7. `tests/harness/command-safety-gateway.integration.ps1` 全部通过，且其 before-fix RED 精确落在缺少新入口，不是 Node、PowerShell、quoting、权限或临时清理故障。
8. `tests/harness/control-plane.integration.ps1` 的新增 action 正反测试与既有相关回归通过。
9. 隔离 CodexHome 的 install lock/merge/backup/receipt/idempotence 已验证；真实 `~/.codex` 安装仍由主流程执行，真实写入同样必须保留非托管内容、先备份、写 receipt，最后由用户通过 `/hooks` 核对精确 command hash 后信任 managed Hook。
10. 同一轮至少 60 个独立 fresh gateway process 全部产生合法结构化响应，同时至少 60 个 fresh bare-Node baseline process 正常输出并退出；两组从启动前到输出读取并退出的样本分别使用 nearest-rank，gateway p95 不超过 `120ms`，且 `gateway p95 - bare Node p95` 不超过 `25ms`。两组均不预热、不复用进程、不剔除任何样本。
11. 测试创建的隔离 CodexHome、临时 hooks、sentinel 和捕获文件在 happy path 与失败路径都由同一测试 `finally` 清理。
12. 当前 `main` primary dirty workspace 保持用户控制；两个 overlap 文件只在已冻结 SHA-256 仍匹配时做窄补丁，不扫描或处理其他 clone/worktree。
13. 七个 `review_evidence` 槽位均由已完成的执行型或测试型子任务写入非空短证据；不能只用全套测试通过替代 `hit_proof_observed`。
14. 独立 reviewer 审阅最终 changed files、命中证据、相关回归、安装证据、性能证据、dirty boundary 与残余风险，并对最新 HEAD 或最终变更哈希给出 `final/pass`。

## 必备证据

### 最小复现与命中证明

`minimal_repro` 固定为：向 PreToolUse 网关输入每个高频错误族的最小 payload，并对 expected-red 运行声明内和声明外失败。

`hit_proof` 固定为：新入口必须在真实命令执行前返回 `deny` / `updatedInput`，或由 expected-red 包装器输出可机器判读的 `expected_red` 状态。证据不得只记录最终测试为绿。

回放结果必须按下表逐项记录：

| 检查项 | Before-fix / diagnostic 证据 | After-fix 期望 | 验收信号 |
| --- | --- | --- | --- |
| safe pass-through | 最小安全 payload 与原输入哈希/深比较基线 | allow，输入不变 | `safe_pass_through=true` 或等价断言 |
| missing path deny | 不存在路径 fixture；原始命令设置 sentinel | deny | deny reason code；sentinel 不存在 |
| PowerShell foreach pipeline deny | 未物化 `foreach (...) { ... } | ...` payload | deny | pipeline reason code；sentinel 不存在 |
| raw recursive cleanup deny | 未提供 containment root 的递归清理 payload | deny 或 contained cleanup updatedInput | 原始删除入口未运行；fixture 完整 |
| raw GTO state patch deny | 直接编辑目标 `state.json` 的 Bash/apply_patch payload | deny 或结构化 GTO action updatedInput | raw patch sentinel 不存在；唯一 state 未被直接改写 |
| expected-red match | 声明 A，子进程以 A 类型非零退出 | 结构化成功 | `status=expected_red`、声明/实际类型和原退出码可核对 |
| expected-red mismatch | 声明 A，子进程以 B 类型或基础设施错误退出 | 非零 | 不含 expected-red 成功；保留真实失败分类 |
| expected-red unexpected pass | 声明失败，子进程退出 0 | 包装器退出 0 | `status=unexpected_green`，不输出 expected-red、不触发 CFM，由 TDD 设计层判断 |

### 集成与回归证据

- `tests/harness/command-safety-gateway.integration.ps1` 的首次 expected RED 摘要、最终 PASS 摘要和测试总数。
- `tests/harness/control-plane.integration.ps1` 的最终 PASS 摘要和测试总数。
- GTO 新 action 的合法更新、unknown field、unknown subtask、非法状态、write path 越界、写后验证失败等正反 fixture。
- Hook/网关热路径的静态或行为检查，证明没有 CFM、Git、网络与父目录扫描调用。
- `orchestrator_ctl.ps1 -Action validate` 在进入 `code_impl` 前证明 verification contract 六字段完整，在进入 `review` 前证明全部 evidence slots 已覆盖。

### 安装证据

- 隔离 CodexHome 初始 `hooks.json` 与 SHA-256，包含至少一个非托管字段和一个非本方案 Hook 条目。
- 首次安装后的结构化 diff：非托管内容深比较不变，只新增或更新稳定 managed id。
- 被替换旧内容的 SHA-256、对应内容寻址备份路径和备份内容哈希。
- machine-local receipt 的路径、managed id、源/目标哈希、备份引用与安装结果。
- 二次相同安装后的目标哈希、备份数量和 `updated=false` 或等价幂等信号。
- 测试结束后隔离 CodexHome 已清理的断言。

### 新进程与延迟证据

- 同一轮至少 60 次 gateway 调用均为独立 fresh process，输入为相同的 safe pass-through 最小 payload；至少 60 次 bare-Node baseline 也均为独立 fresh process，并使用同一计时 harness。
- 两组每次从创建进程前到读取合法输出并确认退出的耗时样本，或足以分别复算两个 p95 与差值的机器可读摘要。
- Node 版本、操作系统/PowerShell 基线、两组样本数、nearest-rank p95 计算方式、gateway p95、bare Node p95 与两者差值。
- `fresh_process_runtime_ok` 证明至少 60/60 gateway processes 与 60/60 bare-Node baseline processes 均正常启动、输出并退出，且 gateway 均解析 payload、输出合法响应。
- `latency_budget_ok` 证明 gateway p95 `<=120ms` 且 `gateway p95 - bare Node p95 <=25ms`；证据同时记录 bare Node p95 实测 `82.939ms`，说明旧绝对 `80ms` 会把宿主抖动误判为代码退化。不得把 warm process、复用进程、daemon、常驻服务、native binary 或剔除样本后的值作为证据。

### Review evidence 槽位映射

| 槽位 | 最低可接受内容 | 首要提供者 |
| --- | --- | --- |
| `repro_before_fix` | TEST-001 expected RED 的准确失败类型与最小回放范围 | TEST-001 |
| `pass_after_fix` | 新 integration 全部转绿的命令与短结果 | VERIFY-001 |
| `hit_proof_observed` | deny/updatedInput 在 sentinel 前出现，或 expected-red 输出机器状态 | VERIFY-001 |
| `relevant_regression_ok` | control-plane 相关回归通过的命令与短结果 | VERIFY-001 |
| `install_merge_backup_receipt_ok` | 非托管内容保留、备份和 receipt 的短证据 | VERIFY-001 |
| `fresh_process_runtime_ok` | 同轮至少 60/60 fresh gateway 有效响应，且 60/60 fresh bare-Node baseline 正常输出并退出 | VERIFY-001 |
| `latency_budget_ok` | 两组样本数、nearest-rank、gateway/bare p95、差值，以及 `<=120ms` / `<=25ms` 双门槛结果 | VERIFY-001 |

每个槽位值必须是非空短摘要，实际大输出留在原测试结果中；`state.json` 不保存完整 stdout、diff、prompt、chat 或第二份 report/package。

### 脏工作区与最终审查证据

- 初始 workspace：primary checkout、`main`、`HEAD=bebf35ff6501a92103f48f6b6bb48e9ade1040dc` 和 dirty paths 摘要。
- overlap 基线：
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`：`fa4eb743b07e5068f92f547d3808b3660d57736e6691856df4fa13476277deff`
  - `tests/harness/control-plane.integration.ps1`：`42f1318730c417e7371a23ba8fa2c9e36622e98fa443645258a76365f1e1e131`
- 每次写 overlap 前的新鲜 hash、差异归属和只做窄补丁的说明。
- 最终 changed files 清单、`git diff --check`、临时产物清理结果和人工 diff 审阅摘要。
- 独立 reviewer 的真实 `platform_agent_id`、`final/pass`、覆盖的最新 HEAD 或最终变更哈希、open finding 数与残余风险。

## 未决项

- 当前实现与验证证据为：gateway integration `27/27`，cleanup `6/6`、expected-red `6/6`、installer `2/2`；control-plane full regression `90/90`；fresh gateway/bare Node 各 `60/60`，性能双门槛通过。
- 当前 runtime 的 `deny` / `updatedInput` 精确响应结构仍须由 TEST-001 用真实最小 Hook payload 固定；若官方合同不能表达，任务按 stop condition 停止。
- 隔离 merge/backup/receipt/idempotence 已完成；真实 `~/.codex` 备份、安装、receipt 与 `/hooks` 精确 command hash 信任仍待主流程。当前不得表述为已安装、已激活或已信任。
- 一次破坏性 Red fixture 曾误删 4 个 untracked command-safety 文件；执行被冻结，文件依据 session 证据恢复，cleanup guard 与 teardown 加固后最终测试、文件哈希和 TEMP residue 检查通过。
- 残余风险：`systemTemp` 依赖当前进程环境；生产入口删除前重新验证 realpath/identity，测试只授权自身唯一 sentinel fixture。安装锁为协作式，非协作编辑器由最终写前哈希比较收窄。
- 工作区仍包含任务外既有 dirty 内容；这些内容不归本任务所有，也不由本任务清理。只有目标 overlap 的冻结哈希和窄补丁裁决已明确。
- `docs/ARCHITECTURE.md`、`docs/HOOKS.md`、`docs/CODEX_COMPAT.md` 当前为只读设计输入。若后续实现造成长期合同漂移，必须先由主协调器扩展 scope 和审查范围。

## 最终结论

当前结论：**实现与自动化验证已通过；真实用户级安装、`/hooks` 精确哈希信任和最终独立复审仍待主流程。**

目标 integration、control-plane regression、隔离安装与性能门槛已有通过证据；只有真实 `~/.codex` 安装完成备份与 receipt、用户完成 `/hooks` 精确 command hash 信任，并且独立 reviewer 覆盖最终 changed files 与最终内容哈希给出 `final/pass` 后，主协调器才可完成任务。安装回执不能替代人工信任。
