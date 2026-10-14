# 控制器执行与结果入口

仅按当前阶段读取相应小节；方案编制见 [方案指南](plan-guide.md)，阶段与职责见 [任务流程](workflow.md)，字段定义见 [状态合同](state-schema.md)。

## 运行位置

以当前 `SKILL.md` 所在目录作为 `GTO_SKILL_DIR`；controller、schema 和 references 均从该目录加载，`--repo-root` 始终指向消费项目。普通任务不从消费项目或其他源码目录寻找另一份 GTO。

```bash
GTO_SKILL_DIR='/absolute/path/to/the/loaded/global-task-orchestrator'
GTO_CONTROLLER="$GTO_SKILL_DIR/scripts/orchestrator_ctl.py"
repo_root='/absolute/path/to/the/consumer-project'
```

路径值在执行前替换为已核对的实际目录。新任务合同示例从同一目录的 `revision-3-contract.example.json` 读取，复制到消费项目允许的临时输入位置后填写。

## 六要点合同

初始化前由 Codex 冻结：要做什么、不做什么、改哪些地方、怎么实现落地、怎么验收、有什么风险。Python 只校验这份已结构化的合同，不从自然语言推断任务类型或规则。

同一信息不要改写成两套文本：`objective = six_points.do`、`scope_in = six_points.change_areas`、`scope_out = six_points.do_not`、`acceptance = six_points.acceptance`、`stop_conditions = six_points.risks`，数组顺序和值也必须一致；`decisions` 包含原样的 `six_points.implementation`。六要点是唯一可编辑输入；新 init 自动派生缺失镜像并补入 implementation，保留独立 REQ 清单。显式提供的冲突镜像仍拒绝，已有活动状态不迁移。

`owner` 与 `agent_key` 是逻辑 identifier：以 ASCII 字母或数字开头，后续只含字母、数字、`.`、`_`、`:`、`-`。下面的 `owner='coordinator'` 是可直接执行的合法示例（`root` 也合法）。不要把协作 task 路径 `/root` 或平台显示昵称直接填入这些逻辑字段；`platform_agent_id` 则必须原样复制真实派发工具返回的 ID，不能自行编造或用逻辑 owner 替代。

平台身份字段 `platform_agent_id`、`written_by`、`reviewer_platform_agent_id` 与上述逻辑字段分开。身份取自本轮明确的 developer 代理标识或真实协作工具返回值；若本轮 developer/list_agents 确认主代理是 `/root`，协调阻塞与恢复回执的 `written_by` 就原样填写 `/root`。真实子代理身份也可为 `/root/<child>` 等 canonical 路径或平台返回的 opaque ID；不要假定必须是 UUID、伪造 UUID 或用 `owner='coordinator'`、昵称替代。示例中的 `ACTUAL_*_ID` 均按这个真实来源替换，恢复仍须使用同一身份。

```bash
owner='coordinator'
contract_json_file="$repo_root/.tmp/<task-id>-approved-contract.json"
python3 "$GTO_CONTROLLER" \
  --action new-task --slug control-plane-bootstrap --json

python3 "$GTO_CONTROLLER" \
  --action init-task --repo-root "$repo_root" --task-id "$task_id" \
  --title "$title" --owner "$owner" --contract-json-file "$contract_json_file" --json

python3 "$GTO_CONTROLLER" \
  --action validate --repo-root "$repo_root" --task-id "$task_id" --json

python3 "$GTO_CONTROLLER" \
  --action set-phase --repo-root "$repo_root" --task-id "$task_id" \
  --phase doc_sync --json

python3 "$GTO_CONTROLLER" \
  --action preflight --repo-root "$repo_root" --task-id "$task_id" --json
```

`$contract_json_file` 必须是消费项目自身 `.tmp/` 内已定稿合同 JSON 的明确文件路径。结果和合同载荷只通过
`--result-json-file` 与 `--contract-json-file` 读取；不支持在命令行直接传递 JSON。
`init-task` 仅在完整候选 state 通过 schema 校验后才创建任务目录和六工件；拒绝的合同不留下 `.control.lock`。

