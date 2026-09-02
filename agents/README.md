# AGENTS Catalog

本目录保存 Codex 编排使用的跨项目角色语义真源。

## 目录职责

- 这里只放跨项目可复用的角色语义
- 项目专属角色约束留在项目自己的 `AGENTS.md` 或 `config/ai/`

## 选择原则

使用 `planner`
- 当任务还需要冻结方案、拆边界、生成或重整结构化任务合同

使用 `reader`
- 当任务目标是补上下文、找证据路径、梳理调用链且暂不改文件时

使用 `reviewer`
- 当任务目标是做风险审查、验收裁决、识别回归与测试缺口时

使用 `doc-curator`
- 当任务已经明确，需要优先整理、补齐、迁移文档时

使用 `test-verifier`
- 当需要先设计测试、执行验证、确认实现是否满足验收标准时

使用 `backend-implementer`
- 当任务目标是后端或通用服务端实现，不涉及前端界面时

使用 `frontend-implementer`
- 当任务主要落在前端页面、交互、样式或前端构建物时

使用 `ops-runbook`
- 当任务主要是部署、运维、排障、运行手册或服务侧验证时

不要使用全局 agent
- 当角色严重依赖项目私有路径、项目私有服务、项目私有术语或团队私有流程时

## 角色层统一口径

- 角色文件必须保持统一 8 段结构：`角色目标`、`负责范围`、`不负责`、`输入`、`输出`、`工作规则`、`停止条件`、`协作交接`。
- 角色模型的 `输入` 必须显式包含 `task.md` 与当前子任务提示；提示中给出 assignment、读写边界、依赖和验证要求。
- `reader` 与 `reviewer` 默认只读，不在角色定义内直接承担实现写入。
- 角色语义仅在 `agents/*.md` 维护；平台派发参数不另建静态兼容映射层。
- 执行型委派必须遵守显式子任务提示中的 assignment，不得跳过 read paths。
- 未经授权不得写入提示声明的 write paths 之外，也不得触碰禁改文件。

## 主协调器验收门禁

1. 子代理提交的回收结果必须是结构化结果，并写回 `state.json.subtasks[].result`。
2. `completed` 与 `blocked` 两类终态子任务都必须写 `subtask.result`；缺失结果直接判定不通过。
3. `changed_files` 必须全部位于 `subtask.write_paths` 内，越界写入直接判定不通过。
4. `written_by`、`written_role` 必须存在，且 `written_role` 必须与子任务角色一致。
5. `result.verification.result` 必须与 `result.verification.commands` 对齐，无法验证时必须说明原因与风险。
6. `deviations`、`blocked_by`、`risks`、`follow_up` 必须保留字段，可为空但不得省略。
7. `blocked` 子任务必须在 `blocked_by` 中写清阻塞来源，并在结果中留下下一步建议。
8. 主协调器验收通过前，任务状态不得标记为完成；仅允许 `completed` 或 `blocked` 两类终态。

## Catalog

| name | role | when_to_use | must_not_do | default_tools | notes |
| --- | --- | --- | --- | --- | --- |
| `planner` | 冻结方案与拆单 | 需求未冻结、边界不清、需要重整任务合同与 `subtasks` | 直接跳过方案冻结去写实现 | `Read, Write, Bash` | 对齐六要点合同冻结 |
| `reader` | 只读补上下文与证据收集 | 需要阅读、定位证据、梳理依赖与未知项 | 越权修改业务文件或代替实现落盘 | `Read, Bash` | 对齐 `context_read` |
| `reviewer` | 风险审查与验收裁决 | 需要 findings、回归评估、通过/不通过结论 | 默认直接修复实现问题 | `Read, Bash` | 对齐 `risk_review` |
| `doc-curator` | 文档更新与结构整理 | 先文档后代码、文档迁移、规范补齐 | 越权实现业务代码 | `Read, Write` | 对齐 `update_docs` |
| `test-verifier` | 测试设计与验证 | 需要先写测试、执行验证、输出验收结论 | 直接写业务功能 | `Read, Write, Bash` | 对齐 `tests_and_validation` |
| `backend-implementer` | 后端实现 | 服务端、脚本、接口、数据处理实现 | 越权改前端或运维口径 | `Read, Write, Bash` | 对齐 `backend_code` |
| `frontend-implementer` | 前端实现 | 页面、组件、交互、样式与前端构建 | 越权定义后端契约 | `Read, Write, Bash` | 对齐 `frontend_code` |
| `ops-runbook` | 运维与运行手册 | 部署、日志、systemd、排障、runbook | 把项目私有服务器口径上升为全局规则 | `Read, Write, Bash` | 对齐 `ops_and_runbook` |

## 文件规范

每个 agent 文件都必须包含：

- YAML frontmatter
- `name`
- `description`
- `tools`
- 非空正文

建议遵循 `_schema.example.md` 的正文结构：

- `角色目标`
- `负责范围`
- `不负责`
- `输入`
- `输出`
- `工作规则`
- `停止条件`
- `协作交接`

## 关闭规则

- agent 自然完成不等于可关闭
- 必须先经过主协调器质量验收
- 只有质量验收通过，或者出现死循环、长期无响应、重大阻塞，才允许关闭

## 项目边界

这些内容不应放到全局 agent：
- 项目专属目录
- 项目专属部署命令
- 服务器地址与 SSH 别名
- 业务模块名和业务术语
- 单项目私有验收规则

这些内容可以放到全局 agent：
- 通用职责边界
- 通用输入输出结构
- 通用停止条件
- 通用协作交接方式

## 实时派发

- 主协调器先读取 `task.md` 和当前 subtask 的 `assignment`、读写边界、依赖及验证要求，再按职责选择对应 `agents/*.md`。
- 使用当前协作工具 `spawn_agent` 直接派发；`task_name` 是本轮任务标签，`message` 是显式子任务提示，`fork_turns` 按需要提供真实上下文隔离。
- 派发成功后，把平台返回的真实身份作为 `platform_agent_id`，连同所选角色 `agent_key`、`brief_kind` 和 `brief_sha256` 绑定到 subtask `dispatch`。
- 后续结果与 review 路由只依据原 subtask `assignment`、绑定后的 `dispatch` 身份和 finding lineage，不经过静态角色兼容表。

