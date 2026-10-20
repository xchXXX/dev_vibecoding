# CODEX_COMPAT

> 当前宿主为 Windows 原生 Agent，WSL 保留项目开发与服务。旧 GUI 桥已从运行入口退役，后续清理与验收状态见 [迁移任务](tasks/20260910-windows-native-transition/task.md)。仅在 windows-native-transition.hold 实际存在时暂停发布并按任务接续；正常插件请求不受此安装维护门禁阻塞。

## 目标

本文冻结 `ai-harness` 的纯 Codex/WSL 运行合同。正常控制链只依赖 Codex 可读取的 `AGENTS.md`、规则元数据索引、按需规则与 skills，以及 WSL Python 3脚本和 Linux 原生命令。

## 冻结结论

- 仓库和用户运行时不保留其他代理平台的兼容层、hooks、settings、agents catalog 或回退入口。
- `/mnt/c/Users/Laptop/.claude` 在清理批次中永久删除，包括其中的 `backups` 与 `sessions`，不创建备份、不提供恢复合同。
- Codex 正常链不注册 hook 或受控 command runner；项目命令保留 Linux 入口，Windows 宿主可通过 PowerShell 调用 wsl.exe。
- 规则选择由 Codex 自己完成；Python 不解释自然语言，不判断本轮操作，也不在运行时拼装规则集合。
- Python 只在离线维护或验收时生成、校验 `RULES_INDEX.json`。

## 三层映射

Git 工作流沿用下述三层：全局入口按当前操作引用 `rules/items/workflow/分支与发布管理.md`，项目通过 `config/ai/git-policy.json` 声明参数，`scripts/check_git_workflow.py` 在关键节点只读检查。离线生成的项目副本可用于 CI；本机以 `bootstrap-local.py --git-workflow-only` 定向发布。遵循既有运行边界；脚本通过不能保证代理所有未来行为都符合规范。

### 全局真源层

- `<harness-root>/skills/*`：Codex skills 真源。
- `<harness-root>/rules/items/<kind>/*`：规则正文真源。
- `<harness-root>/rules/registry/RULES_INDEX.json`：唯一机器可读规则元数据索引。
- `<harness-root>/schemas/*`、`scripts/*`、`templates/*`：schema、WSL Python 控制脚本和模板真源。

### 运行时投放层

- `CODEX_HOME/skills/*`：受管 skills 运行时副本。
- `CODEX_HOME/skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json`：安装版 GTO 使用的唯一受管 schema 运行时副本。
- `CODEX_HOME/AGENTS.md`：由 `templates/codex/AGENTS.global.md` 渲染的全局入口。
- `CODEX_HOME/.ai-harness/*`：机器本地 receipt、备份与审计状态；不作为版本控制真源。

### 项目适配层

- `<project>/AGENTS.md`
- `<project>/docs/ai/`
- `<project>/config/ai/`
- `<project>/rules/registry/RULES_INDEX.json`
- `<project>/rules/items/<kind>/*`

项目适配层只放项目边界、增量规则和项目私有配置，不复制全局治理正文。

## 规则自由选读合同

Codex 每轮固定读取：

1. 全局与项目 `AGENTS.md`。
2. 当前可用的 `RULES_INDEX.json` 元数据。
3. 三条最小必读规则：
   - `global.policy.变更约束`
   - `global.workflow.用户提问先回答再继续`
   - `global.style.说明默认使用中文`

其余规则不是固定套餐。Codex 根据对话语义、目标内容、风险、当前阶段和本轮实际操作，自由决定是否读取某条规则正文。索引中的 `summary`、`intents`、`paths`、`linked_skill` 与执行提示只帮助判断相关性；它们不构成 Python matcher、强制路由表或自动 skill 触发器。

`RULES_INDEX.json` 只保存规则元数据和正文路径，不内嵌正文。正常链不生成或消费全正文聚合视图。索引生成和结构校验是离线维护动作，不在每次提问、每个任务或每条规则读取前运行。

其他项目要合并本仓 `scope != project` 的规则，必须在离线生成或校验时显式传入 `--global-rules-root <harness-root>`。未传入时只处理目标项目规则，不扫描 sibling clone、用户目录或其他工作区。

