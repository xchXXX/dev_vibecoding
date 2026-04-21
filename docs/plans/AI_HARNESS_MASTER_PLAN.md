# AI Harness 改造总纲

## 目标与范围
本文是 `ai-harness` 改造主线的 phase 状态真源，用于同步：
- 全局真源层 / 运行时投放层 / 项目适配层的边界
- Claude 闭环与 Codex 最小闭环的当前真实状态
- 当前已完成 phase、已冻结待实施批次，以及停止条件

当前范围：
- 全局真源：`C:\Users\72385\dev\ai-harness`
- Claude 运行时：`C:\Users\72385\.claude\*`
- Codex 运行时：`C:\Users\72385\.codex\skills\*`
- 项目适配层：各项目仓库内的 `AGENTS.md`、`docs/ai/`、`config/ai/`、项目专属 `.claude/` / `.codex/`

## 三层模型

### 1. 全局真源层
- 路径：`C:\Users\72385\dev\ai-harness`
- 职责：长期维护通用 rules、templates、skills、agents、hooks、doctor、install/sync 脚本与测试真源

### 2. 运行时投放层
- Claude：
  - `C:\Users\72385\.claude\agents\*`
  - `C:\Users\72385\.claude\settings.json`
  - `C:\Users\72385\.claude\.ai-harness\*`
- Codex：
  - `C:\Users\72385\.codex\skills\*`
  - `C:\Users\72385\.codex\.ai-harness\*`
- 职责：只承载 CLI 识别与执行所需的受管运行时结果

### 3. 项目适配层
- 路径：各项目仓库内的 `AGENTS.md`、`docs/ai/`、`config/ai/`、项目专属运行时配置
- 职责：保留项目边界、项目增量规则、运行留痕与项目模板；不复制全局通用真源

## 当前 phase 状态

### Phase 0：三层模型与边界冻结
- 状态：已完成

### Phase 1：全局骨架落地
- 状态：已完成

### Phase 2：首批真源迁移
- 状态：已完成

### Phase 3：Claude agents 真源目录与首批 catalog
- 状态：已完成

### Phase 4：Claude agents install/sync/runtime
- 状态：已完成

### Phase 5：Claude hooks + governance 真源
- 状态：已完成，并已补正式验收单
- 当前结论：Claude hooks / doctor / rules governance 批次已通过多轮 review 与正式验收

### Phase 6：Codex 最小闭环 + 真实运行时投放
- 状态：已完成，并已补正式验收单
- 当前结论：
  - `sync-codex.ps1`
  - `doctor-core.ps1 -AuditTarget codex_minimal`
  - `tests/harness/codex-sync.integration.ps1`
  - 真实 `~/.codex/skills/global-task-orchestrator` 投放、receipt 与 doctor 结果已闭环

### Phase 7：项目适配与遗留清理
- 状态：已完成，并已补 `Phase 7` 正式验收单
- 方案入口：`C:\Users\72385\dev\ai-harness\docs\PROJECT_ADAPTER_CLEANUP_PLAN.md`
- 资产盘点入口：`C:\Users\72385\dev\ai-harness\docs\PROJECT_ADAPTER_ASSET_MAP.md`
- 入口收口方案入口：`C:\Users\72385\dev\ai-harness\docs\PROJECT_ENTRY_REFERENCE_PLAN.md`
- Claude local settings 方案入口：`C:\Users\72385\dev\ai-harness\docs\PROJECT_CLAUDE_LOCAL_SETTINGS_PLAN.md`
- 历史 run / legacy 引用方案入口：`C:\Users\72385\dev\ai-harness\docs\PROJECT_HISTORY_LEGACY_REFERENCE_PLAN.md`
- legacy Claude agent 方案入口：`C:\Users\72385\dev\ai-harness\docs\PROJECT_LEGACY_CLAUDE_AGENT_PLAN.md`
- 实施排序入口：`C:\Users\72385\dev\ai-harness\docs\PROJECT_ADAPTER_IMPLEMENTATION_SEQUENCE.md`
- 正式验收入口：`C:\projects\pdf_ai\paddle_ocr\docs\ai\runs\ai-harness-phase0-freeze-20260330-150836-m85l\phase7_acceptance.md`
- 当前结论：
  - 方案冻结已完成
  - 子批次 A 的逐对象资产盘点与映射冻结已完成
  - 子批次 B 的项目入口与全局引用收口方案已冻结，且已显式对齐子批次 A 的五类正式分类
  - 子批次 C 的 `.claude/settings.local.json` 本地化治理方案已冻结，并已明确“个人本地配置却被版本控制”的语义冲突与后续最小实施顺序
  - 子批次 D 的历史 run / legacy 引用治理方案已冻结，并已按真实盘点修正 `.ai/session` 既有命中事实，明确历史事实保留边界、现行新增禁项以及 `docs/ai/runs/` / `.ai/session/` 的差异化口径
  - 子批次 E 的项目内 legacy Claude agent 入口治理方案已冻结，并已完成 3 个 legacy 文件的逐文件目标状态判断
  - Phase 7 当前已完成 A/B/C/D/E 全部方案冻结
  - 实施批次 `I-1：项目入口轻量收口` 已完成，已完成对象为 `AGENTS.md` 与 `docs/ai/README.md`
  - 实施批次 `I-2：项目文档标准与注册入口收口` 已完成，已完成对象为 `docs/ai/SUBAGENT_WORKFLOW.md`、`docs/ai/SESSION_PLANNING_STANDARD.md` 与 `docs/ai/MODULE_DOC_STANDARD.md`
  - registry JSON 未改且与当前文档口径兼容
  - 实施批次 `I-3：.claude/settings.local.json 本地化实施` 已完成，已完成对象为 `.gitignore`、`.claude/settings.local.example.json`、`.claude/settings.local.json` 停止跟踪与本地合法 JSON 修复
  - `.claude/settings.local.json` 当前继续保留为工作树本地自管文件，不再由仓库跟踪
  - 实施批次 `I-4：legacy Claude agent 入口治理实施` 已完成，已完成对象为 `.claude/agents/coder_agent.md`、`.claude/agents/deploy_agent.md` 与 `.claude/agents/tester_agent.md` 的 deprecation / wrapper 收口
  - 实施批次 `I-5：legacy 引用新增约束与检测` 已完成，已完成对象为入口文档 machine-local 绝对路径口径收口与 session/work_order 模板中的“禁止新增 legacy 引用”约束
  - 已排序实施批次 `I-1` 至 `I-5` 全部完成
  - Phase 7 正式收口与验收留痕已完成

