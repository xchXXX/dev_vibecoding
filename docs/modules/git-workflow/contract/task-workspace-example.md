# 普通任务最小示例

先读 [实施状态与字段](task-workspace.md)，确认使用包含该入口的生成包或安装版本。示例没有固定业务名、机器路径或代理代号；`$coordinator` 使用平台返回的实际会话身份。

以下创建任务分支和 begin 操作均以具体方案已获批准为前提；初始“请修好”不等于批准后来提出的方案，报告后须等待明确回复。在已有配置、已核实空闲的项目中，从已核实的主分支创建项目允许的短期任务分支；这一步由主协调器执行，不由任务工具偷偷切换。

```bash
python3 "$tool_dir/task_workspace.py" --repo-root "$project_root" --action inspect --json
# 方案已有用户批准；当前已在符合项目策略的任务分支
python3 "$tool_dir/task_workspace.py" --repo-root "$project_root" --action begin \
  --coordinator "$coordinator" --task-id sample-change --title "示例改进" --point P1 --point P2 --json
```

编辑生成的 `docs/tasks/sample-change/task.md`，写入真实目标、边界、步骤和 P1/P2 判定条件。已有 dirty 任务必须先确认归属，使用 adopt 和明确 basis，不能把 begin 的干净要求理解为“有改动就开新目录”。再次执行：

```bash
python3 "$tool_dir/task_workspace.py" --repo-root "$project_root" --action resume \
  --task-id sample-change --coordinator "$coordinator" --json
```

resume 返回实际目录，check 再验证当前目标目录/分支。只读子代理直接读取任务入口；写入子代理继承原任务及分配范围，不调用 begin，不自行提交或切换分支。

阶段材料保存在 `.artifacts/sample-change/`，示例（必须用真实原始输出替换）：

```json
{
  "actor": "<actual-platform-identity>",
  "outcome": "pass",
  "summary": "已核实的事实及本次检查范围",
  "evidence": [".artifacts/sample-change/raw-output.log"]
}
```

按 investigation、plan、documentation、tests、implementation、review、acceptance 顺序登记；调查和方案引用原始诊断与用户批准，tests 的 `red_observed: true` 必须有真实预期失败，纯文档可使用 `not_applicable` 说明。每次均使用相同命令，只换 stage 和证据文件：

```bash
python3 "$tool_dir/task_workspace.py" --repo-root "$project_root" --action record-stage \
  --task-id sample-change --coordinator "$coordinator" --stage investigation \
  --evidence .artifacts/sample-change/investigation.json --json
```

review 和 acceptance 要有 `dispatch_evidence` 指向实际平台派发事件，actor 分别为独立 reviewer 与原测试/验收者，不使用此示例的占位身份。验收材料还需：

```json
{
  "actor": "<actual-tester-identity>",
  "outcome": "pass",
  "summary": "P1 采用此前未受影响结果；P2 仅复验修复范围",
  "evidence": [".artifacts/sample-change/first.log", ".artifacts/sample-change/retest.log"],
  "dispatch_evidence": ".artifacts/sample-change/platform-events.jsonl",
  "checks": [
    {"id": "P1", "status": "pass", "evidence": [".artifacts/sample-change/first.log"]},
    {"id": "P2", "status": "pass", "evidence": [".artifacts/sample-change/retest.log"]}
  ],
  "open_issues": []
}
```

首次 P1 通过/P2 失败时，先登记真实失败及完整输入输出；修复 P2 后新建材料引用 P1 历史证据、P2 新证据，不覆盖首次文件。若修复涉及 P1 依赖则 P1 也需复验。登记失败仅整理已有证据，登记命令不启动业务。

```bash
python3 "$tool_dir/task_workspace.py" --repo-root "$project_root" --action complete \
  --task-id sample-change --coordinator "$coordinator" --json
```

完成不自动提交、合并或删除。跨窗口交接使用 handoff，原协调者先确认其子代理/进程停止写入，再提供 next-coordinator、writes-stopped 与 basis；新窗口 resume 同任务。GTO 使用 register-gto 定位后仍调用原冻结控制器恢复，不能用此示例创建一份普通替身。

独立使用：由 `sync_git_workflow.py --project-root "$project_root"` 生成两个并列脚本，在独立临时目录中的新消费项目运行。运行入口不依赖原 harness clone；规则与操作说明一并分发或由项目明确引用。无需浏览器、模型能力或固定代理名。已绑定的活动任务不通过复制目录自动迁移，须保留原位置并核实接续。
