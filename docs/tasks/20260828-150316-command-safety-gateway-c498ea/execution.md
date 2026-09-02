# Codex Command Safety Gateway 施工计划

> 本施工计划继续 `task_id=20260828-150316-command-safety-gateway-c498ea`，不重新初始化任务，不建立第二控制面。阶段、子任务状态和最终结果只由主协调器写入 `docs/ai/tasks/20260828-150316-command-safety-gateway-c498ea/state.json`。

**Goal:** 在真实命令执行前，用低延迟网关阻止或安全路由已知高频失败族，并保持 expected-red、安装合并、GTO 状态更新和 CFM 的边界可验证。

**Architecture:** Codex `PreToolUse` 适配层把最小 payload 交给无第三方依赖的 Node 网关；网关只做纯判定并返回 `allow` / `deny` / `updatedInput`，有副作用的动作由 expected-red、contained cleanup、project verify 或 GTO 控制器包装入口执行；安装器只托管稳定 id 的自身 Hook 条目。

**Tech Stack:** Markdown、Node 标准库、PowerShell 7、Codex `PreToolUse`、自包含集成测试、GTO v2 单控制面。

**Spec:** `docs/tasks/20260828-150316-command-safety-gateway-c498ea/plan.md`

## 施工目标

用最小、分批、可回放的改动完成以下闭环：

1. 先冻结方案、施工与验收合同；
2. 先用最小 payload 证明现有入口缺少目标能力；
3. 分别实现 Hook/网关/包装器/安装器与 GTO 结构化更新；
4. 用真实命令前 sentinel、expected-red 状态和隔离安装证明修复点确实命中；
5. 用 control-plane 回归、同轮至少 60 个 fresh gateway + 60 个 fresh bare-Node 基线和独立最终复审完成验收。

## 前置条件

- 用户已批准设计，GTO `current_phase=planning`；DOC-001 完成前不得派发 TEST-001，TEST-001 的预期 RED 完成前不得进入实现。
- `state.json.verification_contract` 的六字段已经冻结：`minimal_repro`、`hit_proof`、`diagnostic_checks`、`acceptance_checks`、`non_goals`、`review_evidence`。实施不得在子任务内静默改写。
- 当前 checkout 为 `main` primary，冻结 `HEAD=bebf35ff6501a92103f48f6b6bb48e9ade1040dc`；工作区既有 dirty 内容属于用户，禁止覆盖、清理、重置或自动归属。
- 写 `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1` 前，当前 SHA-256 必须仍为 `fa4eb743b07e5068f92f547d3808b3660d57736e6691856df4fa13476277deff`；写 `tests/harness/control-plane.integration.ps1` 前，当前 SHA-256 必须仍为 `42f1318730c417e7371a23ba8fa2c9e36622e98fa443645258a76365f1e1e131`。不一致且无法归属时停止。
- 平台必须提供可回放的 `PreToolUse` payload，并确认当前合同能返回 `deny` / `updatedInput`；若不能表达，触发停止条件。
- Node 与 PowerShell 7 必须可用；不通过安装新包或启动常驻服务解决依赖。
- 所有隔离 CodexHome、临时 hooks 配置、sentinel 和 stdout/stderr 捕获必须由创建它们的同一测试在 `finally` 中清理。

## 执行顺序

1. **DOC-001**：只新增三份任务文档，运行字段校验并与 `state.json` 逐项核对。
2. **TEST-001**：新增命令安全集成测试，覆盖 safe、四类 deny/route、expected-red 正反、安装 merge/backup/receipt 和延迟；执行前明确声明 expected RED 类型，只运行新测试。
3. **IMPL-001**：实现 Node 网关、Hook 适配、expected-red/contained cleanup/project verify 包装器和安装器，使 TEST-001 中非 GTO 用例转绿。
4. **IMPL-002**：在冻结 overlap hash 后，为 GTO 控制器增加结构化结果更新 action，并补 control-plane 正反测试。IMPL-001 与 IMPL-002 均依赖 TEST-001；主协调器可在确认写入路径不重叠后并行派发。
5. **VERIFY-001**：在新进程和隔离 CodexHome 中运行目标集成、相关回归，以及同一轮至少 60 个 fresh gateway + 60 个 fresh bare-Node 基线，回填七个 review evidence 槽位。
6. **REVIEW-001**：由真实身份不同的独立 reviewer 审查最终 changed files、最新 HEAD 或最终变更哈希、命中证据、脏工作区边界与残余风险。
7. reviewer 如提出 finding，按稳定 `finding_id` 返回原实现者；原 reviewer 复审 fix delta。全部关闭后再做 `final/pass`。

