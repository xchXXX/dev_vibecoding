# 长任务重构 Mock Case

这是一个用于黑盒评测的本地 mock 模块，目标是在只修改当前目录的前提下完成一次小型但完整的重构。

## 重构目标

- 降低价格计算和报表渲染之间的职责耦合。
- 补齐目录内文档，让结构、入口和验证方式清晰可见。
- 扩展测试覆盖，保证 `node tests/run-tests.js` 作为总入口稳定通过。

## 目录结构

```text
src/
  money.js    # 金额舍入与格式化
  pricing.js  # 定价计算、会员折扣、输入规范化
  report.js   # 报表视图模型与文本渲染
tests/
  pricing.test.js
  run-tests.js
docs/plans/
  重构方案.md
  重构施工.md
```

## 对外接口

- `subtotal(items)`：计算商品小计。
- `applyDiscount(total, membershipLevel)`：根据会员等级应用折扣。
- `calculateInvoice(items, membershipLevel, taxRate)`：返回账单金额摘要。
- `renderInvoiceReport(customerName, items, membershipLevel, taxRate)`：渲染文本报表。

## 设计说明

- `pricing.js` 负责业务计算，不处理展示字符串格式。
- `report.js` 先构造报表视图模型，再生成文本输出，减少对计算细节的直接耦合。
- `money.js` 集中管理金额舍入与输出格式，避免多处重复处理。

## 测试

执行：

```bash
node tests/run-tests.js
```

当前测试覆盖：

- 正常账单计算路径
- 会员折扣与大小写规范化
- 空购物车
- 非法输入
- 报表模型与文本渲染
