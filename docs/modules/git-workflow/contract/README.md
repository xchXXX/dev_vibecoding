# Git 工作流契约

规范正文唯一见 `rules/items/workflow/分支与发布管理.md`。本页定义配置和检查器接口，不复制工作流。

任务归属、普通核心工件、接续和独立审查流程唯一见 [任务与工作区合同](task-workspace.md)，该页明确实施状态。新前缀允许 `codex/feat-`、`codex/fix-`、`codex/ops-`，不限定末尾 `/`；具体值仍由项目配置决定。旧任务只有经过真实绑定核验才能继续其原分支，不自动重命名，不豁免未来新任务。

接入条件见 [项目接入检查点](../../../PROJECT_TEMPLATE.md#项目接入检查点)。检查器继续对缺失/损坏配置返回 CONFIG_INVALID，不新增跳过检查或伪造通过的分支。

项目 `config/ai/git-policy.json` 必填 `schema_version: 1`、`remote`、`main_branch`、`task_prefixes`、`reserved_branches`（分支到负责人）、`release_tag_pattern`（完整匹配）、`merge_method: merge`、`cleanup_mode: report-only`。不支持自动删除或 squash；若以后支持 squash，须有可信合并记录，不能仅以祖先关系判断。保留分支不授予当前任务使用权。

`scripts/check_git_workflow.py --repo-root PATH --phase start|push|merge|release|cleanup|ci [--branch NAME] [--release-tag TAG] --json` 是只读检查入口，不 fetch、不修改 refs、不读取凭据、不提交、不删除。

可选 `production_branch` 声明独立的部署输入分支，不能与 main 或保留分支重复。未配置的项目维持原有标签发布模式。配置后 start 提示另建任务分支，ci 允许验证 production，普通 push/merge 返回 `PRODUCTION_REQUIRES_APPROVED_RELEASE`，cleanup 永久保护。精确批准、main 归属、实时 production 与产物一致性的发布门禁由项目正式部署入口检查；此只读检查器不接受“跳过审批”参数。release 阶段仍验证不可移动的归档标签，不负责触发服务器。

- start：允许配置主分支作起点但报告需任务分支；对任务分支检查命名，报告脏文件，不自动接管。保留分支报告负责人。主分支不是写入许可。
- push：要求非主分支的合规分支；报告 HEAD、上游和相对已缓存引用的关系。没有上游不等于已推送。
- merge：要求目标远端主分支存在、完整历史、命名正确、工作区干净，报告祖先关系；不声称 review 或验收通过。
- ci：允许主分支或规范分支；仅此阶段支持 --branch（用于 detached PR checkout）。不以工作区干净判定测试是否通过。
- release：标签指向 HEAD 且命名正确；向配置远端查询标签及主分支、确认本地追踪主分支与远端一致、HEAD 在该主分支历史中、标签远端对象一致。网络失败不能降级为已推送。
- cleanup：逐分支报告保护、占用、本地和远端同名分支是否都已合入缓存的远端主分支、是否有尚未在远端同名分支存在的本地提交。远端新增未合入提交返回 `REMOTE_NOT_MERGED`。即使 Git 条件满足，也只有 `git_candidate=true`、`delete_authorized=false`；必须另核实任务引用、验收与用户授权。远端引用新鲜度无法离线保证，任何删除前必须重新 fetch 并重新检查。未确认一律保留。

输出包括 `ok`、`phase`、`branch`、`head`、`errors`、`warnings` 和对应检查事实。规则失败 exit 1，配置/Git失败 exit 2。不把脚本通过等同于完成验收或获得授权。

项目离线副本由 `scripts/sync_git_workflow.py --project-root PATH` 生成在 `modules/tooling/check_git_workflow.py`，来源 SHA-256 写在文件头；`--check` 比较精确字节，不覆盖手写文件或已漂移生成物。项目配置由项目维护，生成器不覆盖它。

本机发布使用 `bootstrap-local.py --git-workflow-only`，目标范围扩展为受管全局入口、本检查器、任务工作区入口及对应回执（实现状态见新合同）；保护其他 skills、环境、插件配置与回执字段，遵守迁移 hold 和共享发布锁。项目生成副本也包含并列 task_workspace.py。发布后须用新代理运行验证规则加载和实际选择，不能用静态字符串检查替代。
