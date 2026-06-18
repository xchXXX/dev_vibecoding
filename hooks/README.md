# hooks

本目录保存 hooks 真源、合同说明与脚本。

当前已落地：

- `hooks/claude/`
- `hooks/codex/`

当前未落地但已在文档口径中同步：

- Codex hooks 的职责边界与接入建议

统一原则：

- hooks 只做 guard / audit，不做自动修复
- 可复用规则判断统一收口在 `scripts/*.ps1`
- 不同客户端的 hooks 可以作为前置触发器，但不应成为唯一 enforcement boundary
- 对 Codex 当前最小接线，默认按“观测/提示”理解，不把 hook 失败退出码当成可靠硬阻断