## WSL 正常链

Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；项目 Git/Python/Node/测试/构建继续通过指定发行版的 wsl.exe --exec 执行。外部能力声明 v3 只列 windows_native 与 required_plugins；bootstrap/doctor 不写插件配置或官方 transport，不创建 WSL GUI 桥。磁盘 enabled 不等于 GUI 验收。
- 仓库可位于 `/mnt/<drive>/...`；独立任务可用隔离 worktree，规则真源和共享安装发布入口保持唯一，不搬库或扫描无关 clone。
- Windows 原生文件与官方插件操作可使用 PowerShell；项目 Git/Python/Node/测试/构建经 PowerShell 调用指定 WSL 发行版，保留 Linux 入口与退出码，不改用 Windows 项目依赖或 batch/hook。
- 普通非零退出码进入命令失败闭环，不切换平台重跑，不增加自动 retry、逐命令 preflight、守护进程或通用 wrapper。
- 新进程必须核对实际 `CODEX_HOME`、Linux 用户、工作目录和规则加载位置；不从另一环境的默认值推定，也不整目录复制 `.codex`。
- 项目依赖必须使用 WSL 侧安装；不混用其他平台的 `node_modules`、venv 或原生依赖。

## WSL 环境分层

环境健康按四层判断，详细合同见 [WSL 环境分层合同](modules/wsl-environment/contract/layered-environment-contract.md)：

1. **机器公共工具**：由 `config/ai/wsl-tool-baseline.json` 与 `schemas/wsl-tool-baseline.schema.json` 声明。`provision-wsl.py` 默认只计划；显式 apply 才能在批准边界内安装最小缺口。
2. **项目依赖隔离**：项目按自己的 manifest/lock 在 WSL 的 `.venv`、`node_modules` 中恢复，`project-env-doctor.py` 只读分类，不删除或重建这些目录。
3. **可选能力**：Playwright、Docker、数据库或云 CLI 必须由项目环境声明和本次任务共同证明需要，不能被提升为全部机器的必装项。
Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；项目 Git/Python/Node/测试/构建继续通过指定发行版的 wsl.exe --exec 执行。外部能力声明 v3 只列 windows_native 与 required_plugins；bootstrap/doctor 不写插件配置或官方 transport，不创建 WSL GUI 桥。磁盘 enabled 不等于 GUI 验收。

machine doctor 应在新 worktree setup 后、GTO 长任务第一次运行代码前或普通任务第一次触及运行时运行；project doctor 只在该项目首次需要运行时时运行。两者都不是 hook、daemon、逐命令 wrapper 或自动修复器。doctor 对外部能力只读分类，不把 Desktop 重新生成的官方插件配置当作漂移，也不触发改写和重启循环。禁止 broad upgrade、自动重试、平台回退和破坏性环境修复。

Codex 附件流出现的初始 banner 是上游产品行为；路径桥接成功不保证上传/UI 成功，本仓库不承诺抑制或移除该 banner。

## WSL 工具基线

基础工具：

- `git`、`rg`、`curl`、`wget`、`rsync`、`file`、`lsof`
- `python3`、`python3-venv`、`python3-pip`
- Linux 原生 `node`、`npm`、`pnpm`

通用诊断与构建工具：

- `jq`、`unzip`、`zip`、`tree`、`strace`
- `shellcheck`、`shfmt`、`fzf`、`fd`、`sqlite3`、`dos2unix`
- `build-essential`、`pkg-config`、`cmake`、`ninja`

机器工具由 `config/ai/wsl-tool-baseline.json` 声明。`provision-wsl.py` 默认只输出计划，后续 bootstrap 与 doctor 只检查工具是否存在、版本是否可用、路径是否来自 Linux；不得静默安装、重复安装或把 `pnpm` 解析到非 Linux 路径。

## Bootstrap、sync 与 doctor

