# Frozen Plan

- task_id: global-error-memory-for-codex-20260409-103402-vpb0
- plan_id: PLAN-GLOBAL-ERROR-MEMORY-FOR-CODEX-20260409-103402-VPB0
- status: frozen

## Goal
- 为 Codex 侧建立全局“命令失败经验库”，在跨项目场景下减少重复试错。
- 固化“失败后再查库、缺知识才写入”的流程门禁。

## Scope
- scope_in:
  - Codex 全局目录 `~/.codex/memories/command-failure-memory/` 的数据结构与读写规则。
  - Harness 脚本能力：失败事件记录、重试前检索、解决后决策写回、去重与清理。
  - 案例字段 `scope_kind`（全局/项目）及候选态收敛机制。
  - Codex 托管链路（`sync-codex.ps1`）对相关 skill 的分发与回执校验。
  - 文档、schema、测试最小闭环。
- scope_out:
  - 不依赖 Claude hooks。
  - 不改 Codex 平台原生协议与内部数据库。
  - 不做全盘 runtime takeover。

## Core Rules
- R1 查询触发时机：不在每次命令前查询；同命令首次失败后仅记录，准备重试前才查询。
- R2 写入时机：问题成功解决后先做等价解法匹配；仅在库中不存在可用解法时新增案例。
- R3 已有案例处理：若已存在等价解法，不新增 incident，只更新命中与验证统计。
- R4 范围字段：每条案例必须带 `scope_kind`，初始允许 `candidate_global/candidate_project`，后续收敛到 `global/project`。

## Scope Classification (Frozen V1)
- 初始判定：
  - 若修复步骤依赖项目私有脚本、项目配置或项目路径，标记 `candidate_project`。
  - 若修复步骤为通用环境问题（权限、编码、网络、shell quoting、工具缺失），标记 `candidate_global`。
- 收敛规则：
  - `candidate_project` 在两个及以上项目复现且解法稳定后，可提升为 `global`。
  - `candidate_global` 若长期仅单项目出现且强依赖项目上下文，可降级为 `project`。
- 每条记录保留 `scope_confidence` 与 `scope_reason`。

## Acceptance
- 失败后重试前可召回历史解法，不在命令首次执行前强制查库。
- 成功后可正确判断“是否缺知识”，避免重复写入同类案例。
- 案例结构包含 `scope_kind` 及候选态收敛所需字段。
- 全局记忆库可跨项目复用。
- 同步链路、schema 与最小测试可覆盖坏路径（重复写入、低置信误判、越界写入）。

## Risks
- 相似错误误匹配导致建议偏差。
- scope 判定初期准确率有限，需要候选态与统计收敛。
- 命令与错误文本可能包含敏感信息，必须脱敏后落盘。

## Stop Conditions
- 无法满足最小脱敏要求。
- 需要依赖 Codex 不提供的事件机制才能实现核心流程。
- 需要突破当前最小托管边界才可实现。
- 关键坏路径无法通过测试覆盖验证。
