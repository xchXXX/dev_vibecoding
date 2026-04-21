# hooks/claude

本目录是 Phase 5 Claude hooks 的合同入口，只保留后续 install/sync/doctor 需要消费的静态文件。

1. `hooks/claude/settings.json`
   使用最小官方 `hooks` 结构模板：顶层只有 `hooks`；六个事件分别映射为数组；handler 统一写成 `type: command`，Windows 端显式 `shell: powershell`。
   `PreToolUse` 与 `PostToolUse` 使用字符串正则 matcher `^(Bash|Write|Edit|MultiEdit)$`，只匹配高风险工具名。
   install/sync 后续只允许把该模板定点托管到用户级 `~/.claude/settings.json` 的顶层 `hooks` 字段，其他现有顶层字段必须保留原样。
2. `hooks/claude/manifest.json`
   保留 install/sync/doctor 可读的清单字段：`schema_version`、`runtime`、`items[]`，以及每个事件的 `id`、`source`、`target`、`description`；Pre/Post 额外保留 `tools`。
3. `hooks/claude/scripts/`
   每个事件对应一个 `<Event>.ps1` 命名落点，当前不实现逻辑，只冻结路径和职责边界。

本目录全部内容都以审计/守卫为主，不做自动修复，不设计完整 settings merge/override 体系；唯一允许的运行时写入是对用户级 `~/.claude/settings.json` 顶层 `hooks` 子树的定点托管，不碰项目 `.claude/settings.json` 或 `.claude/settings.local.json`。