- 在 `<harness-root>` 下执行 `python3 ./scripts/bootstrap-local.py --codex-home <已核实的Windows-home的WSL路径>`。
- harness 根按显式参数、`AI_HARNESS_ROOT`、脚本所在仓库选择；Codex home 仅使用显式参数或已核实的 `CODEX_HOME`；缺失则报错，不回退到 Linux 用户目录。
- 无效的显式路径直接失败；不扫描 sibling clone 或整盘目录。
- managed 全局 `AGENTS.md` 只有带 `<!-- ai-harness:managed-global-agents:v1 -->` marker 时才常规刷新；覆盖非空未托管文件前必须显式授权并创建可恢复备份。
- sync 按受管 skill 树投放，GTO schema 与恢复入口随包位于 schemas/ 和 scripts/；receipt 的 managed_files 记录包内文件真源、目标和 SHA-256；不接管未托管目录，不清理项目目录。
- 已有默认安装只发布 GTO 时，使用 `python3 scripts/sync-codex.py --harness-root <harness-root> --codex-home <codex-home> --skill global-task-orchestrator --json`。该入口仅更新 GTO 及其状态 schema，在同一锁内替换对应 receipt 记录并保留其他技能、schema 和元数据；不读取或重写其他技能的源码/安装内容。首次无 receipt 安装仍用默认全量同步。省略 `--skill` 的全量行为保持不变。
- doctor 只读审计入口、skill/schema 同步状态、receipt、安装版 GTO 的临时只读 `validate` 动作、规则索引结构、WSL 工具基线与正常链边界；project doctor 另行审计该项目声明的依赖、临时目录、Windows 工件和可选能力。两者都不自动修复。
- bootstrap 的 JSON 在 managed `AGENTS.md`、skill 或 schema 内容发生变化时返回 `restart_required=true` 和 `restart_reasons`；无变化时为 `false` 和空数组。已启动的长会话不会热更新这些内容。
- 遇到平台边界冲突，先核对磁盘上的 `CODEX_HOME/AGENTS.md` 与 `CODEX_HOME/.ai-harness/codex-sync.receipt.json`，再新建任务或重启 Codex。

## Command Failure Memory

- WSL Codex 直接用 Linux `python3` 运行 `skills/command-failure-memory/scripts/command-failure-memory.py`。
- 数据继续位于 `/mnt/c/Users/Laptop/.codex/memories/command-failure-memory`，不删除、不迁移、不建立第二份经验库。
- 复杂参数通过 Python argv 或 JSON 输入传递；失败后 `record-failure`，重试前 `query-before-retry`，验证成功后 `record-success`。
- 后端不可达时报告阻塞，不绕到另一实现，也不新建临时库。

## GTO v3

- 当前 GTO 只接受 `version=3` 的 `state.json`。
- 每个长任务必须同时存在 `state.json`、`task.md`、`events.jsonl`、`plan.md`、`execution.md`、`acceptance.md`；`events.jsonl` 必备。
- action 与参数只以 `orchestrator_ctl.py --help` 当前公开并实际实现的 GNU 双横线接口为准。
- 当前控制面不从历史 run、旧会话目录或第二套 package 恢复状态。

## 非目标

- 不接管 `.system/*`、插件或任意第三方 runtime 目录。
- 不安装 Docker、数据库服务、云 CLI 或账号工具。
- 不移动仓库、不复制 `CODEX_HOME`、不迁移 Command Failure Memory。
- 不把离线索引生成器变成运行时语义路由器。

## 最小验收

- 仓库活跃入口只描述 Codex/WSL 正常链。
- 用户旧运行时目录已按授权永久删除，CFM 数据目录保持原位。
- `RULES_INDEX.json` 是唯一机器元数据索引且不含正文；不存在运行时 Python matcher 或全正文聚合依赖。
- `always_on` 仅包含批准的三条最小必读规则，其余规则由 Codex 自由选读。
- 正式入口和验收链不调用 `.ps1`、`.cmd` 或 hook。
- WSL 工具基线全部可用，`pnpm` 解析到 Linux 路径，strict doctor 可审计。

## GTO revision 3 运行边界

