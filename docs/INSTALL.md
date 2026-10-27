# INSTALL

> 当前使用 Windows 原生 Agent 与 WSL 开发环境。CODEX_HOME/.ai-harness/windows-native-transition.hold 存在时，下文 bootstrap/sync 命令会在写入前停止；不要删标志重试。按 [接续任务](tasks/20260910-windows-native-transition/task.md) 完成源码/安装/receipt 收口与隔离重复发布验证后解除。项目 WSL 命令和官方 Windows 插件使用不依赖这些安装命令。

## 目标

本文冻结 `ai-harness` 的纯 Codex/WSL bootstrap、sync、doctor 与本机工具基线合同。

## 新机器 Bootstrap

在已选定的 `<harness-root>` 下使用 WSL Python：

```bash
python3 ./scripts/bootstrap-local.py --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}"
```

- harness 根按显式 CLI 参数、`AI_HARNESS_ROOT`、脚本所在仓库的顺序选择。
- Codex home 必须通过显式 `--codex-home` 或已核实的 `CODEX_HOME` 指定；Windows Agent 调用 WSL 时传入该 Windows 目录的 WSL 等价路径。缺失即报错，不回退到 Linux 用户目录、不建立另一套安装。
- 无效的显式值直接失败；不扫描 sibling clone、整盘目录或其他工作区。
- bootstrap 渲染 managed 全局 `AGENTS.md`、写 machine-local receipt，并调用 Codex skill、规则索引与 doctor 链路。
- 非空未托管全局入口默认拒绝覆盖；只有显式 `--force-global-agents` 才先创建内容寻址备份再替换。
- Windows 原生 Agent 使用 PowerShell/文件工具及官方 Browser、Computer Use；项目 Git/Python/Node/测试构建通过指定 Ubuntu-24.04 的 wsl.exe --exec 在 Linux 执行，不替换为 Windows 项目依赖、旧 launcher、batch 或 hook。

## Codex 运行时映射

- 真源：`<harness-root>/skills/*`
- 运行时：`CODEX_HOME/skills/*`
- GTO schema 真源：`<harness-root>/skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json`
- GTO schema 运行时：`CODEX_HOME/skills/global-task-orchestrator/schemas/orchestrator-task-state.schema.json`
- managed 全局入口模板：`<harness-root>/templates/codex/AGENTS.global.md`
- 目标入口：`CODEX_HOME/AGENTS.md`

当前仓库维护的核心 skills 包括：

- `global-task-orchestrator`
- `command-failure-memory`
- `pre-dev-benchmark`
- `fix-closure-gate`

sync 只投放明确受管的 Codex skills、唯一 GTO schema 运行副本与入口文件，receipt 为 schema 记录真源、目标和 SHA-256；默认不接管未托管运行时目录，也不扩展到 `.system/*`、插件、任意目录同步或项目级清理。

bootstrap 的 JSON 在 managed `AGENTS.md`、skill 或 schema 内容发生变化时返回 `restart_required=true` 和具体 `restart_reasons`；无变化时保持 `false`。已有长会话不会热更新这些运行时内容。遇到平台边界冲突时，先核对磁盘上的 `CODEX_HOME/AGENTS.md` 与 `CODEX_HOME/.ai-harness/codex-sync.receipt.json`，再新建任务或重启 Codex。

## 规则索引合同

- `RULES_INDEX.json` 是唯一机器可读规则元数据索引，不内嵌规则正文。
- Python 只在离线维护或验收时生成、校验索引，不在正常交互链中解释自然语言或选择规则。
- Codex 固定读取 `AGENTS.md`、索引元数据及三条最小必读规则；其他规则由 Codex结合语义、目标内容、风险、阶段与本轮实际操作自由选读。
- sync 与 bootstrap 不生成固定任务规则套餐，也不安装全正文聚合运行时视图。

其他项目消费本仓全局规则时必须显式传入规则根：

```bash
harness_root=/path/to/ai-harness
project_root=/path/to/project
python3 "$harness_root/scripts/generate_rules_index.py" \
  --repo-root "$project_root" \
  --global-rules-root "$harness_root"
python3 "$harness_root/scripts/validate_rules.py" \
  --repo-root "$project_root" \
  --global-rules-root "$harness_root"
```

未提供 `--global-rules-root` 时只处理目标项目自己的规则，不自动发现其他 clone 或工作区。

## Doctor / validate

doctor 只读检查：

- managed 全局入口存在且 marker 正确。
- 真源 skill、运行时 skill 和关键文件基本一致。
- 唯一 GTO schema 真源、运行时副本及 sync receipt 一致，并真实运行安装版控制器的临时只读 `validate` 动作。
- `RULES_INDEX.json` 可解析、结构有效且不包含正文。
- 正式入口与验收链不调用 hook、`.ps1` 或 `.cmd`。
- WSL 工具基线存在、版本可执行、路径来自 Linux。

