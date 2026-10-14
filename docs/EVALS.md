# 评估与回归

在当前环境已核实的 Python 3.11+ 中运行，Linux/WSL 可使用 `python3`：

```text
python -B -m unittest discover -s tests/portable -p test_*.py
python -B -m unittest discover -s tests/harness -p test_*.py
python -B tests/gto-standalone/run_regression.py
```

这些是回归入口，不是已经通过的声明。选择与变更相关的最低成本检查，记录候选、解释器、平台、命令和实际退出码。既有测试索引见 `tests/harness/README.md`，冻结夹具在 `tests/fixtures/`；产物放本轮 `.artifacts/`，不新建历史控制面目录。

Portable 验证需分开证明：包清单与引用闭合；独立模块可用；临时 home 生命周期与用户字节保全；冲突/漂移/链接/锁/中断恢复；Windows、Linux、WSL 的真实运行；新 Codex 会话加载；显式 GTO 的真实身份与审查验收；干净接收者仅凭包和说明完成两次 CLI 主流程。

真实云端、GUI、无历史代理和新会话没有取得时分别标记未验收，不能以 mock、合成代理 ID、单元测试、Linux 本地执行或磁盘文件替代。方法技能自己的静态引用检查只能证明独立检索，不能证明行为选择正确。

普通任务的评估不要求 GTO 工件。benchmark 方法从自身 `references/` 取得独立指导；选用 GTO 时再遵循同候选 GTO 黑盒和控制面合同。命令意外失败按适用 CFM 闭环，预先声明且类型相符的最小 TDD Red 保留其例外。
