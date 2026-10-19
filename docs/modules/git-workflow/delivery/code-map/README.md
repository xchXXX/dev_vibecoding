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
