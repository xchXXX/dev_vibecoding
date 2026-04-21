# Frozen Plan

- task_id: command-failure-memory-independent-skill-20260420-163856-g3n2
- plan_id: PLAN-COMMAND-FAILURE-MEMORY-INDEPENDENT-SKILL-20260420-163856-G3N2
- status: frozen

## Goal
- 将 `command-failure-memory` 从 `global-task-orchestrator` 中解耦为独立模块、独立 skill，并保持现有失败记忆能力、托管链路与回归入口可持续演进。

## Why
- 当前 `command-failure-memory` 虽有独立职责，但仍以内嵌脚本形式挂在 `global-task-orchestrator` 下，导致模块边界、托管边界、doctor 审计边界与回归口径都耦合到单 skill 模型。
- 用户已明确确认：`command-failure-memory` 应视为另一模块、另一 skill；本批需先冻结独立 skill 解耦方案，不把自动触发混入当前改造。

## Scope
- scope_in:
  - 新建独立真源目录 `skills/command-failure-memory/`，并提供该 skill 自身的 `SKILL.md` 与脚本落点。
  - 将 `command-failure-memory.ps1` 从 `skills/global-task-orchestrator/scripts/` 迁出到独立 skill。
  - 将 `scripts/sync-codex.ps1` 与 `scripts/doctor-core.ps1` 从单一受管 skill 模型升级为“固定白名单多 skill 托管”。
  - 冻结 `codex-sync.receipt.json` 与 `doctor-core.ps1 codex_audit` 的多 skill 输出口径，不再以单一 managed skill 标量字段作为唯一语义来源。
  - 更新 `docs/CODEX_COMPAT.md`、`scripts/README.md`、`tests/README.md`、`tests/harness/README.md` 对 skill 边界与统一回归入口的说明。
  - 调整 `tests/harness/codex-sync.integration.ps1` 与 `tests/harness/codex-failure-memory.integration.ps1` 以匹配独立 skill 迁移后的路径与托管合同。
  - 默认不保留旧路径 `skills/global-task-orchestrator/scripts/command-failure-memory.ps1` 作为长期兼容入口；仅在 Execute Window 发现仓库内硬依赖旧路径时，才允许新增迁移期薄转发层，并必须同批写明清理条件，不得形成长期双真源。
- scope_out:
  - 不在本批实现 `command-failure-memory` 的自动触发或事件桥接。
  - 不把托管范围扩展到 `.system/*`、plugins、或任意 skill 自动托管。
  - 不修改 Codex 平台原生协议与事件模型。
  - 不重写失败记忆的核心数据规则（`record-failure / query-before-retry / record-success / inspect`），除非为迁移路径所必需。

## Acceptance
- 仓库存在独立 skill 真源：`skills/command-failure-memory/`，且包含可投放的 `SKILL.md` 与脚本文件。
- `global-task-orchestrator` 不再拥有 `command-failure-memory.ps1` 的长期真源职责；最多只保留依赖调用或短期兼容转发。
- `scripts/sync-codex.ps1` 与 `scripts/doctor-core.ps1` 可按固定白名单同时托管并审计 `global-task-orchestrator` 与 `command-failure-memory`。
- `codex-sync.receipt.json` 与 `doctor-core.ps1 codex_audit` 已升级为多 skill 结构，不再把单一 managed skill 标量字段作为唯一语义真源。
- `tests/harness/codex-sync.integration.ps1` 能覆盖双 skill 受管场景；`tests/harness/codex-failure-memory.integration.ps1` 改用独立 skill 路径。
- `docs/CODEX_COMPAT.md`、`scripts/README.md`、`tests/README.md`、`tests/harness/README.md` 不再把 `command-failure-memory` 描述为 `global-task-orchestrator` 的内嵌脚本。
- 统一回归入口说明仍然可定位到相关 failure-memory 与 schema 套件，不因 skill 解耦而丢失入口。

## Risks
- `sync-codex`、`doctor-core` 与 `codex-sync` 测试当前都内建“单一受管 skill”假设，解耦时容易引发回执结构与断言连锁漂移。
- 若兼容转发层保留过久，容易形成 `global-task-orchestrator` 与 `command-failure-memory` 双真源或边界回流。
- 用户可能将“独立 skill”与“自动触发”混同；若执行阶段未显式收口，容易越批次扩大范围。

## Stop Conditions
- 若实现独立 skill 必须依赖 Codex 平台新增事件机制或自动触发协议，则停止并回退方案。
- 若无法在不形成双真源的前提下完成迁移，则停止并回退方案。
- 若多 skill 托管必须扩大到固定白名单之外的动态任意 skill 管理，且未获得额外确认，则停止并回退方案。
- 若回归链路无法在保持当前最小托管边界的前提下验证双 skill 模型，则停止并回退方案。

## Phase Overview
- P1 Plan Window 证据收敛与方案冻结（本窗口完成）
- P2 文档与 skill 边界重构
- P3 `sync-codex` / `doctor-core` 多 skill 托管升级
- P4 测试迁移与统一回归入口校对
- P5 Execute Window 实施、回归与验收

## Decisions
- D1：`command-failure-memory` 视为独立模块与独立 skill，不再作为 `global-task-orchestrator` 的长期内嵌脚本存在。
- D2：本批仅冻结“独立 skill 解耦方案”，不把自动触发接线纳入当前范围。
- D3：托管升级采用固定白名单多 skill 模型，不扩展为任意 skill 自动托管。
- D4：`codex-sync.receipt.json` 从单 skill 标量模型升级为多 skill 结构；Execute Window 不得继续把 `managed_skill_name` 当作唯一真源字段。
- D5：`doctor-core.ps1` 的 Codex 审计输出同步升级为多 skill 结构；Execute Window 应按每个受管 skill 独立审计，再做聚合结论。
- D6：兼容 wrapper 默认不保留；仅当 Execute Window 证实仓库内存在旧路径硬依赖时，才允许新增迁移期薄转发，并必须同批写明清理条件。
