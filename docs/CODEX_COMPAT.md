# CODEX_COMPAT

## 目标

本文冻结 `ai-harness` 的纯 Codex/WSL 运行合同。正常控制链只依赖 Codex 可读取的 `AGENTS.md`、规则元数据索引、按需规则与 skills，以及 WSL Python 3 标准库脚本和 Linux 原生命令。

## 冻结结论

- 仓库和用户运行时不保留其他代理平台的兼容层、hooks、settings、agents catalog 或回退入口。
- `/mnt/c/Users/Laptop/.claude` 在清理批次中永久删除，包括其中的 `backups` 与 `sessions`，不创建备份、不提供恢复合同。
- Codex 正常链不注册 hook，不设置受控 command runner，不调用 `.ps1` 或 `.cmd`。
- 规则选择由 Codex 自己完成；Python 不解释自然语言，不判断本轮操作，也不在运行时拼装规则集合。
- Python 只在离线维护或验收时生成、校验 `RULES_INDEX.json`。

## 三层映射

### 全局真源层

- `<harness-root>/skills/*`：Codex skills 真源。
- `<harness-root>/rules/items/<kind>/*`：规则正文真源。
- `<harness-root>/rules/registry/RULES_INDEX.json`：唯一机器可读规则元数据索引。
- `<harness-root>/schemas/*`、`scripts/*`、`templates/*`：schema、WSL Python 控制脚本和模板真源。

### 运行时投放层

- `CODEX_HOME/skills/*`：受管 skills 运行时副本。
- `CODEX_HOME/schemas/orchestrator-task-state.schema.json`：安装版 GTO 使用的唯一受管 schema 运行时副本。
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

- Codex 日常文件操作、Git、Python、Node、测试、构建、bootstrap、sync、doctor、GTO、规则维护和 Command Failure Memory 全部使用通用 WSL 开发发行版中的 Linux 原生工具。
- 仓库保持单副本，可继续位于 `/mnt/<drive>/...`；不搬库、不扫描其他 clone、不自动创建 worktree。
- 正式入口、成功路径和验收命令不得调用 PowerShell、batch、`.ps1`、`.cmd` 或 hook。
- 普通非零退出码进入命令失败闭环，不切换平台重跑，不增加自动 retry、逐命令 preflight、守护进程或通用 wrapper。
- 新进程必须核对实际 `CODEX_HOME`、Linux 用户、工作目录和规则加载位置；不从另一环境的默认值推定，也不整目录复制 `.codex`。
- 项目依赖必须使用 WSL 侧安装；不混用其他平台的 `node_modules`、venv 或原生依赖。

## WSL 工具基线

基础工具：

- `git`、`rg`、`curl`、`wget`、`rsync`、`file`、`lsof`
- `python3`、`python3-venv`、`python3-pip`
- Linux 原生 `node`、`npm`、`pnpm`

通用诊断与构建工具：

- `jq`、`unzip`、`zip`、`tree`、`strace`
- `shellcheck`、`shfmt`、`fzf`、`fd`、`sqlite3`、`dos2unix`
- `build-essential`、`pkg-config`、`cmake`、`ninja`

安装只在本机工具部署批次执行一次。后续 bootstrap 与 doctor 只检查工具是否存在、版本是否可用、路径是否来自 Linux；不得静默安装、重复安装或把 `pnpm` 解析到非 Linux 路径。

## Bootstrap、sync 与 doctor

- 在 `<harness-root>` 下执行 `python3 ./scripts/bootstrap-local.py`。
- harness 根按显式参数、`AI_HARNESS_ROOT`、脚本所在仓库选择；Codex home 按显式参数、`CODEX_HOME`、当前 Linux 用户目录选择。
- 无效的显式路径直接失败；不扫描 sibling clone 或整盘目录。
- managed 全局 `AGENTS.md` 只有带 `<!-- ai-harness:managed-global-agents:v1 -->` marker 时才常规刷新；覆盖非空未托管文件前必须显式授权并创建可恢复备份。
- sync 只投放受管 Codex skills 与 `orchestrator-task-state.schema.json`，receipt 为每份受管 schema 记录真源、目标和 SHA-256；不接管未托管目录，不清理项目目录。
- doctor 只读审计入口、skill/schema 同步状态、receipt、安装版 GTO 的临时只读 `validate` 动作、规则索引结构、WSL 工具基线与正常链边界；doctor 不自动修复。
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
