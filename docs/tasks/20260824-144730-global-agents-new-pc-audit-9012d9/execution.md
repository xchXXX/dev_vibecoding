# 全局 AGENTS 与新电脑迁移审计施工文档

## 施工目标

以最小、可验证的改动完成全局 Codex 指令落地，并使当前 harness 的活动态入口适配新电脑。

## 前置条件

- 三个只读审计子任务均已回收。
- 目标 Codex home、现有 `AGENTS.md` 与 `AGENTS.override.md` 状态已确认。
- `state.json.verification_contract` 完整并通过 orchestrator 校验。

## 执行顺序

1. 回收审计，冻结必须修改和仅报告的路径集合。
2. 同步当前批次核心文档与路径测试合同。
3. 运行文档/规则基线测试，确认失败点确实命中旧路径或缺失配置。
4. 写入全局 `AGENTS.md`，刷新活动态规则索引和必要入口。
5. 运行 sync、doctor、规则与指令发现验证。
6. 交给独立审阅子代理，findings 回流原实施子代理。

## 文档先行清单

- 本任务 `plan.md / execution.md / acceptance.md`。
- 根 `AGENTS.md` 与 `rules/registry/RULES_ENTRY.md` 的机器无关入口约定。
- 必要时更新 `docs/ARCHITECTURE.md`、`docs/CODEX_COMPAT.md`、`docs/INSTALL.md` 中仍作为当前默认值的旧路径。

## 测试同步清单

- 将全局 AGENTS 路径测试从旧用户绝对路径改为 `CODEX_HOME/USERPROFILE` 动态解析。
- 运行 `tests/harness/windows-command-guardrails.contract.ps1`。
- 运行规则索引、规则校验、计划文档与 doc routing 验证。
- 运行 Codex sync/doctor 的 dry-run 或最小安全模式；如脚本无 dry-run，再按用户已授权的运行时同步范围执行。

## 实施批次

- 批次 A：文档和测试合同同步；依赖只读审计完成。
- 批次 B：全局 `AGENTS.md` 与活动态入口实现；依赖批次 A 验证。
- 批次 C：生成物刷新、doctor、独立审查与返工。

## 每批写入范围

- 批次 A：`docs/tasks/<task-id>/`、根/核心入口文档、直接相关测试。
- 批次 B：实际 `CODEX_HOME/AGENTS.md`，以及审计确认的少量活动态项目入口。
- 批次 C：`rules/registry/RULES_INDEX.*`、`RULES_RESOLVED.json`、任务状态与验收记录。

## 验证命令

- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/validate-plan-docs.ps1 -TaskId <task-id>`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/validate-doc-routing.ps1`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/generate-rules-index.ps1`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/validate-rules.ps1`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File tests/harness/windows-command-guardrails.contract.ps1`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/sync-codex.ps1 -Json`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/doctor-core.ps1 -Json`

## 回退方案

仓库文件按 Git diff 逐文件回退；若全局 `AGENTS.md` 原先不存在则删除新建文件，若原先存在则恢复写入前快照。不得使用 `git reset --hard` 或覆盖用户其他改动。

## 审查与返工路径

实施后由同一个独立 reviewer 检查内容精简度、路径可移植性、测试证据与越界修改。若不通过，完整 findings 回流原实施子代理；主协调器不代修，返工后仍由原 reviewer 复审。
