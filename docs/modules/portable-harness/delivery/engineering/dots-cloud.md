# dots 云端部署交接与验收

本入口是发给 dots 的部署交接真源，覆盖实际云电脑上的 Codex 运行时及 dots 调用的 Codex Cloud 环境：从 GitHub 获取本仓库，在已核实的执行位置使用基础规则和四项方法技能。不依赖作者电脑、Windows/WSL或Docker。Codex Cloud仓库路线无需个人Codex home或全局安装；已有Codex运行时的portable路线则须核实其真实home。现有产品正常账号授权不要求另备项目API key。GitHub 私有仓库访问由你在产品中连接授权，不把凭据写入命令或仓库。

下文 Codex Cloud 路线是仓库内接入：技能对本仓库及子目录可发现。它不把其他云端仓库或 dot 自身的云电脑变成本仓库，也不隐式安装到用户全局目录。跨仓库安装仍使用 [INSTALL](../../../../INSTALL.md) 的 portable 包流程。


## 直接交给 dots 的部署任务

以下代码块是用户可整体复制给 dots 的交接指令。目标是让后续 Codex 工作默认进入已配置的 harness 环境；不是仅克隆一次，也不是只完成一次验收。

```text
请接手部署我的 portable harness，让你在云端执行我的 Codex 开发任务时自动读取并遵守它。

来源：https://github.com/xchXXX/dev_vibecoding.git
分支：javirs（不要使用 main）
已验证交付基线：9556b353d3d318e543736af3264541a21a71a5cb。
产品代码测试提交：436e52c71d9c371af0e11e3d8249460bd49d8310；9556b35仅追加验收记录。
交接真源：docs/modules/portable-harness/delivery/engineering/dots-cloud.md。
请从 javirs 获取本交接文档的最新版本，记录实际完整 HEAD 并固定本次使用版本；如已有工作区，先检查归属与未提交内容，不覆盖或强制重置。

已授权范围：在你的云端可用环境准备本仓库、仓库内隔离依赖，以及按本交接步骤配置该环境的 harness 启动入口；若确有你要使用的 Codex 运行时和可核实的用户安装目录，按 portable 安装器部署其受管内容。保留原用户配置和未知文件。该授权不包括修改我的本地电脑、其它项目代码、删除资源、推送代码、合并、上线、导入个人记忆、复制认证信息或改变账号权限。

请直接推进以下步骤，只有账号连接、平台发布审批、无法核实目标路径或未知文件冲突等确实需要我的操作时再提出具体要求：
1. 先识别你自己的云电脑、Codex Cloud 任务环境、当前工作目录和实际终端能力。不要连接我的个人电脑代替本次云端部署。报告实际可用 Codex 运行方式和能力，不假设某个目录或工具存在。
2. 在你拥有的持久工作位置克隆 javirs；记录来源、完整提交、系统和 Python/Git 版本。若此环境没有终端/持久文件或可用 Codex，不在它上面假装安装成功，继续准备本文的 Codex Cloud 路线；若该路线需要我先创建环境，给出可直接粘贴的配置并说明具体缺口。
3. 读取本仓库 AGENTS.md 和本交接说明。运行 python3 scripts/cloud-setup.py，再运行同命令 --check；两次退出0且ok=true才继续。使用输出的 .venv Python。实际缺基础工具时在授权环境内按其官方方式准备，GitHub连接交由产品授权流程，不索取明文token。
4. 按本文选择一条真实可用路线：已有可用 Codex 运行时则核实其实际home和技能发现目录，构建固定portable包并install/doctor；使用 Codex Cloud 则完成 Install script、Start skill、Publish和新任务。不要把两处环境的安装状态混在一起。
5. 将本文“持续使用指令”作为后续处理我开发任务的工作约定。为每个实际Codex任务传递环境、仓库、固定版本和规则入口；不能认为子任务会继承本对话。请说明该约定当前只在对话中，还是已有产品支持的持久设置，以及实际验证范围；不能声称已保存不存在的全局设置。不要为了保存约定写入我的个人记忆文件。
6. 完成本文的最小新会话验收，分别证明文件/依赖安装、规则自动入口、技能发现、任务行为；不能用安装成功或手工读取代替新会话加载。真实GTO全流程是单独验收，按下文明确授权及技能门禁推进，缺真实子代理则如实报告该项。
7. 最终给我实际环境及路径、source commit、安装/检查退出码、持久入口、后续启动方式、真实新会话证据、保留资产和未完成项。证据写在本仓库 .artifacts/dots-acceptance/，临时实验在 .tmp/dots-acceptance/。不要只返回计划；可直接做的继续做。
```

## 环境选择与生效范围

