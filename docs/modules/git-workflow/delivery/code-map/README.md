# 代码映射

| 职责 | 唯一入口 |
| --- | --- |
| 工作流规范 | `rules/items/workflow/分支与发布管理.md` |
| 配置和 CLI 契约 | `docs/modules/git-workflow/contract/README.md` |
| Git 事实检查 | `scripts/check_git_workflow.py` |
| 项目离线副本生成 | `scripts/sync_git_workflow.py` |
| 本机定向发布 | `scripts/bootstrap-local.py --git-workflow-only` → `scripts/publish_git_workflow.py` |
| 真实 Git 回归 | `tests/harness/test_git_workflow.py` |
| 安装隔离与漂移保护 | `tests/harness/test_git_workflow_publication.py` |

任务绑定、只读决策、普通阶段证据入口：scripts/task_workspace.py；公开合同见 ../../contract/task-workspace.md。生成和定向发布分别复用 sync_git_workflow.py、publish_git_workflow.py。实现前本映射表示批准目标，实况见任务记录。

显式失效绑定释放同样由 `scripts/task_workspace.py --action recover-release` 实现，回归覆盖位于 `tests/harness/test_task_workspace_recovery.py`；不修改冻结 GTO 控制器。
