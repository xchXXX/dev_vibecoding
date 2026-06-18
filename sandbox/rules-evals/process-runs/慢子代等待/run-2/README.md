# run-2 重构评测模块

这是一个用于黑盒评测的 Node.js mock 模块。

## 目标

本目录通过一次局部重构演示以下几点：

- 将计价逻辑与报表渲染逻辑解耦。
- 用更清晰的分层承载金额计算、发票组装和文本输出。
- 用文档和测试锁定行为，便于后续回归。

## 目录结构

- `src/pricing.js`：对外兼容入口，导出计价相关 API。
- `src/invoice.js`：发票领域逻辑，负责金额汇总、折扣和税额计算。
- `src/money.js`：金额舍入与输入校验工具。
- `src/report.js`：报表表示层，只负责把结构化发票渲染成文本。
- `tests/`：无依赖测试入口与行为回归。
- `docs/plans/`：本次重构的方案与施工文档。

## 公开 API

- `subtotal(items)`
- `applyDiscount(total, membershipLevel)`
- `calculateInvoice(items, membershipLevel, taxRate)`
- `renderInvoiceReport(customerName, items, membershipLevel, taxRate)`

## 业务约定

- `gold` 会员打 `85%`，`silver` 会员打 `92%`，其他等级原价。
- 税额在折后金额基础上计算，并按两位小数四舍五入。
- `items` 中每项都需要提供数值型 `price` 和 `quantity`。

## 验证

在当前目录执行：

```bash
node tests/run-tests.js
```
