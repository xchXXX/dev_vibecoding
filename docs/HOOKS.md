# Hooks 边界

Harness 的正常链使用显式 Python CLI，不注册 `PreToolUse`、`PostToolUse` 或其他事件 hook，不通过 hook 代理、改写或自动重试命令。

安装、更新、卸载和 doctor 不得改写用户已有 hooks、MCP、插件及 `config.toml` 的原始内容。用户 hooks 不属于安装器的受管资产；旧工具留下的配置同样先核实归属，portable 安装器不自动接管。

规则元数据生成与校验是离线操作；普通任务由 Codex 按语义选规则。显式 GTO 的机械门禁由其控制器承担，CFM 由独立 runner 承担，不建立全局命令拦截器。

验收需要预置非空 hooks 和用户配置，执行完整生命周期后比对字节；仅检查“没有新 hook”不足以证明保全。产品验收入口见 [EVALS](EVALS.md)。
