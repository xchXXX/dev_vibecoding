# tests/harness

harness happy path / bad path 回归测试落点。

## 目录级统一入口

- 当前冻结执行方式：
  - `Get-ChildItem -LiteralPath .\tests\harness -Filter *.ps1 | Sort-Object Name | ForEach-Object { powershell -NoProfile -ExecutionPolicy Bypass -File $_.FullName }`
- 目录入口按文件名顺序执行 `tests/harness/*.ps1`，因此 `tests/harness/command-failure-case.schema.ps1` 已纳入统一回归集

## claude hooks phase5 HookCommon 套件

- 脚本：`tests/harness/claude-hooks-phase5.hook-behavior.ps1`
- 直接对象：
  - `hooks/claude/scripts/HookCommon.ps1`
- 覆盖：
  - Hook payload 的 `session_id` / `tool_name` 多字段变体兼容解析
  - canonical payload 归一化后必须暴露顶层 `session_id` 与 `tool_name`

## claude hooks phase5 集成套件

- 脚本：`tests/harness/claude-hooks-phase5.integration.ps1`
- 黑盒入口：
  - `scripts/sync-claude-hooks.ps1`
  - `scripts/install-claude-hooks.ps1`
  - `scripts/doctor-core.ps1`
- 覆盖：
  - happy path：hooks install / sync / doctor 在 phase5 冻结结构下通过
  - guard：manifest target / event / runtime command 的冻结边界校验
  - guard：reparse point / dotdot / junction escape 必须被阻断
  - receipt：staged commit 回滚、trusted/untrusted receipt 差异与 stale managed file 清理
  - runtime：PreToolUse guard marker、白名单工具、stdin payload 合法性
  - drift：HookCommon 与 runtime script 漂移检测

## codex sync 集成套件

- 脚本：`tests/harness/codex-sync.integration.ps1`
- 黑盒入口：
  - `scripts/sync-codex.ps1`
  - `scripts/doctor-core.ps1`
- 覆盖：
  - happy path：固定白名单三 skill（`global-task-orchestrator` + `command-failure-memory` + `pre-dev-benchmark`）的 install / sync / doctor 闭环
  - source mapping：固定白名单中的 `skills/pre-dev-benchmark` 可同步到 `~/.codex/skills/pre-dev-benchmark`
  - guard：仅托管冻结 skill，不接管 `.system/*`、plugins 与 unmanaged sibling skills
  - receipt：trusted/untrusted receipt 差异、stale managed file 清理与 drift 检测
  - safety：runtime root 越界、malformed receipt、空 `managed_files` 必须失败
  - robustness：并发 sync、幂等 sync、源文件漂移传播

## control-plane 集成套件

