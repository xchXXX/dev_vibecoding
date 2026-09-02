# hooks/codex

当前开发环境不托管 Codex hooks，也不安装 `PreToolUse` 命令网关。

`scripts/bootstrap-local.py` 只按稳定 managed id 从用户级 `hooks.json` 删除已退休 command-safety 项，保留其他 hook 与顶层字段；`scripts/doctor-core.py --strict` 同时检查用户级 `hooks.json`、用户级 `config.toml` 和项目 `.codex/config.toml` 不再引用退休路径。

规则索引、文档校验、GTO、bootstrap、sync、doctor 和 session 入口由 `scripts/*.py` 的 WSL Python 标准库控制面负责。语义判断仍由 Codex 根据提示词、规则和 skill 完成，脚本只处理结构化输入与机械校验。
