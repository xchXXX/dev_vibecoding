# Windows Agent 与 WSL 开发环境定向迁移

Task ID: `20260910-windows-native-transition`

## 任务目标

Windows 原生 Codex 承担 Browser、截图和 Windows 插件；Linux 项目开发命令继续交给现有 Ubuntu-24.04。当前批次完成重启前准备及接手包，不修改 Desktop 的 Agent 开关、不重启、不宣称插件真实可用。

## 背景与问题

WSL Desktop 的 Browser 自动化无工具及 sandboxCwd 不兼容导致反复改配置。当前仓库混有无关 GTO/业务未提交内容；安装版 machine doctor 的原始问题为 managed_runtime_hash_mismatch、managed_runtime_receipt_mismatch、windows_external_required_mcp_disabled，已记 CFM signature f1d30d3eca1806a94cfa6844d6216fdd8f1a05df10f549f27cc8d2103a5c8584。不能为清除旧 doctor 报错发布进行中的桥接代码。

## 范围

六要点之修改范围：本任务文档/控制记录、scripts/bootstrap-local.py 和 scripts/sync-codex.py 的入口维护闸门、模板与生效 AGENTS 的环境段、drugsale_practice_system/AGENTS.md 的环境段、相关测试；三条环境规则与生成索引；docs/CODEX_COMPAT.md、docs/INSTALL.md、scripts/README.md 的维护提示；CODEX_HOME/config.toml 中 computer_use_wsl/browser_use_wsl 的 enabled、现存 computer-use 插件 enabled；CODEX_HOME/.ai-harness 下的维护标志与私有恢复包。

## 非目标

六要点之不做：不调用 GTO、控制器、工作流 schema 或全量发布；不搬库、重装依赖、关闭 WSL、改安全策略、改 Docker/服务/数据卷；不重置 Git、不清除他人修改、不修改官方 MCP command/args/env、不删除历史证据。不把未验收 Browser 桥发布到机器。

## 约束与依赖

六要点之目标：先恢复 Windows 插件可用路径，再清理旧兼容层。主协调实施与验收；独立子代理 review，首次全局检查当前交付物及整个剩余计划，后续修复范围复审。首次正式运行验收必须全局；切换前诊断不替代它。

本任务不使用 GTO：六份人工维护工件同置 docs/tasks/本任务目录，避免伪装成 docs/ai/tasks 中的 GTO 控制器状态。state.json 是人工接续账本，无自动调度作用，task.md 是导航，events.jsonl 是追加事实记录。

## 方案摘要

六要点之实施：冻结当前需要修改文件的副本与 hash；先测试入口维护闸门，再最小修改两处发布入口；更新模板/生效指令与项目增量；备份后禁用兼容 MCP、启用已存在的原生 computer-use 插件，保留官方 MCP 字段由 Desktop 在原生重启时重建。维护标志使旧安装器在任何写入前明确停止；不是自动重试或常驻程序。先在隔离目标完成源码、安装产物和真实 receipt 的闭环及重复发布验证；冻结经审查的定向候选、允许写入清单与恢复前像。主协调确认无并行发布后，受控解除真实维护标志，仅通过正式定向入口同步并生成真实 receipt，立即核对源/安装/receipt。任何失败立即恢复维护标志并记录实际部分写入，按前像做范围恢复或合并；不得为重试绕过入口。全程不发布无关 GTO 或业务内容。真实机器 receipt 收口是受控同步的结果，不是解除标志之前的循环前提。

## 风险与回退

六要点之风险：并行改动、失效安装记录、Windows 插件自身缺陷、路径/quoting、旧源码回写。写前比较前像，发现漂移不覆盖；私有备份不进入 Git、不输出配置敏感内容；恢复前比较迁移后的 hash，漂移时手工合并。本轮备份不包含 Docker 数据或整机，不声称能恢复业务数据。生效 AGENTS 的旧 receipt 会失配，清楚标为维护中，后继应真实同步生成新 receipt，不直接伪造绿灯。

## 验收标准

