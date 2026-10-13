# tests

本目录存放 ai-harness 的 WSL Python 回归测试与冻结 fixtures。

## 统一回归入口

```bash
python3 -m unittest discover -s tests/harness -p 'test_*.py'
```

Windows 原生宿主可用 PowerShell 调用指定 WSL 发行版；项目测试/构建继续使用 Linux 入口和依赖，官方 GUI 验收使用 Windows 原生工具。聚焦套件及职责见
`tests/harness/README.md`。

## 目录边界

- `tests/harness/`：Python unittest 行为与机械合同测试。
- `tests/fixtures/`：冻结输入夹具，不保存运行生成物。
- `tests/benchmarks/`：分层黑盒 runner 与可选 benchmark 落点；选层、场景卡、结果、夹具和批准协议以 [分层黑盒测试方法论](../skills/global-task-orchestrator/references/blackbox-methodology.md) 为唯一正文。runner 只做确定性采集与门禁，主协调器负责语义选择和判断。

所有测试临时目录必须由创建它的测试在成功和失败路径中清理。
