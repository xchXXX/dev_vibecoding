# AGENTS

本文定义 `ai-harness/agents/` 的当前 Codex 角色说明边界。角色文件是派发时的人读职责真源，不是另一套任务状态、运行时安装目录或控制器。

## 当前目标

- 在 `agents/` 中维护跨项目可复用的角色职责。
- 由主协调器先选择职责，再结合冻结的 `state.json.subtasks[]` 合同调用平台真实代理能力。
- 把任务边界、读写路径、验证要求和停止条件保存在当前 subtask 合同中，不复制成角色私有状态。
- 把协作治理统一引用到 `docs/SUBAGENT_GOVERNANCE.md`，把规则读取统一引用到根 `AGENTS.md` 与 `rules/registry/RULES_INDEX.json`。

## 当前目录

```text
agents/
  README.md
  _schema.example.md
  planner.md
  reader.md
  reviewer.md
  doc-curator.md
  test-verifier.md
  backend-implementer.md
  frontend-implementer.md
  ops-runbook.md
```

目录约束：

- 一个 Markdown 文件只描述一个通用角色。
- 文件名使用小写英文和短横线，并与角色标识保持一致。
- 普通模型直接消费 `task.md` 与显式子任务 `assignment`；主协调器调用 `spawn_agent`，并把返回的 `platform_agent_id` 绑定到该子任务的 `dispatch` 实时身份。
- 项目专属路径、模块名、环境名、部署信息和私有流程保留在项目自己的 `AGENTS.md`、规则或任务合同中。

## 角色文件合同

角色正文至少包含：

1. `角色目标`
2. `负责范围`
3. `不负责`
4. `输入`
5. `输出`
6. `工作规则`
7. `停止条件`
8. `协作交接`

角色文件可以声明平台识别所需的最小 frontmatter，但不得把本机绝对路径、用户数据、长期任务状态或项目私有配置写入通用角色真源。

## 派发合同

- 长任务必须先冻结六份工件：`docs/ai/tasks/<task_id>/state.json|task.md|events.jsonl` 与 `docs/tasks/<task_id>/plan.md|execution.md|acceptance.md`。
- `events.jsonl` 是必备的 append-only 关键事件流；`state.json` 是唯一机器状态真源。
- 执行者只接收目标 subtask 的 allowlist brief、读写边界和必要证据；审查者接收 review brief、目标变更与验收标准。
- 无历史派发、真实代理身份和独立 reviewer 必须由平台实际参数与返回值证明，不能用提示词或角色文件冒充。
- 控制面动作只以 `orchestrator_ctl.py --help` 当前公开并实际实现的 `--action` 为准；文档不得发明动作或保留单横线参数别名。

## 规则读取

每轮固定读取：

1. 全局与项目 `AGENTS.md`。
2. 当前 `RULES_INDEX.json` 元数据。
3. 恰好三条 `activation=always_on` 规则：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。

其余规则由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮实际操作自由选读。`summary`、`intents`、`paths` 与 `linked_skill` 只是相关性提示；Python 只离线生成和校验索引。

## 历史边界

- 旧任务、旧 run 与旧方案正文只保留历史事实，不作为当前角色、派发或运行时合同。
- 当前入口不路由历史 packet、旧会话目录、事件拦截接线或其他代理平台资产。
- 新任务不得从历史文件复制旧字段、命令或兼容入口；需要历史证据时只读取明确相关的只读记录。

## 验收

- 角色说明只面向 Codex 当前协作链。
- 角色、任务合同、规则和控制器职责边界一致。
- 所有可执行命令使用 WSL `python3` 与 GNU 双横线参数。
- 新派发只依赖平台真实代理能力、v3 `state.json` 和六份必备工件。