新任务显式 workflow_revision=3、state version=3；历史记录保留，当前包不兼容旧合同。GTO 专属脚本、schema 和示例位于 skills/global-task-orchestrator 包内，公共安装/环境工具留在共享 scripts。源码包布局和隔离安装验证不等于实际 CODEX_HOME 已投放；发布与新进程加载另留真实证据。

GTO 命令按本轮实际读取的 SKILL.md 所在绝对目录设置 GTO_SKILL_DIR/GTO_CONTROLLER，再用独立 --repo-root 传消费项目。控制器从同一真实部署树加载schema；消费项目不需要skills目录，不从CWD或未核对的CODEX_HOME猜工具位置，也不扫描clone或混用不同候选。

文档校验的显式消费根与工具根分开：`validate_plan_docs.py --repo-root <consumer-root>` 和 `validate_doc_routing.py --repo-root <consumer-root>` 接受已有业务目录，不要求业务项目含 harness rules/skills 标记。工具脚本从已核对的 harness 真源位置执行；文件根和不存在的目录明确失败。该约定只用于这两个文档 CLI，不改变其他入口的 harness 根发现规则。

## Revision 3 行为证据与版本一致性

流程和开测出口统一见 [GTO 任务流程](../skills/global-task-orchestrator/references/workflow.md)。review 与验收分别保留真实操作证据；Windows 官方 Browser/Computer Use 在 Windows-native Agent environment 使用；非 UI CLI/API 按实际适用范围验证，不能互相冒充。

skill 效果验收先完成受管投放与版本、环境、输入和采证准备，准备问题在授权范围内自行修复复查；新顶层会话实际加载必须与候选/receipt 一致。仅源码、隔离安装或当前会话缓存不能证明全局已生效；正式首轮效果失败的报告与停止规则由流程真源裁决，不自动重跑。

需要 namespace 或只读白名单的隔离诊断时，按冻结合同保留 receipt 逻辑路径、受管文件哈希和实际可读边界证据；不把这种诊断机制强制替代平台新顶层效果验收。共享文件系统上的无历史会话只证明相应隔离等级，不能宣称物理不可访问。准备环境不复制认证、真实 CFM 历史或施工评分材料；实际依赖需由项目解释器验证，系统 Python 可导入不能代替项目 venv 可用。
## Windows 原生迁移的限定维护入口

维护标志存在时发布入口拒绝写入。先在隔离目标验证，再冻结候选、受控解除、正式定向发布，失败恢复标志。

- `python3 scripts/bootstrap-local.py --environment-only --harness-root <root> --codex-home <home> --json`：只投放环境 runtime 并更新其真实 receipt；不改动 AGENTS、hooks、插件 config、其他技能和 schema。
- `python3 scripts/sync-codex.py --retire-legacy-gui --harness-root <root> --codex-home <home> --json`：旧桥 MCP 已明确停用且技能符合既有 receipt 时，仅将旧技能移入私有恢复目录并更新该技能记录；未知改动拒绝退役。
- `python3 scripts/doctor-core.py --environment-only --root <root> --codex-home <home> --json`：只审计环境 runtime/receipt、Linux 工具和原生插件配置；不执行 GTO 或其 schema，不等价于全局 doctor 通过。

bootstrap/doctor 不修改原生插件配置。一次性迁移在私有备份和定点核对后删除旧 WSL GUI 桥配置、代码与技能；完成后不保留旧运行或发现入口。Windows 调用 WSL 时使用 `wsl.exe -d <distro> --cd <project> --exec python3 <script>`；复杂内容先写脚本文件，避免默认 shell 解释反引号、重定向或变量。

## 并发任务、固定运行版本与能力证明

当前操作合同见 [GTO 运行与证据](../skills/global-task-orchestrator/references/runtime-evidence.md)。普通流程职责维护于全局 AGENTS 模板；技能开关唯一声明在 `config/ai/skill-policy.json`，由 `scripts/configure-skill-policy.py` 更新实际 path 配置，插件升级后重新检查路径并用新会话验明。方法技能不能接管流程。磁盘配置、CLI 快照验证和真实新会话加载分别报告。

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](../skills/global-task-orchestrator/references/acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](../skills/global-task-orchestrator/references/streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。
