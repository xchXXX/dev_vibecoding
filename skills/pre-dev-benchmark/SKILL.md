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
- 默认从 `contract`、`component`、`forward`、`blind` 四层开始。
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

7. 开始编码前先产出具体文件。
- 至少留下 `benchmark plan`、`fixture matrix` 和 `runbook`。
- 明确写出通过阈值，以及哪些失败会直接阻断。
- 即使用户要求马上实现，也要留下最小但清晰的 benchmark 包。

## 产出合同

输出物必须能直接被后续实现阶段复用：

- `benchmark-plan.md`：改动目标、测试层、通过/失败标准、阈值和自动化范围
- `fixture-matrix.md`：稳定 case 清单，包括 setup、信号、污染风险与隔离说明
- `runbook.md`：执行顺序、证据留存要求，以及哪些套件是诊断、哪些是验收

如果仓库已经有约定好的 benchmark 位置，就写到那个位置；如果没有，就在仓库的 `benchmark/` 下建一个聚焦目录，不要只把方案留在聊天里。

## 资源导航

- 阅读 `references/benchmark-design.md`，了解可复用方法、判定规则和常见反模式。
- 用 `skills/pre-dev-benchmark/scripts/scaffold_benchmark.py` 从模板生成 starter benchmark bundle。
- 优先复用 `assets/benchmark-plan.template.md`、`assets/fixture-matrix.template.md` 和 `assets/runbook.template.md`，不要每次手写结构。

## 最小使用方式

```bash
python3 skills/pre-dev-benchmark/scripts/scaffold_benchmark.py \
  --output benchmark/my-change \
  --slug my-change \
  --title "我的改动"
```

然后把真实改动范围、每层成功标准、fixture 清单以及诊断/验收拆分填进去。
