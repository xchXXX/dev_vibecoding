# tests

本目录存放 ai-harness 的 WSL Python 回归测试与冻结 fixtures。

## 统一回归入口

```bash
python3 -m unittest discover -s tests/harness -p 'test_*.py'
```

当前正式验收链不调用 PowerShell、batch 或 hook。聚焦套件及职责见
`tests/harness/README.md`。

## 目录边界

- `tests/harness/`：Python unittest 行为与机械合同测试。
- `tests/fixtures/`：冻结输入夹具，不保存运行生成物。
- `tests/benchmarks/`：可选 benchmark 落点；真实 blind behavior 由独立 fresh task
  驱动，不保留 Windows launcher。

所有测试临时目录必须由创建它的测试在成功和失败路径中清理。
