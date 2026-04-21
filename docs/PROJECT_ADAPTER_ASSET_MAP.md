# PROJECT_ADAPTER_ASSET_MAP

## 目的

本文是 `Phase 7 / 子批次 A：项目适配层资产盘点与映射冻结` 的正式产物。

目标：
- 基于当前项目真实目录，对项目适配层关键对象做逐对象盘点
- 为每个对象冻结：
  - 当前路径
  - 当前角色/用途
  - 分类归属
  - 后续动作建议
  - 非目标/注意事项
- 为后续子批次 B / C / D 提供可执行输入

本文只做盘点与映射，不直接修改项目文件。

## 分类说明

- `保留`：继续留在项目层，作为项目增量入口或运行留痕
- `替换为全局引用`：后续保留项目入口，但正文/模板/schema 逐步改为引用 `ai-harness` 真源
- `移出共享真源`：若后续发现项目专属对象被错误纳入全局候选，应明确回退到项目层，不进入共享真源
- `本地化`：继续作为项目本地配置保留，不在当前批次直接收敛
- `延后处理`：先记账，后续单独处理；本批不直接改写或清理

关于 `移出共享真源`：
- 子批次 A 已正式承接这一分类，保证与 `PROJECT_ADAPTER_CLEANUP_PLAN.md` 的 5 类体系一致。
- 当前项目本轮盘点下，暂无已归入 `移出共享真源` 的对象。
- 若在后续子批次 B / C / D 中发现误入全局候选的项目专属对象，应回归此类处理，而不是继续并入 `ai-harness` 共享真源。

## 对象映射总表

| 对象 | 当前路径 | 分类 | 后续子批次 |
|---|---|---|---|
| Claude coder agent | `C:\projects\pdf_ai\paddle_ocr\.claude\agents\coder_agent.md` | 延后处理 | B |
| Claude deploy agent | `C:\projects\pdf_ai\paddle_ocr\.claude\agents\deploy_agent.md` | 延后处理 | B |
| Claude tester agent | `C:\projects\pdf_ai\paddle_ocr\.claude\agents\tester_agent.md` | 延后处理 | B |
| Claude local settings | `C:\projects\pdf_ai\paddle_ocr\.claude\settings.local.json` | 本地化 | C |
| Agent registry | `C:\projects\pdf_ai\paddle_ocr\config\ai\registry\agents.json` | 保留 | B |
| Workflow registry | `C:\projects\pdf_ai\paddle_ocr\config\ai\registry\workflows.json` | 保留 | B |
| AI schemas | `C:\projects\pdf_ai\paddle_ocr\config\ai\schemas\*.json` | 替换为全局引用 | B |
| AI templates | `C:\projects\pdf_ai\paddle_ocr\config\ai\templates\*` | 替换为全局引用 | B |
| AI README | `C:\projects\pdf_ai\paddle_ocr\docs\ai\README.md` | 保留 | B |
| Subagent workflow | `C:\projects\pdf_ai\paddle_ocr\docs\ai\SUBAGENT_WORKFLOW.md` | 保留 | B |
| Session planning standard | `C:\projects\pdf_ai\paddle_ocr\docs\ai\SESSION_PLANNING_STANDARD.md` | 替换为全局引用 | B |
| Module doc standard | `C:\projects\pdf_ai\paddle_ocr\docs\ai\MODULE_DOC_STANDARD.md` | 保留 | B |
| AI run history | `C:\projects\pdf_ai\paddle_ocr\docs\ai\runs\` | 延后处理 | D |
| Session files | `C:\projects\pdf_ai\paddle_ocr\.ai\session\` | 保留 | D |

## 逐对象盘点

### 1. `.claude/agents/coder_agent.md`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.claude\agents\coder_agent.md`
- 当前角色/用途：项目侧旧 Claude coder 角色入口，正文仍描述 Python 功能代码实现职责。
- 分类归属：`延后处理`
- 后续动作建议：在子批次 B 中判断它应被移除、降级为项目增量包装，还是替换为对全局 Claude agents 的引用说明。
- 非目标/注意事项：本批不直接删除、不直接替换为全局 agent、不直接改其 frontmatter 或正文。

### 2. `.claude/agents/deploy_agent.md`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.claude\agents\deploy_agent.md`
- 当前角色/用途：项目侧旧部署/运维 agent 入口，正文仍描述 Linux/DevOps 与远程运维职责。
- 分类归属：`延后处理`
- 后续动作建议：在子批次 B 中判断其是否保留为项目专属 wrapper，或改成引用全局 `ops-runbook` 加项目增量说明。
- 非目标/注意事项：本批不直接删，不直接与真实 `~/.claude/agents/*` 做接管或清理。

### 3. `.claude/agents/tester_agent.md`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.claude\agents\tester_agent.md`
- 当前角色/用途：项目侧旧测试 agent 入口，正文仍描述 unittest 测试用例职责。
- 分类归属：`延后处理`
- 后续动作建议：在子批次 B 中判断其是否可收敛为对全局 `test-verifier` 的引用，或继续保留项目增量包装。
- 非目标/注意事项：本批不直接删，不直接替换运行时 agent。

### 4. `.claude/settings.local.json`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.claude\settings.local.json`
- 当前角色/用途：项目本地 Claude 权限与执行口径配置；当前内容含大量历史 `permissions.allow` 记录。
- 分类归属：`本地化`
- 后续动作建议：在子批次 C 中做字段级分类，区分“必须保留的项目本地权限”与“历史遗留可收缩项”。
- 非目标/注意事项：本批不直接改文件、不删权限、不做 merge/override 设计。

