# tests/harness

harness happy path / bad path 回归测试落点。

规则口径说明：

- 全局治理合同仍以 `docs/SUBAGENT_GOVERNANCE.md` 为真源。
- 当前仓库的项目规则入口已切到 `rules/registry/*` 与 `rules/items/<kind>/*`。
- 历史测试说明若出现 `rules/common/SUBAGENT_RULES.md`，应按旧口径兼容背景理解，不再视为项目规则唯一入口。

## 目录级统一入口

- 当前冻结执行方式：
  - `Get-ChildItem -LiteralPath .\tests\harness -Filter *.ps1 | Sort-Object Name | ForEach-Object { pwsh -NoProfile -ExecutionPolicy Bypass -File $_.FullName }`
- 目录入口按文件名顺序执行 `tests/harness/*.ps1`，因此 `tests/harness/command-failure-case.schema.ps1` 已纳入统一回归集

## Windows 命令约束合同套件

- 脚本：`tests/harness/windows-command-guardrails.contract.ps1`
- 直接对象：
  - `C:\Users\72385\.codex\AGENTS.md`
  - `rules/items/policy/Windows命令构造约束.md`
  - `rules/items/policy/PowerShell7脚本基线.md`
  - `docs/CODEX_COMPAT.md`
- 覆盖：
  - global preference：全局长期偏好层必须声明中文说明、答问优先、quiet long-run 与 Windows 命令偏好
  - rule：项目规则必须明确复杂 one-liner 禁止项、复杂参数不走 `.cmd`、`NUL` / `ghost snapshot` 单独视为平台噪音
  - baseline：项目兼容文档必须明确 `pwsh7` 基线，不再把 5.1 作为默认主路径

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
  - happy path：固定白名单四 skill（`global-task-orchestrator` + `command-failure-memory` + `pre-dev-benchmark` + `fix-closure-gate`）的 install / sync / doctor 闭环
  - source mapping：固定白名单中的 `skills/pre-dev-benchmark` 与 `skills/fix-closure-gate` 可同步到 `~/.codex/skills/*`
  - guard：仅托管冻结 skill，不接管 `.system/*`、plugins 与 unmanaged sibling skills
  - receipt：trusted/untrusted receipt 差异、stale managed file 清理与 drift 检测
  - safety：runtime root 越界、malformed receipt、空 `managed_files` 必须失败
  - robustness：并发 sync、幂等 sync、源文件漂移传播

## control-plane 集成套件

- 脚本：`tests/harness/control-plane.integration.ps1`
- 黑盒入口：
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action new-task -Topic <topic> -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action init-task -TaskId <task_id> -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action sync-task-md -TaskId <task_id> -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action append-event -TaskId <task_id> -EventJson <json> -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action build-subtask-brief -TaskId <task_id> -SubtaskId <subtask_id> -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action build-execute-handoff -TaskId <task_id> -Json`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1 -Action validate -TaskId <task_id> -Json`
- 覆盖：
  - happy path：`new-task` 在同 topic 连续调用时生成不同 `task_id`
  - happy path：`init-task` 创建 `docs/ai/tasks/<task_id>/state.json`
  - happy path：`init-task` 创建 `docs/ai/tasks/<task_id>/task.md`
  - happy path：`init-task` 创建 `docs/ai/tasks/<task_id>/events.jsonl`
  - happy path：`validate` 在新 task fixture 上通过
  - happy path：`sync-task-md` 根据 `state.json` 重写摘要，并生成 `## 目标 / ## 关键决定 / ## 当前阶段 / ## 子任务` 等核心 section
  - happy path：`append-event` 追加合法事件后 `validate` 仍通过
  - happy path：`build-subtask-brief` 输出子任务简报
  - happy path：`build-execute-handoff` 输出 `Execute Window` 首条交接内容，至少包含 `task_id / current_phase / objective / scope_in / scope_out / acceptance / stop_conditions / task.md / 首批子任务摘要 / 先委派子代理`
  - identity：一个正式长任务只对应一个 `task_id`；`Plan Window` 与 `Execute Window` 共享它
  - bad path：`validate` 缺 `TaskId`
  - bad path：对已存在目录再次 `init-task` 必须失败，阻断误复用与误覆盖
  - bad path：`state.json` 缺必填字段（例如 `current_phase`）
  - bad path：重复 `subtask_id`
  - bad path：`pending / in_progress` 子任务缺 `read_paths` 或 `write_paths`
  - bad path：`blocked` 子任务缺 `result`
  - bad path：`completed` 子任务缺关键 `result` 字段（例如 `result.summary / result.written_role / result.verification`）
  - bad path：`completed` 子任务 `changed_files` 越出 `subtask.write_paths`
  - bad path：`result.written_role` 与 `subtask.role` 不一致
  - bad path：`manifest.json` 或 `agents/codex-role-map.json` 多出未对齐角色
  - bad path：schema 规定为 array 的根字段若被写成单个 string，例如 `scope_in` 或 `acceptance`
  - bad path：schema 规定为 array 的子任务字段若被写成单个 string，例如 `read_paths / write_paths / assignment.must_include`
  - bad path：schema 规定为 array 的结果字段若被写成单个 string，例如 `result.verification.commands` 或 `blocked_by`
  - bad path：`events.jsonl` 含非法 JSON 行
  - 不再覆盖旧控制面对象：`plan.json / work_orders / dispatch_packets / return_packets / .ai/session`

## global-task-orchestrator 文档合同套件

- 脚本：`tests/harness/global-task-orchestrator.skill-doc.ps1`
- 直接对象：
  - `skills/global-task-orchestrator/SKILL.md`
  - `skills/global-task-orchestrator/references/governance-essentials.md`
  - `skills/global-task-orchestrator/agents/openai.yaml`
  - `skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1`
- 覆盖：
  - `task_id` 身份语义
  - `Plan Window / Execute Window` 路由
  - `build-execute-handoff` 必填口径
  - `current_phase` 推荐枚举：`planning / doc_sync / test_sync / code_impl / review / blocked`
  - `openai.yaml` 默认提示不得回退为过薄摘要

## fix-closure-gate 文档合同套件

- 脚本：`tests/harness/fix-closure-gate.skill-doc.ps1`
- 直接对象：
  - `skills/fix-closure-gate/SKILL.md`
  - `skills/fix-closure-gate/agents/openai.yaml`
- 覆盖：
  - frontmatter：`description` 必须明确触发场景、跳过条件与最小字段合同
  - body：必须区分职责 / 非职责、触发条件 / 跳过条件、`diagnostic_checks` / `acceptance_checks`
  - metadata：`agents/openai.yaml` 必须与 `SKILL.md` 的触发意图和字段口径保持一致

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
