# HOOKS

本文件定义当前仓库的 hooks 总体口径。

截至 `2026-06`：

- Claude 支持项目当前已采用的 hooks 合同
- Codex 也已支持自身 hooks，且本仓库已落地最小 `PreToolUse` 接线

统一原则：

- hooks 只做 guard / audit，不做自动修复
- 真正可复用的规则判断统一收口到 `scripts/*.ps1`
- hooks 可以调用脚本，但不复制脚本内部规则
- hooks 属于前置 guardrail，不是完整 enforcement boundary

## Claude 合同范围

Phase 5 Claude hooks 的冻结合同只覆盖六个事件：`SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop`、`SubagentStop`。其余官方事件如 `Notification`、`PreCompact`、`SessionEnd` 不在本合同内。

## Claude 合同要点

1. `hooks/claude/settings.json` 采用官方 `hooks` 层级结构：顶层仅有 `hooks`；第二层键仅为上述六个事件；每个事件值都是数组；数组元素内使用 `hooks` 数组声明 handler；handler 统一用 `type: command`，Windows 端显式写 `shell: powershell`。
2. `PreToolUse` 与 `PostToolUse` 使用字符串正则 matcher 收紧范围，当前冻结口径为 `^(Bash|Write|Edit|MultiEdit)$`，只匹配高风险工具名。
3. `PreToolUse` 只能做守卫，不得改写命令；`UserPromptSubmit`、`Stop`、`SubagentStop` 只能返回 block/allow 或补少量上下文，不能代做缺失工作。
4. hooks 只接用户级 `~/.claude/settings.json`。install/sync 允许在这个单一文件内对顶层 `hooks` 字段做定点托管与回写：只新增或更新顶层 `hooks` 子树，保留其他现有顶层字段原样不动；不触碰项目 `.claude/settings.json` 或 `.claude/settings.local.json`，也不做自动修复。
5. doctor 只读审计 `agents/manifest.json`、`hooks/claude/manifest.json`、`hooks/claude/settings.json` 与 `hooks/claude/scripts/<Event>.ps1` 的注册关系，并核查用户级 `~/.claude/settings.json` 中托管的顶层 `hooks` 子树是否与真源模板一致；doctor 不要求整个 settings 文件全量等于模板，也不代替 install/sync/hook 执行。
6. `hooks/claude/manifest.json` 继续作为 install/sync/doctor 可读清单，至少声明 `schema_version`、`runtime`、`items[]` 以及每个事件的 `id`、`source`、`target`、`description`；`PreToolUse`/`PostToolUse` 保留 `tools` 数组描述高风险工具边界。

## Codex 口径

Codex hooks 当前可用于：

- 在 `PreToolUse` 中拦截 Bash
- 在 `PreToolUse` 中拦截 `apply_patch` 文件编辑
- 在 `PreToolUse` 中拦截 MCP 工具调用
- 根据检查结果执行 `deny`、补充 `additionalContext`，或在受支持场景下改写输入

对本仓库最相关的推荐用法：

- 在写代码或执行高风险 Bash 前调用 `scripts/validate-doc-routing.ps1`
- 在进入长任务正式实施前调用 `scripts/validate-plan-docs.ps1`
- 当校验失败时输出统一提示，由脚本保留真源判断，避免让 hook 自己重复实现一套逻辑

当前已落地的最小接线：

- 项目级配置落点：`<repo>/.codex/config.toml`
- 事件：`PreToolUse`
- matcher：`^(Bash|apply_patch)$`
- 脚本：`hooks/codex/scripts/PreToolUse.ps1`
- 真正的规则判断：`scripts/validate-doc-routing.ps1`

当前语义：

- `PreToolUse` 只做观测/提示，不宣称强阻断
- 发现文档分流违规时，统一输出中文提示并给出建议补齐目录
- 是否阻断写入不能只依赖当前 Codex hook

限制边界：

- 不把 Codex hooks 当作唯一闸门
- 不在 hook 中维护与脚本重复、易漂移的规则正文
- 不假设所有等价写入路径都必然被同一种 hook 拦截
- 不把当前 Codex `PreToolUse` 的失败退出码当成可靠阻断机制

## 当前阶段

当前批次：

- 保留 Claude hooks 合同与现有脚本边界
- 同步 Codex hooks 的观测/提示口径
- 已落地 Codex `PreToolUse` 最小接线
- 暂不新增 `PostToolUse`、`PermissionRequest` 等其他 Codex hook 事件
- 暂不把 `validate-plan-docs.ps1` 接入通用写入前闸门