doctor 不自动修复、不安装工具、不接管项目目录，也不清理未托管运行时内容。

## 分层环境准备

完整合同和路径图见 [WSL 环境工程交付说明](modules/wsl-environment/delivery/engineering/wsl-environment-delivery.md)。不要把“工具命令能执行”误当成项目、浏览器或 Windows GUI 已就绪。

| 层级 | 真源/入口 | 操作边界 |
| --- | --- | --- |
| 机器公共工具 | `config/ai/wsl-tool-baseline.json`、`scripts/provision-wsl.py`、`scripts/doctor-core.py` | provision 默认输出计划；只有显式 apply 才能在批准范围内安装最小缺口 |
| 项目依赖隔离 | 项目 manifest/lock、`schemas/project-environment.schema.json`、`scripts/project-env-doctor.py` | 只在当前 WSL 项目内恢复和诊断，不复用 Windows 工件，也不自动删除旧目录 |
| 可选能力 | 项目环境声明 | Playwright、Docker、数据库、云 CLI 等必须声明且本次任务确实需要 |
| Windows 外部能力 | 官方 Browser、Computer Use、Desktop 运行时、原生插件声明 | Windows Agent 使用官方工具；harness 只读检查，不改 transport、安全设置、插件开关或注册 WSL GUI 桥 |

在新 worktree setup 完成后、GTO 长任务第一次运行代码前，或普通任务第一次触及运行时，运行一次 machine doctor；该项目第一次需要运行时时再运行 project doctor。不要把这些检查扩展为 hook、daemon、逐命令 wrapper、自动重试或自动修复。

Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；项目 Git/Python/Node/测试/构建继续通过指定发行版的 wsl.exe --exec 执行。外部能力声明 v3 只列 windows_native 与 required_plugins；bootstrap/doctor 不写插件配置或官方 transport，不创建 WSL GUI 桥。磁盘 enabled 不等于 GUI 验收。

## WSL 工具部署

已有并保留：

- `git`、`rg`、`curl`、`wget`、`rsync`、`file`、`lsof`
- `python3`、`python3-venv`
- Linux 原生 `node`、`npm`

如已获得对本机工具部署的明确授权，可在 Ubuntu WSL 中按 `provision-wsl.py` 的计划执行固定基线；不要把下列示例当成 bootstrap/doctor 的隐式副作用：

```bash
sudo apt update
sudo apt install -y jq unzip zip tree strace shellcheck shfmt fzf fd-find sqlite3 dos2unix \
  build-essential pkg-config cmake ninja-build python3-pip
```

然后在 **Linux 原生 Node.js 已安装且其 `node`/`npm` 不来自 `/mnt/c`** 的 shell 中，通过已批准的外部运行时或包来源安装 Linux 原生 `pnpm`：

```bash
curl -fsSL https://get.pnpm.io/install.sh | sh -
exec "$SHELL" -l
```

doctor 固定审计 `jq unzip zip tree strace shellcheck shfmt fzf fdfind sqlite3 dos2unix gcc g++ make pkg-config cmake ninja pip3 pnpm`，以及 `node npm pnpm` 的可用性和 Linux 原生路径。Corepack 不是机器基线要求；Ubuntu 的 `fd-find` 通常提供命令 `fdfind`，`fd` 是兼容替代。doctor 会将 `/mnt/c` 或 Windows Program Files 中的受审计 Node 工具报告为路径泄漏。bootstrap 与 doctor 之后只检查，不重复安装、升级发行版或自动修复项目依赖。

## 删除边界

- 旧代理平台的仓库资产和用户运行时不属于 Codex install/sync 合同。
- `/mnt/c/Users/Laptop/.claude` 将按用户授权永久删除，包括 `backups`、`sessions` 和整个目录；不生成备份。
- `/mnt/c/Users/Laptop/.codex/memories/command-failure-memory` 保持原位，不删除、不迁移、不复制。

## 非目标

- 不安装 Docker、数据库服务、云 CLI 或账号工具。
- 不做 Codex 运行时目录全盘 takeover。
- 不移动仓库、不复制整个 `.codex`；独立并行任务按授权使用隔离 worktree。
- 不在 bootstrap 或 doctor 中加入包管理器自动安装、自动重试或跨平台回退。

## 最小验收

- bootstrap、sync、doctor 可从 WSL Python 正常链运行。
- managed skills 和全局入口同步关系可审计。
- 规则索引只含元数据，运行时无 Python matcher 和固定规则套餐。
- 用户旧运行时删除边界与 CFM 保留边界清晰且互不重叠。
- WSL 工具全部可执行，Linux 原生 `pnpm` 可用。

## GTO 默认发布版本

