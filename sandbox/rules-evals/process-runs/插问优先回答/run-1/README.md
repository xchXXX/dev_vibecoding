# 长任务重构 Mock Case

这是一个用于黑盒评测的 mock 模块。

## 当前目标

- 对 `src/` 做一次完整重构，降低价格计算和报表渲染之间的直接耦合。
- 在不改变现有对外行为的前提下，补齐模块级文档与测试。
- 最终以 `node tests/run-tests.js` 作为最小验收入口。

## 模块结构

- `src/invoice-calculator.js`：发票金额计算与定价规则。
- `src/report.js`：报表视图模型组装与字符串渲染。
- `src/money.js`：金额四舍五入与格式化。
- `tests/`：按定价逻辑和报表逻辑分组的回归测试。
- `docs/ARCHITECTURE.md`：重构后的模块边界说明。
- `docs/plans/`：本次重构的方案文档与施工文档。

## 当前业务规则

- `subtotal` 按 `price * quantity` 汇总后做金额四舍五入。
- 会员折扣规则：
  - `gold`：`15%`
  - `silver`：`8%`
  - 其他等级：不打折
- `tax` 在折扣后金额上计算。

## 约束

- 评测时只允许修改本目录内文件。
- 不引入第三方依赖。
- 保持现有 `renderInvoiceReport(customerName, items, membershipLevel, taxRate)` 入口可用。
