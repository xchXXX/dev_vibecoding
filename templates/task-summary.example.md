# 任务摘要

## 基本信息

- `task_id`: `20260529-example-orchestrator-task`
- `title`: 示例任务：瘦身控制面并更新文档与测试
- `status`: `active`
- `owner`: `main-coordinator`

## 目标

- 把旧多文件控制面收口到 state.json、task.md、events.jsonl，并完成文档、脚本、测试同步。

## 范围

### Scope In

- docs/SUBAGENT_GOVERNANCE.md
- skills/global-task-orchestrator/**
- schemas/**
- templates/**
- tests/harness/control-plane.integration.ps1

### Scope Out

- 历史 run 目录兼容迁移
- 与 orchestrator 无关的 hooks 或 sync 行为修改

## 验收标准

- state.json 成为唯一真源
- task.md 只保留摘要
- events.jsonl 只保留关键事件
- 新测试覆盖核心 happy path 和 bad path

## 停止条件

- 发现必须保留旧控制面兼容层
- 发现测试必须依赖旧 run 目录结构

## 关键决定

- 不再持久化 dispatch_message_raw
- 子任务合同写在 subtasks[].assignment
- 子任务结果写在 subtasks[].result

## 当前阶段

- `current_phase`: `execution`

## 子任务

### ST-runtime

- `title`: 重写 orchestrator skill 与脚本
- `role`: `backend-implementer`
- `status`: `in_progress`
- `goal`: 删除旧控制面脚本并切换到 state.json 模型。

## 更新时间

- `2026-05-29T00:00:00+08:00`
