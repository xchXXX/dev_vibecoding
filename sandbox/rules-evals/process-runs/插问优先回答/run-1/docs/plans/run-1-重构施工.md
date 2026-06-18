# run-1 重构施工

## 施工目标

按“文档与测试先行、代码后改”的顺序，在 `run-1` 内完成模块重构并保持对外行为兼容。

## 前置条件

- 方案文档已冻结。
- 当前目录现有测试入口可运行。
- 写入范围限定在 `run-1` 目录内。

## 执行顺序

1. 落盘方案文档与施工文档。
2. 更新 `README.md` 与 `docs/ARCHITECTURE.md`。
3. 先扩充并拆分 `tests/`。
4. 重构 `src/` 并保留兼容入口。
5. 运行 `node tests/run-tests.js` 验证。

## 文档先行清单

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/plans/run-1-重构方案.md`
- `docs/plans/run-1-重构施工.md`

## 测试同步清单

- 新增或重写 `tests/pricing.test.js`
- 新增 `tests/report.test.js`
- 更新 `tests/run-tests.js`

## 实施批次

- Batch 1：文档与测试先行。
- Batch 2：源代码重构与兼容层整理。
- Batch 3：执行验收并按结果修正。

## 每批写入范围

- Batch 1：`README.md`、`docs/`、`tests/`
- Batch 2：`src/`
- Batch 3：如验证失败，仅在 `src/`、`tests/` 内做最小修正

## 验证命令

- `node tests/run-tests.js`

## 回退方案

- 若重构后报表入口不兼容，先恢复 `pricing.js` 兼容导出，再让新文件作为内部实现。
- 若新增测试暴露设计问题，优先调整 `src/`，不回退文档中的职责边界定义。

## 审查与返工路径

- 先以测试结果做第一道验收。
- 若出现失败，回到本目录内对应文件最小返工，再复跑 `node tests/run-tests.js`。
- 本次任务不改仓库其他目录，不把问题外溢到目录外处理。
