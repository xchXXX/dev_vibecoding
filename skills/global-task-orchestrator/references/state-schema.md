# state.json 字段说明

`state.json` 是 GTO 唯一机器状态真源。当前 schema 只接受 `version=3`；控制器不读取、迁移或写入旧版状态。普通模型直接消费 `task.md` 和主协调器给出的显式子任务提示；只有控制器机械读取完整 state。

长任务同时保留：

- `docs/ai/tasks/<task_id>/state.json`
- `docs/ai/tasks/<task_id>/task.md`
- `docs/ai/tasks/<task_id>/events.jsonl`
- `docs/tasks/<task_id>/plan.md`
- `docs/tasks/<task_id>/execution.md`
- `docs/tasks/<task_id>/acceptance.md`

## 根字段

必填字段包括 `task_id`、`title`、`status`、`owner`、`six_points`、`approval`、`artifact_sha256`、`objective`、`scope_in`、`scope_out`、`acceptance`、`stop_conditions`、`decisions`、`current_phase`、`workspace`、`review_policy`、`findings`、`next_action`、`subtasks`、`updated_at` 和 `version`。

`verification_contract` 在进入 `code_impl` 或 `review` 前必填，固定包含：

- `minimal_repro`
- `hit_proof`
- `diagnostic_checks`
- `acceptance_checks`
- `non_goals`
- `review_evidence`

## 初始化

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action new-task --slug control-plane-bootstrap --json

python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action init-task --repo-root "$repo_root" --task-id "$task_id" \
  --title "$title" --owner "$owner" --contract-json-file "$contract_json_file" --json
```

`--contract-json-file "$contract_json_file"` 是 Codex 已定稿的结构化合同 JSON 文件，必须包含六要点、批准信息和至少一个真实子任务。初始子任务状态仅使用 `pending` 或 `ready`。

控制器先在内存中构造完整候选 state 并执行 canonical schema 校验，随后才创建任务目录、获取任务锁和写入六工件。合同读取、结构校验或 schema 校验被拒绝时，`state.json`、其余五份工件和 `.control.lock` 都不得残留。

## 阶段与门禁

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action set-phase --repo-root "$repo_root" --task-id "$task_id" \
  --phase doc_sync --json
```

只允许 `planning -> doc_sync -> test_sync -> code_impl -> review` 的相邻单向推进。`code_impl` 和 `review` 复用同一组机械语义门禁：

- `verification_contract` 六个字段完整。
- `workspace.overlap_decision.status` 为 `not_required` 或 `resolved`。
- `review` 阶段需要的 pre-final evidence 已由任一 completed、非 reviewer 子任务覆盖；不按角色预设 evidence key 套餐。
- `independent_final_review` 在最终 reviewer 完成前可暂缓，不由执行或测试子任务伪造。

转换拒绝时不修改 `state.json` 或 `task.md`；成功时同步 `current_phase`、`task.md` 投影、工件哈希和 `phase_changed` 事件。

## Workspace

`workspace` 固定包含 `repo_root`、`checkout_kind`、`branch`、`head`、`dirty_paths`、`write_overlap` 和 `overlap_decision`。唯一写入入口是：

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action prepare-workspace --repo-root "$repo_root" --task-id "$task_id" --json
```

控制器读取当前 Git checkout 的 branch、HEAD 和 dirty paths，并与所有未完成、非 reviewer 子任务的安全仓库相对 `write_paths` 比较。任务的六个控制工件、`.control.lock` 和仓库外绝对 runtime 路径不参与重叠计算。

- 无 overlap：原子写入 capture，`overlap_decision.status=not_required`，命令成功。
- 有 overlap 且没有非空 `--workspace-summary`：原子写入本次 capture 和 `pending`，随后非零返回并要求明确授权；不得写入伪造的 `resolved` 或 baseline hashes。
- 有 overlap 且提供非空 `--workspace-summary "$summary"`：重新采集同一组实时 Git 证据，为当前 overlap 内容写 `baseline_hashes`，再标记 `resolved`。

该 action 不清理、暂存、提交或改写用户 dirty 内容。

## 派发与结果

`subtasks[]` 至少包含 `subtask_id`、`title`、`role`、`status`、`dependencies`、`read_paths`、`write_paths` 和 `assignment`。`assignment` 包含 `goal`、`must_include` 和 `verification`。

平台完成真实派发后，记录身份与提示哈希：

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action bind-dispatch --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$subtask_id" --agent-key "$agent_key" \
  --platform-agent-id "$platform_agent_id" --context-mode isolated \
  --brief-kind "$brief_kind" --brief-sha256 "$brief_sha256" --json
```

completed 和 blocked 结果均通过 `record-subtask-result --result-json-file "$result_json_file"` 写回。结果必须包含状态、摘要、变更文件、未变更计划文件、验证、偏差、阻塞、风险、后续、写入者和角色。

## Finding 和复审

review result 使用 `record-review-result --result-json-file "$result_json_file"`。finding 保持稳定 `finding_id`，并记录 `lineage.original_implementer` 与 `lineage.original_reviewer`。

```bash
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action dispatch-finding-fix --repo-root "$repo_root" --task-id "$task_id" \
  --finding-id "$finding_id" --json

python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action record-finding-fix --repo-root "$repo_root" --task-id "$task_id" \
  --finding-id "$finding_id" --result-json-file "$result_json_file" --json

python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action build-review-brief --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$review_subtask_id" --finding-id "$finding_id" --json
```

`max_fix_rounds=3` 对每个 `finding_id` 独立生效，仅真实 fix dispatch 增加轮次。re-review 回到原 reviewer：`re_review/pass` 只能报告至少一个既有 finding，且每项 `status=closed`；open 或未知 finding 均被拒绝。task/final 的 pass 不得携带 finding。第三轮后仍 open 则进入 `blocked`/人工裁决。

最终 reviewer 需要独立身份、`kind=final`、`verdict=pass` 与最新 `reviewed_change_sha256`。`finalize-task` 只在没有未关闭 finding 且 final/pass 未过期时完成任务。

## 体积与 allowlist

schema 对固定结构使用字段 allowlist，并限制字符串、数组和哈希形状。state 只保存短摘要、仓库相对路径、哈希、commit range、命令名和结论，不保存完整 stdout、diff、prompt、聊天记录或第二控制面 package/report。
