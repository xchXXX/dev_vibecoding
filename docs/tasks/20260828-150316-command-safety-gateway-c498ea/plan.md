# Codex Command Safety Gateway 方案

## 任务目标

在命令执行前消除可预测失败，降低 Command Failure Memory 新增真实失败，并保持低延迟、低维护复杂度。

本任务使用 `task_id=20260828-150316-command-safety-gateway-c498ea` 的 GTO v2 单控制面；`docs/ai/tasks/20260828-150316-command-safety-gateway-c498ea/state.json` 是唯一状态真源，本文只冻结可执行设计，不复制运行状态，也不代表实现已经完成。

## 背景与问题

当前仓库已有 Codex `PreToolUse` 最小接线，但它只围绕文档分流提供观测或提示，且现有脚本仍会在热路径调用 `git`。CFM 则是在命令已经失败后记录、查询和沉淀解决方案。两者之间仍缺少一个轻量、确定性、可回放的预执行入口，用于提前处理已经反复出现且可以高置信识别的失败族：

- 命令引用的必需路径不存在；
- PowerShell 把 `foreach` / `ForEach-Object` 结果直接接入脆弱管道；
- 未验证目标边界的原始递归清理；
- 绕过 GTO 控制器直接补丁 `state.json`；
- 测试声明 expected-red 后，把声明内失败、声明外失败和环境故障混为同一种成功。

方案必须同时证明两件不同的事：目标测试最终通过，以及新入口确实在真实命令执行前返回 `deny` / `updatedInput`，或 expected-red 包装器确实输出可机器判读的 `expected_red` 状态。仅有整套回归为绿不构成命中证明。

## 范围

本任务的正式写入范围与 `state.json.scope_in` 一致：

- `hooks/codex/command-safety/**`：无第三方依赖的 Node 网关、轻量 Hook 适配入口及受控包装器真源；
- `scripts/install-command-safety-gateway.ps1`：向指定 CodexHome 安装或更新本方案托管条目；
- `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`：增加 GTO 结构化 subtask 结果更新入口；
- `tests/harness/command-safety-gateway.integration.ps1`：命令回放、expected-red、安装与延迟验证；
- `tests/harness/control-plane.integration.ps1`：GTO 新 action 正反测试与现有控制面回归；
- `docs/tasks/20260828-150316-command-safety-gateway-c498ea/**`：本任务的人读方案、施工与验收合同；
- `docs/ai/tasks/20260828-150316-command-safety-gateway-c498ea/**`：仅由主协调器维护的 GTO 控制面文件。

DOC-001 只允许写本目录的 `plan.md`、`execution.md`、`acceptance.md`，不修改 Hook、脚本、测试、长期文档或 `state.json`。

## 非目标

- 不扫描磁盘、父目录、其他 clone 或其他 worktree，也不自动创建、切换、移动、删除或清理 worktree。
- Hook 热路径不读取 CFM，不运行 `git`，不扫描父目录，不访问网络。
- 不构建通用 shell parser，不完整解析 PowerShell 或 Bash 语法，不统一改造所有项目测试框架。
- 不把 hooks 当作完整 enforcement boundary，也不假设所有等价执行路径都会被同一种 Hook 覆盖。
- 不自动修复无法确定用户意图的命令；对已命中高风险族但修复意图不唯一的输入，返回 `deny` 或显式安全入口，不静默猜测。
- 不接管、删除、重排或覆盖用户已有的非本方案 Hook 条目。
- 不引入常驻服务、MCP server、新的包依赖或 CFM 热路径查询。
- 不提交、重置、还原、清理或归属当前工作区中既有的 dirty 内容。

## 约束与依赖

