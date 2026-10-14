# 开发验证

开发依赖按仓库 requirements.txt 装入本工作区 .venv。基础管理 CLI 只依赖标准库；GTO 运行的 jsonschema 另行报告。

从 Git 接入 dots 云端见 [dots 云端接入与验收](dots-cloud.md)，使用仓库技能发现入口与一条环境安装命令，不调用旧机器 bootstrap。

从仓库根运行 `.venv/bin/python -B -m unittest discover -s tests/portable -p 'test_*.py'`，临时夹具位于 .tmp/portable-harness/，结束后清理。生成分发包与执行原始日志位于 .artifacts/portable-harness/20261014/。

新 Codex 会话、原生 Windows、Linux、WSL、云端分别记录；不能以相同 Python 代码或操作系统模拟替代真实平台运行。生命周期失败按 contract 恢复，不直接删除 journal 或 receipt。