依赖图固定为 `DOC-001 -> TEST-001 -> {IMPL-001, IMPL-002} -> VERIFY-001 -> REVIEW-001`，不得跨过测试或证据闸门直接实现、复审或封账。

## 文档先行清单

- `docs/tasks/20260828-150316-command-safety-gateway-c498ea/plan.md`：目标、范围、非目标、Hook/网关/安装器边界、回放矩阵、延迟预算和停止条件。
- `docs/tasks/20260828-150316-command-safety-gateway-c498ea/execution.md`：依赖顺序、写入范围、验证命令、回退与审查路由。
- `docs/tasks/20260828-150316-command-safety-gateway-c498ea/acceptance.md`：验收门槛、矩阵结果与 review evidence 槽位。
- `hooks/codex/README.md`：由后续有写权限的实施批次先同步现有最小 Hook 到新“适配层 + Node 网关 + 安全包装器”边界，再写生产实现。

`docs/ARCHITECTURE.md`、`docs/HOOKS.md`、`docs/CODEX_COMPAT.md` 仅作为 DOC-001 设计输入；它们当前不在任务 `scope_in`。若实现要求修改，主协调器必须先扩展 scope/write paths 与 reviewer 范围。

## 测试同步清单

TEST-001 在 `tests/harness/command-safety-gateway.integration.ps1` 中先冻结以下行为：

- safe pass-through：响应为 allow，`tool_input` 深比较不变；
- missing path：deny，实际命令 sentinel 未创建；
- PowerShell foreach pipeline：deny，提示先物化结果，sentinel 未创建；
- raw recursive cleanup：deny 或 updatedInput 到 contained cleanup，原始删除未执行；
- raw GTO state patch：deny 或 updatedInput 到结构化 action，raw patch 未执行；
- expected-red match：实际非零类型与声明一致，包装器输出 `status=expected_red` 并结构化成功；
- expected-red mismatch / infrastructure failure：包装器保持非零，不伪报 expected-red；
- expected-red unexpected pass：包装器 `exit 0 + status=unexpected_green`，不触发 CFM，由 TDD 设计层判断而不伪报 expected-red；
- installer merge/backup/receipt：保留非托管内容，只更新稳定 managed id，备份与 receipt 可核对；
- installer idempotence：相同输入二次执行不增加备份，目标哈希稳定；
- 性能双基线：同一轮至少运行 60 个 fresh gateway 与 60 个 fresh bare-Node process；两组都不预热、不复用、不剔除样本，分别按 nearest-rank 计算 p95；gateway p95 `<=120ms` 且 `gateway p95 - bare Node p95 <=25ms`。记录 bare Node p95 实测 `82.939ms` 作为原绝对 `80ms` 会误判宿主抖动的依据。

IMPL-002 在 `tests/harness/control-plane.integration.ps1` 中先补：

- 指定 `subtask_id` 的合法结果更新成功；
- 不存在的 subtask、非法状态、未知字段、越界 changed files 被拒绝；
- 写入后 schema 与控制器 `validate` 均通过；
- 验证失败时唯一 `state.json` 不留下半写状态；
- 既有 control-plane 回归保持通过。

首次 TEST-001 执行前必须声明“这是最小目标测试的 TDD expected RED，预期失败为 missing implementation / missing gateway entry”。只有实际失败类型与声明一致时不触发 CFM；任何命令、环境或基础设施意外失败仍立即进入命令失败闭环。

## 实施批次

### 批次 A：DOC-001 文档合同