- 脚本：`tests/harness/control-plane.integration.ps1`
- 黑盒入口：
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate -TaskId <task_id> -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action bootstrap -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action hydrate -Json`
  - `skills/global-task-orchestrator/scripts/compile-dispatch-message.ps1 -Path <work_order-or-dir> -Json`
- 覆盖：
  - happy path：当前冻结 run 模板通过 `validate`
  - happy path：`hydrate` 重编译 stale `dispatch_message_raw`，并回填 `expected_written_role / expected_written_by_patterns / dispatch_packet_required`
  - bad path：`validate` 缺 `TaskId`
  - bad path：`plan.json.status != frozen`
  - bad path：`bootstrap` 绑定 `draft` source plan 或 existing run draft plan
  - bad path：`codex-role-map` 非法 `agent_type` 或缺少必需角色
  - bad path：缺 `work_orders` 目录或没有任何 `work_order JSON`
  - bad path：缺 `read_paths_mandatory`
  - bad path：弱化 `required_return_fields` 后仍缺仓库最低回执字段
  - bad path：`dispatch_message_raw` 与合同编译结果不一致
  - bad path：复杂任务缺 `dispatch_packet`
  - bad path：缺必需 `return_packet`
  - bad path：缺 `work_order_id` 时仍不能绕过缺失 `return_packet`
  - bad path：`return_packet_path` 指向他人工单回执
  - bad path：`return_packet_required=false` 不能绕过缺失回执
  - bad path：`return_packet` 作者角色/作者身份与 `work_order` 的 `expected_written_role / expected_written_by / expected_written_by_patterns` 合同不一致
  - bad path：`expected_written_by_patterns` 非法，或被弱化为不受限的通配/正则转义模式
  - bad path：`dispatch_packet_path` 越出当前 task run 或穿过 reparse point
  - bad path：伪造 `task_id + dispatch_packet_path` 不能绕过当前 run 边界
  - bad path：显式 `dispatch_packet_required=true` 强制进入复杂任务闸门
  - bad path：`hydrate` 在目标路径不存在、目标 task 缺 `work_orders`、JSON 不可解析、编译失败、`dispatch_packet_path` 越界、或施工图字段缺失时必须非零退出
  - bad path：`compile-dispatch-message.ps1` 在空目标目录上必须非零退出

## codex failure-memory 集成套件

- 脚本：`tests/harness/codex-failure-memory.integration.ps1`
- 黑盒入口：
  - `skills/command-failure-memory/scripts/command-failure-memory.cmd`
  - `skills/command-failure-memory/scripts/command-failure-memory.py`
  - `skills/command-failure-memory/scripts/command-failure-memory.ps1`
- 覆盖：
  - gate：未记录失败前执行 `query-before-retry` 必须拒绝查询
  - rule：`record-failure` 后再 `query-before-retry` 可召回历史解法
  - rule：`record-success` 命中等价解法时不得新增 case，只更新统计
  - rule：新增 case 必须提供 `scope_kind`
  - rule：`candidate_project -> global` 收敛
  - rule：`candidate_global -> project` 收敛（项目特异证据）
  - bad path：篡改索引为非法 `case_id` 时必须拒绝，阻断越界写入
  - bad path：case 存储路径穿过 junction 逃逸 memory root 时必须拒绝
  - validation：`scope_confidence` 必须保持在 schema 允许范围内
  - redaction：敏感信息落盘前必须脱敏
  - capacity：pending failure event 数量必须受控
  - concurrency：并发 `record-failure` 更新不得丢失增量
  - normalization：缺失 `schema_version` 的旧 case 会在重写前归一化
  - signature：多行错误按首行稳定去重
  - compat：受限 PowerShell 会话优先经 `.cmd -> .py` 兼容入口，保留 `.ps1` 回退
  - compat：省略 `-CodexHome` 时优先跟随 `CODEX_HOME`，未设置时再回退到 `~/.codex`

## command-failure-memory skill 文档套件

- 脚本：`tests/harness/command-failure-memory.skill-doc.ps1`
- 直接对象：
  - `skills/command-failure-memory/SKILL.md`
  - `skills/command-failure-memory/agents/openai.yaml`
- 覆盖：
  - frontmatter：`description` 必须明确说明何时触发，并基于执行信号与重试语义而不是过拟合错误枚举
  - frontmatter：必须明确“即使用户没有显式提到 skill，命令失败后也要自动使用”
  - body：必须包含兼容 launcher、`CODEX_HOME` 默认解析、backend 说明、标准闭环与四个动作的使用示例
  - metadata：`agents/openai.yaml` 必须与 `SKILL.md` 的触发意图保持一致
  - 验收补充：真实自动触发率仍以 blind forward-test 为准，文档合同测试只负责防止触发描述回退
  - 验收补充：`codex exec` Windows CLI 链路与新的子代理窗口 blind benchmark 要分开看；当前真实自动触发率以子代理 blind benchmark 为准

## command-failure-case schema 套件

- 脚本：`tests/harness/command-failure-case.schema.ps1`
- 直接对象：`schemas/command-failure-case.schema.json`
- 覆盖：
  - schema root / `required` / `scope_confidence` 边界合同
  - canonical valid case 必须通过 schema
  - bad path：缺失 `schema_version`
  - bad path：非法 `case_id` / `signature`
  - bad path：非法 `scope_kind`
  - bad path：`scope_confidence` 越界
  - bad path：空 `projects_seen`
  - bad path：负数统计或缺失必填 stats 字段
