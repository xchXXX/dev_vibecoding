# project/docs/ai

项目侧 role-first 委派入口与增量边界。

只记录项目增量说明，不复制全局治理正文。通用规则统一引用 `../../../../docs/SUBAGENT_GOVERNANCE.md`。

最小应包含：
- 角色优先委派说明：普通模型直接消费 `task.md` 与显式子任务 `assignment`；主协调器调用 `spawn_agent`，并把返回的 `platform_agent_id` 绑定为该子任务的 `dispatch` 实时身份。
- 项目专属约束：仓库路径、模块名、服务名、验收条件、只读/可写边界等。
- 与项目根 `AGENTS.md`、`config/ai/README.md` 的协同说明。