- 只写本任务 `plan.md`、`execution.md`、`acceptance.md`。
- 收口条件：三份文档必填章节完整；目标、范围、非目标、停止条件、subtask 顺序、verification contract 与 `state.json` 一致。
- 本批不修改 `state.json`；结果由主协调器通过控制面回填。

### 批次 B：TEST-001 预期 RED

- 新增 `tests/harness/command-safety-gateway.integration.ps1`。
- 使用 fixture 内最小 payload 与真实命令 sentinel；不得调用真实递归清理或修改真实 CodexHome。
- 收口条件：只运行新测试，实际 RED 精确落在缺少新入口，不是 quoting、Node 缺失、权限或临时目录清理失败。

### 批次 C：IMPL-001 Hook、网关、包装器与安装器

- 在 `hooks/codex/command-safety/**` 实现单一规则真源和受控入口；同步 `hooks/codex/README.md`。
- 在 `scripts/install-command-safety-gateway.ps1` 实现稳定 managed id、跨进程锁、非托管内容保留、内容寻址备份、原子写入、receipt、写前哈希检查和幂等；隔离验证完成后，真实 `~/.codex` 安装与 `/hooks` 精确 command hash 信任仍交由主流程。
- 网关热路径不访问 CFM、Git、网络或父目录，不引入包依赖。
- 收口条件：TEST-001 中非 GTO 用例全部转绿，命中证明不是仅靠最终退出码推断。

### 批次 D：IMPL-002 GTO 结构化更新

- 先核对 overlap hash，再窄补丁 `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1` 与 `tests/harness/control-plane.integration.ps1`。
- action 必须以 `subtask_id` 定位、仅接收 allowlist 字段、校验状态转换与 write paths，临时写后验证再原子替换。
- 不提供 raw state patch 兼容分支，不建立第二状态文件。
- 收口条件：GTO 正反测试和 control-plane 相关回归通过。

### 批次 E：VERIFY-001 与 REVIEW-001

- VERIFY-001 只读执行目标集成、回归、隔离安装和性能测试，并回填全部 evidence slots。
- REVIEW-001 只读审查，必须覆盖 DOC-001 之后所有 `result.changed_files`；dirty checkout 下以最新 HEAD 或控制器计算的最终内容哈希为覆盖凭据。
- 收口条件：全部 evidence slots 非空、finding 关闭、独立 reviewer 给出 `final/pass`。

## 每批写入范围

- DOC-001：`docs/tasks/20260828-150316-command-safety-gateway-c498ea/plan.md`、`execution.md`、`acceptance.md`。
- TEST-001：`tests/harness/command-safety-gateway.integration.ps1`。
- IMPL-001：`hooks/codex/command-safety/**`、`hooks/codex/README.md`、`scripts/install-command-safety-gateway.ps1`。
- IMPL-002：`skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`、`tests/harness/control-plane.integration.ps1`。
- VERIFY-001：无生产文件写入；只把短证据交回主协调器写入 `state.json.subtasks[].result.review_evidence`。
- REVIEW-001：无生产文件写入；只把 verdict、findings 和覆盖摘要交回主协调器写入唯一 `state.json`。

任何额外文件或语义范围都必须先由主协调器更新 `scope_in`、subtask `write_paths` 与审查范围；子任务不得顺手修改。

## 验证命令

DOC-001 文档阶段：

```powershell
pwsh -NoProfile -File scripts/validate-plan-docs.ps1 -Json
pwsh -NoProfile -File scripts/validate-doc-routing.ps1 -Json
pwsh -NoProfile -File skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate -TaskId 20260828-150316-command-safety-gateway-c498ea -Json
```

TEST-001 首次预期 RED（执行前按“测试同步清单”声明 expected RED）：

```powershell
pwsh -NoProfile -File tests/harness/command-safety-gateway.integration.ps1
```

实现与最终验证：

```powershell
pwsh -NoProfile -File tests/harness/command-safety-gateway.integration.ps1
pwsh -NoProfile -File tests/harness/control-plane.integration.ps1
pwsh -NoProfile -File skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate -TaskId 20260828-150316-command-safety-gateway-c498ea -Json
```

最终还必须执行：