| 实际环境 | 部署与自动入口 | 不能由此推断 |
| --- | --- | --- |
| dot 自己的云电脑，确有可用 Codex 运行时 | 下方 portable 路线，安装到运行时实际读取的 home/技能目录；新进程加载 | 在云电脑写文件就改变了 dot 编排器自身的系统指令 |
| dots 调用的 Codex Cloud 环境 | 仓库 AGENTS、`.agents/skills`、Install script、Start skill、Publish后新任务 | 本机个人技能已同步，或另一个云环境/仓库已自动配置 |
| 只有 dot 云电脑文件与终端，没有可核实的 Codex 运行时 | 可准备 Git/依赖；用已配置 Codex Cloud 执行开发任务 | 创建一个叫 `.codex` 的目录就完成了 Codex 集成 |

官方文档确认 dot 云电脑与其调用的 Codex Cloud 环境是不同的工作位置；未确认任意 dot 云电脑目录会被编排器自动当作全局 AGENTS/skills 加载。对 dot 自身的工作习惯使用清晰的持续指令，对 Codex 使用产品支持的规则和技能入口。它们是需要验证的指令机制，不能保证模型永不偏离，也不替代实际权限和审批。

## 持续使用指令

以下短指令由用户交给 dots，属于任务路由约定；具体 harness 规则仍以已部署真源为准，不在 dot 的说明中复制另一套规则：

> 此后处理我的 Codex 开发任务时，默认使用已验证的 harness 环境。每次开始或委派前核对实际环境、项目路径和 harness 版本，把项目 AGENTS、harness 全局入口、规则索引和技能入口传给执行任务；先做环境只读检查，再开展工作。缺少入口时先完成授权范围内的接入，不默默绕过。按当前 harness 规则开展工作：普通任务不强制 GTO；只有我明确选择 GTO 或接续已批准 GTO 时才沿用它的原任务和门禁。保留现有改动、用户资产和失败证据，不把未执行的验证说成通过。新项目、新云环境或运行时升级后重新确认生效范围。继续我已授权的工作，不反复询问同一授权；涉及账号连接、未知资产冲突或范围外操作时说明具体问题。

dots 在当前对话接受此约定，不等于所有未来线程已自动继承。实际配置好环境启动入口后，还需在新的对话/任务中用普通开发请求验证路由；若当前产品没有可确认的持久工作偏好入口，报告这个限制，保留可复用的短指令，不虚构“已写入全局”。Custom rules 用于动作授权边界，不当作整份 harness 的存储或技能安装机制。

## 云电脑上已有 Codex 时：portable 安装

仅在实际具备 Codex 运行时、可启动新会话、并核实其配置目录与技能搜索目录时使用。Codex 登录或账号连接使用平台正常授权；不复制本机登录态，不默认需要额外 API key。若运行时尚未提供，不能以安装一个目录冒充其存在；先采用下一节 Codex Cloud 路线。

先按本仓库 `cloud-setup.py` 准备 Python 依赖。以下是 Linux shell 命令模板，在源码仓库根执行；`DOTS_CODEX_HOME`、`DOTS_SKILLS_DIR` 必须由 dots 依据实际运行时核实后赋值为绝对路径，不能照抄作者机器路径，也不能用一个临时测试home充当真实安装目标。官方当前用户技能目录可为 `$HOME/.agents/skills`；本安装器默认 `<codex_home>/skills`，因此这里显式传入已验证的发现目录，不盲用默认值。

```sh
# 先核实并设置 DOTS_CODEX_HOME 与 DOTS_SKILLS_DIR，然后执行。
: "${DOTS_CODEX_HOME:?请先核实实际 Codex home}"
: "${DOTS_SKILLS_DIR:?请先核实实际技能发现目录}"
DOTS_HARNESS_COMMIT="$(git rev-parse HEAD)"
DOTS_HARNESS_BUNDLE="$PWD/.artifacts/dots-acceptance/bundle-$DOTS_HARNESS_COMMIT"
.venv/bin/python -B scripts/harness.py build \
  --output "$DOTS_HARNESS_BUNDLE" \
  --version "0.3.0-cloud-$DOTS_HARNESS_COMMIT" \
  --source-commit "$DOTS_HARNESS_COMMIT" --json
.venv/bin/python -B "$DOTS_HARNESS_BUNDLE/scripts/harness.py" install \
  --codex-home "$DOTS_CODEX_HOME" --skills-dir "$DOTS_SKILLS_DIR" \
  --environment linux --dry-run --json
.venv/bin/python -B "$DOTS_HARNESS_BUNDLE/scripts/harness.py" install \
  --codex-home "$DOTS_CODEX_HOME" --skills-dir "$DOTS_SKILLS_DIR" \
  --environment linux --json
.venv/bin/python -B "$DOTS_HARNESS_BUNDLE/scripts/harness.py" doctor \
  --codex-home "$DOTS_CODEX_HOME" --skills-dir "$DOTS_SKILLS_DIR" \
  --environment linux --json
```

