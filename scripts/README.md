# scripts

本目录保存 `ai-harness` 的脚本真源与脚本合同说明。

说明：

- 全局治理规则真源见 `docs/SUBAGENT_GOVERNANCE.md`。
- 当前仓库的项目级 rules system 真源见 `rules/registry/*` 与 `rules/items/<kind>/*`。
- 旧 `rules/common/SUBAGENT_RULES.md` 若仍出现在历史留痕中，仅按兼容/迁移语境理解。

## 当前已存在脚本

- `install-claude-agents.ps1`
- `sync-claude-agents.ps1`
- `install-claude-hooks.ps1`
- `sync-claude-hooks.ps1`
- `doctor-core.ps1`
- `start_session.ps1`
- `sync-codex.ps1`
- `skills/command-failure-memory/scripts/command-failure-memory.ps1`
- `validate-plan-docs.ps1`
- `validate-doc-routing.ps1`

## 当前脚本责任边界

### Claude

- Claude agents install / sync 已实现
- Claude hooks install / sync / doctor 边界已冻结并实现到当前最小范围

### Codex

当前 Codex 侧最小实现包含：

- `sync-codex.ps1`
- 最小 Codex doctor / validate 校验
- 独立 skill 的全局命令失败经验库脚本：`skills/command-failure-memory/scripts/command-failure-memory.ps1`
- 开发前 benchmark skill 真源：`skills/pre-dev-benchmark`
- 修复闭环闸门 skill 真源：`skills/fix-closure-gate`

## `sync-codex.ps1` 责任冻结

- 只负责固定白名单源路径映射到 `~/.codex/skills/*`
- 当前最小托管模型是固定白名单多 skill：
  - `global-task-orchestrator`
  - `command-failure-memory`
  - `pre-dev-benchmark`
  - `fix-closure-gate`
- 当前固定源路径映射：
  - `skills/global-task-orchestrator -> ~/.codex/skills/global-task-orchestrator`
  - `skills/command-failure-memory -> ~/.codex/skills/command-failure-memory`
  - `skills/pre-dev-benchmark -> ~/.codex/skills/pre-dev-benchmark`
  - `skills/fix-closure-gate -> ~/.codex/skills/fix-closure-gate`
- 最小支持 install / sync 语义
- 默认不接管未托管运行时目录
- 不扩大到：
  - `.system/*`
  - 插件
  - 任意目录同步
- `codex-sync.receipt.json` 记录多 skill 合同：
  - `managed_skills`
  - 聚合后的 `managed_files`
- `command-failure-memory` 作为独立 skill 随同步链路分发，不再作为 `global-task-orchestrator` 的内嵌脚本被描述

## Codex doctor 责任冻结

后续最小 doctor / validate 只负责：

- 检查固定白名单真源 skill 存在
- 检查固定白名单运行时 skill 存在
- 检查每个受管 skill 的关键文件已同步
- 检查真源、运行时与 receipt 基本一致
- 以多 skill 结构输出 `codex_audit`，先逐 skill 审计，再给出聚合结论

其中 `command-failure-memory` 的脚本漂移、缺失与 receipt 目标偏差，`pre-dev-benchmark` 的模板/脚本漂移，以及 `fix-closure-gate` 的文档/metadata 漂移，都应在独立 skill 维度被检测。

本批次不把 doctor 扩展成更广泛项目 doctor，也不处理 Claude settings merge / override，不引入自动触发或事件桥接。

## 文档闸门脚本

- `validate-plan-docs.ps1`
  校验 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md` 是否具备长任务方案文档、施工文档与验收文档的必填章节。
- `validate-doc-routing.ps1`
  校验模块代码目录、模块长期真源目录与任务期文档目录之间的最小分流边界。

这两类脚本是统一真源判断入口。未来若接 Claude 或 Codex hooks，hooks 只负责触发这些脚本，不复制脚本内部规则。
