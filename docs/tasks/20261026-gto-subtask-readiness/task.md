# GTO 子任务就绪状态推进修复

## 目标与范围
用户2026-10-26明确授权修复并验证 GTO 子任务就绪推进，再恢复原产品任务 20261026-140342-385582-admin-mcp-chat。此记录只追踪 harness 工具修复，不复制或重新初始化产品 GTO。分支 codex/fix-gto-readiness；原产品分支、任务身份和已完成D01保留。禁止提交、推送、合并、生产部署。

根因：已安装 controller 接受 pending 初始子任务，结果登记及阶段转换不推进其就绪状态，而 bind-dispatch 只接受 ready。实际 D01 completed、T01 pending、test_sync 下绑定被拒绝；preflight 对指定 pending 项仍误报可写。

范围：GTO controller、对应流程/状态/恢复文档、定向测试；验证后通过既有定向同步发布此技能包。仅修复派发就绪，不改变批准目标、依赖、身份、能力、候选、审查/验收和预算门禁。不手改产品state，不重建控制面，不升级已冻结运行包。

## 实施步骤
/root 同步合同；/root/qa 独立写测试并证明Red；/root 最小实现与Green；独立reviewer审查；原qa验收真源和安装包；/root恢复产品原test_sync并继续原角色。

## 最小验证合同
- minimal_repro: 使用真实控制器合法初始pending依赖链，接收前置结果后读取后继状态并绑定；旧版仍pending/拒绝。
- hit_proof: 后继由pending变ready、原身份绑定成功；blocked原任务恢复后同样可推进，批准合同指纹和既有结果保持。
- diagnostic_checks: 定向状态及绑定测试；未完成依赖、blocked、终态、已有dispatch、expensive模板不被错误放行；指定preflight不得将不可派发项报为可写。
- acceptance_checks: 相关GTO回归；独立审查；定向安装与真实产品恢复/绑定成功。
- non_goals: 不改产品方案/原任务号/依赖/人员/预算；不手改状态或补造证据；不处理无关GTO性能或其它问题。
- review_evidence: repro_before_fix、pass_after_fix、hit_proof_observed、relevant_regression_ok。

## 验收点与证据
- readiness: 合法pending依赖满足后由控制器推进，恢复在途任务不需手改state。
- safety: 不放宽依赖、阻塞、终态、模板、身份、能力及批准指纹门禁。
- installed-recovery: 既有同步入口发布经验证包，产品同任务恢复并绑定T01，旧D01和原身份保留。

当前：文档同步，测试及实现待执行。原始证据放 .artifacts/20261026-gto-subtask-readiness/，阶段状态唯一见同目录task.json。