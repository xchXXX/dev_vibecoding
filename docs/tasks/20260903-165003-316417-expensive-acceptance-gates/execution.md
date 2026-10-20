# GTO 昂贵验收轻量门禁

Task ID: `20260903-165003-316417-expensive-acceptance-gates`

## 施工目标

以最小改动为 GTO 增加跨项目通用的便宜检查先行、前置审查、候选冻结、昂贵验收限次、证据版本绑定和终态不可重开门禁，并让本次自举施工从任务合同开始实际遵守新流程。

## 前置条件

- 用户已确认六要点任务合同。
- 写入前已冻结范围、验收和风险。
- 已用旧 GTO 建立六工件并执行 `prepare-workspace`；基线为 `main@c79d58cb0345a0cb879b2be06073a1ef04962c36`，无写入重叠。
- 本任务人工启用新流程：不重绑任何终态或执行中子任务，不越过依赖，不在安全审查前冻结候选。

## 执行顺序

严格按 `DOC-DESIGN-001 -> TEST-GATES-001 -> IMPL-GATES-001 -> VERIFY-GATES-001 -> REVIEW-SEC-001 -> FREEZE-LOCAL-001 -> DOC-FINAL-001 -> REVIEW-FINAL-001` 执行。只有 finding 修复和同 reviewer 复审可以形成闭环支线；支线完成后回到被阻断的下一阶段，不重新派发原终态子任务。

## 文档先行清单

- 本任务 `plan.md` 明确通用理想流程、次数、证据复用和本次自举执行方式。
- 本任务 `execution.md` 明确逐批命令、写入范围、回退和审查顺序。
- GTO skill 与 references 只写判断和操作入口；可机械执行的限制落到 controller/schema，不依赖提示词兜底。
- 治理总纲、架构、主计划和 workflow rules 使用同一术语，不复制业务项目专用步骤。

## 测试同步清单

- `test_bind_rejects_terminal_or_active_subtask_without_mutation`
- `test_bind_rejects_unfinished_dependencies_without_mutation`
- `test_state_write_rejects_status_result_mismatch`
- `test_expensive_dispatch_requires_reviews_findings_and_frozen_candidate`
- `test_candidate_input_change_stales_expensive_evidence`
- `test_expensive_attempts_are_append_only_and_capped`
- `test_third_expensive_attempt_requires_human_approval`
- `test_final_documentation_and_finalize_require_current_candidate_evidence`

每个测试先单独运行并观察预期 Red：旧控制器错误地允许动作或缺少 action/schema。只有失败类型与目标缺口一致时才进入实现；语法、fixture、环境错误不算 Red。

## 实施批次

### 批次一：文档合同

依赖：无。写通用流程长期真源和本任务文档。收口条件：术语一致、没有项目专用流程、旧规范压力基线已经记录。

### 批次二：Red 测试

依赖：批次一完成。只修改 `tests/harness/test_control_plane.py`，不提前修改 controller/schema。收口条件：新增聚焦测试因目标行为缺失而稳定失败。

### 批次三：最小 Green 实现

依赖：批次二 Red 成立。controller 与两个 schema 作为同一个原子批次修改，避免 schema/controller 暂时双轨。收口条件：新增聚焦测试和既有 control-plane 测试通过。

### 批次四：便宜验证和前置审查

依赖：批次三完成。先执行本地确定性全回归，再由独立 reviewer 做安全、原子性、权限和证据边界审查。finding 走原实现者修复和同 reviewer 复审。收口条件：所有 finding 关闭。

### 批次五：冻结、本地验收、最终文档和终审

依赖：批次四通过。冻结当前 source manifest，确认本次外部昂贵验收不适用，复用同一批本地证据；之后才更新最终文档并执行独立 final review。

## 每批写入范围

- 文档批次：`skills/global-task-orchestrator/SKILL.md`、其 references、`docs/SUBAGENT_GOVERNANCE.md`、`docs/ARCHITECTURE.md`、`docs/plans/AI_HARNESS_MASTER_PLAN.md`、`rules/items/workflow/*`、本任务三份 Markdown。
- 测试批次：`tests/harness/test_control_plane.py`。
- 实现批次：`skills/global-task-orchestrator/scripts/orchestrator_ctl.py`、`schemas/orchestrator-task-state.schema.json`、`schemas/task-event.schema.json`。
- 生成批次：只通过既有生成器刷新 `rules/registry/RULES_INDEX.json`。
- 验证和审查批次不写业务文件；只有 finding 修复可以回到其原实现者的既定写入范围。

## 验证命令

- 聚焦 Red/Green：`python3 -m unittest tests.harness.test_control_plane.ControlPlaneContractTest.<test_name> -v`
- 控制面回归：`python3 -m unittest tests.harness.test_control_plane -v`
- 完整 harness：`python3 -m unittest discover -s tests/harness -p 'test_*.py' -v`
- 规则索引：先用 `rg` 确认现有生成和校验入口，再运行仓库既有 Python 生成器与 validator；不手改生成字段。
- 任务状态：`python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py --action validate --repo-root /mnt/d/prj/harnesss/dev_vibecoding --task-id 20260903-165003-316417-expensive-acceptance-gates --json`
- 差异检查：`git diff --check -- skills/global-task-orchestrator schemas tests/harness/test_control_plane.py docs/SUBAGENT_GOVERNANCE.md docs/ARCHITECTURE.md docs/plans/AI_HARNESS_MASTER_PLAN.md rules/items/workflow rules/registry/RULES_INDEX.json docs/tasks/20260903-165003-316417-expensive-acceptance-gates docs/ai/tasks/20260903-165003-316417-expensive-acceptance-gates`

