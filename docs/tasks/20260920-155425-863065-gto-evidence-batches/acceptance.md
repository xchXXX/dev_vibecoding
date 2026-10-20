# GTO分批验收证据登记与汇总

Task ID: `20260920-155425-863065-gto-evidence-batches`

## 验收目标

修复GTO无法登记分批真实验收证据的问题：保留历史终态，登记已执行且独立评分的局部结果，核验当前适用性，汇总完整覆盖并用于正常关闭。

## 验收标准

- BATCH-01：历史environment_failure保留不变，可登记其中确已执行且独立通过的局部单元；新定向attempt诚实记录partial而非full，调用只记一次。
- COVERAGE-01：依据冻结完整单元集合汇总当前候选覆盖，真实代码/输入失效、假身份、篡改、未执行、漏项、重复和冲突均拒绝；登记、validate与finalize重验。
- RELEASE-01：独立源码审查及安装版CLI验收通过，仅发布GTO且source/install/receipt一致，旧full/scoped及预算和证据归属行为保持。

## 必备证据

- 最小复现、命中证明、相关回归和独立审查证据齐全。

## 未决项

- 按当前任务状态持续更新，未完成项不得提前宣称通过。

## 最终结论

最新候选已通过完整独立审查覆盖及真实验收，事实已同步，任务完成。

## 要求验证索引

- REQ-01
- REQ-02
- REQ-03

### 本任务真实验收结果

- BATCH-01：通过。历史失败终态保留，新partial精确记录执行子集，成本不重复累计。
- COVERAGE-01：通过。完整单元集合与逐单元来源、独立评分、输入投影、候选适用性绑定；输入失效、伪归属、重复、遗漏、篡改与跨kind冒用实际拒绝；已满足DOC-FINAL的finalize正反例通过。
- RELEASE-01：通过。原Reviewer最终PASS、5项finding关闭；只发布GTO，12个source/install/receipt文件一致、其他技能和发布期间宿主配置不变，strict doctor9项通过；二次sync无变化；独立安装CLI验收4节点全部通过。
- 安装验收为132次真实CLI action（104成功、28预期拒绝），214.158秒，模型调用0。它是控制面验收，不是原业务20题的新一轮执行。
- 主要证据均在 `.artifacts/gto/20260920-155425-863065-gto-evidence-batches/`：`ACCEPT-001-attempt-1/installed-cli-summary.json`、`accept-001-installed-cli-trace.jsonl`、`release-integrity.json`、`release-doctor.json`、`release-sync-second.json`、`rereview-3-independent-alias-green.log`。
- 原业务任务仍需按真实18+2来源登记证据，并完成其独立功能性验收；官方Browser不可达不属于本GTO源码与安装能力失败，也不能由本验收替代。
