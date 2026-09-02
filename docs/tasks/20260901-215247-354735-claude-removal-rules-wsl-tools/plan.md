# 清除 Claude、自由按需规则与 WSL 工具基线

Task ID: `20260901-215247-354735-claude-removal-rules-wsl-tools`

## 背景与问题

本任务只保留 Codex/WSL 正常链。规则运行时固定读取 `AGENTS.md`、`RULES_INDEX.json` 和索引中极少数必读规则；其余规则由 Codex 结合对话语义、目标内容、风险、当前阶段与本轮操作自由决定是否读取。Python 不做自然语言分类，也不在每个任务或每条规则读取时运行。

## 任务目标

建立纯 Codex/WSL 的轻量控制面：彻底删除 Claude 和剩余 Windows 正常入口；规则只固定读取 AGENTS、索引和极少必读项，其余由 Codex 结合语义、目标内容、风险、阶段和本轮操作自由选读；一次性部署本机 WSL 常用工具。

## 非目标

- 不保留 Claude 兼容层或用户备份
- 不让 Python 推断自然语言、本轮操作或按任务类型拼规则套餐
- 不迁移 CFM 数据目录
- 不安装 Docker、数据库服务、云 CLI 或账号工具
- 不清理无关工作区改动

## 范围

- agents
- hooks
- scripts
- tests
- docs
- templates
- rules
- skills
- 真实 /mnt/c/Users/Laptop/.claude
- Ubuntu WSL packages
- 真实 /mnt/c/Users/Laptop/.codex runtime

## 方案摘要

先以 Red 证明 Claude/Windows 资产、21 条 always_on、全正文聚合和工具缺失；再并行实施清理、索引改造和工具部署。Codex 自由选读规则，Python 只离线生成与校验元数据索引。

## 验收标准

- 仓库活跃入口和用户目录无 Claude 运行时资产
- 正式 Codex 控制面和验收链不调用 ps1/cmd
- RULES_INDEX.json 是唯一机器元数据索引且不含正文，RULES_RESOLVED.json 不存在
- always_on 仅为批准的最小必读集合，其他规则由 Codex 自由选读
- WSL 常用工具和 Linux pnpm 可用且 doctor 可审计
- 全量 Python、盲测、真实 runtime、独立 final/pass 通过

## 约束与依赖

- 用户 .claude 永久删除不可恢复
- 工作区高度脏且必须保护无关修改
- apt/npm 全局安装需要一次 sudo 密码
- 旧 PowerShell 测试删除前必须确认 Python 等价覆盖

## 当前状态

- status: `active`
- current_phase: `planning`
- next_action: `dispatch_ready_subtask`

## 方案结构

1. 删除仓库 Claude 真源、hooks、agents、脚本、测试、模板和活跃文档引用；永久删除 `/mnt/c/Users/Laptop/.claude`。
2. 删除已由 Python 等价覆盖的 Codex/GTO/CFM/rules/ops `.ps1/.cmd` 与旧 PowerShell 测试，不保留双轨入口。
3. 保留 `RULES_INDEX.json` 为唯一机器元数据索引；`RULES_INDEX.md` 仅为人读生成视图；停止生成并删除包含全部正文的 `RULES_RESOLVED.json`。
4. 索引保存规则摘要、路径、关联 skill、适用语义/路径/操作提示；提示只供 Codex 判断，不构成 Python 强制映射。
5. `always_on` 只保留批准的最小必读项；问答、小改、修复、长任务由 blind behavior 验证实际读取范围，而不是验证固定套餐。
6. Ubuntu WSL 一次安装常用工具，之后 bootstrap/doctor 只检查，不重复安装。

## WSL 工具基线

- 已有且保留：`git`、`rg`、`curl`、`wget`、`rsync`、`file`、`lsof`、`python3`、`python3-venv`、Linux `node`/`npm`。
- 本次安装：`jq`、`unzip`、`zip`、`tree`、`strace`、`shellcheck`、`shfmt`、`fzf`、`fd-find`、`sqlite3`、`dos2unix`、`build-essential`、`pkg-config`、`cmake`、`ninja-build`、`python3-pip`。
- 安装 Linux 原生 `pnpm`，最终 PATH 不得命中 Windows `corepack`/`pnpm`。

## 删除边界

- 用户已明确授权永久删除 `/mnt/c/Users/Laptop/.claude/backups`、`sessions` 和整个 `.claude` 目录，不生成备份。
- CFM 仍使用 `/mnt/c/Users/Laptop/.codex/memories/command-failure-memory`，不得删除或迁移。
- 无关历史工作区修改不清理、不重置、不覆盖。

## 风险与回退

- 删除只针对已核对的精确路径；范围不明时停止，不扩大删除。
- PowerShell/CMD 旧入口只在 Python 等价覆盖验证后删除；验证失败时保留失败证据并返工。
- 工具部署失败时保留 apt/npm 原始退出状态，不把 Windows 工具路径当作成功。

## 阶段划分

1. 文档合同与三组预期 Red。
2. 清理、规则、工具三个互斥实施批次并行 Green。
3. 全量、真实 runtime、blind behavior 验收。
4. 独立 review，按 finding_id 返修和 re-review，最终 final/pass。

## 需先同步的核心文档与测试

- 核心文档：`AGENTS.md`、`RULES_ENTRY.md`、Codex 全局模板、架构/兼容/安装/审查治理文档。
- 核心测试：Claude/Windows 清零、规则运行时、WSL 工具、GTO 六工件一致性。
