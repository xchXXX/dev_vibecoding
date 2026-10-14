# 架构

Harness 采用一个源码真源、一个可重复构建的共享核心和按平台适配的生命周期入口。普通规则与方法可以独立消费；GTO 是用户显式选择的编排模块。规格见 [portable harness 设计](modules/portable-harness/design/portable-harness-design.md)，接收者入口见 [INSTALL](INSTALL.md)。规格和文档不替代当前候选的运行验收。

## 三层

| 层 | 职责与边界 |
| --- | --- |
| 源码 | `rules/`、`skills/`、`schemas/`、`templates/`、`scripts/`、`modules/harness/` 和测试；只维护通用值与相对路径 |
| 安装 | `<codex_home>/.ai-harness/portable/runtime/` 和配置的技能目录；清单、receipt、哈希、事务与备份可审计，不依赖源码 checkout |
| 消费项目 | 项目 AGENTS、增量规则、业务实现及自己的证据；不复制共享方法为第二真源，不改变全局安装位置 |

`AGENTS.md` 的受管区块负责发现已安装规则与技能。区块外内容归用户所有；其他技能、hooks、MCP、个人配置与记忆不在安装所有权内。安装层是生成副本，不手工维护为源码。

## 模块

| 模块 | 内容 | 启用边界 |
| --- | --- | --- |
| `base` | 最小协作入口、规则元数据与叶子、公共运行内容 | 默认安装；普通任务自由选读 |
| `benchmark` | pre-dev-benchmark 及本技能 references、assets、scaffold | 需要实现前可测方案时使用；不依赖 GTO |
| `fix` | fix-closure-gate 的复现、命中证明与证据合同 | 需要修复闭环时使用；普通证据与 GTO 映射分开 |
| `cfm` | command-failure-memory 程序和方法 | 真实失败链；用户数据独立于代码和分发包 |
| `gto` | global-task-orchestrator、schema、controller 与 references | 安装默认包含，编排仅在用户显式选择后启动 |

默认完整安装，模块选择是高级参数。单模块更新/卸载不改其他模块。主版 GTO 与 standalone 从共同真源生成分发，不能各自维护控制器；生成过程仍须保留既有运行快照、receipt 核验、Unicode 和超时进程树清理行为。

## 配置、适配与生命周期

公共 CLI 为 `scripts/harness.py`：`build/install/update/uninstall/recover/doctor`。配置仅含接入所需 `codex_home`、`skills_dir`、`environment`；CLI 高于用户 JSON、允许环境变量和默认值。home 不猜测，项目配置不能扩大安装边界。完整操作与恢复说明见 [INSTALL](INSTALL.md)。

Python 3.11+ 共享逻辑处理清单、所有权、模块和结果。环境适配仅处理路径、锁、子进程树、解释器解析和编码。Windows 原生、Linux、WSL 使用各自工具和依赖；项目自行选择环境。基础安装/doctor 不强制 Node、Docker、GUI、WSL 或 MCP。

生命周期先预检全部受影响资产，再 staging、备份、替换、验证并写完成凭据。未知同名、用户漂移、链接越界、大小写碰撞和损坏元数据不能扩大写入/删除范围。失败回滚与恢复不完整分别报告；单文件原子写不冒充整事务原子。固定包与安装版本可追溯，在途 GTO 任务不自动迁移。

## 规则与流程

固定读取全局与项目入口、索引元数据及三条 always_on 规则；其余规则由 Codex 按语义选择。索引只由离线脚本生成，正常交互不运行 matcher 或固定规则套餐。其他项目只消费 `scope != project`，需要离线合并时显式指定规则根。

普通任务按授权、范围与风险交付，使用相称文档和验证；方法技能不创建控制面或擅自组织代理。只有显式 GTO 任务维护六工件、阶段与 preflight，运行同一冻结版本，遵循实际安装技能的流程和 schema。治理入口见 [SUBAGENT_GOVERNANCE](SUBAGENT_GOVERNANCE.md)。

## 数据、目录和证据

正式代码、模块长期文档、任务期说明、冻结夹具及临时产物按 [通用落点规则](../rules/items/architecture/通用文件存储位置.md) 分层。仅 GTO 状态位于 `docs/ai/tasks/`；普通任务不为接入预建该目录。CFM 数据保留在用户明确选择的 home 下，不随程序打包、迁移或卸载。

磁盘完整性、当前进程可运行、新会话实际加载、真实 GTO 与业务验收分别取证。原始任务和历史日志保持历史事实，不作为发布物的隐式依赖。完整验收层次见 [EVALS](EVALS.md)。
