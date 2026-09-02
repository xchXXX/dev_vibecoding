---
name: global-task-orchestrator
description: 面向仓库级复杂改动的全局主协调 skill。用于接收新需求、定稿任务合同、维护单一 task state，并按 subtasks 委派阅读、实施、验证和审查。适用于需要跨模块协作、并行子任务和统一验收的任务。
---

# Global Task Orchestrator

GTO 用一份 `state.json` 维护机器状态，用五份配套工件保留人读合同和事件。Codex 负责理解语义、拆分任务和撰写显式子任务提示；Python 控制器只读完整 state 并执行结构、状态和审查门禁。

## 任务与工件

- 一个正式长任务只对应一个 `task_id`；窗口切换不创建新任务。
- 机器唯一真源：`docs/ai/tasks/<task_id>/state.json`。
- 人读摘要和事件：`task.md` 与 `events.jsonl`。
- 任务合同：`docs/tasks/<task_id>/plan.md`、`execution.md`、`acceptance.md`。
- 当前状态只接受 `version=3`。

普通 coordinator、implementer、test-verifier 和 reviewer 直接阅读 `task.md` 与主协调器提供的显式子任务提示；不要求它们调用不存在的 brief/projection action。完整 `state.json` 仅由控制器机械读取，或由主协调器在明确的状态损坏诊断中审计。

## 六要点合同

初始化前由 Codex 冻结：要做什么、不做什么、改哪些地方、怎么实现落地、怎么验收、有什么风险。Python 只校验这份已结构化的合同，不从自然语言推断任务类型或规则。

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action new-task --slug control-plane-bootstrap --json

python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action init-task --repo-root "$repo_root" --task-id "$task_id" \
  --title "$title" --owner "$owner" --contract-json-file "$contract_json_file" --json
```

`$contract_json_file` 必须是已定稿合同 JSON 的明确文件路径。结果和合同载荷只通过
`--result-json-file` 与 `--contract-json-file` 读取；不支持在命令行直接传递 JSON。
`init-task` 仅在完整候选 state 通过 schema 校验后才创建任务目录和六工件；拒绝的合同不留下 `.control.lock`。

## 阶段推进

`current_phase` 的正常顺序固定为：

`planning -> doc_sync -> test_sync -> code_impl -> review`

只使用相邻单向推进，不跳过文档或测试阶段，不回退。

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action set-phase --repo-root "$repo_root" --task-id "$task_id" \
  --phase doc_sync --json
```

进入 `code_impl` 前必须有完整 `verification_contract`，并且 workspace overlap 已是 `not_required` 或 `resolved`。进入 `review` 前还必须有任一已完成、非 reviewer 子任务提供的 pre-final evidence。拒绝转换不修改 `state.json` 或 `task.md`。

实现派发前，用唯一的 workspace action 采集当前 Git 证据：

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action prepare-workspace --repo-root "$repo_root" --task-id "$task_id" --json
```

无写入重叠时该 action 写入 `not_required`。有重叠时，首次调用写入实时 capture 和 `pending` 后非零返回；主协调器取得明确授权后，用同一命令增加非空 `--workspace-summary "$summary"`，控制器重新采集实时证据、写入当前 baseline hashes 并标记 `resolved`。控制器排除本任务六个控制工件和仓库外绝对 runtime 路径，不清理或改写用户 dirty 内容。

## 实际 CLI action

- `new-task`：产生本地时间 task ID，不创建任务文件。
- `init-task`：从已批准合同初始化六工件。
- `validate`：校验 v3 state、配套工件和语义门禁。
- `accept-artifact-update`：在人工核对后接受 Markdown 工件更新。
- `prepare-workspace`：采集当前 Git workspace，并机械记录 overlap 决定与 baseline。
- `set-phase`：执行相邻单向阶段推进。
- `bind-dispatch`：绑定真实平台代理身份与已发送提示哈希。
- `record-subtask-result`：记录执行或测试结果。
- `record-review-result`：记录 task、re-review 或 final review。
- `dispatch-finding-fix`：将稳定 finding 返回原实现者并增加该 finding 的轮次。
- `record-finding-fix`：记录 fix delta 并路由同一 reviewer 复审。
- `build-review-brief`：为审查子任务生成当前变更哈希和 finding 摘要。
- `finalize-task`：在最新独立 `final/pass` 且 finding 全部关闭后完成任务。

参数以 `python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py --help` 为准；只支持 GNU 双横线形式。

## Finding 和最终门禁

- `max_fix_rounds=3` 对每个 `finding_id` 独立计数。
- 只有 `dispatch-finding-fix` 真实派回原实现者时才增加轮次；查询、补证据和复审不计轮次。
- 第三轮修复后仍 open 的 finding 进入 `blocked`/人工裁决。
- re-review 复用 `lineage.original_reviewer`。`re_review/pass` 必须携带至少一个既有 finding，且每项均以 `status=closed` 关闭；task/final 的 pass 不得携带 finding。最终审查必须由独立 reviewer 覆盖最新 scoped source manifest。

## 结果合同

completed 或 blocked 子任务都写回 `state.json.subtasks[].result`，至少包含 `status`、`summary`、`changed_files`、`planned_files_not_changed`、`verification`、`deviations`、`blocked_by`、`risks`、`follow_up`、`written_by`、`written_role`。子任务不生成另一套 package/report 控制面。

## 参考

- 字段说明：`references/state-schema.md`
- 使用模式：`references/usage-modes.md`
- 治理摘要：`references/governance-essentials.md`