- 在隔离 CodexHome 对 `hooks.json` 做 merge/backup/receipt/idempotence 验证；
- 在同一轮、同一计时 harness 中至少运行 60 个 fresh gateway 与 60 个 fresh bare-Node process，分别按 nearest-rank 计算 p95，并断言 gateway p95 `<=120ms`、`gateway p95 - bare Node p95 <=25ms`；
- 核对性能实现没有引入 daemon、常驻服务或 native binary；
- 检查 Hook 热路径未引用 CFM、`git`、网络或父目录扫描入口；
- 对最终 changed files 执行 `git diff --check` 与人工 diff 审阅；
- 确认临时目录、sentinel 和捕获文件均已清理；
- 由独立 reviewer 核对最新 HEAD 或最终内容哈希。

## 回退方案

- 任一批次失败，停止其依赖批次，保留最小复现、错误签名和必要短证据；不自动继续扩大实现。
- 不使用 `git reset --hard`、`git checkout --`、递归清理或覆盖式复制回退用户工作区。
- overlap hash 变化无法归属时不写目标文件，交回主协调器裁决。
- Hook 合同不能表达 `deny` / `updatedInput` 时停止，不用退出码或提示文本冒充已阻断。
- 安装验证失败时只影响隔离 CodexHome，并由测试 `finally` 清理；隔离验证已经通过，但当前真实 `~/.codex` 尚未由本子任务写入，后续仍须写前备份、写后 receipt 校验，并由用户通过 `/hooks` 核对精确 command hash 后人工信任。
- 真实安装后如需恢复，使用 receipt 指向的内容寻址备份，并先核对当前目标哈希，避免覆盖安装后的用户新改动。
- 性能超预算时停止发布，保留 fresh-process 证据；不引入常驻服务规避预算。
- GTO 更新 action 写后验证失败时不得替换原 `state.json`，不保留临时状态或双轨兼容文件。

## DOC-003 执行结果同步

- gateway integration：`27/27`；cleanup `6/6`、expected-red `6/6`、installer `2/2`。
- control-plane full regression：`90/90`。
- fresh-process：gateway `60/60`、bare Node `60/60`；gateway p95 `81.900ms`、bare p95 `79.214ms`、overhead `2.686ms`；TEMP residue `0`。
- 破坏性 Red fixture 曾误删 4 个 untracked command-safety 文件；施工随即冻结，按 session 证据恢复后加固了 TEMP-only cleanup、realpath/identity/sentinel guard 和 suite teardown，最终全量回归通过。
- 剩余执行项：真实用户级 `~/.codex/hooks.json` 安装、`/hooks` 精确 hash 信任与最终独立复审。文档同步不代表 Hook 已安装或已激活。
- 残余风险：system TEMP 取自当前进程环境；安装锁只协调本安装器实例，非协作编辑由写前哈希比较 fail closed。

## 审查与返工路径

1. 实施者按各自 write paths 完成变更并提交短结果与验证证据，不自行写第二份 report。
2. VERIFY-001 回填七个证据槽：`repro_before_fix`、`pass_after_fix`、`hit_proof_observed`、`relevant_regression_ok`、`install_merge_backup_receipt_ok`、`fresh_process_runtime_ok`、`latency_budget_ok`。
3. 独立 REVIEW-001 对最终文件集合做 `task` / `final` review；reviewer 的真实 `platform_agent_id` 必须不同于被审实现者。
4. finding 使用稳定 `finding_id`，记录路径、严重级别、证据、状态和 fix round，并沿 lineage 返回原实现者。
5. 返工只处理 finding 与必要 fix delta；原 reviewer 复审。同一 finding 最多三轮。
6. changed paths 或语义影响超出原 finding 时必须记录原因并升级审查范围，不得伪装为局部 re-review。
7. 任何文档或代码在 final review 后变化，旧 `final/pass` 失效，必须重新计算最终覆盖并复审。
8. 只有所有 evidence slots 被覆盖、finding 已关闭且独立 reviewer 对最新 HEAD 或最终变更哈希给出 `final/pass`，主协调器才可把任务标记 completed。