GTO 当前默认发布版为 `workflow_revision=3`。新任务直接使用已安装 skill 中的 revision 3 合同，无需用户提醒版本。主工作区 `skills/global-task-orchestrator/` 是包含 schema 在内的唯一同步真源；开发 worktree 中的候选只有整合到此真源并执行 `python3 scripts/sync-codex.py --harness-root "$PWD" --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --json` 后才成为默认安装。

发布时整套同步 SKILL、agents 元数据、references、controller 和 schema，随后运行 `doctor-core.py` 核对同步回执和安装哈希，并用已安装的 revision 3 合同实际初始化及校验隔离任务。以后版本更新按同一发布链完成，不保留第二个旧版默认入口。已经启动的会话可能持有旧 skill 元数据；发布后新任务加载更新后的入口，已有会话需要重新读取或重启后刷新。

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

范围复验分发入口：

```sh
python3 skills/gto-standalone/build_release.py --refresh-source skills/global-task-orchestrator --output-dir .artifacts/scoped-acceptance/release
```

`--refresh-source` 显式指定通用真源；刷新 scripts、schemas、references、agents 和 SKILL.md 后，由既有 ZIP/manifest 生成器打包。包专属 README、依赖声明和 doctor 保留；SOURCE.json 记录当前源内容摘要。不得手工修改分发控制器；不得把源码路径写进运行时查找逻辑。独立目录运行包内十点示例，证明执行次数 10+2、路径自包含与冻结版本保护，再声明分发可用。
续跑与时间协议修复使用既有定向同步入口发布：

```sh
python3 scripts/sync-codex.py --harness-root <root> --codex-home <home> --skill global-task-orchestrator --json
```

需要同步全局入口模板时，另运行 `python3 scripts/bootstrap-local.py --harness-root <root> --codex-home <home> --git-workflow-only --json`。该入口同时核验其受管 Git 检查器；发布前确认该检查器属于本次范围或与已安装内容相同。不要为单技能更新调用全量 bootstrap。

发布者先备份安装内容与 receipt，并核验维护标志、所有权和其他技能状态；同步后分别核验实际安装文件及 receipt、新进程公开入口、旧冻结任务快照不变。新任务冻结当前安装版本；旧任务通过 `start_session.py` 恢复原快照，不自动升级，也不改写旧时间证据。磁盘同步不代表已运行会话已重新加载指令。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](../skills/global-task-orchestrator/references/streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。

任务工作区新增入口及版本边界见 [任务与工作区合同](modules/git-workflow/contract/task-workspace.md)。按既有 sync_git_workflow.py 生成并列 portable 脚本，按 git-workflow-only 定向发布；只安装已验收产物。新会话规则加载单独验收，旧 GTO 冻结包不改写，不能用安装成功代替行为通过。


## 20261027 性能改进

性能发布合同（20261027）：文件树无变化时不复制/替换受管目录；同轮源/安装清单复用。范围doctor不读取无关源包，仍核验未选中安装包的回执完整性。开发、隔离分发通过不等于共享安装或新会话加载已通过。

源码入口采用以下接口；本次源码验收结果见 `docs/tasks/20261027-harness-performance/task.md`，后续发布见该任务的 `release.md`，实际安装版本以本机回执及发布验收为准。bootstrap 在单一发布锁内调用 sync 与安装 audit，并保留整批发布回滚；源侧 strict 测试已移出该锁。

- 探针通过 `runtime_common.run_probe` 执行，接受单探针 `timeout` 和绝对单调时钟 `deadline`，取较早边界；到期终止整个进程组并回收父进程，报告超时失败，不留下后台子进程继续工作。项目环境和机器探针均适用。
- 实际 doctor 入口的共享探针预算、strict 测试独立预算及超时分类唯一见 [doctor 与启动边界](modules/wsl-environment/design/doctor-and-startup-boundaries.md#20261027-性能改进)；`deadline` API 的存在不单独构成入口总预算已接入的证明。
- bootstrap 的规则生成、规则校验和 strict 源侧合同测试在发布锁外完成。准备阶段记录源文件内容清单，测试结束及取得发布锁后重新核对同一代源码（包含测试和执行的工具代码）；变化时拒绝发布，不复用上一代测试结果。安装包内容检查及实际安装入口验证仍在锁内完成，并与已验证源侧结果合成原 strict 结论；不增加跳过源侧门禁的公开参数。
- sync 先计算源清单并复用其摘要构造回执，内容相同的受管目录不调用替换。目标清单不能跨独立发布事务缓存；发布时复核 hold 和回执代际，冲突失败保留既有安装。替换与回执提交失败须恢复本次已变更内容，不能留下混代安装。
- 清单复用仅限单次稳定读取阶段；内容变更、增删文件和链接换向不能被长期 mtime/size 缓存掩盖。隔离制品与实际共享安装的代际分别报告。
