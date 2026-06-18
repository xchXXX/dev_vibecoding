# 长任务重构 Mock Case

这是一个用于黑盒评测的 mock 模块，目标是演示一个小型 Node.js 模块的重构收口方式。

## 当前目标

- 降低价格计算与报表渲染之间的耦合。
- 补齐设计说明与实施文档。
- 扩充测试覆盖，并保证 `node tests/run-tests.js` 通过。

## 目录结构

- `src/pricing.js`：金额舍入、折扣和发票摘要计算
- `src/invoice.js`：报表模型组装
- `src/report.js`：报表文本渲染
- `tests/`：无依赖测试入口和用例
- `docs/plans/`：本次长任务的方案文档与施工文档

## 对外接口

- `calculateInvoice(items, membershipLevel, taxRate)`
- `createInvoiceReportModel(customerName, items, membershipLevel, taxRate)`
- `renderInvoiceReport(customerName, items, membershipLevel, taxRate)`

## 验证

```bash
node tests/run-tests.js
```

## 约束

- 评测时只允许修改本目录内文件。
- 模块使用 CommonJS，不引入第三方依赖。
