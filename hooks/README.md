# hooks

本目录只保留 Codex 不使用 hooks 的边界说明，不包含可安装的 hook runtime。

- 正式 bootstrap、sync、doctor、规则校验、GTO 与 CFM 统一使用显式 WSL Python 入口。
- 不注册事件 hook，不通过 hook 改写、代理或重试命令。
- 机械门禁由对应 Python 脚本与 unittest 承担。
