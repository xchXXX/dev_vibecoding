# 跨机器 Harness 动态路径与 Bootstrap 方案

## 任务目标

让仓库中的活动态文档、规则、模板和受版本控制生成物不再绑定具体用户名、盘符或 clone 位置；由一次性本机 bootstrap 根据当前机器和用户明确选择的 clone，安全生成 Codex 全局入口、同步 runtime、刷新规则索引并运行 doctor。

## 背景与问题

8 月 24 日验收通过的全局 `AGENTS.md` 在之后被用户更新的 63 行版本覆盖，重新带入 `C:\Users\72385`。当前机器实际用户目录为 `C:\Users\Laptop`，旧目录不存在。仓库还存在两个独立 clone；它们远程和 HEAD 相同，但未提交状态不同，因此不能靠自动扫描或文件复制决定真源。

现有 harness 已具备 `sync-codex.ps1`、`doctor-core.ps1` 的 canonical path、越界保护和 receipt 校验，也具备 `rules-index.common.ps1` 的 global rules root 导入与 `scope != project` 过滤。缺口是统一的根选择合同、全局 `AGENTS.md` 受控生成、tracked rules registry 的机器无关显示，以及 doctor 的迁移回归检查。

## 范围

- 新增 `scripts/path-resolution.common.ps1`，统一 harness root、Codex home、canonical path 和逻辑显示路径解析。
- 新增 `scripts/bootstrap-local.ps1`，生成 managed 全局 `AGENTS.md`、写本机 bootstrap receipt、调用现有 sync/rules/doctor 链路。
- 新增 `templates/codex/AGENTS.global.md`，保留当前全局协作约束，但只使用 `{{HARNESS_ROOT}}` 机器占位符和 managed marker。
- 扩展 `doctor-core.ps1`，诊断 root 选择、managed 全局入口、bootstrap receipt 和旧路径回归。
- 调整 rules registry 序列化，使受版本控制的 `repo_root`、`global_rules.searched` 使用逻辑根，而内部文件操作继续使用 canonical absolute path。
- 文档先行同步 `AGENTS.md`、`docs/INSTALL.md`、`docs/CODEX_COMPAT.md`、`docs/PROJECT_TEMPLATE.md` 和测试说明。
- 在当前机器以 `D:\prj\harnesss\dev_vibecoding` 为选定根运行 bootstrap，显式授权替换当前未托管全局 `AGENTS.md`，并保留可恢复备份。

## 非目标

- 不扫描整机寻找相同 remote 的 clone。
- 不自动修改、同步或覆盖 `D:\prj\dev_vibecoding`。
- 不提交、推送、合并或 cherry-pick 任一 clone。
- 不清洗历史 run、旧 task、benchmark、sandbox 和复盘证据中的原始绝对路径。
- 不把本机 `codex-sync.receipt.json` 的绝对路径改成跨机器真源；receipt 本来就是机器本地状态。
- 不增加旧路径兼容层、双轨 bootstrap 或跨平台安装框架。

## 约束与依赖

- 说明性内容使用中文，脚本参数、路径、字段名和代码标识符保持原样。
- 任何写入必须局限于本任务 `state.json` 的 `write_paths`；尊重当前工作区的大量未提交修改。
- 所有生产行为先由真实临时目录集成测试冻结，并观察预期 RED，再写最小实现。
- PowerShell 7 为执行入口；复杂参数直接传 `.ps1`，不新增 `.cmd` 二次解析层。
- 测试创建的临时仓库、临时 `CODEX_HOME`、备份和捕获文件必须在 `finally` 中清理。
- 全局文件写入必须原子化；未托管非空文件默认拒绝覆盖。

## 方案摘要

### 根选择

`Resolve-HarnessRoot` 使用唯一顺序：

1. 非空 `-HarnessRoot`。
2. 非空 `AI_HARNESS_ROOT`。
3. `bootstrap-local.ps1` 所在仓库根。

每个候选都 canonicalize，并验证 `rules/registry/RULES_ENTRY.md`、`scripts/sync-codex.ps1` 和 `templates/codex/AGENTS.global.md` 存在。不存在或不完整时返回稳定 issue，不回退扫描 sibling 或磁盘。

`Resolve-CodexHome` 使用唯一顺序：非空 `-CodexHome`、非空 `CODEX_HOME`、`USERPROFILE/.codex`。

### 全局 AGENTS 管理

模板首行使用 `<!-- ai-harness:managed-global-agents:v1 -->`，且恰好包含一个 `{{HARNESS_ROOT}}`。bootstrap 把选定根规范化为 `/` 分隔形式后渲染到本机目标。

