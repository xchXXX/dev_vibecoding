# GTO 按需上下文、工作区基线与审查闭环施工计划

> **执行入口：** 本计划只使用仓库自制 `global-task-orchestrator` 和仓库既有测试入口。已禁用的 SDD 不参与调度、产物、复审或完成判定。

**Goal:** 将 GTO 中已有但偏文字化的上下文隔离、返修和审查约定，升级为可验证的单控制面合同。

**Architecture:** `state.json` 作为唯一真源，PowerShell 控制器在机器侧解析完整状态，对 coordinator、子任务和 reviewer 输出最小投影；平台派发返回的真实身份、workspace 基线和 review lineage 写回 state，由 schema、validator 和行为测试共同约束。

**Tech Stack:** Markdown、JSON Schema、PowerShell 7、Pester 风格自包含集成测试、Git 只读检查。

**Spec:** `docs/tasks/20260827-152719-gto-context-review-hardening-6f260f/plan.md`

## 施工目标

用最小、可审阅的增量完成以下闭环：

1. 文档先冻结合同；
2. 测试先证明当前实现缺口；
3. schema 与模板先统一数据结构；
4. 控制器实现按需投影、workspace、dispatch、lineage 和 final review；
5. 独立 reviewer 覆盖最新 `HEAD` 后才允许完成。

## 前置条件

- 用户已经确认本 Plan Window，但进入 Execute Window 前仍需复核本书面方案。
- 重新运行工作区检查并比较当前 `HEAD`、dirty paths 与目标 overlap。
- 当前两个重叠文件的 Plan Window 基线为：
  - `docs/ARCHITECTURE.md` SHA-256 `f9fa7956d9579550d5f6375975fcbe856221a80bb69677f394e396c26599e7c9`
  - `docs/SUBAGENT_GOVERNANCE.md` SHA-256 `8e415acfb5aaf03d45de8844b98c69b2d4b266de3b4218495d4ae27bb0c24ce2`
- 若上述文件变化无法归属，停止施工，不覆盖现有改动。
- 若使用当前 dirty checkout，必须把上述哈希作为显式增量基线；若使用隔离 worktree，必须由用户提供或确认基线与位置。
- 派发子代理时，平台必须支持真实的无历史上下文模式；只写提示词不算满足前置条件。

## 执行顺序

1. 重新捕获 workspace 基线，确认是否允许进入 `doc_sync`。
2. 执行 `DOC-GTO-001`，同步架构、治理和 workflow 规则。
3. 执行 `TEST-GTO-002`，增加行为测试并记录预期 RED。
4. 执行 `CONTRACT-GTO-003`，实现 schema、模板和字段说明。
5. 执行 `IMPL-GTO-004`，实现控制器、skill 和代理约束，逐项转 GREEN。
6. 由 `REVIEW-GTO-005` 做独立整体 review；finding 返回原实现者，原 reviewer 做范围化复审。
7. 复跑相关全量验证，确认 final review 覆盖最新 `HEAD`，再更新验收结论。

## 文档先行清单

- `docs/ARCHITECTURE.md`：说明单控制面、机器侧投影、workspace 与 final review 总体关系。
- `docs/SUBAGENT_GOVERNANCE.md`：说明真实身份、无历史派发、finding lineage 和范围化复审。
- `rules/items/workflow/复杂任务全局编排.md`：加入状态体积、工作区和完成门禁。
- `rules/items/workflow/子代理委派与协作.md`：加入原实现者返修、同 reviewer 复审和三轮上限。
- `skills/global-task-orchestrator/references/state-schema.md`：冻结新字段语义和完整 state 的例外读取条件。

文档批次完成后先运行计划文档和 doc routing 校验，再允许测试批次开始。

## 测试同步清单

### Task 1：按需投影与长状态控制

修改 `tests/harness/control-plane.integration.ps1`：

- coordinator view 只输出当前阶段、阻塞、依赖、workspace 摘要和下一项。
- subtask brief 只输出该任务 assignment、边界、依赖摘要和验证合同。
- review brief 只输出 finding、修复 delta、必要证据和 reviewer lineage。
- fixture 放入无关哨兵、完整 stdout、完整 diff 和其他子任务内容，断言投影均不出现。
- 初次运行应因动作不存在或输出过宽而 RED。

### Task 2：workspace 与真实身份

修改 `tests/harness/control-plane.integration.ps1`：

- primary checkout、linked worktree、clean、dirty 和 write-path overlap fixture。
- dirty overlap 未裁决时，进入 `code_impl` 必须失败。
- `bind-dispatch` 缺少 `platform_agent_id`、隔离模式或 brief 哈希时失败。
- 高风险 reviewer 与 implementer 使用同一真实 ID 时失败。
- 初次运行应因字段或门禁缺失而 RED。

### Task 3：finding lineage、范围化复审和最终完成门禁

修改两个相关测试：

- finding 缺少稳定 `finding_id` 时失败。
- finding 未返回原实现者时失败。
- re-review 更换 reviewer 或输入超出 finding/fix delta 且未升级范围时失败。
- 第四轮返修必须转为 blocked 或人工裁决。
- completed 缺少 `final/pass`、final reviewer 不独立或没有覆盖最新 `HEAD` 时失败。
- 保留并复跑既有 24 项 control-plane 回归和 skill 文档合同。

