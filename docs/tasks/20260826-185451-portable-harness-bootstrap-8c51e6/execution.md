# 跨机器 Harness 动态路径与 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用一个安全、幂等的 PowerShell bootstrap 消除活动态机器绝对路径，并生成可由 doctor 验证的本机 Codex 全局入口。

**Architecture:** 路径解析集中在共享 helper；bootstrap 只编排 managed AGENTS、sync、rules 和 doctor；rules 模型区分内部绝对路径与 tracked 显示路径。所有行为通过临时仓库和临时 `CODEX_HOME` 集成测试验证。

**Tech Stack:** PowerShell 7、JSON、Markdown、现有 harness scripts/tests。

**Spec:** `docs/tasks/20260826-185451-portable-harness-bootstrap-8c51e6/plan.md`

## Global Constraints

- 不扫描磁盘，不自动同步 `D:/prj/dev_vibecoding`。
- 正式仓库内容不写用户名、盘符或本机绝对 harness 根。
- 未托管非空全局 AGENTS 默认拒绝覆盖；force 前必须备份。
- 生产代码前必须观察对应行为测试因功能缺失而失败。
- 不自动 commit、push 或清理用户既有未提交改动。

## 施工目标

按 `doc_sync → test_sync → code_impl → review` 顺序交付机器无关模板、bootstrap、统一路径解析、doctor 扩展和逻辑 rules registry，并在当前机器完成一次可恢复的全局入口迁移。

## 前置条件

- 完整读取本任务 `state.json`、本方案和验收文档。
- 每个执行型或审查型 subtask 必须先读自己的 `read_paths`，只写 `write_paths`。
- 进入 `code_impl` 前运行 orchestrator `validate`，确认 `verification_contract` 六项完整。
- 当前工作区保持原有未提交内容；若目标文件出现任务外并发修改则停止。

## 执行顺序

1. 派 `DOC-PORTABILITY-002` 同步文档和 managed 模板。
2. 派 `TEST-BOOTSTRAP-003` 写真实行为测试，运行并记录预期 RED。
3. 验证任务状态后推进到 `code_impl`，派 `IMPL-BOOTSTRAP-004` 写最小实现。
4. 运行 GREEN 和完整回归，在当前机器以 force 迁移全局 AGENTS。
5. 推进到 `review`，派 `REVIEW-PORTABILITY-005` 独立复验并回填验收。

## 文档先行清单

- `templates/codex/AGENTS.global.md`：managed marker、机器无关协作约束、单一 `{{HARNESS_ROOT}}`。
- `AGENTS.md`：只声明 bootstrap 与规则装配入口，不增加本机绝对路径。
- `docs/INSTALL.md`：新机 clone 后的一条 bootstrap 命令、force 行为、环境变量覆盖。
- `docs/CODEX_COMPAT.md`：根选择、receipt、doctor issue 和 rules 显示路径合同。
- `docs/PROJECT_TEMPLATE.md`：消费项目显式使用选定 global rules root，不复制机器路径。
- `tests/harness/README.md`：新增测试入口与临时文件清理说明。

## 测试同步清单

### Task 1：Bootstrap 行为合同

**Files:**

- Create: `tests/harness/bootstrap-local.integration.ps1`
- Consumes: `scripts/bootstrap-local.ps1`
- Produces: `Test-ExplicitHarnessRootWins`、`Test-EnvironmentHarnessRootWins`、`Test-ScriptRootFallback`、`Test-UnmanagedAgentsRefusesOverwrite`、`Test-ForceBackupAndIdempotence`、`Test-InvalidRootFails`

- [ ] 写测试支架，在系统临时目录复制最小 harness fixture，并在 `finally` 清理 fixture、临时 `CODEX_HOME` 和环境变量。
- [ ] 用两个不同 fixture 根设置冲突输入，断言 `-HarnessRoot` 选择结果为第一个 fixture 的 canonical path。
- [ ] 省略显式根并设置 `AI_HARNESS_ROOT`，断言选择环境变量根；随后清空变量，断言使用脚本根。
- [ ] 创建未托管非空 `AGENTS.md`，断言默认退出非零、issue 为 `global_agents_unmanaged`、原内容 SHA-256 不变。
- [ ] 使用 `-ForceGlobalAgents`，断言备份存在、目标含 marker 和选定根；再次运行断言目标 SHA-256 不变且备份数量不增加。
- [ ] 传入缺少 `rules/registry/RULES_ENTRY.md` 的目录，断言 issue 为 `harness_root_invalid` 且不写全局文件。
- [ ] 运行测试并确认因 `scripts/bootstrap-local.ps1` 缺失而 RED，而不是 fixture 或语法错误。

