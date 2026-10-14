# ai-harness

`ai-harness` 为 Codex 提供可跨项目、跨执行环境复用的规则和方法技能。共享核心支持 Windows 原生、Linux 与 WSL 适配；实际支持状态以对应版本的运行及会话证据为准。

默认安装全部模块：`base`、`benchmark`、`fix`、`cfm`、`gto`。普通任务直接使用基础规则与适用方法；安装 GTO 不等于启用编排，只有用户显式选择 GTO 才创建它的控制工件。

接收者从固定版本包根使用 `scripts/harness.py`，首次主流程为安装、doctor 两次调用，再新开 Codex 会话。完整命令、依赖与故障处理见 [安装说明](docs/INSTALL.md)。本版可移植改造的实现和验收尚在推进；文档合同不表示真实平台、云端或新会话已经通过。

dots 云端从 Git 使用本仓库：检出 `javirs`，Install script 填 `python3 scripts/cloud-setup.py`，Start skill 运行同一命令加 `--check`，发布环境后新开任务。四个技能通过仓库 `.agents/skills` 引用唯一真源，不需要安装到作者或用户全局目录。完整配置、可直接发送给 dots 的验收请求和结果边界见 [dots 云端接入](docs/modules/portable-harness/delivery/engineering/dots-cloud.md)。

- [架构与模块边界](docs/ARCHITECTURE.md)
- [Codex 运行与环境合同](docs/CODEX_COMPAT.md)
- [消费项目最小适配](docs/PROJECT_TEMPLATE.md)
- [评估层次](docs/EVALS.md)
- [协作与可选 GTO 治理](docs/SUBAGENT_GOVERNANCE.md)
- [总纲](docs/plans/AI_HARNESS_MASTER_PLAN.md)
- [规则入口](rules/registry/RULES_ENTRY.md)

规则、技能与生成模板各自只有一个源码真源。安装层是带清单和哈希的自包含副本，不依赖作者 checkout、用户名、个人记忆或历史任务。更新与卸载只处理明确拥有且内容未漂移的资产；用户 AGENTS 正文、hooks、MCP、其他技能和数据保持在原所有权边界内。
