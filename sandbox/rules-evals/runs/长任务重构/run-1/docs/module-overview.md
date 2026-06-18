# 模块说明

## 概览

`run-1` 是一个简化的开票与报表模块，负责两件事：

- 根据商品、会员等级和税率计算发票金额。
- 将计算结果渲染为纯文本报表。

## 公开接口

### `src/pricing.js`

- `subtotal(items)`: 计算商品小计。
- `applyDiscount(total, membershipLevel)`: 根据会员等级返回折后金额。
- `calculateInvoice(items, membershipLevel, taxRate)`: 返回 `{ beforeDiscount, discounted, tax, total }`。

### `src/report.js`

- `renderInvoiceReport(customerName, items, membershipLevel, taxRate)`: 返回多行纯文本报表。

## 设计目标

- 计算逻辑只负责金额推导，不负责字符串格式化。
- 报表逻辑只负责组织展示文本，尽量复用计算结果而不是内嵌金额规则。
- 金额统一保留两位小数，行为由测试固定。

## 验证

- 运行 `node tests/run-tests.js`
