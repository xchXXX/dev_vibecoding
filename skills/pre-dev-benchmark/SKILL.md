---
name: pre-dev-benchmark
description: "在开始实现前设计 benchmark。适用于 Codex 将要构建、重构、迁移或调试功能、skill、agent、hook、prompt、脚本、API 集成或工作流，并且需要先把需求转成可测的验证闭环：按需要拆成 `contract`、`component`、`forward`、`blind` 等测试层；为每层定义唯一成功标准；设计稳定 fixture；区分诊断 benchmark 与最终验收 benchmark；并决定哪些检查需要先脚本化。用户提到 benchmark-first、验收口径、fixture 设计、盲测、eval 方案或开发前验证闸门时也使用。"
---

# 开发前 Benchmark

## 概述

在真正开始改代码前，先冻结一套可执行的 benchmark 方案。最终至少留下明确的通过/失败闸门、fixture 设计和执行说明，供后续迭代与最终验收复用。

## 工作流

1. 先冻结目标，再设计测试。
- 先复述用户真正要保护的结果、明确非目标、风险边界和当前未知项。
- 不要把“要做什么”和“怎么验收”混成一段模糊描述。

2. 把验证面拆成不同层。
- 按真实风险选择 `contract`、`component`、`forward`、`blind` 等层，不强制全部具备。
- 只有在能提升信号质量时，才合并或增加层级。
- 判断某层是“仅用于诊断”还是“属于最终验收”时，阅读 `references/benchmark-design.md`。

3. 每层只回答一个成功问题。
- 每一层只证明一件事，不要混问。
- 成功条件必须可观测，例如文件、命令输出、结构化日志或唯一 PASS 标记。
- 避免出现“文档看起来更好了，脚本似乎也能跑”这种混合闸门。

4. 先设计 fixture，再写命令。
- 优先使用本地、确定性强、成本低的 fixture。
- 要求每个 case 都有唯一 PASS 标记，或其他不含糊的成功产物。
- 覆盖真正重要的失败形态，不能只测 happy path。
- 如果 case 矩阵还不清晰，先用 `assets/fixture-matrix.template.md` 起草。

5. 区分诊断 benchmark 和验收 benchmark。
- 诊断 benchmark 用来定位系统到底坏在哪一层。
- 验收 benchmark 用来决定这次改动是否达标。
- 不要把脆弱、过于合成的诊断检查直接升级成最终验收闸门。

6. 决定哪些步骤需要脚本化。
- 对重复打分、fixture 搭建、结果收集、报告生成优先脚本化。
- 真正的 blind evaluation 要和任何会泄露隐藏上下文的准备步骤隔离。
- 需要快速起一套骨架时，从仓库根运行 `python3 skills/pre-dev-benchmark/scripts/scaffold_benchmark.py --output <dir> --slug <name> --title <title>`。

7. 将基线、通过阈值、fixture 与执行说明写入已有合同。
- GTO 任务复用同一六工件：要求与范围在 plan，执行分工在 execution，验证与证据在 acceptance；不另建固定 benchmark 文档套餐或第二账本。
- 只有独立 benchmark 交付本身是用户目标时，才使用下方 scaffold 和模板；落点遵循项目存储规则。

## 产出合同

输出需让后续执行者可复用：可观察标准、稳定 fixture、诊断/验收区分、运行入口和证据位置。材料的唯一存放位置由现有任务合同决定，无需每种内容单建文件。skill 效果黑盒的投放、无提示顶层会话、准备复查与正式首轮停止出口引用 [GTO 黑盒方法](../global-task-orchestrator/references/blackbox-methodology.md#结果分类)，不在这里另建返工规则。

## 资源导航

- 阅读 `references/benchmark-design.md`，了解可复用方法、判定规则和常见反模式。
- 用 `skills/pre-dev-benchmark/scripts/scaffold_benchmark.py` 从模板生成 starter benchmark bundle。
- 优先复用 `assets/benchmark-plan.template.md`、`assets/fixture-matrix.template.md` 和 `assets/runbook.template.md`，不要每次手写结构。

## 最小使用方式

```bash
python3 skills/pre-dev-benchmark/scripts/scaffold_benchmark.py \
  --output .tmp/benchmark/my-change \
  --slug my-change \
  --title "我的改动"
```

然后把真实改动范围、每层成功标准、fixture 清单以及诊断/验收拆分填进去。
