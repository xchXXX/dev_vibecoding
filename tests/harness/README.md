# tests/harness

harness 的正式回归入口统一为 WSL Python unittest：

```bash
python3 -m unittest discover -s tests/harness -p 'test_*.py'
```

## 环境定向验证

Windows 宿主通过指定 WSL 发行版执行下列 Linux 测试；环境迁移不运行包含 GTO 的全量 discovery。

```bash
python3 -m unittest discover -s tests/harness -p test_windows_native_environment.py
python3 -m unittest discover -s tests/harness -p test_windows_native_transition.py
python3 -m unittest discover -s tests/harness -p test_command_failure_memory.py
```

- `test_windows_native_environment.py`：原生声明、明确home、限定发布、恢复与配置保护。
- `test_windows_native_transition.py`：维护hold在写入前停止，文件/目录树保全。
- `test_wsl_environment.py`：Linux项目与工具治理；其中部分整机路径依赖GTO，迁移时按具体方法选择，不直接运行整套。
- `test_docker_desktop_safe_start.py`：单独授权的Windows Docker安全启动器；不等于容器或GUI验收。
- `test_wsl_runtime.py`：整机/strict路径含GTO，环境变更只验证相关非GTO分支；健康夹具需明确三插件配置。

## 聚焦套件

- `test_wsl_runtime.py`：bootstrap、sync、doctor、session 与 Codex runtime 黑盒行为。
- `test_control_plane.py`：GTO 六工件、workspace、派发、review/rework/final 门禁。
- `test_command_failure_memory.py`：CFM CLI、锁、原子写、容量与 active/archive 行为。
- `test_rules_runtime.py`：规则索引、自由选读边界、缺失工具分层规则及规则/文档校验 CLI。
- `test_wsl_tools.py`：Ubuntu WSL 工具基线与 doctor 审计输出。
- `test_pure_codex_cleanup.py`：已退役代理/具体旧GUI桥入口的否定约束，允许合法Windows宿主操作。

测试只对当前活跃入口和明确机器合同做断言；历史任务、运行留痕与普通迁移正文
不作为关键词扫描对象。测试产生的临时目录统一使用 `TemporaryDirectory` 或等价
teardown 清理。

## GTO revision 3 范围验证

`PYTHONPATH=tests/harness python3 -m unittest test_gto_workflow -v` 通过真实 CLI 覆盖正常闭环、结构化检查、独立身份、正式文档漂移、review批量问题、复审新增 finding、验收身份发现和新候选重验。旧 revision 2 保护在 test_control_plane.py。实际代理黑盒使用 tests/fixtures/gto-workflow 与 tests/benchmarks 下的冻结入口；层级、场景卡、结果、停止点、夹具和批准协议唯一见 [分层黑盒测试方法论](../../skills/global-task-orchestrator/references/blackbox-methodology.md)。机械证据与真实代理效果分别判定，静态或模拟不扩大为实际行为结论。运行证据放 .artifacts/gto-workflow，临时文件放 .tmp/gto-workflow，且仅清理本轮自有产物。

本轮 revision 3 行为合同测试应由独立测试子代理依据需求设计，按独立文件并行，共享 fixture 单一写入者；整合子代理不得提前介入影响测试。重点覆盖独立身份、全部实现 TDD 后唯一整合、发现者完整问题合同、原整合者修复且不放宽测试、首审批量与范围复审、首验全量与同验收者范围复验/delta 检查、历史证据保留、实际工具使用证据和单文档子代理纯文字纠正直接收口。新增用例是否已通过须以执行记录为准，不能沿用前述既有覆盖说明。源码 review 后统一投放，再由主协调器依照分层方法论选择最低成本可信场景；不把新顶层完整任务当成默认验收入口。
# Plan 分工与结果预检回归

`test_gto_execution_plan.py` 覆盖批准分工、真实身份映射、计划内测试/验收复用、依赖与批准失效、生成展示、结果预检无副作用及正式提交重新检查。与 `test_gto_workflow.py`、`test_gto_initial_test_routing.py`、`test_gto_plan_preflight_contract.py` 组合运行，确保返工和旧合同不回归。
