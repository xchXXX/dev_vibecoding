---
name: global-task-orchestrator
description: 仅在用户显式要求 GTO 或继续已批准的 GTO 任务时使用；维护单任务合同、派发、审查、返工和验收，不因普通任务需要方案而启用。
---

# Global Task Orchestrator

仅在用户显式选择 GTO 或继续已批准任务时启用；消费项目自身权限与约束仍适用。本包独立运行，不要求全局 AGENTS、ai-harness 或其他 skill。GTO 自身改造任务如用户选择普通实施，不用被修改的旧 GTO 编排自己。

安装与依赖见 [使用说明](README.md)。使用实际环境的 Python 3.10+ 运行 `scripts/doctor.py --json`；脚本自检不证明宿主工具可用。治理与命令失败边界见 [包内治理](references/governance.md)。

## 先定位任务

- 新任务：读取 [方案编制与交接](references/plan-guide.md)，按完整要求和实际分工形成可读 Plan。批准后至六工件创建、校验及首次 preflight 通过前，只写消费项目 `.tmp/` 中的一次性合同 JSON，不做交付写入。
- 在途任务：读取原 `docs/ai/tasks/<task_id>/task.md`，恢复同一 `state.json`，不得复制状态到另一工作区并同时推进。当前工具只接受当前合同；历史状态不自动升级、不走兼容分支。
- 从本 SKILL 所在包定位 controller、schema、references；消费项目用 `--repo-root`。冻结后的运行入口取任务记录中的 runtime snapshot，不受共享安装随后更新影响。
- 恢复与结果登记精简的目标入口见 [简化合同](references/streamlined-execution.md)。新版本先读取恢复摘要，只展开当前步骤需要的正文；工具只定位公开固定位置，不递归扫描 CODEX_HOME。

## 按阶段读取

| 当前工作 | 必读入口 |
|---|---|
| Plan、呈现、批准与交接 | [方案编制与交接](references/plan-guide.md) |
| Execute、职责、依赖、返工与恢复 | [任务流程与职责](references/workflow.md) |
| 初始化、阶段、派发、结果、CLI | [控制器指南](references/controller-guide.md) 的对应小节 |
| 字段、身份、证据批次、覆盖 | [状态合同](references/state-schema.md) |
| 能力准备、版本冻结、证据留存、并发 | [运行与证据](references/runtime-evidence.md) |
| 黑盒选层、场景、预算、停止 | [黑盒方法](references/blackbox-methodology.md) |
| 面向用户的 Plan 展示实例 | [阅读样例](references/plan-reading-examples.md) |

## 不可省略的边界

- `state.json` 是任务状态唯一真源，其他五工件由同一合同生成或引用。一个任务一个工作区写入者；不能以新 task_id、复制 state 或换代理清零历史。
- 派发前核对批准的 assignment、依赖和能力证明。能力缺失只阻塞依赖它的子任务；preflight 只读消费证据，不执行探针。
- 新子代理必须真实 `spawn_agent(fork_turns="none")`，绑定真实返回身份；声明 isolated 不证明实际隔离。原 reviewer 复审、原 acceptor 复验。
- 候选、控制器、schema、skill 一起冻结；结果接收检查版本和证据绑定。原始证据直接写 `.artifacts`，失败和中断同样保留，不覆盖为通过。
- Review 与验收分别使用适用的真实 CLI/API/官方 Browser；工具名称、配置开启或 schema 通过不能替代行为证据。
- 黑盒按目标选择最低充分层级，L6 必须具体单轮批准。环境问题不触发自动平台切换或通用安装。
- 面向用户先说明变化、原因、验证和剩余限制，不把内部字段/命令当作方案正文。

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](references/acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](references/streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。
