# 失效任务绑定恢复与工作区释放

## 目标与范围
用户在原 AI 输出修复聊天明确批准补齐可审计的失效任务绑定恢复入口，再依据本聊天原始整合证据释放大项目主目录。授权经来源聊天 01a15d10-2759-7fc1-9bfd-ef1cf5bc670c 转交。本任务只修改 harness 工作区工具、合同和定向测试；实际运用只写大项目本地登记索引及审计回执，不改业务代码、不部署，不把历史未验收状态改为完成。

根因：discover 无条件读取索引中的工作区；已归档目录导致 BINDING_INVALID。没有显式释放入口，旧 GTO 即使已停止施工仍永久占用主目录。

具体合同见 docs/modules/git-workflow/contract/task-workspace.md 的“显式恢复释放”。保留原状态和绑定，通过可核验的释放回执解除占用，避免伪完成或拷贝 GTO 状态。

## 实施步骤
调查与方案 → 文档 → 测试 → 实现 → 独立 review → 验收。

## 验收点与证据
- audited-release: 缺失原工作区及当前目录旧 GTO 均可显式释放，记录字节不变，回执可校验。
- fail-closed: 授权证据/记录/哈希/停止写入声明缺失、其他工作区存活、脏目录、并发锁、篡改及重复释放均拒绝；既有任务门禁保持。
- real-recovery: 大项目两条旧任务的原状态、证据和独立验收边界如实保留，inspect 返回 available，业务 Git 字节和 refs 不变。

## 最小验证合同
- minimal_repro: 小型真实 Git 夹具中注册普通任务后删除原工作区，inspect 返回 BINDING_INVALID；当前目录 active GTO 返回 occupied。
- hit_proof: 经显式 recover-release 后 inspect 返回 available 并列出 released_tasks，原状态和 checkout_binding 的 SHA-256 不变。
- diagnostic_checks: 定向 CLI 正负例、原索引/记录哈希对比、回执哈希与授权证据检查。
- acceptance_checks: 原任务工作区/发布回归、独立 reviewer、原测试者验收、真实消费项目只读复核。
- non_goals: 不重跑业务模型/生产验收、不部署、不复制/重写冻结 GTO、不增加自动过期回收。
- review_evidence: repro_before_fix、pass_after_fix、hit_proof_observed、relevant_regression_ok。

## 未解决事项与接续
工具实现已完成：10 项新增 CLI 测试、28 项原有工作区与分发回归通过；独立 reviewer 无 P1/P2。通过结果分别见 `.artifacts/20261021-task-binding-release/qa/tool-results.json` 与 `review/stage.json`（后者相对同一证据目录）。

真实消费项目两条旧任务已通过公开 recover-release 释放，inspect 返回 available、occupants=[]、main、dirty=false。旧整合 task.json 保持 active/review，旧模拟 GTO state.json 保持 active/doc_sync；原记录 SHA-256 和 checkout_binding 不变。生产验收及后续 Git 清理的既有证据沿用，原流程未登记的完整验收不补造。主目录 HEAD、分支、远端跟踪分支与标签未变；Codex 自动维护的 refs/codex/turn-diffs 有自然变化，不能声称全部内部 refs 静止。

恢复证据位于消费项目 `.artifacts/20261021-task-binding-release/`，释放回执在该 clone Git common dir 的 `ai-harness/task-releases/`。这些文件参与后续完整性检查，不可当临时垃圾删除。原验收者最后只读复核见 `.artifacts/20261021-task-binding-release/qa/final-acceptance.json`；仅登记该报告通过后才执行 complete。

交付范围限于 harness 源码、合同和测试及本 clone 的恢复回执；不改消费项目受管文件、不部署、不自动全局安装、不替旧 GTO 更换冻结控制器。后续施工可使用 harness 真源公开入口；已释放旧任务不可直接 resume，需继续旧任务时另行走恢复合同。
