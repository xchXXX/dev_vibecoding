# GTO 独立分发版

将整个 `global-task-orchestrator` 文件夹复制到你的 Codex 用户级技能目录；该目录内应直接看到 `SKILL.md`，不要多嵌套一层。无需安装 ai-harness、全局 AGENTS 或其他 skill。

当前官方文档列出的用户级目录是 `~/.agents/skills/`（Windows 为用户主目录下的 `.agents\skills\`）。部分 Codex 环境也从 `CODEX_HOME/skills`（通常 `~/.codex/skills`）加载。以你实际版本的技能列表为准，只选择一个位置，避免两份同名技能。参见 [官方技能目录说明](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。若复制后未出现，重启 Codex 并重新检查列表。

## 首次准备

运行脚本的环境需要 Python 3.10+、Git 和包内 `requirements.txt` 指定的 Python 依赖。Python 与 Git 必须处于同一实际执行环境；Windows 原生、WSL/Linux 不共用虚拟环境。依赖已满足时无需安装任何东西。

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

新任务使用当前安装版本。已有任务沿用消费项目内的六工件；冻结后的任务按记录使用运行快照，不能复制状态到另一工作区后继续冒充同一任务。升级前备份现有 skill 文件夹，并确认没有正在使用它的未冻结任务；关闭占用后整体替换，重新自检和检查新会话加载。

卸载只删除你安装的这个 skill 文件夹。消费项目中的任务、证据和运行快照不会随之删除；正在进行的任务应先妥善收尾。不要覆盖另一来源的同名 skill。

本包由 ai-harness 的 GTO 真源生成，禁止手工维护第二套控制器，来源见 [SOURCE.json](SOURCE.json)。原版不会自动同步到本包。本包不需要 ai-harness 安装 receipt；候选和运行快照哈希仍按 [运行与证据合同](references/runtime-evidence.md) 校验。脚本检查通过与宿主新会话实际加载成功是两种不同证据。

范围复验行为见包内 [验收合同](references/acceptance-points.md) 及[通用十点示例](references/examples/point-acceptance/README.md)；实际分发内容以 SOURCE.json 和压缩包清单为准。安装更新不得替换消费项目已冻结的运行快照。
# 恢复与登记精简

新入口和观察摘要格式见 [简化合同](references/streamlined-execution.md)。本包由真源生成后提供相同行为；没有全局 Codex 安装时，只使用包内工具入口，不查找其他项目或机器目录。旧任务继续使用其冻结快照。

