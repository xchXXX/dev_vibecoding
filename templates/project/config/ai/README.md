# project/config/ai

项目侧配置覆盖入口。

只记录项目级配置覆盖边界，不复制全局治理正文。普通模型直接消费 `task.md` 与显式子任务 `assignment`；主协调器调用 `spawn_agent`，并把返回的 `platform_agent_id` 绑定为该子任务的 `dispatch` 实时身份。

最小应包含：
- 与 `docs/ai/README.md` 对齐的项目级配置差异。
- 需要时的模型或运行参数覆盖，以及对应原因。
- 仅对本项目成立的运行约束或启用范围。