每条依赖命令只在前一步退出码为 0 且 JSON `ok=true` 后执行；失败先保存原始输出，按包内命令失败规则处理。不能连续粘贴整段 action 清单，把尚未记录成功的验收当作 CLOSE 的前提。预期 TDD Red 的判定与真实失败处理统一引用 [命令失败与重试](governance.md#命令失败与重试)，按预先声明的最小目标和实际失败类型判断。

## JSON 文件输入与只读预检

合同和结果文件必须包含一个 JSON 值。`init-task` 的输入必须位于消费项目自身 `.tmp/` 内；交付文件、仓库外路径和 `.tmp-other/` 等伪前缀路径均拒绝。读取、解析或字段校验失败时不修改任务工件；初始化拒绝不创建六工件。

`preflight` 只读复用完整 `validate` 和执行阶段门禁，返回任务、阶段、批准合同指纹、下一步和六工件检查摘要；不保存通过标记，成功或失败均不修改六工件。首次交付放行责任见 [流程前置条件](workflow.md#适用范围与施工前置条件)。

## 分批验收操作

原验收者整理真实归档单元与独立评分，由已绑定的独立 reviewer 审查完整候选差异和输入投影完整性。按 [分批证据合同](state-schema.md#分批验收证据合同) 登记批次；定向运行以 `partial_pass` 终结，再引用批次登记当前完整覆盖。只补缺失或失效单元的必要验证，不缩小完整场景集合。聚合不代表同轮全量执行；CLOSE 仍核对 Review、finding、各 kind 与必需证据归属。载荷见同包 `revision-3-results.example.json`。

## Revision 3 执行顺序

子代理提示词由执行主协调器基于冻结子任务撰写，不依赖独立角色目录。提示包含任务摘要入口、assignment、必要依赖结果、read_paths、write_paths、禁改项、验收要求及结果合同入口。子代理先完成指定阅读，只修改授权范围；输入冲突、依赖未就绪或需要越界时回报主协调器。结果按下文“结果合同”提交，由主协调器核验实际证据后推进，不能仅凭子代理自报完成关闭任务。

每次新建子代理，先组织只含当前任务合同、assignment、read_paths、write_paths、验收要求和必要治理约束的独立提示，再调用平台 `spawn_agent`，显式传入 `fork_turns="none"`。不能省略该参数，也不能使用 `fork_turns="all"` 或其他历史继承模式后填写 `context_mode=isolated`。派发成功后，才把工具真实返回的代理 ID 原样用于 `bind-dispatch`；保留可观察的派发参数、返回 ID 与绑定记录供验收核对。提示中的“独立”和 state 中的 `context_mode=isolated` 都是声明，不能证明平台实际隔离；当前控制器不读取平台派发事件或私有推理来验证这件事。

继续原整合者修复、原 reviewer 复审或原验收者复验时，可以重用同一已经以 `fork_turns="none"` 合规创建的代理，并提交当前范围提示。重用不重新宣称其历史为空，不能把曾继承历史的旧代理改名或改写绑定来视为合规。平台不支持无历史派发、创建失败或线程额度不足时，保存实际失败回执并报告 blocked；没有成功返回 ID 就不绑定，不编造新身份，也不能由父代理代替独立测试、审查或验收后宣称完成。

具体阶段、测试负责人复用、文档与实现先后及两条普通返工回路统一执行 [任务流程](workflow.md)；黑盒的层级选择、准备、停止和结果统一执行 [分层黑盒测试方法论](blackbox-methodology.md)。本入口不重复维护步骤表；独立测试者先建立行为证明，实现者不得提前给出答案。文档收尾提供事实材料，由主协调器核对后维护六工件。

review 和验收各自实际使用并留证：网页使用宿主实际提供的官方 Browser，桌面 GUI 使用宿主支持的官方 Computer Use，非 UI 用真实 CLI/API 并说明适用性。记录真实身份、工具、入口/命令、操作范围、结果及证据引用，不能只记录工具名称或复用一次操作冒充两阶段。本文描述目标规范，机械门禁是否实现须核对同候选 schema、控制器和真实行为证据。
取消的是重复 verify 工序；实现和整合的测试责任仍保留。环境问题按实际项目与宿主能力定位，先用包内只读 doctor 检查 GTO 依赖；不做通用自动安装或反复全量诊断。黑盒选层与执行合同见 [分层黑盒测试方法论](blackbox-methodology.md)，通用证据真实性与自有产物清理边界见 [包内治理](governance.md)。

## 阶段推进

`current_phase` 的正常顺序固定为：

`planning -> doc_sync -> test_sync -> code_impl -> review`

正常推进只使用相邻单向阶段，不跳过文档或测试阶段。revision 3 的显式阻塞与原阶段恢复见下节，不用 blocked 绕过正常顺序。

```bash
python3 "$GTO_CONTROLLER" \
  --action set-phase --repo-root "$repo_root" --task-id "$task_id" \
  --phase doc_sync --json
```

进入 `code_impl` 前必须有完整 `verification_contract`，并且 workspace overlap 已是 `not_required` 或 `resolved`。进入 `review` 前还必须有任一已完成、非 reviewer 子任务提供的 pre-final evidence。拒绝转换不修改 `state.json` 或 `task.md`。

实现派发前，用唯一的 workspace action 采集当前 Git 证据：

```bash
python3 "$GTO_CONTROLLER" \
  --action prepare-workspace --repo-root "$repo_root" --task-id "$task_id" --json
```

无写入重叠时该 action 写入 `not_required`。有重叠时，首次调用写入实时 capture 和 `pending` 后非零返回；主协调器取得明确授权后，用同一命令增加非空 `--workspace-summary "$summary"`，控制器重新采集实时证据、写入当前 baseline hashes 并标记 `resolved`。控制器排除本任务六个控制工件和仓库外绝对 runtime 路径，不清理或改写用户 dirty 内容。

## 实际 CLI action

- `new-task`：产生本地时间 task ID，不创建任务文件。
- `init-task`：只从消费项目自身 `.tmp/` 内的已批准合同初始化六工件。
- `validate`：校验 v3 state、配套工件和语义门禁。
- `preflight`：只读复用完整校验与执行阶段门禁，在首次交付写入前返回批准合同指纹和六工件摘要。
- `validate-result`：按 `--result-action` 选择正式结果入口进行只读预检；不能替代证据判断或正式接收。
- `accept-artifact-update`：在人工核对后接受 Markdown 工件更新。
- `prepare-workspace`：采集当前 Git workspace，并机械记录 overlap 决定与 baseline。
- `set-phase`：正常相邻推进；revision 3 还可提交阻塞回执或有成功证明的原阶段恢复。
- `bind-dispatch`：绑定真实平台代理身份、提示哈希和已校验的 `--brief-path`。
- `record-subtask-result`：记录执行或测试结果。
- `record-verification-evidence`：由原验收作者补登记已有证据引用；输入字段、归属、原子拒绝和幂等规则见 [终态证据合同](state-schema.md#终态证据补登记合同)。
- `record-review-result`：记录完整 task 或范围 re_review。
- `record-acceptance-findings`：真实验收身份批量提交问题合同、原整合修复责任者及同一验收复验责任者。
- `create-integration-subtask`：修复后追加原整合责任者的新结果，终态子任务不重开。
- `dispatch-finding-fix`：将稳定 finding 交给记录的原整合责任者并增加该 finding 的轮次。
- `record-finding-fix`：记录 fix delta；review 来源回同一 reviewer 复审，验收来源回同一验收者复验。
- `build-review-brief`：为审查子任务生成当前变更哈希和 finding 摘要。
- `create-re-review-subtask`：为既有 finding 创建同 reviewer 的复审子任务。
- `freeze-candidate`：在前置门禁完成后，按声明的目录、symlink、配置、运行输入和验收条目冻结候选指纹。
- `create-subtask-attempt`：为冻结候选创建不可覆盖的昂贵验收尝试。
- `extend-acceptance-budget`：在用户明确授权后为当前任务追加预算续批链；只递增总 attempt 上限，不恢复任务或放宽其它验收门禁。
- `finalize-task`：要求最新候选审查覆盖、绑定运行清单的验收映射、问题关闭与事实回执。

参数以 `python3 "$GTO_CONTROLLER" --help` 为准；只支持 GNU 双横线形式。

## Finding 和最终门禁

首次 integration 的文档同步权限不延续为 finding 返工权限。发现者亲自维护失败测试和需要更新的正式文档；`documentation_update` 的不适用说明不得把可选说明或测试调整委派给返工者。确需补充时先回发现者完成，再交原整合者依据冻结测试只修产品。revision 3 的返工回执拒绝 candidate_inputs.document_paths 中的正式文档和 tests 路径，即使它们在历史 integration.write_paths、finding.paths 或 regression_proof.scope 中；这些范围不等于返工授权。按候选用途区分文档，不按 `.md` 后缀封禁：合法产品范围中的运行时 SKILL、references 或 rules 仍可作为产品修复。原整合身份保持不变，不再派原并行实现者返工。

- 发现者在 `regression_proof` 中记录作者身份、具体命令、范围、实际/预期退出码、证据路径；`root_cause` 解释路由原因。reviewer 可写证明测试，不写实现或放宽断言来自行关闭问题。
- `routed_to` 固定为原整合责任者的真实已绑定身份；`lineage.original_implementer` 保存这个初次选定的修复者，后续不通过换 ID/换人清零。`discovered_by` 与来源 lineage 区分 review 复审和验收复验责任，验收者不伪装成 reviewer。
- 每 finding 最多三次实际 `dispatch-finding-fix`；查询、补证据、复审不计次。`record-finding-fix` 要求修复者身份和 Red/Green/相关回归 checks，并追加 fix_history。
- `re_review/pass` 可关闭已有 awaiting_re_review finding；复审中新发现问题用新 ID 和证明，verdict=fail。旧 ID 不覆盖，修复范围扩大必须扩大审查范围。没有 finding 的候选范围更新也可追加范围复审。
- review 来源 finding 经原整合者追加 integration 后用 `create-re-review-subtask` 回同一 reviewer；验收来源 finding 直接走同一验收者的范围复验，不创建 reviewer 复审。终态结果不重开，历史追加保留。

## 昂贵真实验收门禁

- revision 3 的 stage 为 `work -> integration -> pre_acceptance_review -> expensive_acceptance -> final_documentation`，无需独立 cheap_check 或 final_review。
- acceptance_gate 的预算由同候选 schema 与控制器执行，默认总 attempt 上限为 4；只有带用户明确批准、当前上限和证据引用的 `extend-acceptance-budget` 回执可以严格递增本任务上限，历史续批和 attempt 均追加保留。普通验收、准备检查和正式黑盒分别判断，不把同候选 ordinary pass 当作禁止 preparation/blackbox 的理由。预算耗尽如实阻塞，不换 ID 或清零；续批不恢复 blocked 状态，不提供候选、审查或验收证据；正式效果停止另受用户决定约束。
- 以下 attempt 返工规则适用于普通验收；黑盒先适用 [分层方法论](blackbox-methodology.md)，不能借普通重试规则自动启动下一效果轮。准备检查不占正式效果轮次，资源和总预算仍照实记录。
- revision 3 普通业务验收失败走发现者完整问题合同、原整合者修复与重新整合、新候选及同验收者范围复验/delta 检查；仅有范围诊断的环境失败允许同候选一次重试（`max_environment_retries_per_candidate=1`）。
- candidate_inputs 明确 code_paths、config_paths、runtime_input_paths、runtime_inputs、document_paths。所有职责的实质 write_paths 均需被候选范围覆盖，包括 reviewer 和验收发现者编写的可执行测试；不能因角色而漏掉。仅本任务受控工件和 `.tmp/`、`.artifacts/` 下明确的 `.log` 日志文件可不声明为候选；不豁免日志目录、可执行证明或作为执行输入使用的日志。若日志也用于业务执行，应显式列入 runtime_input_paths。全部受影响正式文档列入 document_paths；控制器仅排除本任务六工件和内部锁，不能用 closeout 任意文档白名单绕过审查。
- 验收前完整审查和增量复审共同覆盖逐文件内容，验收来源修复则保留该基线证据并由同验收者检查 delta；文件新增/删除、配置、运行输入、验收条目或实质文档变化使对应证据过期。`build-review-brief` 给出候选指纹和清单，review 回填 `reviewed_candidate_fingerprint`、`covered_paths`、检查完成/未执行项及证据。
- 首次 `freeze-candidate` 要求最新 integration 和充分独立审查覆盖；验收修复候选使用原审查基线及明确 delta，由原验收者补齐检查。`create-subtask-attempt` 为模板生成实际 attempt 子任务；不要绑定 EXPENSIVE 模板本身。验收结果映射该 attempt kind 的业务 acceptance_id；最终聚合同候选 ordinary 与 blackbox 证据，准备结果不贡献业务覆盖。失败和历史尝试追加保留。
- 验收模板的证据 key、attempt 归属及 CLOSE 汇总规则见 [终态证据合同](state-schema.md#终态证据补登记合同)；操作时按同包结果示例填写，不手工推断 owner。
- 最终范围收敛后才执行昂贵全量；全量失败且代码变化时重跑受影响的最终验收，不承诺整个任务永远只跑一次。等待使用平台协作能力，不新增调度器。

## 结果合同

派发时提供对应角色的完整结果模板，填写已知任务、绑定身份和证据位置；子代理据实补充工作与验证结果。提交前使用 `validate-result`，通过后由协调器核对证据，再调用对应正式 action；后者重新检查当前候选与状态。格式修正不要求重做仍有效的业务验证。详见 [计划代理与只读结果预检](state-schema.md#计划代理与只读结果预检)。

completed 或 blocked 子任务都写回 `state.json.subtasks[].result`，至少包含 `status`、`summary`、`changed_files`、`planned_files_not_changed`、`verification`、`deviations`、`blocked_by`、`risks`、`follow_up`、`written_by`、`written_role`。子任务不生成另一套 package/report 控制面。

先读取 `revision-3-results.example.json`：work、integration、review、acceptance_pass、final_documentation 都是可直接选取的完整载荷。选一个对象写入本任务结果输入文件，替换 `ACTUAL_*` 身份、业务路径、真实命令/退出状态/耗时/次数/证据和验收 ID；不要提交示例证据。review 指纹取当前 `build-review-brief` 返回值；普通结果 `written_role` 必须等于绑定的 agent_key。具体派发、验收及事实回填顺序见 `state-schema.md` 的“现场调用与回执”。

通过验收的 `expensive_acceptance.failed_stage` 仍是非空字符串，填写 `"none"`；`status="completed"`、`outcome="pass"`、`blocked_by=[]`，每个 acceptance_id 都映射真实证据。`acceptance.md` 的 `## 最终结论` 是控制器受管区，保留当前精确句子；业务结论、耗时与证据写在“必备证据/未决项”等非受管段落。finalize 成功后控制器自动切换完成标记。

## 必需能力不可达与恢复

意外命令失败按 [包内治理](governance.md#命令失败与重试) 保留原始输出并核对重试条件；只有任务依赖的必需能力缺失才阻塞相关操作。

如果 init-task 尚未成功，没有可更新 state：在本任务允许的证据落点保留失败和阻塞说明，直接告知主协调器/用户；不得为造出 state 而重试受阻 init。若任务已存在，使用 `revision-3-results.example.json` 的 coordinator_blocked 完整载荷，填真实协调者身份、非空 blocked_by 和实际失败证据：

```bash
python3 "$GTO_CONTROLLER" --action set-phase --repo-root "$repo_root" --task-id "$task_id" --phase blocked --result-json-file "$blocked_json_file" --json
```

控制器保存 coordinator_blocker.previous_phase/result，并将任务 status/current_phase 置为 blocked、next_action 置为 human_adjudication。阻塞期间可 validate、build-review-brief、accept-artifact-update、extend-acceptance-budget；已绑定独立任务可记录结果，仍保持 human_adjudication。治理续批只追加用户授权并递增本任务总 attempt 上限，不恢复阶段；新派发、新候选/attempt、依赖调度和 finalize 均被拒绝。子任务结果的 blocked 不会自动代替协调层阻塞，主协调器需要明确登记影响整个流程的必需能力缺口。

外部状态实际恢复后，同一协调者填 coordinator_resumed：status=completed、blocked_by=[]、非空 verification，以及实际成功的 checks/证据。CFM 缺口须包含原能力恢复与原失败对应的成功 query-before-retry；无成功查询就不能恢复。只允许回到阻塞时的 previous_phase，不跳阶段，不自动重试，不换 task_id。结构检查只核验提交的结果与证据引用，不能证明命令真实执行；语义真实性由协调者和独立验收核对。

仅下文“会话中断且尚无交付的身份移交”成功登记的接替协调者可代替原协调身份提供恢复回执；原失败回执作者保持不变。

```bash
python3 "$GTO_CONTROLLER" --action set-phase --repo-root "$repo_root" --task-id "$task_id" --phase "$previous_phase" --result-json-file "$recovered_json_file" --json
```

阻塞/恢复完整回执追加保存于 events.jsonl；恢复只清除当前 coordinator_blocker。当前包拒绝旧合同。

## Revision 3 CLI 顺序示例

### 会话中断且尚无交付的身份移交

原协调者或初始代理因宿主会话中断不可达，且用户明确允许接替时，可使用 `recover-interrupted-dispatch --result-json-file <回执>`。它只适用于 blocked 的 doc_sync/test_sync 初始任务：仅一个活动派发、没有任何子任务结果、候选、attempt 或 finding，交付范围内没有非本任务受管工件文件。空目录可保留；符号链接不允许。已有交付不适用此入口。

回执包含 `approval={approved_by:"user",authorization_source,reason,evidence:{path,sha256}}`、`previous_coordinator_id`、`new_coordinator_id`、`subtask_id`、`previous_platform_agent_id`、`new_platform_agent_id`。身份必须来自实际宿主；新代理先独立创建、仅准备等待，不提前写交付。授权证据必须位于消费项目 `.artifacts/` 且 hash 匹配；控制器检查结构与留存，协调者仍负责核实真实用户授权与身份。

成功后仍保持 blocked，原阻塞回执、原派发与执行包 hash 留在 `interruption_recoveries` 和追加事件中。目标回到 ready，随后只接受授权的新代理正常 bind；新协调者提供真实成功恢复 checks，通过原 `set-phase` 回到原阶段，再正常 preflight、绑定和施工。不更改批准合同、依赖、范围、预算或业务结果，不自动完成或重试。没有移交时仍要求原协调者身份恢复。

此入口不修改冻结包或放宽候选 runtime 校验。尚无候选时使用修复后的包须有用户授权并追加包版本证据；已冻结候选不适用本入口。

完整普通流程的载荷和分段命令见 `state-schema.md` 的“现场调用与回执”。先完成整合，再获取审查 brief；独立 reviewer 检查后才填写结果文件：

```bash
python3 "$GTO_CONTROLLER" --action build-review-brief --repo-root "$repo_root" --task-id "$task_id" --subtask-id "$review_id" --json
```

真实审查通过后，结果成功写入才冻结并创建实际验收 attempt：

```bash
python3 "$GTO_CONTROLLER" --action record-review-result --repo-root "$repo_root" --task-id "$task_id" --subtask-id "$review_id" --result-json-file "$result_json_file" --json && \
python3 "$GTO_CONTROLLER" --action freeze-candidate --repo-root "$repo_root" --task-id "$task_id" --json && \
python3 "$GTO_CONTROLLER" --action create-subtask-attempt --repo-root "$repo_root" --task-id "$task_id" --subtask-id "$acceptance_template_id" --json
```

review/fail、验收失败时不执行这段通过分支。先让发现者登记完整问题合同，再 dispatch-finding-fix，原整合者真实修复后 record-finding-fix；随后 create-integration-subtask、绑定原整合者、完成范围检查并记录结果。review 来源最后 create-re-review-subtask、绑定原 reviewer 范围复审；验收来源直接交同验收者范围复验及 delta 检查。每一步均以之前的实际成功回执为前提，不跳过中间真实执行。

验收发现使用真实 attempt ID：先 record-acceptance-findings，再提交引用 finding_id 的 product_failure 回执；正式黑盒 effect_failure 已记录且用户明确允许 repair 时，原验收者可为同一当前候选 attempt 补登记 finding，终态回执和失败历史保持不变；通过则 outcome=pass/status=completed/failed_stage="none"。收尾子任务依赖验收模板，由控制器核对当前候选真实 passing attempt；实际验收回执记录成功后，才可绑定 CLOSE 并按参考中的事实收尾顺序完成。

## 参考

- 字段说明：`state-schema.md`
- 方案、任务表与交接：[方案编制与交接](plan-guide.md)
- 通用施工图、职责与返工：[任务流程与职责](workflow.md)
- 治理摘要：`governance-essentials.md`

发现者实际新增测试后仍可登记 fail 及其证明，不能因此堵住返工入口；review 保存 source_candidate_fingerprint，验收 finding 保存 source_candidate_id 并关联原 attempt。这个通路不授予 pass：新测试/代码变更仍要求新 integration、有效审查覆盖与新候选验收。

初始测试依据需求与可观察行为独立设计；整合子代理不得提前介入影响测试。独立测试和全部实现 TDD 完成之后才开展整合工作。验收通过后的单文档子代理可直接进行纯文字纠正与遗漏同步，不限于空白或排版；只有真正行为、契约或配置变化才返回验收链。新增接口字段须在独立行为测试及实现后与 schema、示例统一核对，不能将提前设计的字段当作测试答案。
