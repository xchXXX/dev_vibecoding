# 接入与检查的最小示例

项目接入条件唯一见 [项目模板](PROJECT_TEMPLATE.md)，GTO 操作合同见 [恢复与登记](../skills/global-task-orchestrator/references/streamlined-execution.md)。版本/诊断字段适用于包含这些入口的运行包；实际安装以发布回执和新进程核验为准，旧任务继续使用原冻结版本。

以下 Bash 命令在已核实的 WSL 项目环境执行。`harness_root`、`codex_home`、`repo_root` 分别是已选择真源、实际宿主安装目录的 WSL 路径、消费项目；没有默认机器路径。先给变量真实值，任何失败均停止依赖步骤，不整段无条件粘贴执行。

## 项目接入和普通检查

根据项目真实约定填写 `templates/project/config/ai/git-policy.example.json` 对应配置；不把样例的远端、分支、负责人直接当成实际策略。环境声明同样依据项目 manifest/lock，不凭样例安装依赖。配置必须先存在并经维护者确认。

```bash
python3 "$harness_root/scripts/check_git_workflow.py" --repo-root "$repo_root" --phase start --json
```

配置缺失/损坏是配置错误，不能当成功；明确未接入项目按原有约定核对，不因此取得推送/合并/发布许可。普通任务记录验收点、实际入口、结果、证据与关联范围即可，不执行 init-task。

```bash
python3 "$codex_home/.ai-harness/runtime/wsl-environment/bin/project-env-doctor.py" \
  --project-root "$repo_root" --environment "$repo_root/config/ai/environment.json" --json
```

## 已有 GTO 恢复与局部复验

```bash
python3 "$harness_root/skills/global-task-orchestrator/scripts/start_session.py" \
  --repo-root "$repo_root" --task-id "$task_id" --json
```

使用返回的 controller；按当前子任务必要字段补读，真实身份绑定后再执行。观察摘要必须在同一原运行封存，按简化合同 prepare-result、核验证据、正式登记。保留未失效历史通过点，完整覆盖后按原收尾门禁完成。

无已有任务者可运行包内 [10＋2 示例](../skills/global-task-orchestrator/references/examples/point-acceptance/README.md)；这是作为被测对象的隔离 GTO 项目，不是普通任务必须采用的流程。

## 版本查询与定向安装

版本摘要入口（以实际运行包是否包含该能力为准）：

```bash
python3 "$harness_root/skills/global-task-orchestrator/scripts/tool_paths.py" \
  --harness-root "$harness_root" --codex-home "$codex_home" --json
```

先核对安装所有权、维护标志、回执并备份；在已批准发布范围内，仅同步所改技能：

```bash
python3 "$harness_root/scripts/sync-codex.py" --harness-root "$harness_root" \
  --codex-home "$codex_home" --skill global-task-orchestrator --json
```

安装后比较真源、安装、receipt；其他受管组件保持，旧任务冻结目录前后哈希一致，并通过新进程恢复确认实际 controller 仍指向原快照。新进程 CLI 成功不证明既有聊天已重新加载；新会话验收单独记录。全局入口变化另用既有定向 bootstrap 发布，不调用完整安装来掩盖缺口。

普通任务从调查到接续、复验和完成的最小操作见 [任务工作区示例](modules/git-workflow/contract/task-workspace-example.md)；字段与版本边界见同目录合同。
## 已归档任务仍阻塞工作区时

先只读 `scripts/task_workspace.py --repo-root <project> --action inspect --json`。不要手工删除索引或把旧任务改成 completed。已确认用户授权、停止旧写入并保留原始记录后，按[恢复释放合同](modules/git-workflow/contract/task-workspace.md)准备证据，再执行：

```bash
python3 scripts/task_workspace.py --repo-root <project> --action recover-release \
  --task-id <old-task-id> --coordinator <platform-id> --writes-stopped \
  --basis '用户明确授权的释放原因' --evidence .artifacts/<recovery>/release.json --json
```

再次 inspect 应列出 released_tasks 及原状态；只有无其他占用且 Git 干净时才返回 available。释放不是完成，也不授权续写原任务；旧 GTO 控制面保持原样。
