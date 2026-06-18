# run-3 重构方案

## 任务目标

在 `run-3` 目录内完成一次完整重构，降低价格计算与报表渲染之间的耦合，补齐模块文档与测试，并确保 `node tests/run-tests.js` 通过。

## 背景与问题

当前模块把价格计算结果的结构细节直接暴露给报表渲染函数，导致：

- 计价逻辑与报表输出之间存在隐式数据耦合。
- 测试集中在单一路径，缺少边界场景覆盖。
- README 只描述问题，没有说明模块结构、验证命令与扩展方式。

## 范围

本次仅修改以下目录内文件：

- `src/`
- `tests/`
- `docs/plans/`
- `README.md`

## 非目标

- 不修改 `run-3` 目录之外的任何文件。
- 不引入第三方依赖或测试框架。
- 不改变既有对外字符串格式的核心字段文案。

## 约束与依赖

- 必须保持 Node.js CommonJS 运行方式。
- 验证命令固定为 `node tests/run-tests.js`。
- 长任务要求先落盘方案文档与施工文档，再进入代码实现。

## 方案摘要

采用“三层拆分”的轻量结构：

1. `pricing.js` 只负责金额计算与发票摘要。
2. `invoice.js` 负责把客户名、商品列表和计价结果组装成报表模型。
3. `report.js` 只负责把报表模型格式化为文本。

同时补充 README，说明目录职责、公开 API 和验证方式；测试按职责拆分为 pricing、invoice、report 三组。

## 风险与回退

- 风险：重构后导出接口变化可能导致测试或调用点失配。
- 控制：保留 `renderInvoiceReport(customerName, items, membershipLevel, taxRate)` 兼容入口。
- 回退：若验证失败，优先回退到单文件职责合并前的导出签名，再逐步恢复内部拆分。

## 验收标准

- `src/` 中计价、报表模型、渲染职责清晰分离。
- README 与 `docs/plans/` 文档完整描述目标、边界、执行与验证方式。
- 测试覆盖正常路径与关键边界场景。
- `node tests/run-tests.js` 成功退出并输出通过结果。

## 阶段划分

1. 文档阶段：补齐方案文档、施工文档、README。
2. 重构阶段：拆分模块边界并保持兼容接口。
3. 验证阶段：扩充测试并执行回归命令。

## 需先同步的核心文档与测试

- 文档：`README.md`、`docs/plans/run-3-重构方案.md`、`docs/plans/run-3-重构施工.md`
- 测试：`tests/pricing.test.js`、`tests/report.test.js`、`tests/invoice.test.js`、`tests/run-tests.js`
