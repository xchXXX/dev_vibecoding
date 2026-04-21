# AGENTS

本文件是 `ai-harness` 的默认读取入口，只保留高层强制规约、仓库边界与真源入口，不重复复制全局治理正文。

## 交互语言与流程

- 说明性内容默认使用中文；字段名、路径、脚本参数、代码标识符保持原样。
- 用户一旦提问，先回答问题，再继续手头工作。
- 任何会落盘的改动，先给出简短计划，再实施。
- 用户显式指定 skill 时按指定 skill 执行；未指定时走默认轻量协作流程。

## 命令失败闭环

- 对任何 shell、terminal、PowerShell、bash、test、build、install、script、toolchain、git、npm/pnpm/yarn、node、python/pip/uv/pytest、cargo、go、docker 命令，不要靠枚举错误文案判断是否触发；只要执行信号表明命令未成功，例如退出码非 0、超时、工具调用失败，或输出明确表明命令未完成，就视为命令失败。
- 一旦命令失败，必须自动调用当前 Codex runtime 的 `command-failure-memory.cmd` 执行 `record-failure`；优先使用 `$env:CODEX_HOME\skills\command-failure-memory\scripts\command-failure-memory.cmd`，只有在 `CODEX_HOME` 未设置时才回退到 `%USERPROFILE%\\.codex\\skills\\command-failure-memory\\scripts\\command-failure-memory.cmd`；不要在 Codex shell 里直接调用 `.ps1`。
- 在任何 retry、rerun、重跑、重试或等价命令再次执行前，必须先执行 `query-before-retry`，不要盲目重试。
- 修复方案经重跑验证成功后，必须执行 `record-success`；需要审计经验库时执行 `inspect`。
- 该闭环默认启用，即使用户未显式提到 `command-failure-memory` skill 也一样。
- `ProjectId` 使用稳定仓库标识；`CommandText` 传实际执行命令；`ErrorText` 优先传首行错误摘要。

## 真源入口

- 项目总纲：`C:/Users/72385/dev/ai-harness/docs/plans/AI_HARNESS_MASTER_PLAN.md`
- 架构与分层：`docs/ARCHITECTURE.md`
- Codex 兼容闭环：`docs/CODEX_COMPAT.md`
- 协作治理真源：`docs/SUBAGENT_GOVERNANCE.md`
- Claude agents 真源说明：`docs/AGENTS.md`
- 项目接入骨架：`docs/PROJECT_TEMPLATE.md`

## 仓库目录边界

- `agents/`：Claude agents 长期真源、角色目录、Codex 角色映射
- `skills/`：Codex skills 长期真源
- `hooks/`：Claude hooks 真源与脚本
- `rules/`：通用协作规则与专项规则
- `schemas/`：control-plane schema 真源
- `scripts/`：安装、同步、doctor、session 脚本
- `templates/`：plan、work order、dispatch、review、return packet 模板
- `tests/`：harness 与集成测试
- `docs/`：架构、迁移、计划、兼容说明、run 留痕
- `contexts/`：启动、压缩、项目类型上下文
- `C:/Users/72385/dev/` 根目录只允许保留 `ai-harness/` 与 `AGENTS.md`；其他文档、临时目录、测试目录与隔离目录都必须进入 `ai-harness/` 内部

## 变更约束

- 项目入口只写入口和增量规则，不在这里复制通用 subagent / review / testing 正文。
- 通用治理规则统一收口到 `docs/SUBAGENT_GOVERNANCE.md`、`rules/common/SUBAGENT_RULES.md` 和 `templates/*.example.*`。
- 修改 `agents/`、`skills/`、`hooks/`、`schemas/`、`scripts/`、`templates/` 时，必须同步检查相关 `docs/` 与 `tests/` 是否需要更新。
- 仓库专属适配优先放在根 `AGENTS.md`、`docs/ai/`、`config/ai/`；不要把项目私有约束回写进可跨项目复用的真源。
- 可复用逻辑优先沉淀到现有真源目录，不要散落到临时 run 产物或一次性说明里。

## 提交与验证

- 变更后优先运行最小相关验证；未执行的验证必须明确说明。
- 提交信息建议使用 Conventional Commits 加中文描述。
- 涉及 control-plane、派发合同、回执或会话编排的留痕，统一放在 `docs/ai/runs/`。
