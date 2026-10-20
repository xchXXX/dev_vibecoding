# 活跃真源 v3-only 全量收口

Task ID: `20260902-000944-980373-active-truth-v3-only-closure`

## 要做什么

把仓库当前活跃真源、命令、规则、AGENTS.md、skills、schema、模板、测试与真实 Codex runtime 全量收口到纯 Codex、WSL Python 3、规则由 Codex 语义自由选读、GTO 仅支持真实 action 且只接受 v3 的唯一逻辑，并完成独立 review、返修和 re-review。

## 不做什么

- 不恢复或保留 Claude、PowerShell、cmd、hook、v1/v2 state、机械规则 matcher、RULES_RESOLVED.json 或旧 packet 控制面兼容入口
- 不删除 docs/ai/runs、docs/ai/tasks、docs/tasks 和 .artifacts 中明确归档的真实历史证据，仅确保其不被当前入口路由
- 不覆盖、不清理、不归属与本任务无关的现有未提交改动，不提交、合并、推送或自动管理 worktree
- 不迁移或清空 Command Failure Memory 现有数据

## 改哪些地方

- AGENTS.md、README.md 与当前 docs 真源
- rules/registry 与活跃 rules/items
- skills/global-task-orchestrator、skills/command-failure-memory、skills/pre-dev-benchmark
- schemas、templates、agents
- scripts 与 tests/harness 自动门禁
- 真实 /mnt/c/Users/Laptop/.codex 受管 runtime

## 怎么实现落地

先用失败测试冻结活跃真源、CLI、schema、模板和 runtime 的唯一合同；随后按互不重叠写入边界并行修正文档规则、控制器与 schema、模板与 benchmark；再运行 bootstrap/sync/doctor 和全量测试，最后由独立 reviewer 审查，finding 按同一 finding_id 返给原实现者修复并 re-review。

## 怎么验收

- 当前入口和受管 runtime 不再肯定式声明或实现 Claude、PowerShell/cmd/hook、v1/v2、RULES_RESOLVED、task_profile matcher 或旧 packet 控制面
- GTO/CFM Python CLI 只接受 GNU 双横线参数，文档 action 和参数全部可由真实 parser 验证
- GTO schema 只接受 version=3，当前模板全部通过 schema 且不含失效 action 或 Windows 命令
- 规则索引继续保持 3 条 always_on、其余由 Codex结合对话语义、目标内容、风险、当前阶段和本轮操作自由选读，Python 不参与日常语义匹配
- bootstrap、sync、strict doctor、规则/文档校验、全量 unittest 与新增盲测全部通过，源码和真实 Codex runtime 一致
- 独立 final reviewer 覆盖全部本次变更并给出 final/pass；发现问题时完成 fix 与 re-review

## 有什么风险

- 现有工作树包含大量用户未提交改动，若与本任务写路径重叠必须保留原内容并做窄范围修改
- 移除 CLI 和 schema 兼容会让旧调用立即失败，这是本次明确目标但必须由测试证明错误信息清楚
- 历史证据中的旧词不能被误判为当前兼容层，自动门禁必须限定当前活跃范围
- sync 会写入真实 Codex runtime，只能在源文件验证通过后执行并复核哈希

## 当前状态

- status: `completed`
- current_phase: `review`
- next_action: `none`
