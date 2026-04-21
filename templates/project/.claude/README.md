# project/.claude

项目模板中的 Claude 覆盖层。

用于放项目专属：
- agents
- settings 覆盖
- hook 覆盖
- 局部规则

全局角色真源仍在 `../../../agents/*.md`，项目 `.claude/agents/` 仅承载项目增量或覆盖版本，并标注与全局口径的差异。

约束：

- 这里只放项目增量，不复制全局 `ai-harness` 的统一协作规则正文。
- 通用 subagent / review / testing 规则统一引用：
  - `../../../docs/SUBAGENT_GOVERNANCE.md`
  - `../../../rules/common/SUBAGENT_RULES.md`
