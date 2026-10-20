# 活跃真源 v3-only 全量收口

Task ID: `20260902-000944-980373-active-truth-v3-only-closure`

## 验收目标

把仓库当前活跃真源、命令、规则、AGENTS.md、skills、schema、模板、测试与真实 Codex runtime 全量收口到纯 Codex、WSL Python 3、规则由 Codex 语义自由选读、GTO 仅支持真实 action 且只接受 v3 的唯一逻辑，并完成独立 review、返修和 re-review。

## 验收标准

- 当前入口和受管 runtime 不再肯定式声明或实现 Claude、PowerShell/cmd/hook、v1/v2、RULES_RESOLVED、task_profile matcher 或旧 packet 控制面
- GTO/CFM Python CLI 只接受 GNU 双横线参数，文档 action 和参数全部可由真实 parser 验证
- GTO schema 只接受 version=3，当前模板全部通过 schema 且不含失效 action 或 Windows 命令
- 规则索引继续保持 3 条 always_on、其余由 Codex结合对话语义、目标内容、风险、当前阶段和本轮操作自由选读，Python 不参与日常语义匹配
- bootstrap、sync、strict doctor、规则/文档校验、全量 unittest 与新增盲测全部通过，源码和真实 Codex runtime 一致
- 独立 final reviewer 覆盖全部本次变更并给出 final/pass；发现问题时完成 fix 与 re-review

## 必备证据

- `repro_before_fix`：首轮 9 个新门禁中 8 个因真实旧残留按预期失败；review 后 5 个 finding 以及第 2 轮 3 个残留均有独立命中证据。
- `pass_after_fix`：同一批门禁经两轮 fix/re-review 后全部转绿，5 个稳定 finding 全部 closed。
- `hit_proof_observed`：旧 CLI、v2 schema、未上报 Git 修改/删除、越界 changed_files、role map 残留、虚假 brief、任意 hook 与混合句绕过均被真实测试命中。
- `relevant_regression_ok`：独立 final reviewer fresh 运行 69 项 unittest 全部通过；规则、任务文档和文档路由 validator 全部通过。
- `docs_and_rules_synced`：23 条规则有效，always_on 恰为 3 条；其余规则由 Codex 按对话语义、目标内容、风险、阶段和本轮操作自由选读。
- `ideal_behavior_acceptance`：bootstrap、sync、strict doctor 9/9 通过；四个受管 skill 源码/runtime 18/18 文件哈希一致，全局 AGENTS 一致，hooks 为 `{}`，`.claude` 与 v2 role map 均不存在。
- `independent_final_review`：独立 reviewer 覆盖任务范围 Git dirty 317/317 项和删除 35/35 项，review target 为 `3220cf956c47bc6cee076abe57f6c7fa7b8b5040a60a23b2deae2fb10cdfe357`，结论为 final/pass。

## 未决项

- 无未决 finding；无 blocked finding。
- 仓库原有其他未提交改动未被覆盖、恢复或提交。

## 最终结论

独立 final/pass 已覆盖最新 scoped source manifest，任务完成。
