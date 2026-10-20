# EVALS

本文件说明 ai-harness 自身的当前评估与回归入口。

## 统一入口

```bash
python3 -m unittest discover -s tests/harness -p 'test_*.py'
```

- 套件索引：`tests/harness/README.md`
- 冻结夹具：`tests/fixtures/`
- 规则、文档路由、GTO、CFM、bootstrap、sync、doctor 与工具基线均由 WSL
  Python 测试或对应 `.py` CLI 验收。
- 正式成功路径与验收链不调用 hook、PowerShell 或 batch 入口。

真实自动触发率、独立 reviewer 与 fresh-task blind behavior 属于附加验收层，不能用
单元测试或进程退出码替代；其留痕统一进入 `docs/ai/runs/`。
