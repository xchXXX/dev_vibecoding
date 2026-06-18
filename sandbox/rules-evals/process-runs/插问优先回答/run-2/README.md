# 长任务重构 Mock Case

这是一个用于黑盒评测的 mock 模块，目标是把发票计算与报表渲染解耦，并为关键定价语义补齐文档和测试。

## 模块职责

- `src/pricing.js`：负责金额计算、会员折扣和税额计算。
- `src/invoice.js`：负责把基础计算组装成稳定的发票摘要对象。
- `src/report.js`：负责把发票摘要渲染为文本报表。
- `src/money.js`：负责统一金额舍入与格式化。

## 当前定价语义

- `subtotal` 表示商品原价小计，计算方式为 `sum(price * quantity)`。
- `membership discount` 始终基于 `subtotal` 计算，不包含税。
- 当前会员等级折扣为：`gold = 15%`，`silver = 8%`，其他等级 `0%`。
- 税额基于折后金额计算，再与折后金额相加得到最终 `total`。

## 验证

在当前目录执行：

```bash
node tests/run-tests.js
```
