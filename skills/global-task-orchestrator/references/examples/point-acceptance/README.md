# 十点首验、两点复验

状态：示例已通过独立分发验收；隔离目录实测 12 次检查、2 次程序启动、保留 8 点历史通过，无第三轮。

在已安装 Python 及包根 `requirements.txt` 依赖的环境中，从任意当前目录运行：

```sh
python /path/to/global-task-orchestrator/references/examples/point-acceptance/demo.py --project-dir /path/to/new-disposable-project
```

目标目录必须不存在。示例创建自己的 Git 仓库、任务状态和证据，不读取现有业务项目，也不使用 harness 工作区路径。

`config.json` 是可复制的示例配置：`contract.acceptance_gate.acceptance_items` 声明点和关联路径，`entry` 声明检查入口，`inputs` 将点映射到夹具。换用自己的入口时，输出每点 JSON（`acceptance_id/status/input/actual/expected`）到指定输出目录。正式项目沿用现有合同配置；普通任务只需本文上级范围复验原则中的简洁清单，不必复制示例控制面。

第一次真实启动检查程序执行 10 点，保留 9 个通过和 1 个失败；修复共享输入后控制器自动安排 CHECK-09、CHECK-10，第二次只执行这 2 点。最终检查保留的 8 点和新通过的 2 点，直接完成。`.artifacts/executions.jsonl`、`commands.jsonl`、每次运行的 manifest 和 `demo-summary.json` 保留全过程，可核对 12 次检查、2 次程序启动、无第三轮。

演示中的实现者、reviewer 和验收者身份及治理回执都是明确标记的合成夹具，不代表真实独立人员审查；业务检查、原始输出、运行次数及控制器决策是真实执行。这一演示只将 GTO 作为被测程序，不用于编排 harness 改造。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](../../streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。
