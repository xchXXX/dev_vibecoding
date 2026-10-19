# Control plane contract

Task ID: `20300102-030405-control-plane-contract`

## 施工目标

Implement the WSL Python control plane.

## 前置条件

- 用户已确认六要点任务合同。
- 写入前已冻结范围、验收和风险。

## 执行顺序

Codex supplies semantics; Python performs mechanical gates.

## 文档先行清单

- 先同步长期真源和任务施工文档。

## 测试同步清单

- 先建立最小 Red，再实施 Green 和相关回归。

## 实施批次

- skills/global-task-orchestrator
- tests/harness

## 每批写入范围

- skills/global-task-orchestrator
- tests/harness

## 验证命令

- The deterministic review loop reaches final/pass.

## 回退方案

- Existing dirty work must be preserved.

## 审查与返工路径

独立 reviewer 记录稳定 finding_id；原实现者修复，同一 reviewer re-review，直至可验收。