六要点之验收：PRE-01 恢复清单及副本 hash 一致；PRE-02 两入口维护标志前置停止且无文件写入；PRE-03 自定义 MCP 不启用、原生 computer-use 已存在并启用、官方 transport 及其他配置不变；PRE-04 源模板/生效指令/项目环境入口与新分工一致；PRE-05 从 Windows wsl.exe 指定 Ubuntu-24.04 执行 Linux 命令且两个项目 project doctor 完成；PRE-06 独立全局 review 无未处理阻断项；PRE-07 接手工件可读且状态真实。

重启后全局验收 ACC-01 急用插件实际用户操作（computer-use@openai-bundled、browser@openai-bundled；unified-computer-use@openai-bundled 配套运行时保持启用）；ACC-02 内置 Browser 点击 example.com More information 并报告实际 title/URL；ACC-03 用户新附件实际读取；ACC-04 Windows 原生应用只操作任务自建窗口并清理；ACC-05 两项目代表性测试/构建与解释器来源；ACC-06 Docker 只读健康及现有服务保全；ACC-07 解除维护前在隔离目标重复发布、不复活旧入口且该隔离目标 receipt 与源/安装一致；受控解除后正式定向同步，再核对真实机器源/安装/receipt；ACC-08 恢复演练、临时夹具清理、关键证据保留。未发生或无工具的项写 pending/blocked，不写 pass。

## 阶段划分

P0 记录合同与当前基线；P1 TDD 与维护入口；P2 指令和配置准备；P3 独立首次全局 review、范围修复/复审、主协调 PRE 检查；P4 用户在 Settings 将 Agent environment 改为 Windows native 并退出重启；P5 后继主协调优先验急用插件；P6 旧实现/测试/文档/receipt 收口与全局 review 补齐；P7 首次全局真实验收及范围修复/复审/复验；P8 完成并保留恢复包。

## 需先同步的核心文档与测试

当前 plan/execution/acceptance、task/state/events 与 handoff-prompt；模板和生效指令；维护闸门的直接同步 API 与 bootstrap CLI 测试。长期文档全面收口作为后继明确待办，不把历史 task 记录改写成新合同。

## Verification contract

- minimal_repro：隔离 CODEX_HOME 存在维护标志时旧 bootstrap/sync 仍可进入写入链。
- hit_proof：两入口在标志存在时返回 WINDOWS_NATIVE_TRANSITION_HOLD，隔离目标逐文件内容及目录树不变；无标志原行为不变。
- diagnostic_checks：目标 unittest、真实配置结构差、备份 hash、Windows 到 WSL 只读调用。
- acceptance_checks：PRE 与 ACC 分开执行；ACC 未完成不得声称迁移成功。
- non_goals：不替换官方 Browser trusted runtime，不进行在运行宿主中的假重启验收。
- review_evidence：最小 Red、Green、前后配置定点差、维护停止无写入、实际 WSL 调用、待重启状态。

## 主协调接续澄清（2026-09-10）

急用范围已由用户明确为 Computer Use 和内置 Browser，包含上述三个插件。配置项或缓存缺失仅表明本机当前发现结果，不证明新 Windows 宿主是否可加载；不在 WSL 重复配置或强开 MCP。当前 browser 配置/标准缓存未发现，ACC-01/02 保持 pending，优先在新宿主核对官方插件可用路径。

配置唯一结构漂移为 model_reasoning_effort，属于迁移目标外设置，保留原状。PRE-01 的备份完整性与可直接整文件恢复分开记录：备份仍完整；当前配置整文件恢复已被前检拒绝。恢复时对当前配置生成私有前像，仅合并本迁移两处 enabled 键，保留其余设置和 Desktop 新字段，主协调核对脱敏差异；不重新 seal 原始恢复包。

## PRE06-003 补证据合同

- minimal_repro：在现有 NativeTransitionGuardTests 夹具新增空目录，旧 snapshot 不变。
- hit_proof：同一最小断言先失败后通过；增强快照记录目录类型，能检测空目录新增。
- diagnostic_checks：仅运行该空目录测试观察 AssertionError，再运行修订后的该测试。
- acceptance_checks：test_windows_native_transition 全部通过，入口无写入比较覆盖目录项与文件类型/内容/mtime。
- non_goals：不修改 bootstrap/sync 生产行为、不运行 GTO/schema 相关套件、不修改私有原始快照脚本。
- review_evidence：保存最小 Red、Green、目标回归结果；PRE06-004 由独立只读 before/after 副本 hash 核验补充，明确 snapshot.py verify 自身仍不检查 after_copy。

