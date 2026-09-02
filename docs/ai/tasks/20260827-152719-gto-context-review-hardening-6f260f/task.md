# 任务摘要

## 基本信息

- `task_id`: `20260827-152719-gto-context-review-hardening-6f260f`
- `title`: GTO 按需上下文、工作区基线与审查闭环增强
- `status`: `completed`
- `owner`: `main-coordinator`

## 目标

- 在不引入第二控制面的前提下，为 global-task-orchestrator 增加按需状态视图、隔离派发、工作区基线、代理身份、范围化复审与最终整体审查硬门禁。

## 范围

### Scope In

- docs/ARCHITECTURE.md
- docs/SUBAGENT_GOVERNANCE.md
- rules/items/workflow/复杂任务全局编排.md
- rules/items/workflow/子代理委派与协作.md
- skills/global-task-orchestrator/**
- agents/backend-implementer.md
- agents/reviewer.md
- agents/test-verifier.md
- schemas/orchestrator-task-state.schema.json
- schemas/README.md
- schemas/task-state.schema.json
- templates/orchestrator/state.template.json
- tests/harness/global-task-orchestrator.skill-doc.ps1
- tests/harness/control-plane.integration.ps1
- rules/registry/RULES_INDEX.json
- rules/registry/RULES_INDEX.md
- rules/registry/RULES_RESOLVED.json
- docs/ai/tasks/20260827-152719-gto-context-review-hardening-6f260f/**
- docs/tasks/20260827-152719-gto-context-review-hardening-6f260f/**

### Scope Out

- 不保留或引入第二套任务编排控制面，也不依赖已禁用的 SDD 工作流
- 不把文件系统隔离或安全沙箱伪装成上下文隔离
- 不在 state.json 中保存完整命令输出、完整 diff、完整提示词或聊天记录
- 不自动创建、删除、切换或清理 Git worktree
- 不修改、同步或选择其他 clone
- 不提交、合并、推送、变基或清理当前工作区的既有改动
- 不修改与本任务无关的规则、脚本、文档和测试

## 验收标准

- state.json 继续是唯一任务真源，控制脚本能按 coordinator、subtask、review 三类视图投影最小上下文
- 子任务派发必须绑定真实平台代理身份，并记录 agent_key、platform_agent_id、context_mode、brief_kind 与 brief_sha256
- 支持显式无历史上下文派发；提示词只能声明边界，不能替代平台隔离参数
- 工作区检查能记录逻辑 repo_root、checkout 模式、分支、HEAD、基线、dirty 路径和目标重叠，并在高风险重叠时阻止实现阶段
- 高风险实现任务必须由不同身份 reviewer 审查，finding 必须结构化并返回原实现者修复
- 修复后只把 finding、修复差异摘要和必要证据交给原 reviewer 做范围化复审；范围扩大时必须显式升级审查
- 同一 finding 最多三轮修复，超过后进入 blocked 或人工裁决，不允许无限循环
- 任务完成前必须有覆盖最新 HEAD 的最终整体 review pass，或对剩余问题有显式裁决记录
- 旧任务的迁移与兼容边界有明确一次性策略，不长期保留双轨字段
- 相关文档、schema、模板、PowerShell 控制器和测试同步更新，且正式产物不写入机器绝对路径

## 停止条件

- 目标文件与当前 dirty 工作区发生无法安全归属的重叠，且没有明确基线或用户裁决
- 目标平台无法提供无历史上下文的真实派发参数，却要求把提示词当作等价隔离
- 实现必须引入第二真源、第二编排器或恢复已禁用的 SDD 才能继续
- 实现需要自动扫描 clone，或自动创建、切换、删除 worktree
- 现有消费方无法迁移到新状态合同，且只能通过长期双轨兼容才能维持
- 需要越过本任务 scope_out 或覆盖无法归属的用户改动

## 关键决定

- 用户确认只保留 global-task-orchestrator 作为任务编排栈。
- 先落地方案、施工和验收文档；用户复核书面方案后才进入 Execute Window。
- state.json 仍是唯一真源，PowerShell 在机器侧读取完整状态并输出按需投影视图。
- 正常上下文只允许 coordinator view、subtask brief 和 review brief；原始完整 state 只用于损坏诊断、schema 迁移、投影诊断和最终控制面审计。
- 上下文隔离必须依赖派发工具的无历史参数，并在 state 中记录真实代理身份和 brief 哈希；提示词不是隔离机制。
- state 只保存结构化摘要、路径、哈希和 commit range，不保存大段 stdout、diff、prompt 或聊天记录。
- 本次 Plan Window 只新增当前任务目录；工作区决策完成前不修改与现有 dirty 变更重叠的核心文档。
- 独立 final review 的 REVIEW-GTO-005-F005/F006 证明新 schema 与新增 workflow 规则存在正式入口歧义；为关闭 finding，范围扩展到 schemas/README.md、schemas/task-state.schema.json 与三个规则生成索引。旧 schema 不删除，生成索引只允许由既有脚本刷新，并以扩展前 SHA-256 为 overlap 基线。

## 当前阶段

- `current_phase`: `review`

## 子任务

### DOC-GTO-001

- `title`: 同步 GTO 上下文、工作区与审查治理文档
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 先于代码冻结 GTO 单栈、按需上下文、工作区基线和 review 拓扑合同。

### TEST-GTO-002

- `title`: 冻结状态投影、工作区和审查闭环行为测试
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 先写可观察 RED，覆盖最小投影、隔离派发元数据、dirty overlap、代理身份、finding lineage、范围化复审和最终整体 review。
- `dependencies`: `DOC-GTO-001`

### CONTRACT-GTO-003

- `title`: 实现 GTO 状态 schema 与模板合同
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 用最小结构扩展 workspace、dispatch、lineage 与 review 合同，并保持 state 精简。
- `dependencies`: `TEST-GTO-002`

### IMPL-GTO-004

- `title`: 实现按需投影、工作区检查与审查闭环控制器
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 用单一 PowerShell 控制面实现按需视图、工作区基线、派发绑定、finding 返修、范围化复审和最终整体 review 门禁。
- `dependencies`: `CONTRACT-GTO-003`

### REVIEW-GTO-005

- `title`: GTO 状态与审查闭环最终独立审查
- `role`: `reviewer`
- `status`: `completed`
- `goal`: 独立核对单栈设计、最小上下文、工作区基线、真实身份、finding 修复链和覆盖最新 HEAD 的最终整体审查门禁。
- `dependencies`: `DOC-GTO-001`, `TEST-GTO-002`, `CONTRACT-GTO-003`, `IMPL-GTO-004`

## 更新时间

- `2026-08-27T22:49:17+08:00`
