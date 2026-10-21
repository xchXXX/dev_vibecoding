# 恢复、登记与收尾的简化合同

版本边界：本页描述包含新增入口的运行包。实际安装以发布回执和新进程核验为准；现有冻结任务继续使用原版本，不自动迁移。

## 使用流程

普通任务用简洁清单；明确选择 GTO 的任务仍保留分工、依赖、固定版本、整合和独立审查。恢复时先读任务摘要，仅展开当前步骤需要的正文。共享依赖变化按传递影响扩大检查范围，无关有效结果保留。工具缺失只影响依赖该能力的范围。

`start_session.py` 是 harness 自己的恢复脚本，不是 OpenAI 官方程序。它验证六工件、冻结版本和证据完整性，返回原控制器、下一步及当前逐点覆盖。`validate` 的成功表示任务结构/证据有效，不表示业务已全部通过；返回 `acceptance`（含 complete、points、rerun_acceptance_ids、evidence_warnings）、`capability_checks`（按待执行子任务）和简短 `summary`。逐点投影使用 invalidation_kind 区分 inputs_changed、dependency_not_passing、later_failure 与 evidence_invalid；该诊断字段不另建持久状态。未执行、真实失败、关联内容改变和依赖未通过是可继续的工作状态；证据改写、绑定错误、快照损坏及未重新冻结的候选漂移仍拒绝。`finalize-task` 继续严格检查完整覆盖，不因恢复成功放行。

## 精确工具入口

### 当前步骤的必要阅读

恢复摘要之后，读取当前 subtask 的 assignment、read_paths、write_paths、planned_agent_key、dependencies、验收要求、预算及关联 finding。摘要缺项必须补读；新独立代理必须取得自身任务的完整必要信息。仅在同一代理已读过、内容未变且上下文仍保留时避免重复全文读取；内容变化、上下文丢失或矛盾时重新核对。首次 preflight、实际能力检查、身份绑定、依赖和独立审查不因摘要成功而省略。

brief 定稿且取得平台真实身份后，可在一次 shell 调用中顺序计算指纹并绑定，避免手抄指纹；前一步失败立即停止。创建代理、绑定、发送施工放行仍是三个有顺序的事实，不可合并成未绑定先施工。以下 Bash 片段在消费项目根目录执行，`brief_path` 必须为项目相对路径；所有变量须来自当前任务，不能照抄示例身份：

```bash
brief_sha256=$(sha256sum -- "$brief_path") || exit $?
brief_sha256=${brief_sha256%% *}
python3 "$GTO_CONTROLLER" --action bind-dispatch --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$subtask_id" --agent-key "$agent_key" --platform-agent-id "$platform_agent_id" \
  --context-mode isolated --brief-kind subtask --brief-path "$brief_path" --brief-sha256 "$brief_sha256" --json
```

从本 skill 的 `scripts/tool_paths.py --codex-home <实际已核实的 Codex home> --json` 获取工具位置；只检查固定公开位置，禁止递归搜索整个 CODEX_HOME、工作区集合、备份、会话或记忆目录。没有 Codex 安装的独立包可以省略 codex-home，只返回包内入口和缺失能力，不回退搜索别的机器目录。

返回 `tools` 映射，各项含 `path`、`available`：controller、resume、runtime_evidence 来自当前包；project_env_doctor 的唯一安装位置为 `<codex-home>/.ai-harness/runtime/wsl-environment/bin/project-env-doctor.py`。Windows 调用时使用已核实的系统 WSL 入口和实际发行版；这些机器值不写入通用实现。工具存在不等于能力已实际验证。

## 从原始证据生成登记

执行入口输出项目自己的原始证据，并生成观察摘要 JSON。摘要必须被同一次 runtime_evidence 运行纳入 `--evidence-path` 哈希清单；未捕获的后写摘要不能生成可信登记。

观察摘要至少有 `outcome`、`real_call_count`、`point_results`。每个 point_results 项沿用 acceptance_id、status、evidence_refs（可选 reason）；outcome 沿用现有 pass/partial_pass/product_failure/environment_failure/effect_failure；真实调用数由执行器计量，不按点数猜测。可选 failed_stage、usage_evidence、execution_kind、finding_id、closed_finding_ids、review_evidence、blackbox、invalid_observation、preparation 用于已有合同要求；这些字段仍执行原正式校验。环境、模型或页面运行必须如实提供相应 usage_evidence，不能由 CLI 启动事实推断页面已通过。省略 usage_evidence 时必须在原观察中显式声明 execution_kind="cli"，才生成 CLI 使用事实；UI 不适用理由明确为适配器的原始声明。其他类型必须提供真实 usage_evidence。最小可复制格式见 [观察摘要示例](observation.example.json)，ACTUAL 值必须替换。

