# GTO 独立分发版

将整个 `global-task-orchestrator` 文件夹复制到你的 Codex 用户级技能目录；该目录内应直接看到 `SKILL.md`，不要多嵌套一层。无需安装 ai-harness、全局 AGENTS 或其他 skill。

当前官方文档列出的用户级目录是 `~/.agents/skills/`（Windows 为用户主目录下的 `.agents\skills\`）。部分 Codex 环境也从 `CODEX_HOME/skills`（通常 `~/.codex/skills`）加载。以你实际版本的技能列表为准，只选择一个位置，避免两份同名技能。参见 [官方技能目录说明](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。若复制后未出现，重启 Codex 并重新检查列表。

## 首次准备

运行脚本的环境需要 Python 3.11+、Git 和包内 `requirements.txt` 指定的 Python 依赖。Python 与 Git 必须处于同一实际执行环境；Windows 原生、WSL/Linux 不共用虚拟环境。依赖已满足时无需安装任何东西。

先运行轻量自检（路径换成实际安装目录）：

```sh
python "/absolute/path/global-task-orchestrator/scripts/doctor.py" --json
```

Linux/WSL 如果只有 `python3`，使用 `python3`；Windows 可用已核实的 `python` 或 `py -3`。自检只读，不安装软件、不修改 Codex 设置，也不能证明子代理工具已可用。

如果缺少 Python 包，优先使用已有、符合要求的项目虚拟环境。否则在用户选择的运行环境目录新建虚拟环境（不要放进 skill 文件夹），使用该环境的 Python 执行：

```sh
python -m pip install -r "/absolute/path/global-task-orchestrator/requirements.txt"
```

安装依赖需要可用的包源或事先准备的离线包。后续控制器和自检必须使用同一个 Python 解释器。

## 开始使用

在消费项目中显式请求：`使用 $global-task-orchestrator 为这个任务制定方案：……`。技能保持显式启用，不会把普通任务自动升级成 GTO。

完整执行需要宿主实际提供无历史子代理创建能力，能够返回真实代理身份，并支持后续继续同一代理。没有该能力时可以讨论方案，但不能宣称独立 Review 或验收已完成。浏览器等能力仅在任务确实需要时检查。

操作入口见 [SKILL.md](SKILL.md)，执行方式见 [控制器指南](references/controller-guide.md)。此包既不启动 Codex，也不注入或伪造平台工具。

## 更新、卸载与状态

新任务使用当前安装版本。已有任务沿用消费项目内的六工件；冻结后的任务按记录使用运行快照，不能复制状态到另一工作区后继续冒充同一任务。通过 harness 安装的技能使用同一安装器更新与卸载，由 receipt 核验所有权和文件漂移。手工安装则先备份并核对文件归属、未知改动和正在使用它的未冻结任务；确认边界后更新，重新自检和检查新会话加载。

手工卸载仅处理已核实属于该次安装的文件，未知内容保留。消费项目中的任务、证据和运行快照不会随之删除；正在进行的任务应先妥善收尾。不要覆盖另一来源的同名 skill。

唯一可编辑真源是 ai-harness 仓库的 `skills/global-task-orchestrator`。独立 standalone 分发副本由仓库维护者运行 `python scripts/generate-gto-standalone.py` 生成，附带 `SOURCE.json` 精确文件哈希与来源信息；`--check` 只读检查缺失、额外文件和字节漂移，发布入口核验生成一致性，不得手工修改副本。通过 portable harness 分发的 GTO 技能使用分发包根 manifest 与安装 receipt 记录完整性和所有权，技能目录不附带 standalone 的 `SOURCE.json`。基本运行不需要 ai-harness 安装 receipt；需要验证原安装态的实验与普通内容快照的边界见 [运行与证据合同](references/runtime-evidence.md)。脚本检查通过与宿主新会话实际加载成功是两种不同证据。
