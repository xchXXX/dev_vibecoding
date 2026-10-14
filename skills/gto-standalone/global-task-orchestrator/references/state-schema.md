# state.json 字段说明

## 中断身份移交记录

`interruption_recoveries` 是追加历史；每项包含经 schema 校验的 `request`、控制器入库时间 `recorded_at`、完整 `previous_blocker`、`previous_dispatch` 与当次执行包 `runtime_sha256`。request 含明确用户授权及留存证据 hash、旧新协调身份和目标派发旧新身份。入库时间不代表用户消息时间；历史身份和失败不改写。

`coordinator_blocker.recovery_coordinator_id` 只标识已批准的当前接替协调者，必须与最新恢复记录一致；原 `result.written_by` 保留。移交不恢复阶段、不提供业务结果、不变更批准合同和预算；正常阶段恢复仍需成功检查。目标回到 ready 后只能绑定批准的新真实代理。适用边界与 CLI 唯一见 [控制器身份移交](controller-guide.md#会话中断且尚无交付的身份移交)。

## 计划代理与只读结果预检

新方案各子任务填写 `planned_agent_key`，表示施工前确认的代理代号；`role` 仍表示任务职责。相同代号绑定同一 `dispatch.platform_agent_id`，不同代号不得使用同一真实身份；`dispatch.agent_key` 必须等于计划代号。不全面禁止测试代理兼任验收。

新 revision 3 初始化必须为每项任务填写计划代理；控制器生成 `approval.planned_subtask_ids`，列出本次批准的初始任务。批准指纹覆盖这些任务的标识、标题、职责、阶段、计划代理、依赖、阅读/写入范围与 assignment；运行状态、实际 ID 与结果不参与。当前包拒绝缺少该字段的合同，不提供旧状态兼容或自动迁移。

控制器创建的整合返工、复审、验收尝试通过 `plan_source_subtask_id` 指向批准的初始任务，继承其代理、职责与范围。初始化合同不得填写此派生字段；新任务不得冒充正常返工绕过批准。更改分工或依赖需要确认后修订同一合同，不能手改哈希冒充已批准。

### 结果提交协议

派发时提供 [完整结果样例](revision-3-results.example.json) 中对应对象；协调器填已知身份，实际执行者补事实。结果写入允许的输入文件后执行只读检查：

```bash
python3 "$GTO_CONTROLLER" --action validate-result --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$subtask_id" --result-action record-subtask-result --result-json-file "$result_file" --json
```

work、integration、acceptance、final_documentation 使用 `record-subtask-result`；审查使用 `record-review-result` 且载荷为 `{"review": ...}`；修复取样例中的 `finding_fix` 对象，使用 `record-finding-fix` 并提供 `--finding-id`。修复模板的 `sha256` 替换为实际变更哈希，`verification` 为字符串；身份必须匹配已登记的修复负责人。预检共用正式处理函数，在内存副本中应用并验证，不创建锁文件、不写六工件、不追加事件、不增加次数。

`ready_for_record=true` 只表示此刻符合接收条件；协调器仍核对真实证据，再用对应正式 action 提交。正式接收重新读取状态、候选与证据；预检不是可复用批准凭证。可独立判断的 schema 错误一次返回，依赖有效结构或阶段的语义检查随后执行。审查的 `input_scope` 缺省时仍由控制器生成，不要求子代理伪造。

字段、枚举或身份错误修正载荷即可；缺少真实证据需补验证；产品行为失败才走修复。不因格式修正重做仍然有效的工作。

## 分批验收证据合同

本节是分批证据字段与机械边界的唯一正文；示例见 `revision-3-results.example.json`。本合同于任务 `20260920-155425-863065-gto-evidence-batches` 冻结，文档完成不表示实现或验收已经通过。仅适用于 `workflow_revision=3`；原有 full/scoped 路径及其首次全量、继承、预算和 finding 门禁保持不变。

新增 `record-acceptance-evidence-batch`、`record-acceptance-coverage`，均使用现有 `--repo-root/--task-id/--result-json-file/--json` 参数。前者追加 `acceptance_gate.evidence_batches`，后者追加 `acceptance_gate.coverage_receipts`；首批冻结 `acceptance_gate.batch_contracts` 中对应 kind 的合同。所有派生值由控制器计算，不手工编辑 state。两个动作不创建运行或 attempt，不增加模型调用和预算。

### 可重算的文件与单元合同

`fileRef={path,sha256}`：path 是消费仓库内真实普通文件的相对路径，不允许越界或借 symlink 指向仓库外；sha256 是文件原始字节哈希。`valueRef={path,sha256,pointer}` 在 fileRef 上增加 RFC 6901 JSON pointer；空字符串指整个 JSON。读取缺失、歧义或类型不符均拒绝。对象值哈希使用 UTF-8、键排序、无额外空格的 canonical JSON。哈希字段使用小写 64 位十六进制。

`contract` 为 fileRef，所指 JSON 固定为：

- `kind`：`ordinary` 或 `blackbox`，不接受 preparation。
- `fixture`：`{path,sha256,collection_pointer,id_pointer}`。collection_pointer 选中完整场景数组，id_pointer 相对每个元素取非空唯一字符串 ID。禁止过滤表达式和只选择部分数组；独立 reviewer 审查此集合确实是完整验收输入集合。
- `required_units`：`[{unit_id,acceptance_id,current_input:{pointers:{name:pointer}},raw_selectors}]`。unit_id 集合必须精确等于 fixture 派生全部 ID，不重不漏；acceptance_id 均属于该 kind，且映射覆盖该 kind 全部 AC。current_input.pointers 相对相应 fixture 元素，名称非空、映射非空；控制器重算命名值对象作为当前输入投影。raw_selectors 必须显式声明并随本合同字节哈希冻结，不提供隐式字段名或旧格式兼容默认。

`raw_selectors` 为 `null` 或 `{unit_id,execution_status,executed_values}`。使用 JSON valueRef 时必须为对象：unit_id 与 execution_status 都是相对 raw.pointer 所选记录自身的 RFC 6901 pointer，控制器仅在该对象内解析，不能引用原文件根、祖先或相邻记录；所选 ID 必须精确等于本 unit_id。executed_values 是非空且不重复的字符串或布尔值数组，以 canonical JSON 严格类型相等比较所选执行状态。比如归档记录可声明 `{"unit_id":"/scenario_id","execution_status":"/status","executed_values":["OUTPUT_ARCHIVED"]}`，合成夹具同样显式声明 `{"unit_id":"/id","execution_status":"/executed","executed_values":[true]}`；控制器不硬编码任一业务字段或状态。映射只证明该单元存在实际归档输出，不能代表效果通过，独立 source_score 的 PASS、作者、输入及原始文件哈希绑定仍全部必需。

使用不选取 JSON 记录的 whole-fileRef 时 raw_selectors 必须为 null，原有真实执行独立审查仍必需。同一文件可为多个不同 JSON record 提供证据，唯一性按原始文件与具体 selection 保留；重复同一 selection 或用同一 whole-fileRef 重复计数仍拒绝。不得复制、改写原始输出来伪造符合固定字段的记录，也不能把 whole-fileRef 当作绕过具体单元验证的替代路径。

首批登记时冻结 contract 字节哈希与解析合同；后续批次必须使用同一 kind 的相同合同。合同变化不能通过减少 required_units、缩小 collection_pointer 或删除 AC 规避既有要求。历史 fixture 无完整归档时，允许从真实历史 raw 选择实际执行输入投影，但必须有下述独立投影完整性审查；禁止用当前 fixture 重建历史再声称旧输入一致。

### 批次载荷

顶层字段固定为 `batch_id/source_attempt_id/written_by/written_role/contract/units/applicability_review`。written_role 为原 dispatch 角色，written_by 同时匹配原 attempt 子任务 dispatch 与已有 result（若有）。units 为非空列表，每项字段：

- `unit_id/acceptance_id`：必须匹配冻结合同。
- `raw`：fileRef 或 valueRef，绑定真实已执行的原始文件字节；日志、图片等非 JSON 证据使用 fileRef，选中 JSON 内具体记录时使用 valueRef，并按冻结 `raw_selectors` 核对该记录的单元 ID 和实际归档状态。历史 terminal 来源的 raw.path 必须属于原 result 的 `evidence_refs` 与 `evidence_by_acceptance_id` 引用并集，不能事后塞入未知来源输出；当前 pending 来源允许正式绑定原验收者提交其真实归档记录，由独立审查通过 `units_sha256` 连同 raw 文件/可选 pointer、input 与 score 一起绑定，随后 partial 结果必须把这些 raw.path 全部列入本次 evidence_refs。此分支不声称 pending 已存在原 result。
- `input`：`{path,sha256,pointers:{name:pointer}}`，pointer 相对该文件根。命名集合与合同一致，历史和当前命名投影 canonical 值必须相等。input 可指真实 raw 文件不同层级；历史来源必须属于原 attempt 已归档证据，当前 pending 则与该批次真实归档来源一起审查。
- `score`：valueRef，指原验收者新增规范化评分索引中对应记录。所选记录固定为 `{unit_id,outcome,raw_sha256,input_sha256,written_by,source_score,source_score_selectors}`；outcome 只能 `pass`，raw_sha256 绑定 raw 整文件字节哈希，input_sha256 绑定命名输入投影哈希，written_by 匹配原验收者。
- 评分记录中的 `source_score` 为 valueRef，指真实既有独立评分单元；`source_score_selectors={unit_id,outcome,written_by}` 的每个值为相对 source_score 所在文件根的 pointer。控制器读取并核对 ID、作者和通过状态；通过字符串仅按大小写归一接受 `pass`，不接受失败、未执行、不可判定。不得只复制一个自报 PASS 代替已有评分来源；原 score/raw 文件不修改。

原 attempt 为 terminal environment_failure 时可追加其中真实已执行且后来独立评分通过的部分单元；不修改原 result、terminal、dispatch、失败记录或预算。有效效果失败、未执行或评分不通过单元不通过该入口改判；现有有效效果失败处理与用户决定门禁保持。

### 独立适用性审查

`applicability_review` 为 fileRef，所指记录固定为 `written_by/written_role/source_attempt_id/source_candidate_id/current_candidate_id/source_coverage_sha256/current_coverage_sha256/delta_sha256/changed_paths/unit_ids/units_sha256/input_projection_complete/compatible/reason/evidence_refs`。

written_role 为 reviewer；written_by 必须匹配本任务已绑定且已有通过结果的独立 reviewer，并与该批次验收者及实施/整合/修复身份不同。source/current candidate 对应真实源 attempt 与当前 frozen candidate。source_coverage_sha256 和 current_coverage_sha256 绑定完整 coverage_snapshot 的 canonical hash；delta_sha256 绑定按路径排序的 `[{path,before,after}]`（缺失值为 null），changed_paths 精确覆盖全部新增、删除及变更路径。unit_ids 精确等于该批次单元，`units_sha256` 精确等于 `sha256(canonical(batch.units))`，两个布尔值都须 true，reason 非空，evidence_refs 为非空 fileRef 数组；这些旁证只核原始字节/hash，不要求日志或图片解析为 JSON。

控制器保留源 coverage 与原 AC dependency paths，核验实际完整差异及证据哈希；不接收验收者自定义较窄 paths。历史代码/config/runtime 差异触及依赖时，必须由该真实独立 reviewer 依据完整差异证明这些单元仍适用。未触及原 AC 的差异同样保留在审查记录中，不从全局 manifest 删去。输入投影完整性、fixture 集合完整性、同文件其他函数变化的语义兼容性由 reviewer 判断；机器只保证身份、完整差异、哈希、对应关系与布尔声明被绑定，不能把结构通过表述为机器证明业务语义无影响。

### 局部运行终态与聚合

原 `record-subtask-result` 增加诚实局部终态：`status=completed`、`expensive_acceptance.outcome=partial_pass`、`mode=partial`、`failed_stage=none`；保留原实际调用、耗时、工具使用、blackbox 会话输入 trace 等要求，并增加 `executed_unit_ids` 与 `evidence_batch_ids`。至少一个已登记批次必须来自该 attempt；executed_unit_ids 精确等于这些批次单元并为合同完整集合的真子集。`scope_acceptance_ids` 等于单元对应 AC，`evidence_by_acceptance_id` 只能含本次真实单元证据；不能声称这些 AC 下未执行单元通过。partial_pass 不能单独通过 CLOSE/finalize，不消除待处理 finding，不豁免效果失败决定；它只把实际局部运行成本记录一次。首个局部 attempt 使用该独立分批路径，不能借 mode=partial 放宽 full/scoped 原门禁。

聚合载荷固定为 `{coverage_id,kind,candidate_id,contract_sha256,batch_ids,written_by,written_role}`。作者必须为同一原验收者，candidate_id 指当前 frozen candidate，batch_ids 非空且唯一。所有批次重验后，其单位并集必须精确覆盖合同全集且彼此不重叠；所引用当前 attempt 必须已诚实终结，不能将 pending 当作完成。控制器生成 `same_round_full_execution=false`、完整场景→AC 覆盖及来源索引；聚合不是新运行，不写假 `outcome=pass` 到任一源 attempt。

同一 ID、完全相同 payload 为幂等无写入；同 ID 不同 payload、换 ID 重复同源场景/raw、重叠 batch 计数均拒绝。所有动作先在副本完整校验再持久化；拒绝必须使六工件字节不变。历史 batch/coverage 的结构、来源文件与哈希始终追加保留并可重验，后来出现真实失败或冻结新候选时不能让旧回执阻止该事实落账；当前可用性另行严格判断，只有目标仍为 current frozen candidate、完整引用仍有效且没有更新的失败时才贡献 CLOSE/finalize。登记及当前消费重新核对完整 source/current coverage、身份和单元集合；引用替换、当前候选变化、来源丢失、漏项或后来失败会使其不再贡献当前覆盖，不能仅信首次通过缓存。合法完整聚合可满足对应 kind 的当前覆盖门禁；独立 Review、finding、必需 verification evidence 归属、其他 kind 验收和最终文档闸门继续单独执行。必需 evidence key 不因存在聚合而自动视为满足，只能从聚合所引用的源 acceptance result 中取得该模板/kind 合同 key，并继续通过 owner、registered ref、文件存在与 hash 校验。

本页命令先沿用 SKILL.md 的路径约定：GTO_SKILL_DIR 是本轮实际读取的 SKILL.md 所在绝对目录，GTO_CONTROLLER="$GTO_SKILL_DIR/scripts/orchestrator_ctl.py"；repo_root 单独指向消费项目。不要把项目目录或未核对的 CODEX_HOME 当成工具来源。

当前包仅接受本文的 workflow_revision=3 合同；不接受旧版或未声明版本的合同。

`state.json` 是 GTO 唯一机器状态真源。当前 schema 只接受 `version=3`；`workflow_revision=3` 和机械 `acceptance_gate` 必填。普通模型直接消费 `task.md` 和主协调器给出的显式子任务提示；只有控制器机械读取完整 state。

长任务同时保留：

- `docs/ai/tasks/<task_id>/state.json`
- `docs/ai/tasks/<task_id>/task.md`
- `docs/ai/tasks/<task_id>/events.jsonl`
- `docs/tasks/<task_id>/plan.md`
- `docs/tasks/<task_id>/execution.md`
- `docs/tasks/<task_id>/acceptance.md`

## 根字段

必填字段包括 `task_id`、`title`、`status`、`owner`、`six_points`、`approval`、`artifact_sha256`、`objective`、`scope_in`、`scope_out`、`acceptance`、`stop_conditions`、`decisions`、`current_phase`、`workspace`、`review_policy`、`findings`、`next_action`、`subtasks`、`updated_at` 和 `version`。还必须有 `workflow_revision=3`、`checkout_binding`、`initial_test_owners` 和 `acceptance_gate`。

`verification_contract` 在进入 `code_impl` 或 `review` 前必填，固定包含：

- `minimal_repro`
- `hit_proof`
- `diagnostic_checks`
- `acceptance_checks`
- `non_goals`
- `review_evidence`

## 初始化

`owner` 与 `agent_key` 是逻辑 identifier：以 ASCII 字母或数字开头，后续只含字母、数字、`.`、`_`、`:`、`-`。下面的 `owner='coordinator'` 是可直接执行的合法示例（`root` 也合法）。不要把协作 task 路径 `/root` 或平台显示昵称直接填入这些逻辑字段；`platform_agent_id` 则必须原样复制真实派发工具返回的 ID，不能自行编造或用逻辑 owner 替代。

`platformAgentId` 与 `writerIdentity` 专用于真实平台身份，接受既有 opaque ID 以及 canonical `/root`、`/root/<child>`、更深子路径；不会把这些路径放入 owner/agent_key 的 identifier 值域。`written_by`、派发/血缘的 `platform_agent_id`、`reviewer_platform_agent_id` 从本轮 developer 代理标识或真实协作工具取得并保持原值。若 developer/list_agents 明确主代理为 `/root`，协调 blocked/resumed 载荷的 `ACTUAL_COORDINATOR_ID` 就替换为 `/root`，不能伪造 UUID 或改成逻辑 owner/昵称。schema 识别格式，不证明身份来源；实际派发、作者匹配及同身份恢复校验继续保留。

```bash
owner='coordinator'
python3 "$GTO_CONTROLLER" \
  --action new-task --slug control-plane-bootstrap --json

python3 "$GTO_CONTROLLER" \
  --action init-task --repo-root "$repo_root" --task-id "$task_id" \
  --title "$title" --owner "$owner" --contract-json-file "$contract_json_file" --json
```

`--contract-json-file "$contract_json_file"` 是 Codex 已定稿的结构化合同 JSON 文件，必须包含六要点、批准信息和至少一个真实子任务。初始子任务状态仅使用 `pending` 或 `ready`。

控制器先在内存中构造完整候选 state 并执行 canonical schema 校验，随后才创建任务目录、获取任务锁和写入六工件。合同读取、结构校验或 schema 校验被拒绝时，`state.json`、其余五份工件和 `.control.lock` 都不得残留。

## 阶段与门禁

```bash
python3 "$GTO_CONTROLLER" \
  --action set-phase --repo-root "$repo_root" --task-id "$task_id" \
  --phase doc_sync --json
```

只允许 `planning -> doc_sync -> test_sync -> code_impl -> review` 的相邻单向推进。`code_impl` 和 `review` 复用同一组机械语义门禁：

- `verification_contract` 六个字段完整。
- `workspace.overlap_decision.status` 为 `not_required` 或 `resolved`。
- `review` 阶段需要的 pre-final evidence 已由任一 completed、非 reviewer 子任务覆盖；不按角色预设 evidence key 套餐。

转换拒绝时不修改 `state.json` 或 `task.md`；成功时同步 `current_phase`、`task.md` 投影、工件哈希和 `phase_changed` 事件。

## Workspace

`workspace` 固定包含 `repo_root`、`checkout_kind`、`branch`、`head`、`dirty_paths`、`write_overlap` 和 `overlap_decision`。唯一写入入口是：

```bash
python3 "$GTO_CONTROLLER" \
  --action prepare-workspace --repo-root "$repo_root" --task-id "$task_id" --json
```

控制器读取当前 Git checkout 的 branch、HEAD 和 dirty paths，并与所有未完成、非 reviewer 子任务的安全仓库相对 `write_paths` 比较。任务的六个控制工件、`.control.lock` 和仓库外绝对 runtime 路径不参与重叠计算。

- 无 overlap：原子写入 capture，`overlap_decision.status=not_required`，命令成功。
- 有 overlap 且没有非空 `--workspace-summary`：原子写入本次 capture 和 `pending`，随后非零返回并要求明确授权；不得写入伪造的 `resolved` 或 baseline hashes。
- 有 overlap 且提供非空 `--workspace-summary "$summary"`：重新采集同一组实时 Git 证据，为当前 overlap 内容写 `baseline_hashes`，再标记 `resolved`。

该 action 不清理、暂存、提交或改写用户 dirty 内容。

## 派发与结果

`subtasks[]` 至少包含 `subtask_id`、`title`、`role`、`status`、`dependencies`、`read_paths`、`write_paths` 和 `assignment`。`assignment` 包含 `goal`、`must_include` 和 `verification`。

平台完成真实派发后，记录身份与提示哈希；若 brief 已落盘，`bind-dispatch` 还必须传入 `--brief-path "$brief_path"`，控制器校验该路径对应的实际摘要后再绑定派发记录：

```bash
python3 "$GTO_CONTROLLER" \
  --action bind-dispatch --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$subtask_id" --agent-key "$agent_key" \
  --platform-agent-id "$platform_agent_id" --context-mode isolated \
  --brief-kind "$brief_kind" --brief-sha256 "$brief_sha256" \
  --brief-path "$brief_path" --json
```

completed 和 blocked 结果均通过 `record-subtask-result --result-json-file "$result_json_file"` 写回。结果必须包含状态、摘要、变更文件、未变更计划文件、验证、偏差、阻塞、风险、后续、写入者和角色。

`bind-dispatch` 要求声明的 dependencies 已完成，并校验真实 brief 文件、计划代理、能力证明、stage 和候选门禁。

## Finding 和复审

review result 使用 `record-review-result --result-json-file "$result_json_file"`。finding 保持稳定 `finding_id`，并记录 `lineage.original_implementer` 与 `lineage.original_reviewer`。

```bash
python3 "$GTO_CONTROLLER" \
  --action dispatch-finding-fix --repo-root "$repo_root" --task-id "$task_id" \
  --finding-id "$finding_id" --json

python3 "$GTO_CONTROLLER" \
  --action record-finding-fix --repo-root "$repo_root" --task-id "$task_id" \
  --finding-id "$finding_id" --result-json-file "$result_json_file" --json

python3 "$GTO_CONTROLLER" \
  --action build-review-brief --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$review_subtask_id" --finding-id "$finding_id" --json
```

`max_fix_rounds=3` 对每个 `finding_id` 独立生效，仅真实 fix dispatch 增加轮次。re-review 回到原 reviewer：`re_review/pass` 只能报告至少一个既有 finding，且每项 `status=closed`；open 或未知 finding 均被拒绝。task/final 的 pass 不得携带 finding。第三轮后仍 open 则进入 `blocked`/人工裁决。

`record-review-result` 只接受已绑定、`in_progress` 且尚无 result 的 reviewer 子任务。`kind=re_review` 只属于 `create-re-review-subtask` 追加且带 lineage 的子任务；普通 review 使用 `kind=task`。终态 review 不能覆盖或改写。

`create-re-review-subtask` 从 terminal `task/fail` 或 `re_review/fail` 创建同一原 reviewer 的 append-only 复审子任务，只纳入当前 `awaiting_re_review` 且已有 `fix_delta` 的 finding。复审继续应用当前阶段与候选门禁。多轮 pre-acceptance review 按同一 reviewer 的各轮 `status=closed` finding 取并集，并要求后续至少一轮 `re_review/pass`，不能要求单轮重复完整 finding 集合。


## 当前候选与昂贵验收

`subtasks[].stage` 固定为 `work / integration / pre_acceptance_review / expensive_acceptance / final_documentation`。测试与实施的依赖顺序、整合与审查汇合点以批准 DAG 为准；验收后仅作最终文档收尾。已完成或 blocked 子任务不可重开；后续昂贵验收由 `create-subtask-attempt` 创建新子任务和 append-only attempt。

`acceptance_gate` 保存声明的候选输入、当前冻结候选、验收条目、attempt policy 和 attempts。frozen candidate 必须同时保存 `fingerprint` 和 `frozen_at`；`freeze-candidate` 计算候选指纹，覆盖目录、symlink、配置、运行输入和验收条目，任一输入改变即令候选 stale。

每次昂贵验收必须由 `create-subtask-attempt` 预建，并在结果中保存 `outcome`、`real_call_count`、耗时、失败阶段、证据引用和每个 acceptance item 的 evidence mapping。完成 attempt 必须指向对应的 `stage=expensive_acceptance` 子任务，并与该子任务的结果证据一致；pending attempt 必须属于当前 frozen candidate。控制器默认限制 `max_expensive_attempts=4`；只有 `written_role=coordinator`、`approved_by=user`、包含非空原因和授权证据、声明的 previous maximum 精确匹配当前值且新值严格增加的 `extend-acceptance-budget` 回执，才会追加 `acceptance_gate.budget_extensions` 并提高当前任务上限。续批不修改历史 attempt、候选、身份、finding、任务阶段或下一动作，也不提供审查/验收通过证据。`max_full_attempts_per_candidate=1`、`max_environment_retries_per_candidate=1` 保持不变，并从 `approval_required_from_attempt=3` 开始要求每次 attempt 明确批准。attempt、预算续批与 review 均为 append-only；没有完整自洽用户授权链的上限修改会被拒绝，授权事实真实性由协调者和独立验收核对，passing evidence 仍不能手写预种。


## 体积与 allowlist

schema 对固定结构使用字段 allowlist，并限制字符串、数组和哈希形状。state 只保存短摘要、仓库相对路径、哈希、commit range、命令名和结论，不保存完整 stdout、diff、prompt、聊天记录或第二控制面 package/report。

## workflow_revision=3 行为合同与接口核对

通用流程唯一见 [workflow.md](workflow.md)；本页是字段导航，不另建字段真源。完整要求清单及其责任/验收引用需要由同一机器合同生成与校验；准备复查和正式首轮效果停止必须区分。具体字段方案在独立测试后与 schema/实现统一，本规范不预设新增字段。

角色语义：`subtask.role` 是职责，`assignment` 是目标、必含项与验证说明，没有 `assignment.role`；`dispatch.agent_key` 是逻辑派发键，`platform_agent_id` 是平台真实身份，当前 `result.written_role` 对齐逻辑键，`written_by` 对齐真实身份。后续最小合同变动须同时更新 schema 与示例，避免手填重复和含混。

本节先冻结行为合同；新增或调整字段、允许值及 CLI 载荷必须在独立行为测试和实现完成后，连同同候选 schema、JSON 示例一起核对。字段建议不能反过来规定测试实现。不能将本文当作机械门禁已实现或已投放的证明。

### 终态证据补登记合同

- 只允许已完成、`outcome=pass` 且非 preparation 的 `expensive_acceptance` 原验收作者，针对该验收原终态结果缺失但合同要求的证据引用发起追加；receipt 固定为 `written_by`、`written_role`、`source_subtask_id`、`source_result_sha256`（原 result canonical hash）、`candidate_id`、`candidate_fingerprint`、`evidence_key`、`evidence_refs[]` 八个字段。`written_by/written_role` 必须同时匹配原 dispatch 和原 result，来源仍须属于当前候选；补登记不是重验，不能改写原 result、候选、attempt、验收结论、finding 或失败历史。
- 索引只引用来源验收结果已经登记、仓库内真实存在的证据文件，不复制证据内容，不建立第二份事实。身份不符、源 hash 不符、候选过期、引用未登记、不存在或越界时整次拒绝且零修改；完全相同的重放幂等，同一 `source_subtask_id/evidence_key` 绑定下内容冲突时拒绝。
- 昂贵验收模板的 assignment 可声明 `required_verification_evidence={ordinary:[generic_key],blackbox:[generic_key]}`；key 是 `verification_contract.review_evidence` 的子集，并且在模板/kind 之间唯一归属，attempt 对模板的继承不算新归属。preparation 不要求该声明。验收登记先检查实际 attempt/kind 的声明；声明 key 在结果中完全漏填也拒绝。
- 新建 attempt 显式保存 `template_subtask_id`；缺少该字段的 attempt 拒绝，不从 ID 推断或回溯历史模板。直接验收结果、补登记 receipt 以及 CLOSE/finalize 消费都核对 template/kind owner，不能跨模板或 kind 使用专属 key。
- 仅 `expensive_acceptance` 的 `result.review_evidence` 值必须是本轮已经登记且真实存在的证据索引文件路径，不写摘要或复制证据正文；普通 work/integration 的 Red/Green 说明按其结果合同填写。CLOSE 绑定与 finalize 前再汇总全部必需证据。未声明 `required_verification_evidence` 时不要求额外通用证据项，控制器不按 AI/FUNC 等业务名称猜测归属；需要补登记时由原验收作者选择正确证据。

- 一个或多个独立测试子代理编写初始测试，与实现者身份分离；独立文件可并行，共享 fixture 单一写入者。整合子代理不提前介入设计或影响独立测试，待全部实现 TDD 完成后才开展唯一整合职责。
- 实现者完成真实 Red/Green 与相关回归；整合者记录入口、接口、配置、数据、异常路径检查及正式文档同步。实际命令、范围、退出结果、证据与身份必须可核对，不能只填 passed。
- reviewer 首次完整审查并尽量完成全部独立检查后批量报告；之后围绕 finding、fix delta 和影响范围复审。影响扩大则扩大覆盖，保留稳定 ID、关闭/重开状态和失败历史。
- 每个 review/验收 finding 均由发现者复现、定位根因、提出修复方案、补真实失败测试或可执行证明、同步相关正式文档或说明不适用。证明记录实际命令、范围、真实失败结果、预期失败及证据引用，作者是发现者。
- 所有代码 finding 的修复责任固定为原整合责任者；修复须依据问题合同，不能放宽测试、删断言或改预期。原并行实现者不返工。修复及重新整合结果追加保存，终态不重开。
- review finding 修复并重新整合后交原 reviewer 范围复审。首次验收在完整审查及必要复审通过后覆盖本任务全部范围；每个验收条目有实际证据映射。
- 验收 finding 修复并重新整合后直接交同一验收者范围复验并检查修复 delta，不回 reviewer。保留首审与复审基线，记录最新候选、改动路径、影响范围、当前通过项及保留证据依据。失败或未运行项不能继承为通过，范围无法证明时扩大复验至必要的全量。
- review 与验收分别记录实际使用证据：真实执行者、环境、工具、入口/命令、操作范围、结果与证据引用。网页使用宿主实际提供的官方 Browser；桌面 GUI 使用宿主支持的官方 Computer Use；非 UI 使用真实 CLI/API 并明确适用性。
- 验收通过后由一个文档子代理直接排查并同步遗漏的正式文档与六工件事实，不增加双人文档 review。纯文字纠正可直接收口，并不限于空白或排版；真正行为、契约或配置变化才返回验收链。记录同步范围和判定依据，不能任意豁免文档变化。
- 候选覆盖各职责的测试、代码、配置、运行输入和受影响正式文档；仅本任务六工件、内部锁及允许的明确日志按既有边界处理。复验、文档同步与历史证据间的关联必须可追溯。

下列现场命令仅在对应当前 CLI、schema 和同候选示例核对一致后使用。接口落地不另造状态真源。

## 现场调用与回执

完整常用结果位于同目录 `revision-3-results.example.json`。它与 `revision-3-contract.example.json` 共用业务路径和验收 ID。主协调器先把一个对象复制到本任务输入文件，再由实际执行者填真实内容：

```bash
jq '.acceptance_pass' "$GTO_SKILL_DIR/references/revision-3-results.example.json" > "$result_json_file"
```

这里仅生成待填写载荷，不能立即把示例当成真实结果提交。所有 `ACTUAL_*` 替换为真实平台返回身份；普通结果 written_role 与 bind 的 agent_key 一致，review 使用独立 reviewer 身份。路径按批准合同填写，检查命令/退出码/证据/次数/耗时来自实际运行。产品实施 work 的 red 必须命中预先声明的缺失行为；文档、测试准备和汇总按各自职责提供检查，不强制伪造产品 Red/Green。预期 Red 判定见 [包内命令失败规则](governance.md#命令失败与重试)。integration 单独提交全部受影响 document_paths。reviewed_candidate_fingerprint 从本轮 build-review-brief 取值；covered_paths 覆盖实际完整审查范围。

合同五个镜像必须逐值一致：objective/do、scope_in/change_areas、scope_out/do_not、acceptance/acceptance、stop_conditions/risks。斜杠右侧均为 six_points 字段；decisions 包含 six_points.implementation。新 init 从 six_points 派生缺失镜像、补 implementation 并保留独立 REQ 清单；调用方不需要手填两遍，显式冲突仍拒绝。既有 state 不批量迁移。

### 派发路径与哈希

brief_path 是相对 `--repo-root` 的路径，例如 `.tmp/refund/brief-WORK-001.md`，不传 `/project/...` 绝对路径。先保存本轮显式派发正文，再用实际文件字节 SHA-256 绑定；平台身份来自已经发生的真实派发。以下在文件已存在且各身份变量已赋值后运行：

```bash
brief_sha256=$(sha256sum "$repo_root/$brief_path") && \
brief_sha256=${brief_sha256%% *} && \
python3 "$GTO_CONTROLLER" --action bind-dispatch --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$subtask_id" --agent-key "$agent_key" --platform-agent-id "$platform_agent_id" \
  --context-mode isolated --brief-kind "$brief_kind" --brief-path "$brief_path" --brief-sha256 "$brief_sha256" --json
```

brief_kind 为 subtask 或 review。不能根据源码文件内容计算 brief_sha256，也不能猜测平台 ID。

`build-review-brief` 的三种哈希不要混用：

| 字段 | 含义及用法 |
| --- | --- |
| source_manifest[].sha256 | 普通文件字节 SHA-256，可与对应文件 sha256sum 对照；missing 是缺失标记 |
| candidate_manifest[path] | 候选记录的结构化哈希，记录同时包含输入类别、逻辑路径、解析目标和内容状态；不是文件字节 SHA-256，不与 sha256sum 直接比较 |
| candidate_fingerprint | 整个候选和验收合同的指纹；原样填 review.reviewed_candidate_fingerprint |

目录、symlink、缺失输入的状态由控制器纳入候选。要复核清单是否变化，针对同一候选再次 build-review-brief 比较同类字段，不把不同哈希混在一起断言。

### 验收与文档收尾

冻结和创建 attempt 是依赖关系，只有前一步 exit 0 / ok=true 才执行下一步；创建动作返回实际 subtask_id，绑定和提交结果必须用此 ID，不使用验收模板 ID：

```bash
python3 "$GTO_CONTROLLER" --action freeze-candidate --repo-root "$repo_root" --task-id "$task_id" --json && \
python3 "$GTO_CONTROLLER" --action create-subtask-attempt --repo-root "$repo_root" --task-id "$task_id" --subtask-id "$acceptance_template_id" --json
```

预算耗尽且用户明确授权继续当前任务时，协调者把授权事实写入仓库内结果 JSON，再执行：

```bash
python3 "$GTO_CONTROLLER" --action extend-acceptance-budget --repo-root "$repo_root" --task-id "$task_id" --result-json-file "$budget_extension_json_file" --json
```

该入口在 blocked 状态也只登记续批，不恢复阶段；恢复仍须按 coordinator recovery 合同单独提交成功证据。

平台验收者在真实运行后填 acceptance_pass 载荷：status=completed、outcome=pass、failed_stage="none"（不能是空串）、blocked_by=[]。real_call_count/duration_seconds 是真实测量，evidence_by_acceptance_id 覆盖该 attempt kind 对应的业务验收项；ordinary 覆盖非黑盒项，blackbox 覆盖 blackbox_acceptance_ids，preparation 不贡献业务验收证据。失败使用 blocked 与 product_failure/environment_failure 及真实 failed_stage；业务失败先通过 record-acceptance-findings 登记发现者证据，再用其 finding_id 关联失败回执。

验收登记立即核对每条 evidence ref 的来源所属，不能等 finalize 才发现 attempt/kind/acceptance item 错配。若已完成通过、非 preparation 的昂贵验收原作者需要补齐合同要求的已有引用，使用 `record-verification-evidence --result-json-file`；receipt 采用本页固定的八个字段。入口只追加 `verification_evidence_receipts` 索引，禁止手工编辑 state 或覆盖原结果模拟补录。

```bash
python3 "$GTO_CONTROLLER" --action record-subtask-result --repo-root "$repo_root" --task-id "$task_id" --subtask-id "$actual_attempt_subtask_id" --result-json-file "$result_json_file" --json
```

只有该结果成功写入，且全部必需证据已按各自 attempt/kind/acceptance item 归属核对，才可绑定和执行 CLOSE。CLOSE 前的汇总检查引用已有登记，不复制证据正文；缺少所属映射不能用其他验收种类的引用代替。不要把上一条命令的拒绝输出当成验收已记录。事实填写保留 task.md 的“当前状态”和 acceptance.md 的“最终结论”受管区域；业务结论写在非受管部分。revision 3 未 finalize 时，“最终结论”必须包含原样标记：

> 任务尚未完成；需最新候选审查、验收和事实回执。

控制器 finalize 成功后会自动改成：

> 最新候选已通过完整独立审查覆盖及真实验收，事实已同步，任务完成。

收尾先由单文档子代理检查并直接同步遗漏的正式文档和纯文字纠正，再修改非受管事实、accept-artifact-update 成功、提交 final_documentation 结果成功、finalize；真正行为/契约变化先返回验收链。不要手填完成标记来提前通过；失败不会因业务语义近似而绕过精确投影校验。

```bash
python3 "$GTO_CONTROLLER" --action accept-artifact-update --repo-root "$repo_root" --task-id "$task_id" --json && \
python3 "$GTO_CONTROLLER" --action record-subtask-result --repo-root "$repo_root" --task-id "$task_id" --subtask-id "$closeout_id" --result-json-file "$closeout_json_file" --json && \
python3 "$GTO_CONTROLLER" --action finalize-task --repo-root "$repo_root" --task-id "$task_id" --json
```

遇到任一步意外非零，保存失败并进入适用的命令失败闭环；缺少必需能力时停止该失败链，不能继续后面的依赖命令。以上分段是不同阶段的示例，不能把 finding/验收/收尾的 action 清单当作无条件连续执行脚本。

## Revision 3 协调层阻塞回执

`set-phase --phase blocked --result-json-file <receipt>` 复用完整 result 载荷，status 必须 blocked，written_role=coordinator、blocked_by 和 verification 非空。控制器保存 `coordinator_blocker={previous_phase,result}`，task status/current_phase=blocked，next_action=human_adjudication。这与正常相邻推进分开。

当前阻塞期间禁止新派发、新候选/attempt、修复调度和 finalize；允许 validate、build-review-brief、accept-artifact-update、`extend-acceptance-budget`，以及已绑定独立任务登记结果/审查回执。治理续批只追加用户授权并递增本任务总 attempt 上限，不恢复阶段，next_action 仍保持 human_adjudication。单个子任务的 blocked 结果不会自动推断整个任务是否受阻，由协调者明确判断并登记。

恢复使用同一个 set-phase，目标只能是保存的 previous_phase，载荷取 `revision-3-results.example.json` 的 coordinator_resumed：同一 written_by、written_role=coordinator、completed、blocked_by=[]、非空 verification、成功 checks（至少 regression，所有退出码=0）及证据引用。能力缺口要记录原能力恢复及对应失败证据的复核；不得在真实探针未成功时填入成功回执。控制器仅核验结构化声明，不执行命令、不读取外部库、不通过命令名猜测根因。阻塞和恢复完整 result 追加到 coordinator_blocked/coordinator_resumed 事件；只清除当前 blocker，不删除历史、不自动重试。

未初始化成功的任务不能调用这一状态入口；此时保留失败证据并明确报告 blocked，不为造 state 重试 init。不能访问未授权历史或伪造恢复证据。恢复前仅保留独立安全工作和事实，不能把局部业务通过改写为整体 completed。

## Revision 3 机械字段与验收返工接口

- `initial_test_owners` 当前标识初始测试任务；目标依赖与复用合同见 [测试协作](workflow.md#测试协作与文档清理)。文档/测试准备/汇总不冒充产品实现；按可达依赖等待测试，同一测试负责人可复用，测试与实现/整合保持身份独立。控制器检查传递可达的依赖和真实绑定身份；结构通过不能证明平台实际隔离。
- 新 finding 必须有 `root_cause`、`fix_plan`、`regression_proof` 和 `documentation_update`。后者包含 `written_by`、`status=updated|not_applicable`、`paths`、`reason`；updated 必须列出正式文档，not_applicable 说明原因。证明作者与文档同步作者均为发现者，失败退出码非零且等于预期；`routed_to` 固定为首个 integration 的真实身份。
- review 和 expensive_acceptance 各自包含非空 `usage_evidence` 数组。每项为 `written_by/environment/tool/entry/scope/result/evidence_refs/ui_applicability/ui_not_applicable_reason`；required 使用宿主实际提供的 Browser 或 Computer Use，不按操作系统限制工具；`environment` 如实填写实际执行环境的非空名称，无操作系统白名单。not_applicable 使用实际 CLI/API 并说明 UI 不适用原因。回执是对真实操作的索引，字段格式本身不是实际使用证明。
- expensive_acceptance 包含 `mode=full|scoped`、`scope_acceptance_ids`；首次始终 full。`evidence_by_acceptance_id` 仅记录实际通过项，控制器生成 `passed_acceptance_ids`。scope 之外通过项必须在 `retained_evidence_by_acceptance_id` 中逐项给出最近 attempt 的 `source_attempt_id/evidence_refs/reason`，作者保持同一验收身份。失败和未运行项不能继承。
- scoped 必须提交 `impact.changed_paths/affected_acceptance_ids/reason`。控制器核对两次实际候选 manifest，包括删除项；每个 acceptance item 的 `paths` 声明其依赖路径，所有被改动命中的项目都必须重新执行。输入/验收合同变化、未映射改动或证据不足时运行 full，不靠自报影响范围保留旧证据。
- 验收发现的问题可声明 `acceptance_ids`，这些项目不能同时被本轮记录为通过。修复回执使其进入 `awaiting_retest`；创建并完成新的 integration 后 freeze 新 candidate，再 create-subtask-attempt，绑定同验收者。通过复验在 `closed_finding_ids` 列出全部待关闭验收 finding，控制器追加 `closed_by_attempt_id` 并直接关闭，不调用 create-re-review-subtask。首次完整审查形成的 `review_baseline` 及每次实际候选快照由控制器维护，后续免重复review不能靠预种失败回执获得。
- 文档收尾仍只有一个 final_documentation 子任务。`documentation_sync` 包含 `checked_paths/changed_paths/behavior_changed/contract_changed/configuration_changed/reason`，纯文字同步将三个 changed 布尔值记为 false 并说明判断依据。控制器核对真实代码/配置/运行输入及正式文档 delta，仅允许正式文档变化且实际变更与回执一致；记录文档前后候选 hash 后保留原验收证据。真正行为、契约、配置变化必须新整合和复验，不能自报纯文字掩盖可执行文件漂移。

以下是普通验收返工的命令顺序；正式 skill 黑盒效果失败不自动进入该链，先按 blackbox-methodology 的停止出口报告。普通验收返工的实际命令顺序为 `record-acceptance-findings` → 失败 `record-subtask-result` → `dispatch-finding-fix` → `record-finding-fix` → `create-integration-subtask` → 原整合者新结果 → `freeze-candidate` → `create-subtask-attempt` → 同验收者范围复验结果 → 单文档同步 → `finalize-task`。每步只在前一步成功后继续。

初始测试的文件互斥按实际相同的文件判断；`tests/file.py` 与 `tests/./file.py` 等等价路径不构成两个写入范围。同一验收 finding 复验仍失败时，沿用稳定 ID 追加本次失败证明、候选及 attempt 关联，重新交原整合者修复；不得新建重复 ID 清零 fix_round 或丢弃此前失败和 fix_history。验收者的真实平台身份应与实现及整合身份分离，改写 agent_key 或 written_role 不会产生独立执行者。

`acceptance_gate.documentation_sync` 是控制器从真实文档收尾结果生成的派生回执，不能作为手填豁免入口。沿用旧候选证据前仍需核对真实 delta 仅属于 document_paths、未命中 code/config/runtime 输入，且与对应文档执行者的完成结果和变更清单一致。schema 形状和前后指纹本身不足以证明这项约束。

## 正式黑盒的机器入口

字段定义以 [包内 schema](../schemas/orchestrator-task-state.schema.json) 为准，载荷例子仅在 [结果示例](revision-3-results.example.json) 中维护。普通阶段流程见 [任务流程](workflow.md)，黑盒层级与用户决定时机见 [分层方法论](blackbox-methodology.md)。

`create-subtask-attempt --attempt-kind ordinary|preparation|blackbox` 默认 ordinary。准备结果验证投放、版本、环境、输入/会话及采证检查与引用，不声明业务 AC 通过；创建 blackbox 前必须已有同候选 preparation pass，控制器绑定 preparation_attempt_id。普通通过与准备通过不能解除既有正式效果失败的停止状态。

正式结果使用 pass、effect_failure 或有 invalid_observation 证据的 environment_failure。effect_failure 保留 session/input/trace 引用与 report_ref；report_ref 可指向现有 acceptance.md 或已有证据，不要求新报告账本。已记录的正式结果不能重分类或覆盖。

主协调器收到真实用户决定后，才提交 `record-blackbox-decision --result-json-file "$decision_json_file"`。载荷引用失败 attempt_id，repair 和 next_round 分别授权；重复相同决定幂等，不改失败历史。repair 仅允许原整合者修复；next_round 不授予修复权限，必须新候选重新 preparation pass，且 authorization_attempt_id 回指原失败。普通 finding 不得绕过停止派发产品修复。无效观察须先留原因及证据，再准备复查，其资源消耗仍保留。

最终业务通过按同候选 ordinary 与 blackbox 各自 AC 聚合；preparation 不补业务覆盖，缺正式黑盒通过时不得绑定最终文档或 finalize。控制器只校验这些结构及证据关联，不认证会话隔离、根因或真实用户授权本身。

六工件保存针对可捕获 OSError 做局部一致性保护：状态替换或事件追加失败时恢复该次写入前的六工件，并保留结构化诊断。该保护不承诺硬杀、断电或恢复写入再次失败时的持久事务语义。

## 运行绑定与能力证明

`assignment.required_capabilities[]` 的定义、探针记录与失效机制，`capability_receipts[]` 的用途，以及 `current_candidate.runtime_snapshot` 的恢复方式唯一见 [运行与证据](runtime-evidence.md)。字段允许项由同包 schema 强制检查；能力声明属于批准合同，回执属于运行事实。公开 validate/preflight 检查当前候选；历史证据仍保留，修复动作不据旧候选过期禁止记录返工事实。