公开入口：

```sh
python3 "$GTO_CONTROLLER" --action prepare-result --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$attempt_subtask" --run-manifest "$manifest_relative" \
  --observation-file "$observation_relative" --output-file .tmp/acceptance-result.json --json
python3 "$GTO_CONTROLLER" --action record-subtask-result --repo-root "$repo_root" --task-id "$task_id" \
  --subtask-id "$attempt_subtask" --result-json-file .tmp/acceptance-result.json --json
```

prepare-result 从当前已绑定身份、安排范围和经过核验的 manifest 提取 task/attempt/candidate/runtime、耗时、argv、来源哈希，生成既有完整 result，并在内存中执行正式登记同等检查。它只写指定的 `.tmp/` 草稿，不登记状态、不运行检查、不改原始证据。正式登记仍重查当前事实；刚生成且状态未变化时无需额外再调用 validate-result。记录手工改错时可从同一原始证据重新生成，不能为修字段重跑。缺少真实发现/关闭证据时先补现有 finding 流程，生成器不代写诊断或伪造关闭。

## 简短收尾

final_documentation 已按原合同绑定真实执行者，且正式候选文档与已验收内容逐字一致时，可以调用 `complete-task --subtask-id <final_documentation_id>`。程序自动生成纯事实文档回执，核对覆盖、问题关闭、整合、独立审查、必需证据与文档无差异，再原子记录回执和完成状态，返回简短 summary。它不生成新的独立审查结论、不绑定假身份、不执行任何业务。

如果正式文档发生变化，仍使用已有文档同步回执说明语义影响，不能自动宣称只是措辞变化。检查失败不得留下半完成回执或篡改失败历史。普通 finalize-task 也返回简短覆盖/来源汇总，仍可使用原手工路径。

## 版本、分发与验证

### 版本展示与诊断

既有 `tool_paths.py` 增加可选 `--harness-root`，仅检查显式指定真源与 `--codex-home` 下已知 GTO 安装位置；不自动发现其他 clone。返回附加 `version_summary`：`source`、`loaded`、`installed` 各包含 `path` 和 `content_sha256`，缺失或未指定为 null；`installed.receipt_status` 为 unknown/missing/invalid/mismatch/matched，matched 仅表示受管 GTO 文件与现有 receipt 一致，不代表全局健康或会话已加载。包内容指纹按相对文件名和字节哈希计算，排除 Python 缓存及 `.snapshot.json` 元数据；不把 Git HEAD 当脏工作区内容版本。`session_load` 固定为 unknown，本入口无法观察模型会话加载。

既有 `start_session.py` 成功后附加 `version_summary`：`launcher` 标明恢复脚本所在包，`task_runtime` 标明实际所选控制器所在包及内容指纹，`snapshot_sha256` 沿用任务记录，`selection` 为 frozen/current/explicit，`session_load=unknown`。这些展示不覆盖原校验，不把当前全局包当成旧任务冻结版本，也不迁移旧包。安装/真源信息用 tool_paths 的显式参数查询，不向旧控制器注入新参数。

两入口附加 `diagnostics`，每项包含 `code`、`owner`、`affected_scope`、`next_step`；原 ok、错误、退出码保持。工具缺失按具体工具归属定位；恢复的 `capability_checks` 只说明对应 subtask 的能力缺口，其他结果保留；失败恢复仍拒绝，诊断不得变成执行或发布授权。已有 project doctor 的分类和下一步继续复用，本次不重写环境诊断系统、不自动修复。

新增入口只对包含这些脚本的冻结运行包可用；旧包保持原行为，不偷偷用全局新版覆盖。独立包从唯一真源通过既有 build_release.py 生成。全局更新先核对安装所有权、备份和 receipt，再定向同步 GTO 及确实变化的全局入口，确认其他技能、旧快照不变。

验收先跑正式 CLI 的低成本测试：正常待复验恢复、完整性拒绝、固定位置工具发现、从同一 run 生成登记、原子收尾门禁、跨模块依赖和局部能力。之后真实 Codex 分别验证普通任务、恢复登记和多模块整合。记录业务次数、重复尝试、登记拒绝、命令数和耗时；仅比较等价阶段，不承诺固定节约比例。首次失败保留，修复后只复验受影响范围。

任务身份与目录接续：同 task_id 的 Plan/Execute、子代理和复验沿用已绑定工作区、分支与冻结包；不同会话不自动成为新任务，dirty 不触发新建。共享目录的冲突写入串行、Git 由主协调器统一，交接先停止原写入。普通任务核心工件与流程另见 harness 的 docs/modules/git-workflow/contract/task-workspace.md，不叠加到本 GTO 合同。新定位入口不改写 state 或绕过 checkout_binding；相关新增能力仍以安装版本及验收记录为准。
