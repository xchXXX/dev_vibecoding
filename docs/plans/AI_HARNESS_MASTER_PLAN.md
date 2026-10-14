# AI Harness 总纲

本页是当前架构与维护入口。历史任务、旧发布记录和迁移日志只保存当时事实，不作为接收者依赖，也不据此宣称当前候选已通过。当前 portable 改造按 [设计规格](../modules/portable-harness/design/portable-harness-design.md) 实施，具体运行证据须另核验。

## 共同核心

同一仓库维护规则、方法、schema、公共 Python 代码及平台适配。默认完整安装 `base benchmark fix cfm gto`，高级用户可选择模块。Windows 原生、Linux 与 WSL 使用同一方法合同，平台差异限制在路径、锁、执行器与编码。基础规则及 benchmark/fix/cfm 不依赖 GTO。

Codex 负责语义判断和按需选读。公共 CLI `scripts/harness.py` 负责包构建、安装、更新、卸载、恢复与只读 doctor。安装层包含自足运行内容、技能及带哈希 receipt，不引用作者 checkout；消费项目只维护自己的边界和业务证据。

## 模块与流程边界

普通任务直接按用户授权推进，方法技能只提供测试、诊断、命中证明和失败经验，不另设审批、编排控制面或自动派发。GTO 只有显式选择才启用；六工件、真实身份、阶段和 preflight 均只在该流程内适用。在途任务沿用固定工具包，不由更新自动迁移。

全局入口、索引元数据及三条 always_on 规则为最小读取面；其余按语义选择。Python 离线生成和校验索引，不运行自然语言 matcher 或固定规则套餐。规则与技能均只有一个可编辑真源，standalone 是生成分发，不是第二套控制器。

## 安全与数据

生命周期仅管理清单拥有的文件与 AGENTS 标记区块。未知同名、哈希漂移、链接/路径逃逸、损坏元数据和未完成事务均须明确处理；不覆盖用户内容，不清空 hooks，不编辑 MCP 或 `config.toml`。多文件操作发生中断时报告真实恢复程度，不用单文件原子写冒充整个事务原子。

CFM 代码与个人记录分离，包不含作者历史、秘密、缓存或任务日志。运行快照、用户数据、未受管技能和原 AGENTS 正文不因更新/卸载被自动清理。

## 持续验收

合同与引用闭合、可重复包、模块独立、生命周期用户字节保全、冲突与恢复、真实 Windows/Linux/WSL、真实 Codex 新会话、真实 GTO、干净接收者分别留证。Linux 本机不能冒充云端会话；磁盘安装不能冒充技能加载；合成 ID 不能冒充独立代理。缺少能力时明确未验收。

发生未授权范围、未知 dirty 内容、文档/CLI 冲突或未闭合 review finding 时保留现场并协调，不扩大写入边界。开发、打包、安装、会话加载与发布是不同状态。

## 长期入口

- [架构](../ARCHITECTURE.md)
- [安装、更新与恢复](../INSTALL.md)
- [Codex 与环境边界](../CODEX_COMPAT.md)
- [消费项目适配](../PROJECT_TEMPLATE.md)
- [普通协作与显式 GTO](../SUBAGENT_GOVERNANCE.md)
- [评估与回归](../EVALS.md)
- [规则入口](../../rules/registry/RULES_ENTRY.md)
