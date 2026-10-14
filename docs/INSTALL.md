# 安装与生命周期

本文描述 portable harness 的接收者合同。当前改造仍需按候选版本完成验收；下列命令是冻结 CLI 接口，不能以本说明替代实际运行结果。取得固定版本的完整包，在包根执行；不要求接收者拥有源码仓库。

若使用 dots 云端直接从 Git 拉取本仓库，走 [Git 仓库的 dots 云端接入](https://github.com/xchXXX/dev_vibecoding/blob/javirs/docs/modules/portable-harness/delivery/engineering/dots-cloud.md)：一条 Install script 准备仓库环境，仓库内技能随 Git 发现，不需要先构建或安装 portable 包。云接入脚本只随源码仓库提供；以下流程用于将固定分发包安装到明确的 Codex home，两条路线的验收分别留证。

## 依赖与环境

基础安装与 doctor 使用 Python 3.11+ 标准库。先确认所用解释器及真实 Codex home；Windows 示例可用 `python`，Linux/WSL 可用 `python3`。示例统一写 `python`，应替换为当前环境已核实的解释器。基础入口不要求 Node、Docker、GUI、WSL 或任意 MCP。GTO 等可选动作所需依赖由对应技能与 doctor 报告，不能自动安装。

执行环境可选 `auto`、`windows`、`linux`、`wsl`。`auto` 检测当前进程，不根据作者机器偏好选择 WSL。Windows 原生与 WSL 各自使用本环境解释器、依赖和路径；跨边界时只使用已核实的路径映射。

## 两步主流程

在发布包根，将 `<codex-home>` 替换为当前环境下已核实的绝对路径：

```text
python scripts/harness.py install --codex-home "<codex-home>" --json
python scripts/harness.py doctor --codex-home "<codex-home>" --json
```

默认完整安装 `base benchmark fix cfm gto`。然后新开 Codex 会话，确认全局入口及技能已加载，执行下方普通任务示例。磁盘安装成功与 `doctor` 完整性通过都不能证明会话加载；没有新会话证据时保持 `session_verified=false`。

最多三项接入配置：

| 字段 | 含义与默认 |
| --- | --- |
| `codex_home` | 目标 Codex home；必须显式配置或提供 `CODEX_HOME`，不猜用户目录 |
| `skills_dir` | 技能目录；默认 `<codex_home>/skills` |
| `environment` | 当前执行环境；默认 `auto` |

CLI 参数高于用户 JSON，用户 JSON 高于允许环境变量，最后才是已验证默认值。项目配置不得覆盖全局安装位置。JSON 中的相对路径相对该配置文件解析，未知字段拒绝。`CODEX_HOME` 是 home 的环境输入；其他允许环境变量以当前 CLI/配置合同为准，不继承任意环境值。

可选 JSON（保存为自己的本地配置，不放入发布包）：

```json
{"codex_home":"/absolute/codex-home","environment":"linux"}
```

使用 `--config <path>` 传入。高级用户可用 `--skills-dir` 和 `--modules` 选择位置与模块；具体列表语法用 `python scripts/harness.py install --help` 核实。这些高级参数不是首次安装必填项。

## 安装内容与所有权

- `<codex_home>/.ai-harness/portable/runtime/`：规则、模板及配套运行内容。
- `<skills_dir>/`：所选技能的自包含安装副本。
- `<codex_home>/.ai-harness/portable/receipt.json`：受管文件、模块版本、安装根与哈希。
- `<codex_home>/AGENTS.md`：只管理明确标记的区块，保留区块外原始内容。

首次遇到同名未知技能或冲突管理块时停止并列出冲突，不推定所有权。更新和卸载先检查所有受影响文件；漂移时保留用户内容并整体拒绝受影响操作，不部分删除。安装器不修改 `config.toml`、hooks、MCP、插件开关、个人记忆或其他技能。

CFM 程序属于 `cfm` 模块，记忆数据属于用户。新用户从空数据开始；升级或卸载不携带、删除或自动迁移个人记录。共享同一安装范围时只允许一个发布者；任务使用自己的固定运行版本，不能删除仍被在途任务引用的快照。

## 更新、卸载与恢复

保留原安装配置，进入要安装的新固定版本包根运行：

```text
python scripts/harness.py update --codex-home "<codex-home>" --json
python scripts/harness.py uninstall --codex-home "<codex-home>" --json
python scripts/harness.py recover --codex-home "<codex-home>" --json
```

`install`、`update`、`uninstall` 可先用 `--dry-run` 预览；单模块操作用 `--modules`，不改变未选模块。配置了自定义技能目录或环境时，后续动作继续使用同一配置。保留固定版本包及 receipt 以供核验。

生命周期采用互斥、预检、staging、备份、替换、校验和完成凭据。单文件原子替换不代表整个多文件事务原子。失败时尝试恢复本次受管变更；未完成 journal 阻止继续安装，使用 `recover` 处理。备份损坏、外部变更或部分恢复须明确报告，不删 journal 假装成功。

旧 `bootstrap-local.py`、`sync-codex.py` 与旧 receipt 不构成 portable 安装所有权。不要手改 receipt 或直接覆盖旧安装；先保留原现场并使用独立目标验证。若发现旧 `windows-native-transition.hold`，它是该用户的维护约束，应读取标志指定的记录并暂停受影响旧发布链；不复制作者历史任务，也不通过删除标志绕过维护。

## 新会话示例

普通任务输入：“为一个读取配置文件的函数设计最小测试，列出输入、成功条件和失败边界，暂不实现。”应按需求选规则或 benchmark 方法，直接产出相称结果；不创建 GTO task_id、六工件，不要求编排 preflight。

修复任务输入：“一个 fallback 修复的大套测试已通过，但不确定是否命中，请列出最小验证合同。”应能得到复现、命中证明、诊断和验收的区分；未安装 GTO 也可完成。

GTO 单独示例：“我明确选择 GTO，请先为一个隔离小任务准备方案。”须使用实际安装的 GTO 技能及平台真实代理能力，按其批准合同推进。没有真实代理能力就报告对应流程未验收，不能由主代理冒充各角色。

## 诊断与结果边界

人读与 `--json` 对应同一结果，成功退出码为 0，其余非零。诊断至少分清配置/路径错误、依赖缺失、未知冲突、受管漂移、锁占用、包完整性失败与恢复不完整。出现失败先保留输出和现场，再按最小建议处理，不无限重试、提权或换环境掩盖错误。

源码维护者从固定候选使用 `build --output <空目录> --version <版本> --source-commit <提交>` 构建白名单包。`source_commit` 必须是真实可解析的 Git 提交，并与纳入发布的内容一致；不得把脏工作区内容打包却标为旧 HEAD。先冻结真实提交，再构建并核验清单；包目标必须新建或为空，不覆盖已有产物。发布包的文件哈希不是发布者签名。Windows、Linux、WSL 运行、真实云端与新 Codex 会话应分别留证，未测项明确未验收。