## P6 定向清理实施合同

用户确认三个插件正常使用。主协调 GUI 证据缺失只影响对应 ACC，不阻止源码清理。

目标：schema v3 Windows 原生插件声明与只读诊断；删除旧自动开关/GUI 桥注册和运行时代码；环境文件通过正式限定入口同步，保留 Linux 环境治理和所有非目标 receipt。
范围：runtime_common/bootstrap/sync/doctor、外部能力声明/schema、旧桥技能/运行时/对应测试、环境长期文档和任务记录。改前像在 .tmp/windows-native-transition/p6-before，混合 dirty 不以 Git HEAD 还原。
非目标：不执行 GTO 或其 schema、不全量发布、不修改当前插件共享配置、不重建官方 transport、不改业务数据/依赖/服务。
实现：只读能力诊断不解析可执行 transport；环境限定发布不调用技能同步，真实 receipt 由正式入口生成。旧 installed 文件按已核实 receipt 和前像退役；配置中停用的旧键在插件使用期间保留。
验收：声明/只读诊断、重复正式环境同步不改变插件 config、hold 前置停止、Linux 环境目标检查；独立完整迁移候选 review 与范围复审后再定向发布；GUI/新附件缺口单列。
风险：混合 dirty、安装记录旧 hash、活跃插件配置、旧测试合同；先隔离验证与备份，失败保留/恢复 hold，不伪造 receipt。

Verification contract：minimal_repro 为当前声明仍是 wsl_windows_bridge，bootstrap 调用旧开关/桥注册；hit_proof 为 schema v3 只读检查及隔离入口两次执行后 config 字节/mtime 不变、旧桥不生成；diagnostic_checks 为最小声明测试 Red/Green；acceptance_checks 为限定发布与回归；non_goals 如上；review_evidence 记录前像、Red、Green、重复同步、无写入及未决 ACC。

## 用户追加的删除原则

已切换 Windows 原生；删除旧 WSL GUI 桥代码、技能、安装副本与停用 MCP 表，不保留运行兼容层。WSL 保留命令行、代码开发、Linux 依赖、测试构建及服务。配置清理仅移除 computer_use_wsl/browser_use_wsl，先解析和 hash 前检、私有备份，保持所有原生插件及 Desktop 字段。恢复包离线保留，不参与运行或发现。

## 全面扫描整改实施合同

用户授权全部清理，ENV-SCAN-001..011全部关闭后才能再次声明环境清理收口。目标：受管home必须显式指定；删除旧GUI路由/过期Windows禁令，修正健康夹具和临时产物生命周期，统一长期文档与当前宿主。范围为新独立审查列出的源码/CFM技能/规则/测试/文档与相关安装副本，冻结前像见envscan-backup-location.txt。非目标：不调用GTO或其schema，不全量发布，不删Linux开发治理/依赖/服务/用户历史，不改原生插件配置。新增hold保护安装期；仅受审候选定向发布environment runtime及CFM技能，正式receipt保留无关记录。

minimal_repro：未设置CODEX_HOME时resolve/CFM回退Linux home；原生PowerShell句被旧测试认定退休；两个测试类制造固定临时父目录。hit_proof：最小测试先断言失败，修复后目标缺失非零且无文件创建、显式目标成功、原生句放行/旧桥句仍拒绝、测试临时目录自清理。diagnostic_checks：最小单测、只读引用扫描与安装hash。acceptance_checks：相关非GTO单测、两项目doctor、隔离重复定向发布/真实receipt、同reviewer范围复审。文档用事实/链接核查不堆镜像测试。review_evidence：保存Red/Green与实际退出码，历史全量测试不继承。风险：错误目标、混合dirty、全量入口含GTO；不运行这些路径，保留其源码但修当前影响链。修复后受控解除hold；失败恢复hold并记录实际状态。