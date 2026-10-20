# 清除 Claude、自由按需规则与 WSL 工具基线

Task ID: `20260901-215247-354735-claude-removal-rules-wsl-tools`

## 要做什么

建立纯 Codex/WSL 的轻量控制面：彻底删除 Claude 和剩余 Windows 正常入口；规则只固定读取 AGENTS、索引和极少必读项，其余由 Codex 结合语义、目标内容、风险、阶段和本轮操作自由选读；一次性部署本机 WSL 常用工具。

## 不做什么

- 不保留 Claude 兼容层或用户备份
- 不让 Python 推断自然语言、本轮操作或按任务类型拼规则套餐
- 不迁移 CFM 数据目录
- 不安装 Docker、数据库服务、云 CLI 或账号工具
- 不清理无关工作区改动

## 改哪些地方

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

## 怎么实现落地

先以 Red 证明 Claude/Windows 资产、21 条 always_on、全正文聚合和工具缺失；再并行实施清理、索引改造和工具部署。Codex 自由选读规则，Python 只离线生成与校验元数据索引。

## 怎么验收

- 仓库活跃入口和用户目录无 Claude 运行时资产
- 正式 Codex 控制面和验收链不调用 ps1/cmd
- RULES_INDEX.json 是唯一机器元数据索引且不含正文，RULES_RESOLVED.json 不存在
- always_on 仅为批准的最小必读集合，其他规则由 Codex 自由选读
- WSL 常用工具和 Linux pnpm 可用且 doctor 可审计
- 全量 Python、盲测、真实 runtime、独立 final/pass 通过

## 有什么风险

- 用户 .claude 永久删除不可恢复
- 工作区高度脏且必须保护无关修改
- apt/npm 全局安装需要一次 sudo 密码
- 旧 PowerShell 测试删除前必须确认 Python 等价覆盖

## 当前状态

- status: `completed`
- current_phase: `planning`
- next_action: `none`