逐条执行并检查退出码与JSON，任一步失败不继续安装链；模板不是忽略错误的一键脚本。目标包必须不存在或为空，重试先核验已存在包而非删除。已管理安装升级走 [INSTALL 的生命周期](../../../../INSTALL.md)，不覆盖同名未知技能或手改receipt。若是其他操作系统，按实际环境和解释器调整，不能硬套linux。

安装器生成 `<codex_home>/AGENTS.md` 的受管区块，指向自包含规则根和所选技能目录；保留用户区块外内容。receipt记录实际安装位置、模块和哈希。全局入口是否实际加载，以同一用户/运行时的新 Codex 会话为准；项目仍保留自己的 AGENTS 增量。仓库内四技能入口与用户级同名安装可能同时被发现：本仓库优先使用仓库路线；跨项目验收使用该用户安装，不删除仓库真源或假装两个版本会自动合并。

在另一个已授权项目中使用时，核实该项目的 AGENTS、规则索引、环境与 Git 约定；全局安装不替代项目配置。未安装真实用户范围时，当前仓库路线只对本仓库生效，不能声称“一次clone后所有项目自动遵守”。

## Codex Cloud 路线：一次配置

1. 创建 Codex Cloud 环境，选择 GitHub 仓库 `xchXXX/dev_vibecoding`，要求检出 `javirs` 分支。核对 `git branch --show-current` 与 `git rev-parse HEAD`；不要误用默认 `main` 或旧缓存中的源码。
2. 将 Install script 设为以下一行，在检出的仓库根运行：

   ```sh
   python3 scripts/cloud-setup.py
   ```

3. 将 Start skill 设为：

   > 进入实际检出的 dev_vibecoding 仓库根，读取 AGENTS.md 及 templates/codex/AGENTS.global.md 作为本环境的全局协作约定。读取模板时把 HARNESS_ROOT 解析为本克隆绝对路径、SKILLS_DIR 解析为本克隆 skills 目录；不改写模板，不复制作者路径。按入口读取规则索引和固定三条规则，其余按任务语义选择。运行 `python3 scripts/cloud-setup.py --check`。仅在退出码为 0 且 JSON 的 ok=true 后继续。使用报告中本仓库 .venv 的 Python 执行 Python/GTO 命令。报告缺失能力，不调用本机 bootstrap，不修改全局配置，不将磁盘检查当作新会话技能加载证明。

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

## 最小新会话验收

1. 安装任务保留实际source commit、命令、退出码、receipt（若走portable）与doctor；`session_verified=false`不能手改为true。
2. 新建使用同一已配置运行时/已发布环境的Codex任务，不把完整规则再贴进测试提示。普通输入采用上述验收请求中的普通任务示例，要求结果附实际生效的AGENTS/技能路径与环境，不要求输出内部推理。确认启动入口被读取，四项技能在初始可用列表中实际发现；后来手动读文件另记。
3. 普通任务不创建GTO；修复示例能给出最小验证合同；用户未授权的Git写入、个人数据和其它项目保持原样。验收结束核对工作区差异。
4. 再用新的dots对话发一个普通开发请求，观察它是否选择已配置环境并传递规则入口。若只能在旧对话或反复粘贴规则后工作，记录“会话内可用，跨会话自动路由未验收”，不能宣称自动化目标完成。
5. 跨仓库目标仅在已授权且确实接入的另一项目新任务中证明；仓库内成功不扩展成用户范围通过。GTO使用上文验收请求中的明确授权，依真实工具与门禁单独验收。

## 判定标准

- Git 接收：实际 HEAD 对上本次交付；技能链接解析到本克隆，源码/用户环境中无作者绝对路径依赖。
- 环境：安装和只读检查成功，依赖在本仓库 `.venv`；另一个新克隆可独立配置。
- 新会话：实际初始技能发现和规则加载有证据；只报告读文件不算通过。
- 普通任务：不强制 GTO；修复方法可独立调用。
- GTO：真实独立角色、实际运行证据、原生完成状态都通过；缺能力单独报告。

## 官方依据

2026-10-14核对：[dots 的电脑与应用](https://learn.chatgpt.com/docs/dots/computers-and-apps)、[dots 持续指令与权限规则](https://learn.chatgpt.com/docs/dots/controls)、[云环境安装/启动/发布](https://learn.chatgpt.com/docs/environments/cloud-environments)、[仓库技能发现及符号链接](https://learn.chatgpt.com/docs/build-skills)。云端产品和本机能力不同；官方当前说明仓库技能可用于云任务，个人本机技能不自动同步，Codex Cloud 不提供 Computer/Browser Use，因此本次选择纯 CLI 场景。
