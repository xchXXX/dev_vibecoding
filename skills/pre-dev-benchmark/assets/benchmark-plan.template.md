# {{TITLE}} Benchmark 方案

## 1. 改动目标

- `slug`: `{{SLUG}}`
- `change_type`: `{{CHANGE_TYPE}}`
- `goal`: [描述这套 benchmark 要保护的用户可见结果。]
- `non_goals`: [列出明确不在本次范围内的内容。]
- `primary_risks`: [列出最重要的回归风险或误判风险。]

## 2. 分层矩阵

| layer | question | artifact or signal | success criterion | notes |
| --- | --- | --- | --- | --- |
| contract | [这一层要证明什么？] | [doc / prompt / metadata / schema] | [可观测通过规则] | [可选] |
| component | [这一层要证明什么？] | [script / function / matcher / scorer] | [可观测通过规则] | [可选] |
| forward | [这一层要证明什么？] | [端到端命令或完整运行] | [可观测通过规则] | [可选] |
| blind | [这一层要证明什么？] | [fresh agent / hidden-hint run] | [可观测通过规则] | [可选] |

## 3. Fixture 策略

- `reusable_fixtures`: [本次可以直接复用的 fixtures 或现成 artifacts。]
- `new_fixtures`: [实现前必须先补齐的新 fixtures。]
- `determinism_rules`: [如何保证 suite 稳定、可重复。]
- `contamination_controls`: [如何避免隐藏上下文或陈旧状态污染结果。]

## 4. Benchmark 拆分

### 诊断 Benchmark

- [名称] - [它诊断什么] - [为什么它不是最终闸门]

### 验收 Benchmark

- [名称] - [它证明什么] - [为什么它具有代表性]

## 5. 通过闸门

- `minimum_pass_threshold`: [例如：10 个 blind case 至少通过 9 个]
- `blocking_failures`: [列出一旦出现就必须阻断的失败]
- `evidence_to_save`: [需要留存的日志、报告、文件、memory snapshot、截图等]

## 6. 自动化计划

- `scripted`: [优先脚本化的部分]
- `manual`: [仍然需要人工判断的部分]
- `orchestration_notes`: [suite 如何启动、如何评分]

## 7. 未决问题

- [问题 1]
- [问题 2]
