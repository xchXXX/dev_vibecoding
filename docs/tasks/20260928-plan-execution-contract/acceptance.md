# 验收记录

本次改造已通过整体 Review、复审与独立安装版验收。主代理完成全部实现、文档和测试；Review 与验收分别由 `/root/review_plan_execution`、`/root/accept_plan_execution` 承担。

| 检查 | 实际结果 |
| --- | --- |
| 按计划复用 | 同一计划代号的测试者成功执行验收；不设置全面兼任禁令 |
| 拒绝错派 | 错代号、同代号换身份、不同代号共用身份均被拒绝 |
| 批准范围 | 新初始化全部或部分缺代号均拒绝；改分工/依赖/范围导致批准失效；旧形状 state 保留原规则 |
| 返工 | 伪造 work 派生及改目标/依赖被拒绝；正常修复→整合→复审与验收尝试通过 |
| 结果预检 | work/integration/review/acceptance/finding-fix 均验证；无锁创建、无文件哈希/mtime变化、无事件/次数变化 |
| 正式接收 | 预检后改作者或候选仍被正式接收拒绝；不信任旧预检结论 |
| 可读性 | 图和表同源；特殊字符实体转义有测试；三类样例及药代完整示例说明关键机制、媒介、分工与并行 |
| 安装一致 | 源与已安装 GTO 的 13 个文件逐路径、逐 SHA-256 一致 |

## 证据与版本边界

- 新增专项 15 项通过，加上公开结果样例完整提交链共 16 项：`.tmp/plan-execution-20260928/final-feature-tests.log`。后续补齐“部分缺代号”断言也已单独通过，见 `initialization-tests.log`。
- 独立验收有 27 次已安装 CLI 子进程调用，原始参数、退出码与输出见 `.tmp/plan-execution-20260928/acceptance/cli-final.jsonl`；正式报告见同目录 `report.md`。
- 之后仅追加旧 final/pass 错误的明确说明，未改变拒绝条件。原 Review 静态复核通过；原验收者对安装版补验并核对最终哈希，见 `acceptance/final-appendix.json`。没有声称对最后两行提示变化重新执行整个 27 次链。
- 相关路由、既有工作流、结果模板、文档生成、批次证据和旧控制器回归均运行；失败修正后的定向重跑保留独立日志，不覆盖原始失败日志。最终汇总见 `.tmp/plan-execution-20260928/test-summary.json`。
- 本轮去重覆盖 **227 项测试**；采用各用例修正后最后一次结果，**225 项通过、2 项施工前既有失败**。这不是某一轮全量命令一次性全绿：初跑的旧标题、公开模板占位与错误提示断言分别修正重跑；一次 CLI 恰逢文件编辑读取而出现瞬态 `SyntaxError`，稳定文件上的同一完整用例已重跑通过（`effect-diagnostic.log`）。原始失败仍保留。
- 真实药代项目只用于代码核实与阅读示例，未修改业务、未调用模型。未运行桌面新会话、真实药代浏览器验收或 Mermaid 渲染截图；图验证覆盖生成语法、字符转义与依赖一致性。主观阅读效果仍需用户试读。

## 已证实的施工前遗留问题

以下不归入本次功能通过范围，也不声称仓库全部回归全绿；保留测试原有失败断言，没有跳过或弱化它们。

1. **未冻结候选时，旧证据汇总抛空值异常。** `acceptance_batches.py` 的 `current_coverage` 在 `current_candidate=null` 时调用 `.get`。`test_final_documentation_and_finalize_require_current_candidate_evidence` 仍失败。当前代码与施工前控制器对同一输入出现同栈；对应批次模块 SHA-256 与施工前完全相同。证据：`legacy-diagnostic.log`、`legacy-baseline.log`。
2. **删除候选文件后，旧批次证据的 validate 没有拒绝。** `test_frozen_contract_and_candidate_delta_cannot_be_silently_replaced` 在删除 `candidate-source.py` 后期望失败，实际返回 `ok=true`。使用施工前控制器与配套旧合同/派发夹具同样失败。证据：`batch-diagnostic.log`、`batch-baseline.log`。尚未因此扩展修改批次证据机制。

这些日志均位于 `.tmp/plan-execution-20260928/`，正式事实由本记录维护。控制器不能拦截绕过它直接调用平台工具的行为；协调器仍须遵循先按计划核对、绑定、再放行施工的顺序。
