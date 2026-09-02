# INSTALL

## 目标

本文冻结 `ai-harness` 的纯 Codex/WSL bootstrap、sync、doctor 与本机工具基线合同。

## 新机器 Bootstrap

在已选定的 `<harness-root>` 下使用 WSL Python：

```bash
python3 ./scripts/bootstrap-local.py
```

- harness 根按显式 CLI 参数、`AI_HARNESS_ROOT`、脚本所在仓库的顺序选择。
- Codex home 按显式 CLI 参数、`CODEX_HOME`、当前 Linux 用户目录的顺序选择。
- 无效的显式值直接失败；不扫描 sibling clone、整盘目录或其他工作区。
- bootstrap 渲染 managed 全局 `AGENTS.md`、写 machine-local receipt，并调用 Codex skill、规则索引与 doctor 链路。
- 非空未托管全局入口默认拒绝覆盖；只有显式 `--force-global-agents` 才先创建内容寻址备份再替换。
- 正式 bootstrap 成功路径只使用 WSL `python3` 和 Linux 原生命令，不调用 hook、`.ps1` 或 `.cmd`。

## Codex 运行时映射

- 真源：`<harness-root>/skills/*`
- 运行时：`CODEX_HOME/skills/*`
- GTO schema 真源：`<harness-root>/schemas/orchestrator-task-state.schema.json`
- GTO schema 运行时：`CODEX_HOME/schemas/orchestrator-task-state.schema.json`
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

## WSL 工具部署

已有并保留：

- `git`、`rg`、`curl`、`wget`、`rsync`、`file`、`lsof`
- `python3`、`python3-venv`
- Linux 原生 `node`、`npm`

在 Ubuntu WSL 中一次性安装固定基线：

```bash
sudo apt update
sudo apt install -y jq unzip zip tree strace shellcheck shfmt fzf fd-find sqlite3 dos2unix \
  build-essential pkg-config cmake ninja-build python3-pip
```

然后在 **Linux 原生 Node.js 已安装且其 `node`/`npm`/`corepack` 不来自 `/mnt/c`** 的 shell 中安装 Linux 原生 `pnpm`：

```bash
curl -fsSL https://get.pnpm.io/install.sh | sh -
exec "$SHELL" -l
```

doctor 固定审计 `jq unzip zip tree strace shellcheck shfmt fzf fdfind sqlite3 dos2unix gcc g++ make pkg-config cmake ninja pip3 pnpm`，以及 `node npm pnpm corepack` 的可用性和 Linux 原生路径。Ubuntu 的 `fd-find` 通常提供命令 `fdfind`；`fd` 是兼容替代。doctor 会将 `/mnt/c` 或 Windows Program Files 中的 Node 工具（包括 Windows `corepack`）报告为路径泄漏。bootstrap 与 doctor 之后只检查，不重复安装。

## 删除边界

- 旧代理平台的仓库资产和用户运行时不属于 Codex install/sync 合同。
- `/mnt/c/Users/Laptop/.claude` 将按用户授权永久删除，包括 `backups`、`sessions` 和整个目录；不生成备份。
- `/mnt/c/Users/Laptop/.codex/memories/command-failure-memory` 保持原位，不删除、不迁移、不复制。

## 非目标

- 不安装 Docker、数据库服务、云 CLI 或账号工具。
- 不做 Codex 运行时目录全盘 takeover。
- 不移动仓库，不复制整个 `.codex`，不自动创建 worktree。
- 不在 bootstrap 或 doctor 中加入包管理器自动安装、自动重试或跨平台回退。

## 最小验收

- bootstrap、sync、doctor 可从 WSL Python 正常链运行。
- managed skills 和全局入口同步关系可审计。
- 规则索引只含元数据，运行时无 Python matcher 和固定规则套餐。
- 用户旧运行时删除边界与 CFM 保留边界清晰且互不重叠。
- WSL 工具全部可执行，Linux 原生 `pnpm` 可用。