Run: `pwsh -NoProfile -File tests/harness/bootstrap-local.integration.ps1`

Expected RED: 至少 1 项失败，明确指出 bootstrap 入口或预期 issue 尚不存在；测试支架清理完成。

### Task 2：Rules 显示路径合同

**Files:**

- Modify: `tests/harness/rules-index.integration.ps1`
- Consumes: `scripts/generate-rules-index.ps1`、`scripts/validate-rules.ps1`
- Produces: `Test-TrackedIndexUsesLogicalRoots`、`Test-ExplicitGlobalRootOrderIsStable`

- [ ] 在不同临时绝对根生成同构 rules registry，断言两份 `repo_root` 都是字面量 `<repo-root>`。
- [ ] 传两个显式 global roots，断言 `global_rules.searched` 使用 `<global-rules-root:1>`、`<global-rules-root:2>` 且导入顺序稳定。
- [ ] 断言 project scope 仍不被外部 global root 导入，local/global/resolved 数量符合手工 fixture。
- [ ] 运行测试并确认当前绝对 `repo_root` 使新用例 RED。

Run: `pwsh -NoProfile -File tests/harness/rules-index.integration.ps1`

Expected RED: 新逻辑根用例失败；现有用例保持通过。

### Task 3：全局入口与 Windows 合同

**Files:**

- Modify: `tests/harness/windows-command-guardrails.contract.ps1`
- Modify: `tests/harness/README.md`
- Consumes: managed 全局 `AGENTS.md`
- Produces: managed marker、旧用户路径禁止和动态 harness 根合同

- [ ] 将测试从六个用户文案短语扩展为 marker、选定根存在、`72385` 不存在和 `C:\Users\<literal-user>` 不存在。
- [ ] 保留 `CODEX_HOME` 优先、`USERPROFILE/.codex` 回退及原有 Windows 命令安全断言。
- [ ] 在本机迁移前运行，确认旧全局文件使新增用例 RED，其他基线保持通过。

Run: `pwsh -NoProfile -File tests/harness/windows-command-guardrails.contract.ps1`

Expected RED: managed marker 或旧路径断言失败。

## 实施批次

### Task 4：共享路径解析与 Bootstrap 最小实现

**Files:**

- Create: `scripts/path-resolution.common.ps1`
- Create: `scripts/bootstrap-local.ps1`
- Modify: `scripts/sync-codex.ps1`
- Modify: `scripts/doctor-core.ps1`

**Interfaces:**

```powershell
Resolve-HarnessRoot -ExplicitRoot <string> -EnvironmentRoot <string> -ScriptPath <string>
Resolve-CodexHome -ExplicitHome <string>
ConvertTo-CanonicalPath -PathValue <string>
Test-HarnessRootContract -Root <string>
Write-ManagedGlobalAgents -TemplatePath <string> -TargetPath <string> -HarnessRoot <string> -Force <switch>
```

`Resolve-HarnessRoot` 返回对象字段：`Path`、`Source`、`Issues`；`Source` 只允许 `explicit`、`environment`、`script_root`。`Write-ManagedGlobalAgents` 返回：`Updated`、`BackupPath`、`TargetSha256`、`Issues`。

- [ ] 把 sync/doctor 中任务所需的 canonical path 与 root contract 逻辑收敛到 helper；保持现有公开参数不变。
- [ ] 写 bootstrap 参数：`-HarnessRoot`、`-CodexHome`、`-ForceGlobalAgents`、`-SkipSync`、`-SkipRules`、`-SkipDoctor`、`-Json`。
- [ ] 渲染模板并实施缺失/空/managed/unmanaged 四分支；force 备份名使用原内容 SHA-256，避免重复备份。
- [ ] 在 `CODEX_HOME/.ai-harness/bootstrap.receipt.json` 写 schema、root source、canonical roots、hash 和 completed steps。
- [ ] 默认依次调用现有 sync、rules generate/validate、strict doctor；子命令非零立即返回失败摘要。
- [ ] 运行 bootstrap 集成测试，确认所有新用例 GREEN。

### Task 5：Rules Registry 逻辑显示路径

**Files:**

- Modify: `scripts/rules-index.common.ps1`
- Modify: `scripts/generate-rules-index.ps1`
- Modify: `scripts/validate-rules.ps1`
- Generate: `rules/registry/RULES_INDEX.json`
- Generate: `rules/registry/RULES_INDEX.md`
- Generate: `rules/registry/RULES_RESOLVED.json`

**Interfaces:**

