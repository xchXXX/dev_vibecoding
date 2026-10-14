# dots 云端接入与验收

本入口面向 dots 使用的 Codex Cloud 环境：从 GitHub 获取本仓库，在云端任务内使用基础规则和四项方法技能。无需作者电脑、Windows/WSL、Docker、个人 Codex home、额外 API key 或本机全局安装。GitHub 私有仓库访问由你在产品中连接授权，不把凭据写入命令或仓库。

这是仓库内接入：技能对本仓库及子目录可发现。它不把其他云端仓库或 dot 自身的云电脑变成本仓库，也不隐式安装到用户全局目录。跨仓库安装仍使用 [INSTALL](../../../../INSTALL.md) 的 portable 包流程。

## 一次配置

1. 创建 Codex Cloud 环境，选择 GitHub 仓库 `xchXXX/dev_vibecoding`，要求检出 `javirs` 分支。核对 `git branch --show-current` 与 `git rev-parse HEAD`；不要误用默认 `main` 或旧缓存中的源码。
2. 将 Install script 设为以下一行，在检出的仓库根运行：

   ```sh
   python3 scripts/cloud-setup.py
   ```

3. 将 Start skill 设为：

   > 进入 dev_vibecoding 仓库根，先读取 AGENTS.md，运行 `python3 scripts/cloud-setup.py --check`。仅在退出码为 0 且 JSON 的 ok=true 后继续。使用报告中本仓库 .venv 的 Python 执行 Python/GTO 命令。报告缺失能力，不调用本机 bootstrap，不修改全局配置，不将磁盘检查当作新会话技能加载证明。

需要 Python 3.11+、Git 和 Python venv/pip 支持。若环境初始镜像缺少它们，让环境设置助手安装这三个基础工具后重跑同一命令。安装阶段允许 Python 包索引访问（`pypi.org`、`files.pythonhosted.org`）；不需要项目 Secrets。网络策略由你的环境/组织决定。安装仅向本仓库 `.venv` 写依赖。

安装及检查通过后选择 **Publish**，再从发布环境开始一个新云任务，让 dots 使用这个环境。保存草稿不等于发布；旧任务不会自动换成新环境。仓库刷新也不会自动重跑安装：依赖变化时重新执行安装、检查并 Republish。

## 接入命令的边界

`scripts/cloud-setup.py` 从自身位置确定仓库，安装不依赖调用者的当前目录。默认准备本仓库 `.venv` 与 requirements；`--check` 只读检查。路径、依赖、Git、仓库技能入口或 GTO doctor 失败时返回非零，不报告成功。已有未知 `.venv` 目录或根符号链接被拒绝，不自动删除、重建或接管。

`.agents/skills` 中四个 Git 符号链接直接引用 `skills/` 的 canonical 真源；没有第二份需要手工维护的技能。不要将它们复制成链接文字文件，也不要另外安装同名技能造成重复发现。源码包/ZIP的生命周期合同不变；这条云端路线不调用全局安装器。

成功 JSON 保留 `session_verified=false`。它只证明依赖、目录与 GTO 文件检查通过；真正的技能加载和真实子代理能力须由下面的新任务验收证明。CFM 数据仍归用户；没有已核实且允许使用的 Codex home 时，不猜路径、不复制作者记忆或自动建立全局数据。

## 直接发给 dots 的验收请求

将下面一段发给 dots，并选择刚发布的云环境：

> 请使用我配置的 dev_vibecoding Codex Cloud 环境，在同一个新云任务中验收 `javirs` 分支的 harness。先报告真实仓库路径、分支、完整 HEAD、系统/Python/Git 版本，读取 AGENTS.md，执行 `python3 scripts/cloud-setup.py --check` 并记录退出码和 JSON。请区分你在新任务初始技能列表中实际发现的四个技能，和后来手工读取的文件；不能把文件存在当成自动加载。先做普通任务：“为读取配置文件的函数设计最小测试，不实现”，应直接给出相称结果，不创建 GTO 控制面；再做修复验证合同示例，检查 fix-closure-gate 可调用。最后我明确授权在本仓库 `.tmp/dots-acceptance/` 内，用 GTO 完成一个无网络、无 UI 的整数加一 CLI 小任务，按当前 GTO 技能准备方案与批准合同，使用真实独立测试、实施、Review 和原测试者验收角色。此验收不授权改本仓库产品代码、推送、上线或写我的个人记忆；若平台缺真实子代理工具，报告该缺口，不冒充角色或伪造通过。将平台/新会话/普通任务/GTO分别记录在 `.artifacts/dots-acceptance/`，完成后给出真实命令、退出码、实际身份、task_id、最终 state、失败与剩余项。保留已创建的原任务接续，不重复建控制面。

若 GTO 当前技能要求进一步确认具体方案，dots 应先给出具体小任务合同再获得确认；上述授权不允许跳过产品门禁。其余无需用户逐条执行命令，交由云任务完成。把 dots 的报告或失败输出带回本任务即可按同一代码版本定位，不能把本地报告当成你的云端验收结果。

## 判定标准

- Git 接收：实际 HEAD 对上本次交付；技能链接解析到本克隆，源码/用户环境中无作者绝对路径依赖。
- 环境：安装和只读检查成功，依赖在本仓库 `.venv`；另一个新克隆可独立配置。
- 新会话：实际初始技能发现和规则加载有证据；只报告读文件不算通过。
- 普通任务：不强制 GTO；修复方法可独立调用。
- GTO：真实独立角色、实际运行证据、原生完成状态都通过；缺能力单独报告。

## 官方依据

2026-10-14核对：[dots 的电脑与应用](https://learn.chatgpt.com/docs/dots/computers-and-apps)、[云环境安装/启动/发布](https://learn.chatgpt.com/docs/environments/cloud-environments)、[仓库技能发现及符号链接](https://learn.chatgpt.com/docs/build-skills)。云端产品和本机能力不同；官方当前说明仓库技能可用于云任务，个人本机技能不自动同步，Codex Cloud 不提供 Computer/Browser Use，因此本次选择纯 CLI 场景。