## 当前已完成闭环

### Claude 侧
- 全局 agents 真源、install/sync、receipt 与真实运行时投放已闭环
- Claude hooks 6 事件真源、install/sync、receipt、doctor 审计与规则治理已闭环

### Codex 侧
- 当前最小受管对象仅 `global-task-orchestrator`
- `sync-codex.ps1` 与 `doctor-core.ps1 -AuditTarget codex_minimal` 已闭环
- 真实 `~/.codex/skills/global-task-orchestrator` 已完成受管投放

## 当前未展开范围
- `.system/*` 托管
- plugins 托管
- 第三方 runtime skill 接管
- 项目接入清理代码实施
- `.claude/settings.local.json` 实际收敛
- Claude settings merge / override
- 更广义 project doctor / cleanup doctor

## 已冻结待实施方案
- `contract-first + 双窗口派发升级`
  - 方案入口：`C:\Users\72385\dev\ai-harness\docs\plans\contract-first-dispatch.md`
  - 当前状态：已冻结方案；`Batch 1-2.5` 已完成，`Batch 3 / 3.5 / 4` 待实施
  - 当前结论：
    - 默认工作模式切换目标已明确为 `Plan Window -> Execute Window`
    - `plan_owner = main_window` 已冻结
    - `plan.md` 为语义真源、`plan.json` 为结构化投影，且 `md -> json` 转化责任固定在 `Plan Window`
    - 后续优化第一优先级已明确为 `contract-first, prompt-compiled`
    - 首批待实施对象已明确为 `work_order / dispatch_packet / dispatch_message_raw / return_packet`
    - `docs/SUBAGENT_GOVERNANCE.md`、`skills/global-task-orchestrator/SKILL.md` 与 `rules/common/SUBAGENT_RULES.md` 已完成 Batch 1 收口
    - `Batch 2` 已完成 `work_order / dispatch_packet / return_packet` schema 与模板升级
    - `Batch 2.5` 已完成 `plan.schema.json`、`plan.example.json` 与 bootstrap/hydrate 脚本的双件制口径收口
    - 后续新增 `Batch 3.5`，用于把真源文档规则继续下沉到派发合同、提示词模板与验收闸门，避免默认假定子代理已自行阅读全部真源文档

## 推荐下一步
主线已完成 `Phase 7` 正式收口，当前不再继续推进已关闭的 `Phase 7`。
- 正式验收入口：`C:\projects\pdf_ai\paddle_ocr\docs\ai\runs\ai-harness-phase0-freeze-20260330-150836-m85l\phase7_acceptance.md`
- 主线 run 留痕：`C:\projects\pdf_ai\paddle_ocr\docs\ai\runs\ai-harness-phase0-freeze-20260330-150836-m85l\orchestration_log.md`
- 主线 session 留痕：`C:\projects\pdf_ai\paddle_ocr\.ai\session\ai-harness-phase0-freeze-20260330-150836-m85l\task_plan.md`
- 当前推荐：保持主线关闭状态；如后续要扩到 `.system/*`、plugins、project cleanup code、settings merge / override 等新范围，必须新开 phase，并重新冻结目标、边界与验收口径。
- Phase 7 收口后的优先候选方案入口：`C:\Users\72385\dev\ai-harness\docs\plans\contract-first-dispatch.md`

## 风险
- 运行时目录中仍可能存在未托管或第三方内容，不能在未冻结 takeover 策略前直接接管。
- 项目历史 run 文档包含旧绝对路径引用，不能未经分类直接重写。
- 如果后续直接扩到 `.system/*`、plugins、项目清理实施或 merge / override，会破坏当前最小闭环边界。

## 停止条件
出现以下任一情况时，不允许继续推进到下一 phase：
- 当前 phase 的正式验收或方案留痕未完成
- review 仍存在阻断项
- 需要写入未授权路径
- 需要扩展到未冻结的托管范围
- 文档与真实状态已发生漂移但尚未回写

## 进入下一 phase 的准入条件
只有同时满足以下条件时，才允许进入下一 phase：
1. 当前 phase 的目标、输入、输出、验收点与非目标已冻结
2. 当前 phase 的文档、测试、代码与运行时结果已同步
3. review 阻断项已清空
4. 正式验收或方案留痕已完成
5. 本总纲已同步回写当前真实状态与推荐下一步
