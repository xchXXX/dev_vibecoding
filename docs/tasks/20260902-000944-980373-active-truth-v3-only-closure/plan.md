# 活跃真源 v3-only 全量收口 Implementation Plan

> **For agentic workers:** 按 `state.json` 中的子任务和写入边界实施；测试先行，实施完成后必须独立 review、fix、re-review。

Task ID: `20260902-000944-980373-active-truth-v3-only-closure`

## 任务目标

把仓库当前活跃真源、命令、规则、AGENTS.md、skills、schema、模板、测试与真实 Codex runtime 全量收口到纯 Codex、WSL Python 3、规则由 Codex 语义自由选读、GTO 仅支持真实 action 且只接受 v3 的唯一逻辑，并完成独立 review、返修和 re-review。

## 背景与问题

当前任务已由用户确认六要点，需要以文档、测试、实现和审查证据保持同一目标。

## 范围

- AGENTS.md、README.md 与当前 docs 真源
- rules/registry 与活跃 rules/items
- skills/global-task-orchestrator、skills/command-failure-memory、skills/pre-dev-benchmark
- schemas、templates、agents
- scripts 与 tests/harness 自动门禁
- 真实 /mnt/c/Users/Laptop/.codex 受管 runtime

## 非目标

- 不恢复或保留 Claude、PowerShell、cmd、hook、v1/v2 state、机械规则 matcher、RULES_RESOLVED.json 或旧 packet 控制面兼容入口
- 不删除 docs/ai/runs、docs/ai/tasks、docs/tasks 和 .artifacts 中明确归档的真实历史证据，仅确保其不被当前入口路由
- 不覆盖、不清理、不归属与本任务无关的现有未提交改动，不提交、合并、推送或自动管理 worktree
- 不迁移或清空 Command Failure Memory 现有数据

## 约束与依赖

- 现有工作树包含大量用户未提交改动，若与本任务写路径重叠必须保留原内容并做窄范围修改
- 移除 CLI 和 schema 兼容会让旧调用立即失败，这是本次明确目标但必须由测试证明错误信息清楚
- 历史证据中的旧词不能被误判为当前兼容层，自动门禁必须限定当前活跃范围
- sync 会写入真实 Codex runtime，只能在源文件验证通过后执行并复核哈希

## 方案摘要

先用失败测试冻结活跃真源、CLI、schema、模板和 runtime 的唯一合同；随后按互不重叠写入边界并行修正文档规则、控制器与 schema、模板与 benchmark；再运行 bootstrap/sync/doctor 和全量测试，最后由独立 reviewer 审查，finding 按同一 finding_id 返给原实现者修复并 re-review。

## 架构与接口

- Codex 负责理解任务语义并自由选读规则；Python 只做索引、结构、状态、命令和同步等机械工作。
- 当前控制面只认 `state.json` 与五份配套工件，不恢复 packet、hook 或多控制面。
- GTO CLI 只暴露真实实现的 GNU 双横线参数；保留最小阶段推进动作，其余已删除 action 从文档和模板移除。
- GTO state 只接受 version 3；历史 v1/v2 state 留在历史目录，不再作为当前可执行输入。
- 当前模板必须能被 schema 和真实 CLI 自动验证；doctor 汇总这些机械检查，但不替 Codex做语义判断。

## 子任务与文件边界

### TEST-RED-001：先建立失败门禁

- 只修改 `tests/harness/`。
- 新增测试覆盖：活跃真源旧合同、CLI aliases、文档 action/参数、v3-only schema、模板合法性、runtime 同步。
- 在任何生产实现改动前运行并保存预期失败证据。

### DOC-001：当前入口文档与规则

- 修改根 `AGENTS.md`、`README.md`、当前 `docs/` 真源、`rules/` 和 `scripts/README.md`。
- 不触碰历史 task/run 正文；历史区只能作为只读事实，不能被当前入口声明为实现真源。
- 所有命令改成真实 WSL `python3` 加 GNU 参数。

### IMPL-CONTROL-001：控制器、skill 与 schema

- 修改 GTO、CFM、`schemas/` 和角色说明。
- 删除 PascalCase 单横线 aliases、v2/legacy schema、`task_profile` matcher 说明和不存在的 action。
- 保留 CFM 数据目录和按 `finding_id` 独立计数的 `max_fix_rounds=3`。

### IMPL-TEMPLATE-001：模板与 benchmark

- 修改 `templates/` 与 `skills/pre-dev-benchmark/`。
- 当前 task 模板统一为 version 3、真实 action 和 WSL Python 3。
- benchmark 示例必须从仓库根可执行。

### SYNC-VERIFY-001：统一验证和 runtime 同步

- 源码全部转绿后运行 bootstrap、sync、strict doctor。
- 验证真实 `/mnt/c/Users/Laptop/.codex` 与源码哈希一致，且不改 CFM 数据。
- 汇总完整测试、规则、文档、schema、CLI 和模板证据。

### REVIEW-001：独立审查闭环

- reviewer 不参与上述实现。
- finding 使用稳定 `finding_id`，返给原实现者；修复后由同一 reviewer re-review。
- 只有全部 finding 关闭、全部变更文件覆盖且验证仍绿，才允许 final/pass。

## 风险与回退

- 现有工作树包含大量用户未提交改动，若与本任务写路径重叠必须保留原内容并做窄范围修改
- 移除 CLI 和 schema 兼容会让旧调用立即失败，这是本次明确目标但必须由测试证明错误信息清楚
- 历史证据中的旧词不能被误判为当前兼容层，自动门禁必须限定当前活跃范围
- sync 会写入真实 Codex runtime，只能在源文件验证通过后执行并复核哈希

## 验收标准

- 当前入口和受管 runtime 不再肯定式声明或实现 Claude、PowerShell/cmd/hook、v1/v2、RULES_RESOLVED、task_profile matcher 或旧 packet 控制面
- GTO/CFM Python CLI 只接受 GNU 双横线参数，文档 action 和参数全部可由真实 parser 验证
- GTO schema 只接受 version=3，当前模板全部通过 schema 且不含失效 action 或 Windows 命令
- 规则索引继续保持 3 条 always_on、其余由 Codex结合对话语义、目标内容、风险、当前阶段和本轮操作自由选读，Python 不参与日常语义匹配
- bootstrap、sync、strict doctor、规则/文档校验、全量 unittest 与新增盲测全部通过，源码和真实 Codex runtime 一致
- 独立 final reviewer 覆盖全部本次变更并给出 final/pass；发现问题时完成 fix 与 re-review

## 阶段划分

1. `planning`：六要点、施工图、验收合同定稿。
2. `test_sync`：TEST-RED-001 先产生可解释的 Red。
3. `doc_sync/code_impl`：DOC-001、IMPL-CONTROL-001、IMPL-TEMPLATE-001 按互斥写入范围并行。
4. `review`：SYNC-VERIFY-001 全量 Green 后，执行独立 review / fix / re-review。

## 需先同步的核心文档与测试

- 同步任务涉及的长期真源文档。
- 建立能直接命中目标问题的最小测试。
