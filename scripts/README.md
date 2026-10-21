# scripts

> Windows 原生迁移维护期间，bootstrap-local.py 和 sync-codex.py 遇到 CODEX_HOME/.ai-harness/windows-native-transition.hold 会返回 WINDOWS_NATIVE_TRANSITION_HOLD，且不执行后续写入。此标志不代表 Agent 已切换；解除条件见 [迁移任务](../docs/tasks/20260910-windows-native-transition/task.md)。不要绕过入口直接发布旧 GUI 桥，项目环境检查仍正常使用。

本目录保存 `ai-harness` 的脚本真源与脚本合同说明。

Git 工作流入口见 `docs/modules/git-workflow/delivery/engineering/README.md`：`check_git_workflow.py` 只读核验、`sync_git_workflow.py` 生成项目副本、`bootstrap-local.py --git-workflow-only` 仅发布相关入口与检查器。不调用完整 bootstrap，不更改其他受管 skill、环境或插件配置。

说明：

- 全局治理规则真源见 `docs/SUBAGENT_GOVERNANCE.md`。
- 当前仓库的项目级 rules system 真源见 `rules/registry/*` 与 `rules/items/<kind>/*`。
- 旧 `rules/common/SUBAGENT_RULES.md` 若仍出现在历史留痕中，仅按兼容/迁移语境理解。

## 当前已存在脚本

- `bootstrap-local.py`
- `sync-codex.py`
- `doctor-core.py`
- `skills/global-task-orchestrator/scripts/start_session.py`
- `rules_index.py`
- `generate_rules_index.py`
- `validate_rules.py`
- `validate_plan_docs.py`
- `validate_doc_routing.py`
- `provision-wsl.py`
- `project-env-doctor.py`
- `resolve-wsl-path.py`
- `skills/global-task-orchestrator/scripts/orchestrator_ctl.py`
- `skills/command-failure-memory/scripts/command-failure-memory.py`

## 当前脚本责任边界

### Codex

当前 Codex 侧最小实现包含：

- `bootstrap-local.py` 负责新环境初始化和全局 `AGENTS.md` 托管。
- `sync-codex.py` 只同步固定白名单 skill，不接管插件或其他运行时目录。
- `doctor-core.py` 核对真源、运行时与 receipt 的文件哈希。
- GTO 安装探测直接复用包内 `revision-3-contract.example.json`，在临时消费仓库初始化当前合同，再调用安装态控制器只读校验；不维护旧版合同夹具，也不复制历史任务冒充当前可运行状态。
- `provision-wsl.py` 读取机器公共工具基线，默认只输出计划；只有显式 apply 才能对批准范围内、来源明确的最小缺口执行变更。
- `project-env-doctor.py` 读取当前项目的声明式环境配置，只读分类 `TEMP`、Python/Node 工件、项目依赖隔离和声明的可选 capability；Python 真源支持 `requirements_file`，也支持 `pyproject_file` 与明确的 `extras`，后者只解析依赖并离线核对，不构建项目。脚本不恢复依赖或删除目录。
- `resolve-wsl-path.py` 只转换已明确为路径值的 Windows/WSL 参数并检查存在性，不改写整段命令或错误文本。
- Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；项目 Git/Python/Node/测试/构建继续通过指定发行版的 wsl.exe --exec 执行。外部能力声明 v3 只列 windows_native 与 required_plugins；bootstrap/doctor 不写插件配置或官方 transport，不创建 WSL GUI 桥。磁盘 enabled 不等于 GUI 验收。
- `rules_index.py` 只负责解析规则 frontmatter 和构造索引元数据，不决定本轮应读取哪些可选规则。
- `generate_rules_index.py`、`validate_rules.py`、`validate_plan_docs.py`、`validate_doc_routing.py` 提供可独立执行的机械闸门。
- 除最小必读集合外，Codex 根据对话语义、目标内容与路径、风险、当前阶段和本轮实际操作五个维度自由选读规则；Python 不参与语义选择。
- 缺失命令、项目依赖或浏览器自动化运行时的安装层与授权边界由 `global.policy.WSL工具分层与缺失依赖处理` 说明；脚本不据此做运行时规则匹配或静默安装。
- 环境责任固定分为机器公共工具、项目依赖隔离、可选能力和 Windows 外部能力。machine doctor 与 project doctor 应在新 worktree setup 后或任务首次触及运行时时运行一次，不扩展成 hook、daemon、逐命令 wrapper、自动重试或自动修复。
- `pnpm` 是需要 Linux 原生可执行文件的外部机器基线；Corepack 不是 doctor 的必需工具，也不会由 provision 自动安装。
- 独立 skill 的全局命令失败经验库脚本：`skills/command-failure-memory/scripts/command-failure-memory.py`
- 开发前 benchmark skill 真源：`skills/pre-dev-benchmark`
- 修复闭环闸门 skill 真源：`skills/fix-closure-gate`

