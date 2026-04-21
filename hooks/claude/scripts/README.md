# hooks/claude/scripts

本目录是 Phase 5 六个 hook 事件的脚本落点。当前只冻结职责，不写具体实现。

| 事件 | 职责边界 |
| --- | --- |
| `SessionStart` | 记录会话起始上下文，用于审计，不修改请求。 |
| `UserPromptSubmit` | 只做 block/allow 或补少量上下文，不补全、不重写 prompt。 |
| `PreToolUse` | 只对高风险工具做守卫，matcher 口径固定为字符串正则 `^(Bash|Write|Edit|MultiEdit)$`，不改写命令。 |
| `PostToolUse` | 只对相同高风险工具做执行后审计，matcher 同样使用 `^(Bash|Write|Edit|MultiEdit)$`。 |
| `Stop` | 只返回终止相关的 block/allow 或少量上下文，不代做工作。 |
| `SubagentStop` | 只做子 agent 结束审计与 block/allow，不执行额外任务。 |

后续脚本批次必须遵守 `hooks/claude/settings.json` 的官方结构：`hooks -> <Event> -> [ { matcher?, hooks: [ { type: \"command\", shell: \"powershell\", command: ... } ] } ]`。运行时落地时只允许对用户级 `~/.claude/settings.json` 的顶层 `hooks` 子树做定点托管，其他顶层用户键保持不变。当前批次不写任何 `.ps1` 实现，也不引入自动修复或完整 settings merge/override 设计。