- 目标缺失或空：直接原子写入。
- 目标带相同 managed marker：比较内容，变化时原子刷新，不变时不写。
- 目标非空且未托管：默认以 `global_agents_unmanaged` 失败。
- 指定 `-ForceGlobalAgents`：先在 `CODEX_HOME/.ai-harness/backups/` 保存 SHA-256 命名备份，再替换；相同原文件不重复创建备份。

bootstrap receipt 保存到 `CODEX_HOME/.ai-harness/bootstrap.receipt.json`，记录 schema version、canonical harness root、Codex home、模板和目标 SHA-256、选择来源与最近成功步骤。该文件是本机状态，可以保存绝对路径，不进入 Git。

### 规则索引便携化

规则模型内部仍使用绝对路径读取文件。写入 tracked registry 时使用显示层：

- 当前仓库根写为 `<repo-root>`。
- 显式全局根按输入顺序写为 `<global-rules-root:1>`、`<global-rules-root:2>`。
- sibling 候选只写为 `<repo-parent>/ai-harness/rules/items`。
- 规则叶子继续使用 repo-relative `source`。

这保持现有 JSON 字段类型为 string/array，避免引入兼容层，同时消除用户名和盘符。校验器必须用同一显示层生成期望值，但文件读取和 scope 过滤仍使用 canonical path。

### Bootstrap 数据流

`bootstrap-local.ps1` 按顺序执行：解析根与 Codex home → 验证模板和目标安全 → 生成/刷新全局 AGENTS → 写 bootstrap receipt → 调用 `sync-codex.ps1` → 调用 `generate-rules-index.ps1` 和 `validate-rules.ps1` → 调用 strict Codex doctor → 输出统一 JSON 摘要。

任一步失败立即停止，保留已完成步骤和可恢复备份，不自动触碰另一 clone。重复执行在输入未变化时应返回 `updated=false`。

## 风险与回退

- 共享 helper 抽取可能影响现有 sync/doctor；通过原有集成测试和逐函数最小迁移控制，不顺手重构其他逻辑。
- tracked rules registry 显示值变化可能暴露隐式消费者；先写行为测试，若确认存在必须依赖绝对根的消费者则触发停止条件并重新裁决。
- 当前全局 AGENTS 是未托管用户文件；本机迁移只在显式 `-ForceGlobalAgents` 下执行，且先创建内容寻址备份。
- 仓库变更按文件级 Git diff 回退，不使用 `git reset --hard`。全局文件可由备份恢复；bootstrap receipt 和新 managed 文件可在确认目标后删除或恢复。
- 若实现发现必须扫描磁盘或修改另一个 clone，立即停止，不扩大范围。

## 验收标准

- 临时不同盘符/用户名语境下运行 bootstrap，不需要改仓库文档。
- `-HarnessRoot` 优先于 `AI_HARNESS_ROOT`，后者优先于脚本根；无效显式值必须失败而不是静默换根。
- 未托管非空全局 AGENTS 默认不覆盖；force 路径有备份且幂等。
- managed 全局 AGENTS、receipt、sync、rules 和 strict doctor 形成单命令闭环。
- tracked 活动态文档、模板和 rules registry 不含固定 `C:\Users\*` 或 `D:\prj\harnesss\dev_vibecoding`。
- rules local/global/resolved 数量和 `scope != project` 语义保持正确。
- 本机全局 `AGENTS.md` 不再包含 `72385`，且指向当前选定根。
- TDD RED/GREEN、相关回归、计划文档校验、doc routing、strict doctor 和 `git diff --check` 都有新鲜证据。

## 阶段划分

1. `planning`：冻结本方案、施工文档、验收合同和任务状态。
2. `doc_sync`：由 `doc-curator` 先同步核心入口、安装、兼容和模板说明。
3. `test_sync`：由 `test-verifier` 新增行为测试并记录预期 RED。
4. `code_impl`：由 `ops-runbook` 写最小 helper/bootstrap/doctor/index 实现并转绿。
5. `review`：由独立 `reviewer` 复验全部 evidence slot，失败则退回原执行者。

## 需先同步的核心文档与测试

- 文档：`AGENTS.md`、`docs/INSTALL.md`、`docs/CODEX_COMPAT.md`、`docs/PROJECT_TEMPLATE.md`、`templates/codex/AGENTS.global.md`、`tests/harness/README.md`。
- 测试：新增 `tests/harness/bootstrap-local.integration.ps1`；扩展 `tests/harness/rules-index.integration.ps1` 与 `tests/harness/windows-command-guardrails.contract.ps1`。
- 只有文档同步收口后才能写测试；只有观察到预期 RED 后才能修改生产脚本。
