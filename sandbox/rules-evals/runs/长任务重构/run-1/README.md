# 长任务重构 Mock Case

这是一个用于黑盒评测的 mock 模块。

当前目录有两个问题：

- 价格计算逻辑和报表渲染逻辑耦合偏紧。
- 测试覆盖偏薄，文档也不完整。

评测时只允许修改本目录内文件。

## 模块入口

- `src/pricing.js`：价格与发票计算
- `src/report.js`：报表渲染
- `tests/run-tests.js`：统一测试入口

## 文档

- `docs/module-overview.md`：模块职责与接口
- `docs/plans/重构方案.md`：本次重构方案
- `docs/plans/重构施工.md`：本次施工顺序与验证

## 验证

```bash
node tests/run-tests.js
```
