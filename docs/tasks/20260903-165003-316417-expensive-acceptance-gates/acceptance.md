# GTO 昂贵验收轻量门禁

Task ID: `20260903-165003-316417-expensive-acceptance-gates`

## 验收目标

以最小改动为 GTO 增加跨项目通用的便宜检查先行、前置审查、候选冻结、昂贵验收限次、证据版本绑定和终态不可重开门禁，并让本次自举施工从任务合同开始实际遵守新流程。

## 验收标准

- 旧行为的最小复现先稳定失败：终态重绑、依赖未完成派发、status/result 矛盾、审查倒序、过期候选证据和覆盖验收历史均被测试命中。
- 新合同能表达通用阶段、冻结候选、acceptance item 到证据映射、max_expensive_attempts=4、同候选完整验收最多一次、同候选环境重试最多一次、第三和第四次需人工批准。
- 控制器拒绝 completed/blocked/in_progress 子任务重绑，拒绝依赖未完成或状态矛盾的写入，且失败不改变 state.json、task.md、events.jsonl。
- 安全或边界审查未通过、存在未关闭 finding、候选未冻结或已过期时，拒绝派发昂贵验收；候选输入变化后既有真实验收自动失效。
- 每次昂贵验收保留独立 attempt、候选哈希、结果分类、真实调用次数、耗时、失败阶段和证据引用，后一轮不能覆盖前一轮。
- 最终文档只能在当前候选验收通过后确认，最终审查和 finalize 只接受当前候选及完整证据。
- 聚焦控制面测试、完整 harness 回归、schema 与规则索引校验、文档路由校验和本任务范围 git diff --check 通过，并取得独立 final/pass。

## 必备证据

- `repro_before_fix`：每个新增门禁的聚焦测试在旧实现上按预期失败。
- `hit_proof_observed`：非法 action 被明确拒绝，且 `state.json/task.md/events.jsonl` 前后哈希不变。
- `pass_after_fix`：同一聚焦测试在最小实现后通过。
- `relevant_regression_ok`：旧 v3 状态兼容、完整 control-plane 和完整 harness 回归通过。
- `candidate_evidence`：安全审查通过且 findings 全闭合后生成最新候选哈希；冻结后没有候选输入变化。
- `expensive_acceptance`：本任务不调用真实外部模型、浏览器或数据库，明确记为不适用；理由是控制面行为可由本地临时仓库确定性证明。
- `independent_final_review`：独立 reviewer 覆盖最新 source manifest 并给出 `final/pass`。

## 未决项

- 独立终审 `REVIEW-FINAL-001` 尚未完成；在其覆盖最新文档后 source manifest 并给出 `final/pass` 前，任务仍不得宣称完成。
- 历史候选证据：删除获授权的 `/mnt/c/Users/Laptop/.claude` 后曾取得 `106/106`、`421.377s`、`OK`，冻结复核 target 为 `e0f68c62afc9b9f05780ba85f8692e5b7f48457556802202dd638dd9a6980e9b`；随后控制器和测试继续修改，因此该证据与 target 已按新规则失效，只保留历史，不用于最终结论。
- 失效候选证据：补齐 `final/fail -> re_review/pass -> new final` 状态迁移后曾取得 `113/113`、`388.348s`、`OK`，target 为 `b67308459b52bf7057c8989c2e0932e12e5ffa31d608420777d11e485170dfb8`；独立终审曾同意该证据，但结果入库前发现新建后续终审子任务缺少明确 final purpose。随后 controller/test 修复使该证据自动失效，只保留历史。
- 当前候选证据：后续终审子任务现在显式携带 `stage=final_review`，并兼容旧控制器已生成的 `-final-review-N` 子任务。聚焦 Red/Green 和控制面 `75/75` 通过；低成本 Schema、规则、文档及 diff 检查通过后，完整 harness 只为新候选运行一次，结果为 `113/113`、`396.183s`、`OK`，外层单调计时 `396.914s`，五个受控文件运行前后 SHA 完全一致。墙钟在运行期间再次回拨约 33 秒，因此不作为耗时真源。本次文档更新后仍须重新生成最终 target 并取得独立 `final/pass`。
- 本任务没有真实外部模型、浏览器或数据库验收需求，昂贵真实验收为不适用，`real_call_count=0`；没有用本地重复测试冒充真实调用。
- 文档代理误启动过两份相同的本地控制面/规则测试；两份均自然结束，未作为验收证据，也未触发额外真实验收。最终有效的完整 harness 证据仅为带单调计时与前后 SHA 的 `113/113`、`396.183s` 运行。

## 最终结论

独立 final/pass 已覆盖最新 scoped source manifest，任务完成。