### 5. `config/ai/registry/agents.json`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\config\ai\registry\agents.json`
- 当前角色/用途：项目侧 agent 注册表，明确本仓工作角色和默认写入范围。
- 分类归属：`保留`
- 后续动作建议：在子批次 B 中保留该文件作为项目适配层入口，但检查是否需要把角色命名和全局真源做更清晰映射。
- 非目标/注意事项：本批不直接删除或并入全局真源。

### 6. `config/ai/registry/workflows.json`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\config\ai\registry\workflows.json`
- 当前角色/用途：项目侧 workflow 注册表，承载本仓任务流与角色路由配置。
- 分类归属：`保留`
- 后续动作建议：在子批次 B 中保留为项目增量对象，同时评估与全局 workflow 说明的边界是否需要补注释。
- 非目标/注意事项：本批不改内容，不尝试上移到全局真源。

### 7. `config/ai/schemas/*.json`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\config\ai\schemas\*.json`
- 当前角色/用途：项目侧保留的控制面 schema，包括 `dispatch_packet`、`plan`、`return_packet`、`work_order`。
- 分类归属：`替换为全局引用`
- 后续动作建议：在子批次 B 中逐文件做映射，判断哪些可直接引用 `ai-harness/schemas/*`，哪些仍需项目增量 schema。
- 非目标/注意事项：本批不删 schema 文件，不直接改引用链路。

### 8. `config/ai/templates/*`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\config\ai\templates\*`
- 当前角色/用途：项目侧控制面示例模板，包括 `dispatch_packet.example.json`、`work_order.example.json` 与 session 示例 markdown。
- 分类归属：`替换为全局引用`
- 后续动作建议：在子批次 B 中逐文件做映射，区分“可直接引用全局模板”与“项目必须保留的增量模板”。
- 非目标/注意事项：本批不删模板，不强行统一到全局单份文件。

### 9. `docs/ai/README.md`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\docs\ai\README.md`
- 当前角色/用途：项目 AI 工作流总入口；当前正文已经明确全局 governance 真源入口与本仓只保留增量规则的口径。
- 分类归属：`保留`
- 后续动作建议：在子批次 B 中检查是否只需最小补充“引用化后哪些对象不再在项目层全文维护”。
- 非目标/注意事项：本批不重写其现有入口职责。

### 10. `docs/ai/SUBAGENT_WORKFLOW.md`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\docs\ai\SUBAGENT_WORKFLOW.md`
- 当前角色/用途：项目 subagent 增量工作流说明；当前正文已明确全局规则真源入口与本仓额外约束。
- 分类归属：`保留`
- 后续动作建议：在子批次 B 中核对是否还有重复的全局通用正文需要进一步缩减为引用。
- 非目标/注意事项：本批不直接精简正文。

### 11. `docs/ai/SESSION_PLANNING_STANDARD.md`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\docs\ai\SESSION_PLANNING_STANDARD.md`
- 当前角色/用途：项目侧会话三件套标准；当前内容与全局 `ai-harness` 会话规划标准高度重合。
- 分类归属：`替换为全局引用`
- 后续动作建议：在子批次 B 中评估改成“引用全局标准 + 项目差异附录”的最小方案。
- 非目标/注意事项：本批不直接删除或重定向该文档。

### 12. `docs/ai/MODULE_DOC_STANDARD.md`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\docs\ai\MODULE_DOC_STANDARD.md`
- 当前角色/用途：项目模块文档分层标准，直接约束当前仓库的 `docs/modules/*` 结构。
- 分类归属：`保留`
- 后续动作建议：在子批次 B 中保留为项目级规范，并明确它不属于可直接上移的全局通用对象。
- 非目标/注意事项：本批不改其分层标准。

### 13. `docs/ai/runs/`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\docs\ai\runs\`
- 当前角色/用途：项目真实 run 留痕目录，包含 plan / work_order / dispatch_packet / return_packet / orchestration_log。
- 分类归属：`延后处理`
- 后续动作建议：在子批次 D 中区分“历史留痕允许保留”与“后续不再新增的旧绝对路径/旧 runtime 引用”。
- 非目标/注意事项：本批不批量重写历史 run 文档，不直接清理旧绝对路径。

### 14. `.ai/session/`
- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.ai\session\`
- 当前角色/用途：项目会话级三件套留痕目录，承载 `task_plan.md`、`findings.md`、`progress.md`。
- 分类归属：`保留`
- 后续动作建议：在子批次 D 中只补“历史留痕规范与引用口径”，不做目录清理；如需收敛，只处理新增规则，不追改历史。
- 非目标/注意事项：本批不删会话目录，不改现有 session 内容。

## 子批次 A 验收口径与结论

### 约定验收口径
- 关键对象盘点齐全
- 每类对象都有明确归属与后续子批次
- 每个对象都写明非目标/注意事项
- 不直接改项目文件内容

### 当前结论
- 本文已覆盖本批要求的全部真实对象：
  - `.claude/agents/coder_agent.md`
  - `.claude/agents/deploy_agent.md`
  - `.claude/agents/tester_agent.md`
  - `.claude/settings.local.json`
  - `config/ai/registry/agents.json`
  - `config/ai/registry/workflows.json`
  - `config/ai/schemas/*.json`
  - `config/ai/templates/*`
  - `docs/ai/README.md`
  - `docs/ai/SUBAGENT_WORKFLOW.md`
  - `docs/ai/SESSION_PLANNING_STANDARD.md`
  - `docs/ai/MODULE_DOC_STANDARD.md`
  - `docs/ai/runs/`
  - `.ai/session/`
- 对象 -> 分类 -> 后续子批次映射表已形成。
- 本批未直接改项目文件、未改 `.claude/settings.local.json`、未清理历史 run 文档。

结论：`子批次 A 已完成，可进入子批次 B`。