- 运行基线为 PowerShell 7 与本机可用 Node；Node 网关必须为无第三方依赖的短生命周期进程。
- Hook 适配层只负责读取 `PreToolUse` payload、调用网关并返回官方支持的结构化结果；分类和改写规则只在网关维护，安装器不复制规则正文。
- 未命中受支持错误族的安全命令必须原样放行。命中错误族后，只有唯一且可证明等价的改写才允许 `updatedInput`；其他情况使用 `deny` 并给出安全入口。
- expected-red 必须由包装器接管实际子进程与退出码；只有实际退出码和输出同时命中调用方事前声明的 `expected_exit_codes` 与 `expected_output_pattern`，才输出 `status=expected_red`。child marker 不受信任；底层命令意外退出 0 时输出 `status=unexpected_green`，类型/模式不匹配或基础设施真实失败保持非零。
- CFM 继续只处理真实未知失败。符合声明的 expected-red 与 `unexpected_green` 都不写 CFM；声明外或基础设施真实失败仍进入既有 `record-failure -> query-before-retry -> retry -> record-success` 闭环。
- 安装器只管理带稳定 managed id 的自身条目；写入前验证 JSON、保留所有非托管内容、为被替换内容生成内容寻址备份，并在 CodexHome 下写 machine-local receipt。没有实际内容变化时不得重复制造备份。
- GTO 结果写回只能通过带 `subtask_id`、状态校验、未知字段拒绝、原子写入并随后执行 `validate` 的结构化 action；不得 raw `apply_patch` 唯一状态真源。
- 当前 workspace 为 `main` primary checkout，冻结 `HEAD=bebf35ff6501a92103f48f6b6bb48e9ade1040dc`，存在大量任务外 dirty 路径。两个后续实施重叠文件已由主协调器裁决为“仅在冻结 baseline hash 后窄补丁”：
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`: `fa4eb743b07e5068f92f547d3808b3660d57736e6691856df4fa13476277deff`
  - `tests/harness/control-plane.integration.ps1`: `42f1318730c417e7371a23ba8fa2c9e36622e98fa443645258a76365f1e1e131`
- 写入上述重叠文件前必须重新计算 SHA-256；若与冻结值不一致且变化无法归属，立即停止，不覆盖现有改动。
- 以下任一条件触发停止并交回主协调器裁决：官方 Hook 合同不能表达 `deny` / `updatedInput`；当前 runtime 禁用 hooks 且需扩大系统配置权限；目标文件出现无法安全合并的语义冲突；同一轮至少 60 个 fresh gateway 与 60 个 fresh bare-Node 基线回放中，gateway p95 超过 `120ms` 或 `gateway p95 - bare Node p95` 超过 `25ms`，且无法在不引入 daemon、常驻服务或 native binary 的前提下降低。

## 方案摘要

### 1. Hook 适配层边界

`PreToolUse` 适配层读取现有 `tool_name`、`tool_input` 与 `cwd` payload，并把标准化后的最小输入交给 Node 网关。它自身不运行 `git`、不查 CFM、不扫描路径树、不维护错误族正则。

适配层只负责三种响应：

- `allow`：未命中受支持错误族，保持 `tool_input` 字节语义不变；
- `deny`：命中确定风险但不存在唯一安全改写，返回稳定 reason code 与安全入口提示；
- `updatedInput`：命中确定风险且存在唯一、可审计的安全包装入口，返回改写后的输入。

网关异常、payload 缺字段或响应无法解析时不得伪报已防护；集成测试必须固定实际合同。Hook 仍只是前置 guardrail，最终 enforcement 继续由包装器、控制器、测试和人工审查共同承担。

### 2. Node 网关边界

Node 网关是无第三方依赖、单次 stdin/stdout、无持久状态的判定器。它只覆盖冻结回放矩阵中的高频错误族，以稳定 reason code 输出结果；不得读 CFM、调用 Git、扫描父目录、访问网络或在判定阶段写文件。

分类顺序以“更具体且更危险的规则优先”为原则：raw GTO state patch、raw recursive cleanup、missing path、PowerShell foreach pipeline、expected-red 包装请求，最后是 safe pass-through。规则只识别足够确定的输入，不把模糊命令改写成推测意图。

### 3. 安全包装器边界

- `expected-red`：要求调用方在执行前声明期望类型、退出码集合与可信输出模式；包装器执行真实子进程并保留 stdout/stderr 与原始退出码。退出码和模式同时匹配时输出 `status=expected_red`；底层退出 0 时输出 `status=unexpected_green`；marker 伪装、模式不匹配或基础设施故障保持非零。
- `contained cleanup`：要求显式根目录与目标目录，先做规范化和 containment 检查，再由受控入口执行；禁止未验证目标的原始递归删除。
- `project verify`：先检查候选路径存在，再调用项目内已批准的测试、构建或验证入口；不会通过扫描磁盘寻找替代仓库。
- `GTO update`：由 `orchestrator_ctl.ps1` 的结构化 action 处理单个 `subtask_id` 的允许字段，写后立即验证；网关只负责阻止 raw patch 并指向该入口。

包装器是命令执行边界，Node 网关本身不代替它们执行有副作用的操作。

### 4. 安装器边界

`scripts/install-command-safety-gateway.ps1` 接收显式或按既有规则解析的 CodexHome。隔离 CodexHome 验证已经完成；真实 `~/.codex` 安装仍是主流程待办。安装器必须：

1. 读取并验证目标 `hooks.json`；
2. 按稳定 managed id 查找自身条目，只新增或更新该条目；
3. 保留非托管字段、事件与条目原样，不接管用户配置；
4. 仅在内容变化前写入以旧内容 SHA-256 命名或关联的可恢复备份；
5. 以临时文件加原子替换方式提交；
6. 写 machine-local receipt，至少记录目标路径、managed id、源/目标哈希、备份引用和安装结果；
7. 对相同输入重复执行时保持幂等，不新增无意义备份。

安装器不自动修改仓库外其他配置，不跨 CodexHome 扫描，也不在 Hook 热路径运行。真实安装完成后仍必须由用户通过 `/hooks` 核对 managed id、绝对 `commandWindows` 与精确 command hash 后人工信任；安装成功回执不能替代人工信任。

### 5. 最小回放矩阵

| 场景 | 最小 payload / 前置 | 期望判定 | 直接命中证明 |
| --- | --- | --- | --- |
| safe pass-through | `tool_name=Bash`，命令不命中任一错误族 | `allow`，输入不变 | 返回对象明确为 allow，原输入深比较相等 |
| missing path | 命令引用 fixture 中明确不存在的必需路径 | `deny`，不给真实命令执行机会 | deny reason code；子进程 sentinel 不存在 |
| PowerShell foreach pipeline | `foreach (...) { ... } | Sort-Object` 或等价未物化管道 | `deny` 并提示先物化结果 | deny reason code；子进程 sentinel 不存在 |
| raw recursive cleanup | 未提供已解析 containment 根的 `Remove-Item -Recurse` / 等价递归删除 | `deny` 或改写到 contained cleanup | deny/updatedInput reason code；原始删除入口未运行 |
| raw GTO state patch | 命令或 `apply_patch` 直接修改目标 `state.json` | `deny` 或改写到结构化 GTO action | deny/updatedInput reason code；raw patch sentinel 不存在 |
| expected-red match | 事前声明失败类型，子进程以该类型非零退出 | 包装器退出 0，输出 `status=expected_red` | 同一输出包含声明类型、实际类型和原始非零退出码 |
| expected-red mismatch | 事前声明 A，子进程以 B 或环境错误非零退出 | 包装器保持非零，不输出成功状态 | 输出 `status=unexpected_failure` 或等价稳定状态 |
| expected-red unexpected pass | 事前声明失败，但子进程退出 0 | 包装器退出 0，输出 `status=unexpected_green` | 不输出 `expected_red`，不触发 CFM，由 TDD 设计层判断 |
| installer merge | 隔离 CodexHome 已有非托管 hooks 内容 | 仅自身 managed id 增量变化 | before/after 结构比较、内容寻址备份和 receipt 同时存在 |

### 6. 延迟预算

性能验收必须在同一轮、同一宿主环境与同一计时 harness 中至少采集两组独立冷启动样本：60 个 fresh gateway process，以及 60 个 fresh bare-Node baseline process。gateway 组使用同一个 safe pass-through 最小 payload，从创建进程前计时到读取完整结构化响应并确认退出；bare-Node 组只测最小 Node 启动、输出与退出的宿主基线。两组都不预热、不复用进程、不剔除任何样本，并分别按 nearest-rank 计算 p95。

双门槛同时成立才算通过：gateway p95 `<= 120ms`，且 `gateway p95 - bare Node p95 <= 25ms`。实测 bare Node p95 为 `82.939ms`，说明原先绝对 `80ms` 门槛会把宿主启动抖动误判为网关代码退化；新口径用 `120ms` 绝对硬上限防止总体不可接受，同时用 `25ms` 增量上限约束网关自身开销。

记录证据时保存两组样本数、每次耗时或可复核摘要、两个 p95、p95 差值、Node 版本与命令名；临时目录和捕获文件必须由同一测试在 `finally` 中清理。若任一门槛超预算，先移除热路径 I/O 与不必要启动层级，不以 daemon、常驻服务或 native binary 绕过约束。

## 风险与回退

- **Hook 合同漂移**：先以最小 payload 固定当前 runtime 的 `deny` / `updatedInput` 结构；若无法表达，触发停止条件，不以退出码冒充强阻断。
- **误拦安全命令**：safe pass-through 做原输入深比较；规则只覆盖冻结高置信族，出现不确定分类时优先返回显式安全入口。
- **expected-red 吞掉真实故障**：匹配必须基于事前声明与稳定分类；`unexpected_green` 使用退出 0 的结构化状态交给 TDD 设计层判断，且不触发 CFM；不匹配和基础设施真实失败保持非零。
- **全局配置损坏**：所有安装验证先在隔离 CodexHome；已授权的真实 `~/.codex` 写入前校验 JSON、创建内容寻址备份，写后重新解析并依 receipt 校验，最终由用户通过 `/hooks` 人工信任。
- **dirty overlap 覆盖用户改动**：每次写重叠文件前重算已冻结哈希，只做窄 `apply_patch`；变化无法归属时停止。
- **性能预算失败**：保留同轮至少 60 个 fresh gateway 与 60 个 fresh bare-Node 的完整证据并停止发布；分别判断宿主基线与网关增量，不把 bare Node 自身抖动误判为代码退化。回退到未安装状态，不引入 daemon、常驻进程或 native binary。
- **批次回退**：任一批次失败即停止依赖批次；不使用 `git reset --hard`、`git checkout --` 或自动清理，已有用户内容不回退、不覆盖。

## 验收标准

1. 路径缺失、PowerShell foreach 管道、危险递归清理和 raw GTO state patch 在真实命令执行前被确定性拒绝，或被路由到冻结的安全入口。
2. expected-red 仅在事前声明的退出码与可信输出模式同时命中时输出 `status=expected_red`；意外转绿时输出 `status=unexpected_green`；marker 伪装、声明外失败以及环境或基础设施真实失败仍非零退出。
3. safe pass-through 保持原输入不变，并且不访问 CFM、Git、网络或父目录扫描。
4. 安装器以跨进程锁和写前哈希比较保护 `hooks.json`，保留非托管内容，变更前创建内容寻址备份，写 machine-local receipt，并对相同输入保持幂等；真实 `~/.codex` 安装与 `/hooks` 精确哈希信任仍由主流程完成。
5. `tests/harness/command-safety-gateway.integration.ps1` 与 `tests/harness/control-plane.integration.ps1` 通过；隔离 CodexHome 的 merge/backup/receipt 证据齐备。
6. 同一轮至少 60 个 fresh gateway 与 60 个 fresh bare-Node 基线均完整执行并分别使用 nearest-rank；gateway p95 不超过 `120ms`，且 `gateway p95 - bare Node p95` 不超过 `25ms`。
7. `repro_before_fix`、`pass_after_fix`、`hit_proof_observed`、`relevant_regression_ok`、`install_merge_backup_receipt_ok`、`fresh_process_runtime_ok`、`latency_budget_ok` 七个 review evidence 槽位均由已完成执行型或测试型子任务回填。
8. 独立 reviewer 审阅最终 changed files、命令证据、dirty workspace 边界和残余风险，并给出 `final/pass`；没有 final/pass 不得完成任务。

## DOC-003 实施同步

- command-safety gateway integration 已通过 `27/27`；其中 cleanup `6/6`、expected-red `6/6`、installer `2/2`，60 个 fresh gateway 与 60 个 bare-Node 基线满足延迟双门槛。
- control-plane full regression 已通过 `90/90`。
- 一次破坏性 Red fixture 曾误删 4 个 untracked command-safety 文件；执行立即冻结，文件依据 session 证据恢复，cleanup 调用闸与 teardown 随后加固，最终测试、哈希与 TEMP residue 检查全部通过。
- 残余风险：`systemTemp` 来源依赖当前进程环境；测试只授权自身唯一命名且带 sentinel 的 TEMP fixture。安装锁是协作式，非协作外部编辑器由最终写前哈希检查收窄。
- 当前真实用户级安装、`/hooks` 精确 command hash 信任和独立最终复审仍待主流程，不能表述为已激活。

## 阶段划分

1. `planning`：DOC-001 冻结本方案、施工和验收合同；不进入代码实现。
2. `test_sync`：TEST-001 先补最小回放并执行明确声明的 expected RED。
3. `code_impl`：IMPL-001 实现 Hook/网关/包装器/安装器；IMPL-002 实现 GTO 结构化状态更新，两者均依赖 TEST-001。
4. `review` 前验证：VERIFY-001 执行目标集成、control-plane 回归、隔离安装，以及同一轮至少 60 个 fresh gateway + 60 个 fresh bare-Node 基线，并回填全部 evidence slots。
5. `review`：REVIEW-001 独立复审；finding 返回原实现者，原 reviewer 做范围化复审，最后覆盖最终 HEAD 或最终变更哈希。

阶段推进只由主协调器更新 `state.json`。进入 `code_impl` 前必须验证根层 verification contract 六字段齐全；进入 `review` 前必须验证七个 evidence slots 已被完成子任务覆盖。

## 需先同步的核心文档与测试

代码实现前必须先完成与本批次直接相关的同步：

- 本任务三件套：`docs/tasks/20260828-150316-command-safety-gateway-c498ea/plan.md`、`execution.md`、`acceptance.md`；
- Hook 入口说明：`hooks/codex/README.md`，由后续获授权批次在实现前同步到新网关边界；
- 命令安全回放：`tests/harness/command-safety-gateway.integration.ps1`，先记录可解释的 expected RED；
- GTO action 合同与回归：`tests/harness/control-plane.integration.ps1`，先冻结正反行为再实现。

`docs/ARCHITECTURE.md`、`docs/HOOKS.md`、`docs/CODEX_COMPAT.md` 是本轮设计的只读真源，但当前不在 `state.json.scope_in` 的写入范围内。若实现导致这些长期文档产生实质漂移，必须先由主协调器扩展 scope/write paths 与审查范围；DOC-001 不擅自修改。
