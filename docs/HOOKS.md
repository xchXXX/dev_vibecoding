# HOOKS

## 冻结结论

`ai-harness` 的 Codex 开发正常链不使用 hooks。

- 不注册 `PreToolUse`、`PostToolUse` 或其他事件 hook。
- 不设置受控 command runner，不通过 hook 改写、代理或重试命令。
- 不保留其他代理平台的 hook settings、handlers、manifest、install/sync/doctor 接线或兼容 wrapper。
- 仓库中的旧 hook 资产由后续清理批次删除；本文不把待删除资产继续描述为可用合同。
- 用户旧运行时 `/mnt/c/Users/Laptop/.claude` 按批准范围永久删除，不创建备份或兼容目录。

## 机械门禁承接

- 文档分流、长任务合同、规则索引、GTO、doctor 和 Command Failure Memory 由显式 WSL Python 入口与 Linux 原生命令承担。
- 可自动化判断由对应脚本与测试保证，不依赖某次工具调用是否偶然命中 hook。
- Python 只离线生成、校验规则索引；正常交互链不运行语义 matcher 或规则套餐装配器。

## 验收

- 仓库活跃入口、bootstrap、sync、doctor、测试和运行时配置不注册 hook。
- 正式成功路径与验收命令不引用 hook handler、`.ps1` 或 `.cmd`。
- 删除旧资产后不留下空配置、占位 wrapper 或“暂时保留”的兼容口径。
