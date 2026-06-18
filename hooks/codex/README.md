# hooks/codex

本目录保存 Codex hooks 真源。

当前最小落地范围：

- 项目级配置落点：`<repo>/.codex/config.toml`
- 已接事件：`PreToolUse`
- 已接脚本：`hooks/codex/scripts/PreToolUse.ps1`

当前职责边界：

- 只拦高风险写入相关工具：`apply_patch` 与 Bash
- 只调用 `scripts/validate-doc-routing.ps1`
- 校验失败时阻断写入
- 不复制规则正文，不在 hook 中重写目录分流逻辑

当前明确不做：

- 不接 `validate-plan-docs.ps1` 到通用 `PreToolUse`
- 不新增 `PostToolUse`、`PermissionRequest` 等其他事件
- 不做用户级 `~/.codex/config.toml` 安装或同步
