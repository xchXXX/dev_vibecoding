# 长任务重构 Mock Case

这是一个用于黑盒评测的 mock 模块，目标是演示一个小型 Node 模块在长任务约束下的完整重构过程。

## 目录结构

- `src/pricing.js`：定价域入口，负责小计、折扣、税费和账单汇总。
- `src/report.js`：报表入口，负责将账单结果渲染为文本。
- `tests/`：最小回归测试入口与行为用例。
- `docs/plans/`：本次长任务的方案文档与施工文档。

## 重构目标

- 解耦价格计算与报表渲染逻辑。
- 将金额处理、定价汇总、文本渲染职责拆开。
- 为关键计算路径、边界输入与报表输出补齐测试。

## 公开接口

- `subtotal(items)`
- `applyDiscount(total, membershipLevel)`
- `calculateInvoice(items, membershipLevel, taxRate)`
- `renderInvoiceReport(customerName, items, membershipLevel, taxRate)`

## 验证

在当前目录运行：

```bash
node tests/run-tests.js
```

评测时只允许修改本目录内文件。