Codex 不托管 `PreToolUse` 命令安全 hook；校验由上述显式 Python 入口执行。

环境合同、时序和路径映射见 `docs/modules/wsl-environment/`。Codex 附件 initial banner 是上游产品限制；路径 resolver 成功不保证上传/UI 成功。

## 正式 CLI

参数统一使用 GNU 双横线写法。下面 bootstrap/doctor/index 示例在 harness 根运行；GTO 使用本轮实际读取的 SKILL.md 所在绝对目录，消费项目与工具根分开：

```bash
harness_root="$PWD"
project_root=/path/to/project
GTO_SKILL_DIR=/absolute/path/to/the/loaded/global-task-orchestrator
GTO_CONTROLLER="$GTO_SKILL_DIR/scripts/orchestrator_ctl.py"
python3 scripts/bootstrap-local.py --harness-root "$PWD" --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --json
python3 scripts/doctor-core.py --root "$PWD" --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --strict --json
python3 skills/global-task-orchestrator/scripts/start_session.py --repo-root "$PWD" --task-id "$task_id" --json
python3 "$GTO_CONTROLLER" \
  --action validate --repo-root "$project_root" --task-id "$task_id" --json
python3 scripts/generate_rules_index.py \
  --repo-root "$project_root" --global-rules-root "$harness_root" --json
```

`start_session.py` 只恢复并校验已经存在的 GTO 任务及其六份工件，不读取 `docs/ai/runs`，也不创建 `.ai/session` 或另一套状态文件。新任务由 GTO 的 `--action init-task` 使用 Codex 已确认的结构化六要点合同初始化。

GTO 当前 state 只接受 `version=3`，`events.jsonl` 与其余五份工件同为必备。action 与参数只以 `orchestrator_ctl.py --help` 当前公开并实际实现的 GNU 双横线接口为准。

其他项目只有在显式提供 `--global-rules-root` 时才合并本仓 `scope != project` 的规则；未提供时不自动发现其他 clone 或工作区。

`bootstrap-local.py` 会将用户级 `hooks.json` 中的 `hooks` 清空为 `{}`。文件内其他顶层字段原样保留；`config.toml` 的顶层 `notify` 由 Codex 正常支持，bootstrap 原样不动。随后 strict doctor 核对托管全局 `AGENTS.md`、bootstrap/sync receipt，并拒绝实际的用户或项目 hook 配置。

## `sync-codex.py` 责任冻结

- 只负责固定白名单源路径映射到 `<已核实CODEX_HOME>/skills/*`
- 当前最小托管模型是固定白名单多 skill：
  - `global-task-orchestrator`
  - `command-failure-memory`
  - `pre-dev-benchmark`
  - `fix-closure-gate`
- 当前固定源路径映射：
  - `skills/global-task-orchestrator -> <已核实CODEX_HOME>/skills/global-task-orchestrator`
  - `skills/command-failure-memory -> <已核实CODEX_HOME>/skills/command-failure-memory`
  - `skills/pre-dev-benchmark -> <已核实CODEX_HOME>/skills/pre-dev-benchmark`
  - `skills/fix-closure-gate -> <已核实CODEX_HOME>/skills/fix-closure-gate`
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

本批次不把 doctor 扩展成更广泛项目 doctor，也不引入自动触发或事件桥接。

## 规则与文档闸门脚本