```powershell
Get-LogicalRootMap -RepoRoot <string> -ExplicitRoots <string[]>
ConvertTo-LogicalDisplayPath -PathValue <string> -RootMap <object[]>
```

- [ ] 在模型中保留 canonical internal path，新增只用于序列化/诊断的 logical display path。
- [ ] current repo 显示为 `<repo-root>`，显式 roots 按参数顺序编号，sibling 候选显示为 `<repo-parent>/ai-harness/rules/items`。
- [ ] 让 generate 与 validate 使用同一显示函数，不建立第二套期望值。
- [ ] 运行 rules index 测试并确认新逻辑根用例 GREEN、scope 语义不变。
- [ ] 只通过 `generate-rules-index.ps1` 刷新三个生成物。

### Task 6：Doctor 增量与本机迁移

**Files:**

- Modify: `scripts/doctor-core.ps1`
- Modify machine-local: `C:/Users/Laptop/.codex/AGENTS.md`
- Create machine-local backup/receipt under: `C:/Users/Laptop/.codex/.ai-harness/`

**Stable issues:**

- `harness_root_invalid`
- `harness_root_selection_mismatch`
- `bootstrap_receipt_missing`
- `global_agents_unmanaged`
- `global_agents_hash_mismatch`
- `global_agents_legacy_path`

- [ ] doctor 读取 bootstrap receipt，验证选定根、模板 hash、目标 hash 和规则入口存在。
- [ ] doctor 只扫描活动态目标清单检测旧用户路径，不扫描历史证据目录。
- [ ] 先 dry-run 或临时 home 通过，再以 `-HarnessRoot D:/prj/harnesss/dev_vibecoding -ForceGlobalAgents` 运行本机 bootstrap。
- [ ] 确认旧全局文件备份存在，目标无 `72385` 且含 managed marker。
- [ ] 运行 Windows 合同、strict doctor 和 bootstrap 幂等复跑。

## 每批写入范围

- 文档批次只写 `DOC-PORTABILITY-002.write_paths`。
- 测试批次只写 `TEST-BOOTSTRAP-003.write_paths`，不得提前创建生产脚本。
- 实现批次只写 `IMPL-BOOTSTRAP-004.write_paths`；另一 clone 不在任何 write path。
- 复审只写 acceptance 和自己的 `subtask.result`，不得代修实现。

## 验证命令

```powershell
pwsh -NoProfile -File tests/harness/bootstrap-local.integration.ps1
pwsh -NoProfile -File tests/harness/rules-index.integration.ps1
pwsh -NoProfile -File tests/harness/rules-validation.integration.ps1
pwsh -NoProfile -File tests/harness/codex-sync.integration.ps1
pwsh -NoProfile -File tests/harness/windows-command-guardrails.contract.ps1
pwsh -NoProfile -File tests/harness/plan-docs.integration.ps1
pwsh -NoProfile -File scripts/validate-plan-docs.ps1 -Json
pwsh -NoProfile -File scripts/validate-doc-routing.ps1 -Json
pwsh -NoProfile -File scripts/generate-rules-index.ps1 -Json
pwsh -NoProfile -File scripts/validate-rules.ps1 -Json
pwsh -NoProfile -File scripts/doctor.ps1 -Profile codex_minimal -Strict -Json
git diff --check
git diff --stat
```

活动态路径扫描使用固定字符串，范围只包含本任务 write paths 和全局 AGENTS；历史证据目录不纳入失败判定。

## 回退方案

- 仓库文件按本任务 diff 逐文件恢复，不使用 `git reset --hard` 或覆盖用户其他改动。
- 全局 AGENTS 从 `CODEX_HOME/.ai-harness/backups/` 的内容寻址备份恢复。
- bootstrap receipt 可在恢复目标文件后删除；Codex skills 仍由现有 sync receipt 管理。
- 若 rules 逻辑显示路径破坏真实消费者，停止任务并保留 RED/诊断证据，不临时增加绝对路径兼容分支。

## 审查与返工路径

- `REVIEW-PORTABILITY-005` 必须独立运行全部验收命令并审阅 diff。
- 审查不通过时，完整 findings 退回原 `DOC-PORTABILITY-002`、`TEST-BOOTSTRAP-003` 或 `IMPL-BOOTSTRAP-004` 执行者；主协调器不代修。
- reviewer 回填 `docs`、`tdd`、`bootstrap_runtime`、`rules_portability`、`global_agents_migration` 五个 evidence slot 后，orchestrator `validate` 才能通过 review 闸门。
- 本任务不自动提交；最终由用户决定如何在两个独立 clone 之间提交和同步。
