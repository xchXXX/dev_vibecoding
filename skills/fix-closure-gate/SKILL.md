---
name: fix-closure-gate
description: "为修复类实施任务建立结果通过之外的命中证明闸门。适用于 bugfix、fallback 或 catch 分支修复、高成本集成/端到端验证链路、以及需要在送审前证明“修复点确实命中”的任务：先冻结 `minimal_repro`、`hit_proof`、`diagnostic_checks`、`acceptance_checks`、`non_goals`、`review_evidence` 的最小 verification contract，再决定是否进入实现或复审；当任务只是纯新增功能、纯文案样式调整、或已有低成本确定性证明且不存在修复闭环风险时可跳过。"
---

# 修复闭环闸门

本技能可独立使用，不依赖 GTO、其他技能或特定操作系统，不创建控制面或擅自派发代理。先冻结“修复点已被证明命中”的最小合同，再进入实现或复审。不要把“大套测试通过”直接当成闭环完成。

## 职责

- 为单次修复、返工或复审回流任务冻结最小 verification contract。
- 强制区分 `minimal_repro`、`hit_proof`、`diagnostic_checks`、`acceptance_checks`、`non_goals`、`review_evidence`。
- 优先选择低成本、确定性、能直接证明修复点是否命中的检查。
- 为普通修复任务和长任务批次提供统一闸门，让外层流程只检查合同是否齐备，不复制本 skill 逻辑。

## 非职责

- 不替代 `pre-dev-benchmark`；不负责为全新能力或大改造设计完整 benchmark 分层、fixture 矩阵或盲测方案。
- 不替代 `global-task-orchestrator`；不维护 `state.json`、`subtasks`、派发路由或控制面阶段。
- 不要求所有修复都升级成高成本自动化；核心是命中证明，不是套件数量。
- 不把 `acceptance_checks` 全部通过自动视为 `hit_proof` 成立。

## 触发条件

命中以下任一场景就进入本闸门：

- 任务本质是 bugfix、缺陷修复、返工修复或审查后补证据。
- 改动命中 fallback、catch、兜底、守卫分支或其他“只有异常路径才会走到”的逻辑。
- 当前验证主要依赖高成本 integration、e2e、联调、手工链路或外部系统，缺少低成本命中证明。
- 任务在进入 reviewer、复审、二次送审前，需要证明“修复点确实命中”，而不是只给最终结果。
- 审查意见已经指出缺少最小复现、命中证明、诊断检查分层或证据链。

## 跳过条件

满足以下任一场景可以跳过，但必须明确写出跳过理由：

- 任务是纯新增功能，没有“修复既有问题”的目标声明。
- 任务是纯文案、样式、静态资源或机械性改名调整，不涉及缺陷闭环、fallback/catch 路径或高成本验证链路。
- 同一批次所需的 verification contract 已在当前真源中冻结，且本次改动没有改变修复点、验证面或审查证据要求。
- 已有现成、低成本、确定性的检查可以直接同时充当 `minimal_repro` 与 `hit_proof`，且没有额外复审证据缺口。

## 最小输入

进入本 skill 时，至少收齐以下输入；缺任何关键项时先补上下文，不要硬写方案：

- 本轮要修复的缺陷或错误声明。
- 受影响路径、分支、模块或异常链路。
- 当前失败症状，或能指向失败的最小复现线索。
- 候选低成本检查，以及现有高成本验收链路。
- 本轮明确不打算解决的边界。
- 预期送审或复审需要的证据形态。

## 最小输出

至少产出一个最小 verification contract。普通任务写入已有任务说明或当前回复，不要求六工件或 preflight。只有用户已选择 GTO 时才写入同一控制面并在验收文档引用，不复制第二份合同；已存在且未变化的有效命中证明直接复用，不强制所有任务再过一次闸门。字段最少如下：

```yaml
minimal_repro: "最低成本、最确定地复现当前问题的命令、步骤或夹具"
hit_proof: "证明修复点已被命中的直接信号"
diagnostic_checks:
  - "用于定位/证明命中的低成本检查"
acceptance_checks:
  - "用于确认整体结果可接受的检查"
non_goals:
  - "本轮明确不解决的范围"
review_evidence:
  - "repro_before_fix"
  - "pass_after_fix"
  - "hit_proof_observed"
  - "relevant_regression_ok"
```

## Diagnostic Checks vs Acceptance Checks

- `diagnostic_checks` 只回答“修复点是否被命中、问题是否被最小成本证明”。
- `acceptance_checks` 只回答“最终行为是否达到可交付标准”。
- 同一条检查可以同时服务两者，只有在其信号足够直接、成本足够低、且语义不混淆时才允许双重记账；否则拆开写。
- 如果只有 `acceptance_checks`，没有能直接证明命中的 `diagnostic_checks` 或 `hit_proof`，则视为闸门未过。

## Review Evidence 最小槽位

`review_evidence` 列出必须覆盖的证据：修复前复现、修复后通过、命中信号和相关回归。普通任务在已有说明中逐项附命令/步骤、实际结果及证据引用，不要求某个机器状态字段。有效且未失效的证据可直接引用。

只有已选择 GTO 的任务，将根层槽位名称映射到 `verification_contract.review_evidence`，把实际证据映射到完成子任务的 `subtask.result.review_evidence.<slot>`；映射和状态写入由外层控制器完成，本技能不接管它。

## 最小工作流

1. 先写清缺陷声明与当前症状。
2. 先找 `minimal_repro`，再决定实现，不要反过来。
3. 为修复点定义单一 `hit_proof`。
4. 把检查拆成 `diagnostic_checks` 与 `acceptance_checks`。
5. 明确 `non_goals`，避免审查时扩大范围。
6. 先明确 `review_evidence` 的证据槽位，再按当前任务已有分工回填真实证据；普通任务由当前执行者完成即可。
7. 若找不到低成本命中证明，明确标记阻塞点，而不是直接用高成本套件硬顶。

## 与其他 Skill 的边界

- 需要在实现前设计完整 benchmark 分层、fixture 矩阵、盲测或评测脚本时，可按需使用已安装的 `pre-dev-benchmark`；它不是本技能的前置依赖。
- 只有用户明确选择 GTO 时才读取已安装的 `global-task-orchestrator` 并维护其状态；长任务本身不触发编排。
- 长任务命中本 skill 时，主协调器只负责在进入实现前和进入复审前检查 verification contract 是否齐备；不要把本 skill 的字段语义复制进 orchestrator 本体。
