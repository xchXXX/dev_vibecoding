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
- 需要时的 `~/.codex/` 配套配置

规则：
- 运行时目录允许被同步脚本覆盖
- 不再把运行时目录视为设计真源

### 3. 项目适配层

职责：
- 放项目边界、模块入口、项目特化规则
- 放项目专属的 docs/ai、config/ai、AGENTS.md
- 放项目与全局能力之间的最小覆盖层

当前项目 `C:/projects/pdf_ai/paddle_ocr` 应保留：
- `AGENTS.md`
- `docs/ai/`
- `config/ai/`
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

## Claude / Codex 边界

- Claude 原生支持 hooks，应把自动门禁优先落在 hooks 上
- Codex 当前不应假设具有与 Claude 等价的 hooks 能力
- Codex 兼容闭环通过 `AGENTS.md + skills + scripts + doctor` 构建

## 当前项目的已知漂移

- `.claude/settings.local.json` 仍被项目跟踪，且绑定旧服务器与旧目录
- `docs/ai/runs/*` 中存在 `C:/Users/72385/.codex/skills/...` 绝对路径引用
- 通用 orchestrator 脚本当前仅存在于 `~/.codex/skills/global-task-orchestrator/`

这些漂移在后续 phase 清理，不在本 phase 直接删除。

## 协作治理真源

- 统一的主协调器 / 执行型子代理 / 审查型子代理规则收口在 `docs/SUBAGENT_GOVERNANCE.md`
- 统一模板收口在 `templates/`
- 项目侧只保留入口引用与项目增量规则，不再复制统一治理正文