- `generate_rules_index.py`
  解析 `rules/items/**/*.md` 的 frontmatter，并机械生成 `rules/registry/RULES_INDEX.json` 与 `rules/registry/RULES_INDEX.md`。
- `validate_rules.py`
  机械校验规则字段、枚举、文件名、linked skill、显式 override、冲突及索引一致性。
- `validate_plan_docs.py`
  校验 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md` 是否具备长任务方案文档、施工文档与验收文档的必填章节。
- `validate_doc_routing.py`
  校验模块代码目录、模块长期真源目录与任务期文档目录之间的最小分流边界。

这两条文档 CLI 的显式 `--repo-root` 是已有业务消费目录，无须含 harness 的 rules/skills 标记；不存在或普通文件根明确失败。未传参数时保留脚本原有 harness 默认解析。已知 harness 真源目录与消费目录分别填写，然后运行：

```bash
python3 "$harness_root/scripts/validate_plan_docs.py" --repo-root "$repo_root" --json && \
python3 "$harness_root/scripts/validate_doc_routing.py" --repo-root "$repo_root" --json
```

不从消费目录猜测工具位置、不导入内部 validate 绕过公开 CLI；其他脚本的 harness 根规则保持不变。

这些脚本只承担生成与机械校验；规则真源仍是 `rules/items/**/*.md`，Codex 自行判断可选规则的读取范围。正常使用方式是从 WSL 直接运行 `python3 scripts/<entrypoint>.py`，不经跨 shell wrapper、自动重试或 hook。

## GTO revision 3 入口

新任务只使用 [包内合同示例](../skills/global-task-orchestrator/references/revision-3-contract.example.json)，schema 与恢复脚本随同一 skill 树加载。共享安装、doctor 与规则维护脚本留在本目录。流程统一引用 [任务流程](../skills/global-task-orchestrator/references/workflow.md)，机器操作见 [控制器指南](../skills/global-task-orchestrator/references/controller-guide.md)。

## Windows 原生迁移的限定维护入口

维护标志存在时发布入口拒绝写入。先在隔离目标验证，再冻结候选、受控解除、正式定向发布，失败恢复标志。

- `python3 scripts/bootstrap-local.py --environment-only --harness-root <root> --codex-home <home> --json`：只投放环境 runtime 并更新其真实 receipt；不改动 AGENTS、hooks、插件 config、其他技能和 schema。
- `python3 scripts/sync-codex.py --retire-legacy-gui --harness-root <root> --codex-home <home> --json`：旧桥 MCP 已明确停用且技能符合既有 receipt 时，仅将旧技能移入私有恢复目录并更新该技能记录；未知改动拒绝退役。
- `python3 scripts/doctor-core.py --environment-only --root <root> --codex-home <home> --json`：只审计环境 runtime/receipt、Linux 工具和原生插件配置；不执行 GTO 或其 schema，不等价于全局 doctor 通过。

bootstrap/doctor 不修改原生插件配置。一次性迁移在私有备份和定点核对后删除旧 WSL GUI 桥配置、代码与技能；完成后不保留旧运行或发现入口。Windows 调用 WSL 时使用 `wsl.exe -d <distro> --cd <project> --exec python3 <script>`；复杂内容先写脚本文件，避免默认 shell 解释反引号、重定向或变量。

- `configure-skill-policy.py`：按 `config/ai/skill-policy.json` 的唯一声明写入受支持的 `[[skills.config]] path` 开关；显式传入已核实的 `--codex-home` 和当前 `--plugin-skills-root`。`--check` 只检查磁盘，不证明运行时加载。保留其他设置与方法技能，不修改插件缓存；升级后重新应用并验证新会话。

项目接入与最小使用示例见 [接入与检查](../docs/harness-usage-examples.md)。版本与诊断新增输出的合同及实施状态见 [简化合同](../skills/global-task-orchestrator/references/streamlined-execution.md)，不另建版本库或自动修复入口。

任务归属新增公开入口 task_workspace.py，普通任务核心工件/阶段证据、GTO 只读定位和发布范围见 [合同](../docs/modules/git-workflow/contract/task-workspace.md)。待实现状态见合同，不将文档列出命令视为功能可用。