## 回退方案

- 某批 Red 不稳定或无法直接命中缺口：不进入实现，缩小 fixture 或重新定义 hit proof。
- Green 破坏旧 v3 任务读取：回退该批 controller/schema 补丁，保留测试和文档证据，停止进入审查。
- 候选失效范围无法轻量定义：保留终态/依赖/审查门禁，候选功能不做猜测性扩张，回到用户裁决。
- 审查发现高风险问题：记录稳定 finding，原实现者修复，同 reviewer 复审；不得绕过审查直接冻结。
- 不使用 `git reset --hard`、`git checkout --` 或清理任务范围外文件；回退使用窄 `apply_patch`。

## 审查与返工路径

`REVIEW-SEC-001` 在候选冻结前执行。任何 finding 使用稳定 `finding_id`，经 `dispatch-finding-fix` 回到 `/root/impl_gates`，由原 reviewer re-review；第三轮仍未关闭进入人工裁决。所有 finding 关闭后才能执行 `FREEZE-LOCAL-001`。

最终文档只能由 `DOC-FINAL-001` 在冻结候选本地验收完成后更新。`REVIEW-FINAL-001` 必须与实现者身份独立，并覆盖最新 source manifest；只有 `final/pass` 后才能 `finalize-task`。

## 实际施工记录

- 2026-09-03：用户明确批准施工，并要求落盘文档写明本任务实际使用新流程。
- 2026-09-03：旧 GTO 初始化成功，工作区基线 `main@c79d58cb0345a0cb879b2be06073a1ef04962c36`，无 dirty overlap。
- 2026-09-03：`DOC-DESIGN-001` 已唯一绑定给 `/root/doc_design`；后续不允许再次绑定此子任务。
- 2026-09-03：Red/Green 实现后，前置安全审查发现 7 个 findings；均经原实现者修复和同一 reviewer 的追加式复审关闭，没有覆盖原失败审查历史。
- 2026-09-04：用户明确授权直接删除 `/mnt/c/Users/Laptop/.claude`；精确核对目标后删除，完整 harness 只重跑一次，`106/106` 在 `421.377s` 内通过。
- 2026-09-04：`FREEZE-LOCAL-001` 复核 target `e0f68c62afc9b9f05780ba85f8692e5b7f48457556802202dd638dd9a6980e9b`，复用完整 harness 证据，外部昂贵验收不适用且 `real_call_count=0`。
- 2026-09-04：候选验收后才执行 `DOC-FINAL-001`。文档代理误启动两份相同本地测试，两进程均自然结束且结果不计入验收；没有再次运行完整 harness或真实昂贵验收。
- 2026-09-04：最终文档已同步，下一步只允许独立 `REVIEW-FINAL-001` 覆盖最新 source manifest；final/pass 前继续保留“任务尚未完成”。
- 2026-09-04：第一次独立终审拒绝 `final/pass`，登记 5 个 findings；其中明确判定旧 `106/106` 证据因后续 controller/test 变化而失效。
- 2026-09-04：5 个终审 findings 均回到 `/root/impl_gates`，经新增 Red/Green、`test_control_plane` 74/74 后修复；代码稳定后完整 harness 只为新候选运行一次，`112/112` 在 `373.166s` 内通过。
- 2026-09-04：原 `/root/final_review` 通过追加式 `re_review/pass` 关闭 5 个 findings，保留原 `final/fail` 历史；复审 target 为 `c189bb1bcb6b601db35035c42ec7c3c50dca84944f06eb217baf62e0d153cbbc`。
- 2026-09-04：本次仅更新任务最终证据，将 `106/106` 和 `e0f68c62...` 标为历史失效，将 `112/112` 标为当前候选证据；仍需新 target 的独立 `final/pass`。
- 2026-09-04：追加实现 `create-final-review-subtask`，以机械支持保留 `final/fail` 与 `re_review/pass` 后创建新的 final-purpose 子任务；专项和 `test_control_plane` 75/75 通过。
- 2026-09-04：最终候选完整 harness 从 `12:17:31+08:00` 到 `12:23:28+08:00` 单次运行，`113/113`、`388.348s`、`OK`；controller、state schema、GTO skill、state-schema reference 和 control-plane tests 的运行前后 SHA 完全一致。
- 2026-09-04：更新最终证据后不再修改实现；下一步通过 `create-final-review-subtask` 追加新的 final 审查并覆盖最新 target。
- 2026-09-04：独立终审指出墙钟区间与 `unittest` 单调计时不一致；核对 Python 3.12 runner 使用 `time.perf_counter()`，且 WSL 启用时间同步。终审接受原候选证据，但写入结果时控制器正确拒绝了缺少明确 final purpose 的新子任务，暴露 `create-final-review-subtask` 未写入 `stage=final_review` 的遗漏。
- 2026-09-04：按 Red/Green 修复：新建后续终审子任务显式写 `stage=final_review`，并兼容识别旧控制器已生成的 `-final-review-N` 子任务；聚焦测试先以 `KeyError: stage` 失败，修复后通过，随后控制面 `75/75`、`341.831s`、`OK`。
- 2026-09-04：上述 controller/test 变化使前一轮 `113/113`、`388.348s` 及 target `b6730845...` 自动失效。低成本 Schema、规则、文档和 diff 检查先通过后，新候选只运行一次完整 harness：`113/113`、`396.183s`、`OK`；外层 `monotonic_ns` 区间为 `396.914s`，五个受控文件运行前后 SHA 完全一致。墙钟再次发生约 33 秒回拨，不作为耗时真源。
