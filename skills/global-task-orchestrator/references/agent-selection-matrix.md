# 角色选择矩阵

默认路由口径：先选 `role`，再通过 `agents/codex-role-map.json` 解析 `agent_type`，禁止直接按裸 `default/explorer/worker` 派发。

## 角色与消费规则

| role | default_agent_type | 何时优先选择 | 输出重点 | 失败回退 |
| --- | --- | --- | --- | --- |
| `planner` | `default` | 目标、边界、验收未冻结 | 阶段方案、边界、停止条件 | 回退 `reader` 补证据 |
| `reader` | `explorer` | 需要补上下文、找证据、梳理调用链 | 结构化阅读回报与证据路径 | 回退 `planner` 澄清边界 |
| `reviewer` | `default` | 需要风险审查、验收裁决、回归评估 | findings 优先、通过/不通过结论 | 回退 `reader` 补证据或 `test-verifier` 补验证 |
| `doc-curator` | `worker` | 需要文档更新、规范收敛、入口同步 | 文档改动与一致性说明 | 回退 `reviewer` 做审查 |
| `test-verifier` | `worker` | 需要测试设计、执行验证、验收证据 | 验证命令、结果与风险 | 回退实现角色补修复 |
| `backend-implementer` | `worker` | 后端逻辑、脚本、服务端实现 | 代码改动与验证结果 | 回退 `reviewer` 或 `test-verifier` |
| `frontend-implementer` | `worker` | 前端页面、交互、样式实现 | 前端改动与验证结果 | 回退 `reviewer` 或 `test-verifier` |
| `ops-runbook` | `worker` | 部署、运维、排障与运行手册 | runbook 与可执行运维步骤 | 回退 `reviewer` 做风险审查 |

## role -> agent_type 消费约束

- 调度顺序固定：`select_role -> resolve_role_map -> build_work_order_and_dispatch_packet -> compile_dispatch_message`
- `work_order.role` 是派发主键；`agent_type` 只作为执行承载，不作为任务语义入口
- `dispatch_message_raw` 必须显式声明当前角色语义与读写边界
- 若 `role` 缺失、role-map 不存在或映射冲突：立即 `blocked`，不得手写兜底 `agent_type`
- `reader` 与 `reviewer` 默认只读；需要写入时必须切换到对应实现角色并重新签发工单

## 复杂任务补充规则

- 跨模块、多角色并行、契约或状态机改造：除实施角色外，默认追加 `reviewer` 工单
- 任何执行型工单都必须先经 `reader` 或已有证据完成上下文补齐
- 不允许两个角色共享同一写入文件；有重叠必须拆分并串行