## 实施批次

### Task 4：状态合同

修改：

- `schemas/orchestrator-task-state.schema.json`
- `templates/orchestrator/state.template.json`
- `skills/global-task-orchestrator/references/state-schema.md`

最小新增结构：

- 根层 `workspace`
- 根层 `review_policy`
- `subtask.dispatch`
- `subtask.lineage`
- `result.review.kind = task | re_review | final`
- `result.review.verdict = pass | fail | needs_more_evidence`
- `result.review.findings[]` 的稳定 `finding_id`

schema 不接受完整 stdout、diff、prompt 或 chat payload 字段。对旧活跃任务只提供一次性迁移，不长期允许新旧字段并存。

### Task 5：workspace 与投影动作

在 `orchestrator_ctl.ps1` 增加：

- `get-task-view -View coordinator`
- `inspect-workspace`
- `capture-workspace-baseline`
- `build-review-brief`

并增强：

- `build-subtask-brief`
- `build-execute-handoff`

实现要求：

- 工作区命令只检查和记录，不创建或删除 worktree。
- 状态路径使用 `<repo-root>` 和仓库相对路径。
- JSON 投影使用明确 allowlist，不通过先复制整对象再删字段来实现。
- 输出稳定、短小，可直接作为代理输入。

### Task 6：dispatch、finding 和 review 门禁

在 `orchestrator_ctl.ps1` 增加 `bind-dispatch`，并增强 `validate`：

- 校验真实 `platform_agent_id`、`context_mode`、`brief_kind`、`brief_sha256`。
- 高风险 reviewer ID 不得等于 implementer ID。
- finding 绑定 original implementer 和 original reviewer。
- re-review 默认只接收 finding 与 fix delta；范围扩大必须带 reason 和新审查范围。
- 修复轮次最多三轮。
- completed 必须有覆盖最新 `HEAD` 的 `final/pass`。

### Task 7：skill 与角色说明

修改：

- `skills/global-task-orchestrator/SKILL.md`
- `agents/backend-implementer.md`
- `agents/reviewer.md`
- `agents/test-verifier.md`

说明各角色默认只消费自己的投影，不自行读取完整 state；实施者、测试者和 reviewer 的结果写回同一 state，不生成独立报告文件。

## 每批写入范围

- `DOC-GTO-001`：只写五份文档或规则文件。
- `TEST-GTO-002`：只写两份测试文件。
- `CONTRACT-GTO-003`：只写 schema、模板和 state 字段说明。
- `IMPL-GTO-004`：只写 GTO skill、控制器和三份代理说明。
- `REVIEW-GTO-005`：只读，不写生产文件；finding 通过 state 交回原实现者。

任何额外文件都必须先更新 state 的 scope、write paths 和范围扩张理由，并重新判断审查范围。不得顺手修改范围外文件。

## 验证命令

文档阶段：

```powershell
pwsh -NoProfile -File scripts/validate-plan-docs.ps1 -Json
pwsh -NoProfile -File scripts/validate-doc-routing.ps1 -Json
```

状态与控制面阶段：

```powershell
pwsh -NoProfile -File skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate -TaskId 20260827-152719-gto-context-review-hardening-6f260f -Json
pwsh -NoProfile -File tests/harness/global-task-orchestrator.skill-doc.ps1
pwsh -NoProfile -File tests/harness/control-plane.integration.ps1
```

最终阶段还需：

- 运行 JSON schema 正反 fixture。
- 对正式写入范围搜索机器绝对路径和长载荷禁用字段。
- 运行 `git diff --check` 并人工审阅目标 diff。
- 重新捕获 `HEAD`，确认 final review 覆盖最终提交或最终变更哈希。

## 回退方案

- 任一批次失败，停止依赖它的后续批次，保留可复现 RED、失败签名和最小诊断。
- 不使用 `git reset --hard`、`git checkout --` 或自动清理工作区。
- 对与既有 dirty 内容重叠的文件，回退等于不写入或由用户明确选择基线；不覆盖未知改动。
- schema/控制器不一致时，先回退到上一批已经验证的合同，不保留长期双轨兼容。
- 平台没有真实无历史派发能力时，停止 dispatch 功能落地，不用提示词降级冒充完成。

## 审查与返工路径

1. 高风险实现完成后，由真实身份不同的 reviewer 做 task review。
2. reviewer 将 finding 结构化写入 state，包含 `finding_id`、证据、路径、严重级别和范围。
3. 控制器把 finding 返回 `lineage.original_implementer`，同时生成 fix brief。
4. 实现者写回短修复摘要、changed paths、验证结果和 fix delta 哈希。
5. 原 reviewer 接收 review brief，只复审 finding 与 fix delta。
6. 若修复扩大范围，记录理由并升级为新的 task review；不得把扩大范围伪装成局部 re-review。
7. 同一 finding 最多三轮；仍未闭合则 blocked 或请求人工裁决。
8. 所有局部 finding 关闭后，再做一次覆盖全任务和最新 `HEAD` 的 final review。
9. 只有 final verdict 为 pass，或所有剩余问题都有显式裁决，才允许任务进入 completed。
