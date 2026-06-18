# run-1 重构方案

## 任务目标

在 `run-1` 目录内完成一次完整重构，降低价格计算与报表渲染耦合，补齐文档与测试，并确保 `node tests/run-tests.js` 通过。

## 背景与问题

现状只有 `pricing.js` 和 `report.js` 两个源文件，报表直接依赖整块定价实现，测试也把金额规则和报表行为混在同一个测试文件中。模块边界模糊，后续扩展折扣规则或报表格式时，定位和回归成本都偏高。

## 范围

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/plans/*.md`
- `src/*.js`
- `tests/*.js`

## 非目标

- 不改动 `run-1` 目录之外的任何文件。
- 不引入第三方依赖或新的测试框架。
- 不新增新的业务规则，只整理现有职责边界并补覆盖。

## 约束与依赖

- 评测只允许修改当前目录。
- 最终验收命令固定为 `node tests/run-tests.js`。
- 现有对外入口 `renderInvoiceReport(customerName, items, membershipLevel, taxRate)` 需要保持可用。

## 方案摘要

- 新增 `money.js` 作为金额工具层。
- 将 `pricing.js` 重构为更聚焦的 `invoice-calculator.js`，保留对旧导入路径的兼容。
- 将 `report.js` 拆成“视图模型组装”和“字符串渲染”两步，降低对定价内部细节的耦合。
- 把测试拆成 `pricing.test.js` 与 `report.test.js`，并扩展对边界行为的断言。

## 风险与回退

- 风险：文件拆分后旧测试或旧引用路径失效。
- 风险：金额展示改用统一工具后，格式化行为可能与原先细节不一致。
- 回退：如出现兼容性问题，可恢复 `pricing.js` 对外接口并让新模块继续在其后实现，保证调用方入口不变。

## 验收标准

- `node tests/run-tests.js` 返回成功。
- 定价测试覆盖 subtotal、折扣、税额与总额。
- 报表测试覆盖模型组装与最终文本渲染。
- README 与架构说明明确新模块边界，并写明 `tax` 在折扣后计算。

## 阶段划分

1. 冻结方案与施工文档。
2. 先更新 README、架构说明与测试。
3. 再进行 `src/` 重构与兼容层整理。
4. 运行验收命令并收口。

## 需先同步的核心文档与测试

- 核心文档：`README.md`、`docs/ARCHITECTURE.md`
- 测试：`tests/pricing.test.js`、`tests/report.test.js`、`tests/run-tests.js`
