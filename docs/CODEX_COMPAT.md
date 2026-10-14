# Codex 运行合同

`ai-harness` 的共享核心是规则、方法、schema 和 Python 入口。Windows 原生、Linux、WSL 的差异限于路径、锁、子进程清理、可执行文件解析和编码等适配层。用户选择运行环境；本仓作者的 WSL 开发习惯不是分发前提。安装教程和生命周期边界唯一见 [INSTALL](INSTALL.md)。

## 三层与发现

源码层维护 `rules/`、`skills/`、`schemas/`、`scripts/`、`templates/`。安装层的规则根位于 `<codex_home>/.ai-harness/portable/runtime/`，技能位于配置的 `skills_dir`；入口由安装器渲染，不引用作者 checkout。消费项目只维护项目边界、增量规则、配置与业务证据。项目不必为普通任务预建 GTO 状态目录。

Codex 读取全局和项目 `AGENTS.md`、可用 `RULES_INDEX.json` 元数据及三条固定规则：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。其他规则按语义、风险、阶段和当前操作自由选读；`linked_skill` 是发现提示，不是自动安装、启动或固定套餐。

Python 只离线生成和校验索引。正常对话不运行 matcher、生成 `task_profile` 或聚合全部正文。消费项目若离线合并全局规则，明确传入 `--global-rules-root <已安装规则根>`，仅消费 `scope != project`；不扫描其他 clone。

## 普通任务与 GTO

`base`、`benchmark`、`fix`、`cfm` 可以在没有 GTO 时独立使用。方法技能提供测试、诊断、命中证明和失败经验，不决定任务阶段、不擅自派发代理、不新增审批控制面。规则中的 GTO 链接只在用户显式选择且已安装该模块时读取；缺少可选模块不能使普通流程失效。

GTO 只在用户显式选择后使用，阶段、六工件、真实身份与 preflight 遵循实际安装技能的合同。在途任务沿用冻结版本，不由安装更新自动迁移。具体 GTO 证据要求见 [协作治理](SUBAGENT_GOVERNANCE.md)。

## 环境与能力

- Windows 原生使用 Windows 路径及解释器；Linux/WSL 使用 Linux 路径及解释器。项目环境和依赖由项目声明，虚拟环境及 `node_modules` 不跨操作系统混用。
- 选择 Windows Agent + WSL 项目时，先核实发行版、项目目录和 home 映射，再用 `wsl.exe -d <发行版> --cd <目录> --exec <解释器> <入口>`。不因命令失败自动换平台。
- Browser、Computer Use、截图及 MCP 使用当前宿主真实暴露的能力；不修改 app-managed transport、插件缓存或安全设置来制造通过。GUI 不可用只阻塞依赖它的场景。
- 基础 doctor 只读检查安装和依赖，不安装工具或修复项目。项目需要运行时，再按项目约定检查对应环境；没有选择 WSL 的用户不承担 WSL 工具清单。
- 文件存在、当前进程可运行、真实新会话已加载是三种证据。已有会话可能缓存旧指令；更新后新会话仍须单独验证。

## 旧环境与恢复

Portable 生命周期不接管旧 bootstrap/sync receipt 或历史任务。旧维护标志只约束对应旧发布链，不代表 portable 或全局 doctor 已通过。发现不明安装或未知改动时保留现场，依 [安装与恢复合同](INSTALL.md#更新卸载与恢复) 给出冲突和下一步；不复制历史任务充当产品依赖。

基础链不注册 hooks，不清空已有 hooks，不编辑用户 `config.toml`、MCP 或其他代理的目录。CFM 数据不随程序分发，不做个人记忆同步。
