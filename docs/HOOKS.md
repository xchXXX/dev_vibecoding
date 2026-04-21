# HOOKS

本文件定义 Phase 5 Claude hooks 的冻结合同，只覆盖六个事件：`SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop`、`SubagentStop`。其余官方事件如 `Notification`、`PreCompact`、`SessionEnd` 不在本合同内。

## 合同要点

1. `hooks/claude/settings.json` 采用官方 `hooks` 层级结构：顶层仅有 `hooks`；第二层键仅为上述六个事件；每个事件值都是数组；数组元素内使用 `hooks` 数组声明 handler；handler 统一用 `type: command`，Windows 端显式写 `shell: powershell`。
2. `PreToolUse` 与 `PostToolUse` 使用字符串正则 matcher 收紧范围，当前冻结口径为 `^(Bash|Write|Edit|MultiEdit)$`，只匹配高风险工具名。
3. `PreToolUse` 只能做守卫，不得改写命令；`UserPromptSubmit`、`Stop`、`SubagentStop` 只能返回 block/allow 或补少量上下文，不能代做缺失工作。
4. hooks 只接用户级 `~/.claude/settings.json`。install/sync 允许在这个单一文件内对顶层 `hooks` 字段做定点托管与回写：只新增或更新顶层 `hooks` 子树，保留其他现有顶层字段原样不动；不触碰项目 `.claude/settings.json` 或 `.claude/settings.local.json`，也不做自动修复。
5. doctor 只读审计 `agents/manifest.json`、`hooks/claude/manifest.json`、`hooks/claude/settings.json` 与 `hooks/claude/scripts/<Event>.ps1` 的注册关系，并核查用户级 `~/.claude/settings.json` 中托管的顶层 `hooks` 子树是否与真源模板一致；doctor 不要求整个 settings 文件全量等于模板，也不代替 install/sync/hook 执行。
6. `hooks/claude/manifest.json` 继续作为 install/sync/doctor 可读清单，至少声明 `schema_version`、`runtime`、`items[]` 以及每个事件的 `id`、`source`、`target`、`description`；`PreToolUse`/`PostToolUse` 保留 `tools` 数组描述高风险工具边界。

## 当前阶段

当前批次只冻结文档和配置模板，不实现六个 `.ps1` hook 脚本逻辑。后续脚本批次必须按本合同补齐 guard/audit 行为。
