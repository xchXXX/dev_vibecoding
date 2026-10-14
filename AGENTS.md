# AGENTS

本文件是 `ai-harness` 在当前项目中的默认读取入口，只保留项目边界、少量高优先级硬约束，以及规则系统装配说明。

全局稳定协作原则唯一维护在 [全局入口模板](templates/codex/AGENTS.global.md)，安装入口由 bootstrap 生成；本页只补充项目规则装配与目录边界。

## 默认读取顺序

每次进入本仓库时，默认按以下顺序读取和装配规则：

1. 读取本文件。
2. 读取 `rules/registry/RULES_INDEX.json` 的元数据。
3. 固定读取索引中仅有的三条 `activation=always_on` 规则：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。
4. 其余规则由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮实际操作自由决定是否读取；`intents`、`paths`、`summary` 与 `linked_skill` 只提供判断线索，不组成固定套餐，也不自动触发 skill。
5. 若当前仓库作为别的项目的全局规则根被引用，只导出其中 `scope != project` 的条目。

说明：

- 规则真源位于当前仓库 `rules/`；其中绝大多数 `rules/items/*` 条目属于跨项目全局规则，项目独属规则只保留少量 architecture 入口。
- 全局规则真源位于当前仓库 `rules/`；其他项目消费本仓规则时，必须把当前仓库根作为 `<harness-root>` 显式传给 `--global-rules-root`，不自动发现同机其他 clone。
- 规则文件名一律使用中文。
- 目录按 `kind` 分；`scope` 通过 frontmatter 表达，不通过目录编码。
- Python 只在离线维护或验收时生成、校验 `RULES_INDEX.json`；正常交互链不运行 Python matcher，不生成 `task_profile`，也不按任务类型拼装规则套餐。

## 真源入口

- 云端从 Git 接入本仓库时，先读 `docs/modules/portable-harness/delivery/engineering/dots-cloud.md` 并执行 `python3 scripts/cloud-setup.py --check`；使用其报告的本仓库 `.venv` Python。新环境设置由用户授权后运行不带 `--check` 的同一命令。
- 仓库 `.agents/skills` 只引用 `skills/` 中四个 canonical 技能，不维护副本。普通任务直接执行，GTO 仍须用户显式选择；文件与依赖检查不等于实际新会话加载或平台能力通过。不要求云任务存在 Windows、WSL、作者 Codex home 或个人记忆。

- 总纲：`docs/plans/AI_HARNESS_MASTER_PLAN.md`
- 项目真源入口：`docs/ARCHITECTURE.md`、`docs/CODEX_COMPAT.md`、`docs/SUBAGENT_GOVERNANCE.md`、`docs/PROJECT_TEMPLATE.md`、`rules/registry/RULES_ENTRY.md`

## Bootstrap 与全局模板入口

- Portable 接收者入口见 `docs/INSTALL.md`；`scripts/harness.py` 从固定 Git 提交构建包，以 receipt 管理安装文件及 AGENTS 区块，不要求作者 checkout 存在。
- 维护既有 WSL 安装时仍可按明确范围使用旧 bootstrap/sync；普通新接入不走旧机器配置发布链，不扫描同机 clone，也不自动同步其他工作区。
- 全局 Codex 入口模板位于 `templates/codex/AGENTS.global.md`，安装器按实际规则根和技能目录渲染；模板和本仓入口不保存机器绝对路径。

## 仓库目录边界

- `skills/`、`rules/`、`schemas/`、`scripts/`、`templates/`、`tests/`、`docs/` 为项目真源目录。
- 正式文档、临时目录、测试目录与隔离目录必须按本仓规则收口在仓库内部；仓库父目录不作为本项目真源目录。

## 规则系统分工

- `AGENTS.md`：默认必读入口与高优先级项目边界。
- `rules/registry/`：规则系统入口、schema、分类说明与元数据索引。
- `rules/items/`：按 `kind` 组织的规则叶子文件；当前仓库中除 `仓库目录边界`、`真源入口` 外，其余条目默认作为全局规则维护。
- `skills/*/SKILL.md`：复杂多步流程与可复用工作流真源。
- `scripts/` 与 `tests/`：可执行校验与回归闸门。
- 缺失工具的分层安装与授权边界由索引中的 `global.policy.缺失工具分层与依赖处理` 按当前操作决定是否适用。

若项目规则与全局规则发生冲突，必须通过项目规则 frontmatter 显式声明 `overrides`；未声明时不得静默覆盖。
