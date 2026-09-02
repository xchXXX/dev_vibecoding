# tests/harness

harness 的正式回归入口统一为 WSL Python unittest：

```bash
python3 -m unittest discover -s tests/harness -p 'test_*.py'
```

## 聚焦套件

- `test_wsl_runtime.py`：bootstrap、sync、doctor、session 与 Codex runtime 黑盒行为。
- `test_control_plane.py`：GTO 六工件、workspace、派发、review/rework/final 门禁。
- `test_command_failure_memory.py`：CFM CLI、锁、原子写、容量与 active/archive 行为。
- `test_rules_runtime.py`：规则索引、自由选读边界、缺失工具分层规则及规则/文档校验 CLI。
- `test_wsl_tools.py`：Ubuntu WSL 工具基线与 doctor 审计输出。
- `test_pure_codex_cleanup.py`：仓库 Claude/Windows 入口清零和用户 runtime 最终清理门禁。

测试只对当前活跃入口和明确机器合同做断言；历史任务、运行留痕与普通迁移正文
不作为关键词扫描对象。测试产生的临时目录统一使用 `TemporaryDirectory` 或等价
teardown 清理。
