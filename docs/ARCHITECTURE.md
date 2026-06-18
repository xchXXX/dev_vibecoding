# ARCHITECTURE

## 目标

建立一套不绑定单项目、可在本机多个项目复用的 AI 开发控制面与运行时接入体系。

## 三层模型

### 1. 全局真源层

建议路径：`C:/Users/72385/dev/ai-harness/`

职责：
- 保存长期维护的 AI 方法论文档
- 保存 Claude agents 真源
- 保存 Codex skills 真源
- 保存 `scope=global` 的跨项目 rules 条目与默认目录基线
- 保存 hooks、rules、schemas、templates、doctor、sync 脚本
- 作为后续新项目脚手架的唯一来源

禁止：
- 直接把 CLI 运行时目录当作真源维护
- 把某个业务项目仓库当作全局方法论真源

### 2. 运行时投放层

职责：
- 接收全局真源同步后的文件
- 只负责被 CLI 识别与执行
- 不承载长期设计讨论

Claude 运行时目标路径：
- `~/.claude/agents/`
- `~/.claude/settings.json`
- 需要时的 hooks 脚本目录

Codex 运行时目标路径：
- `~/.codex/skills/`
- 需要时的 `~/.codex/` 配套配置与 hook 设置

规则：
- 运行时目录允许被同步脚本覆盖
- 不再把运行时目录视为设计真源

### 3. 项目适配层

职责：
- 放项目边界、模块入口、项目特化规则
- 放项目正式代码、模块文档、任务文档与项目私有配置
- 放项目专属的 docs/ai、config/ai、AGENTS.md
- 放项目级 rules system 的 registry 与 items 真源
- 放项目与全局能力之间的最小覆盖层

当前项目 `C:/projects/pdf_ai/paddle_ocr` 应保留：
- `AGENTS.md`
- `docs/ai/`
- `config/ai/`
- `rules/registry/*`
- `rules/items/<kind>/*`
- `.claude/agents/*.md` 中仅项目特化部分
- 项目业务与部署文档
- 项目专属脚本

不应继续作为全局真源维护的内容：
- 通用 orchestrator 脚本
- 通用 schema / template
- 通用 Claude agents catalog
- 通用 hooks

## 运行时映射

### Claude

全局真源：
- `ai-harness/agents/*.md`
- `ai-harness/hooks/claude/settings.json`
- `ai-harness/hooks/claude/scripts/*`

运行时：
- `~/.claude/agents/*.md`
- `~/.claude/settings.json`

项目适配：
- `<project>/.claude/`
- `<project>/AGENTS.md`

### Codex

全局真源：
- `ai-harness/skills/*`
- `ai-harness/schemas/*`
- `ai-harness/scripts/*`

运行时：
- `~/.codex/skills/*`

项目适配：
- `<project>/AGENTS.md`
- `<project>/docs/ai/`
- `<project>/config/ai/`
- `<project>/rules/registry/*`
- `<project>/rules/items/<kind>/*`

## 跨项目文件落点基线

- `ai-harness/rules/items/<kind>/*` 中允许维护 `scope=global` 的跨项目目录基线规则；其他项目通过 sibling `ai-harness` 自动发现链路继承这些规则。
- 项目正式代码默认收口在 `<project>/modules/<module-name>/`，模块内部默认按职责组织，不按语言名称组织。
- 模块正式文档默认收口在 `<project>/docs/modules/<module-name>/contract|design|delivery/`；`delivery/` 继续拆成 `code-map/`、`engineering/`、`work-split/`。
- 长任务文档默认收口在 `<project>/docs/tasks/<task-id>/plan.md|execution.md|acceptance.md`。
- AI 任务状态与运行留痕默认收口在 `<project>/docs/ai/tasks/<task-id>/` 与 `<project>/docs/ai/runs/<run-id>/`。
- 冻结测试夹具默认收口在 `<project>/tests/fixtures/<module-name>/`。
- 临时文件与非真源产物默认收口在 `<project>/.tmp/<module-name>/` 与 `<project>/.artifacts/<module-name>/`。
- PoC / Spike 默认使用 `<project>/modules/arch-poc/` 与 `<project>/docs/modules/arch-poc/`，运行产物默认收口在 `<project>/modules/arch-poc/debug/out/`。

## Claude / Codex 边界

- Claude 与 Codex 当前都支持 hooks，但事件模型、配置结构与覆盖范围不应视为完全等价
- 自动门禁的统一真源应优先落在可复用脚本与规则系统；hooks 负责前置 guardrail，不负责承载唯一规则正文
- Codex 兼容闭环仍通过 `AGENTS.md + skills + scripts + doctor` 构建；当平台 hooks 可用时，可额外在前面挂接 guardrail
- 对“文档先行”“目录分流”“实现前闸门”这类约束，推荐脚本真源为主，Claude/Codex hooks 共用同一脚本入口
- 当前仓库已在项目级 `.codex/config.toml` 落地 Codex `PreToolUse` 最小接线，并通过 `hooks/codex/scripts/PreToolUse.ps1` 调用 `scripts/validate-doc-routing.ps1`

## 当前项目的已知漂移

- `.claude/settings.local.json` 仍被项目跟踪，且绑定旧服务器与旧目录
- `docs/ai/runs/*` 中存在 `C:/Users/72385/.codex/skills/...` 绝对路径引用
- 通用 orchestrator 脚本当前仅存在于 `~/.codex/skills/global-task-orchestrator/`

这些漂移在后续 phase 清理，不在本 phase 直接删除。

## 协作治理真源

- 统一的主协调器 / 执行型子代理 / 审查型子代理规则收口在 `docs/SUBAGENT_GOVERNANCE.md`
- 项目仓库的可执行规则系统收口在 `rules/registry/*` 与 `rules/items/<kind>/*`
- 统一模板收口在 `templates/`
- 项目侧只保留入口引用、项目级 rules system 与项目增量规则，不再复制统一治理正文

## 规则系统与长任务落地

- 当前项目采用“入口最小化 + 规则叶子化 + 字段规范/校验”的方式组织治理约束。
- 入口层只保留 `AGENTS.md` 与 `rules/registry/RULES_ENTRY.md` 这类装配说明；具体规则正文下沉到 `rules/items/<kind>/*`。
- 需要结构化约束的内容，应优先沉淀为固定字段、索引与校验链路，不在架构文档中重复维护一份规则全文。
- 涉及中大规模改造的长任务，执行顺序应保持为：先方案文档、再施工文档、再核心文档与测试同步、最后才进入代码实现。
- 上述长任务文档的必填字段与校验口径，以项目规则系统和对应脚本/测试为准；架构文档只声明分层与顺序，不复制字段清单。
- 核心文档与测试的同步更新由主协调器先行组织并收口；执行型子代理按分配边界实施，不自行改写治理顺序。
