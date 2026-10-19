# 执行记录

状态：实施、独立审查、独立验收和本机受控发布完成。主代理为 `/root`；reviewer 为 `/root/gto_hardening_review`；acceptor 为 `/root/gto_hardening_acceptance`。两位子代理均为真实新建、无历史继承的不同代理，分别复用原身份处理复核。本任务按普通任务实施，没有调用被修改的旧 GTO 编排自身。

## 实施与整合

原生 worktree 隔离开发，继承原源工作区 488 个非忽略文件作为基线。基线归档 `baseline/source.tar.gz` SHA256 为 `d10680e925424b2cb34fb95735c234b86358fc9ee64dc29f809d602a7b541df0`。原工作区已有未提交变更保留；整合前逐文件核对基线与当前内容，仅复制本任务差异，没有 Git 提交、推送或清理其他工作。

最终候选 `candidate-09/source-manifest.json` 含 500 个文件，SHA256 为 `a2d201499766e805096b37a629c777f91be50df4d071a2a23595c0552c8106c9`。相对继承基线共 41 个文件变化。最终只追加本任务 execution/acceptance 的事实收尾，记录于 `closeout-delta.json`，不改冻结候选、运行包或历史证据。

落实职责分工、工作区绑定、候选与运行包快照、运行原始输出及业务证据哈希、能力探针上下文与有效期、当前证据重新校验。当前包严格拒绝旧合同；删除旧流程兼容分支与旧正向测试，通用安全负例迁移到当前合同，映射见 `checks/retired-test-map.json`。GTO SKILL 精简为阶段路由，规则索引由正式脚本刷新。

## 修复与验证

Review 六项发现均关闭：证明重放、运行清单消费、业务报告绑定、父目录链接绕过、安全负例覆盖及原生 stdout/stderr 引用。另修复运行包加入候选指纹后 verification receipt 仍按旧公式计算的遗漏；每个 attempt 保存当时 runtime 哈希，历史证据与当前适用性分开判断。

开发验证分组原始清单见 `checks/development-results.json`：核心 56、流程/默认发布 32、路由/证据 36、回执 19、最后夹具增量 2 项通过。各组绑定实际冻结候选，后续改动按差异补测，未声称全仓或 L6 通过。规则与文档路由检查通过。schema 微基准温调用中位数约 17 ms，改前约 330 ms；仅为同进程局部数据，不代表端到端提速。

发布检查发现 machine doctor 仍内置旧合同。已改为直接读取当前 GTO 包示例；同步迁移复制历史 state、消费合同位置及冷目录初始化测试。独立 reviewer 对 doctor 两条真实调用链复核通过；严格 doctor 隔离测试、安装态 schema 探测及最终两项冷目录测试通过。历史失败、中断和驱动错误均留存，没有覆盖成通过记录。

## 发布与证据

先以正式 scoped sync 发布 GTO，再由 bootstrap 生成全局 AGENTS，最后应用受支持的按路径技能开关。九项重复流程技能禁用，四项方法技能保留，没有修改插件缓存。doctor 的受管副本通过正式 environment-only 发布同步；审计确认额外变化仅为此 doctor 文件，其他受管技能、receipt 条目与环境文件保持一致。非 skills 配置的语义相等由 policy 写入前的强制检查保证。最终宿主 doctor 通过，源/安装/receipt/冻结 GTO 包哈希一致。

证据保留在仓库 `.artifacts/gto-environment-hardening/`，包括各候选、失败记录、独立报告、原生会话事件及发布前像。工作 worktree 保持附着，不归档或清理仍被引用的证据。留存只覆盖本机，没有外部备份或灾难恢复承诺。

## 第二轮执行记录

2026-09-29：批准文档拆分；源与隔离工作区 500 文件一致，已保存独立 baseline 与安装前哈希。最小两项回归已真实失败：新 workflow 路径被旧验证器拒绝，生成工件仍含旧入口。后续审查、独立验收和发布结果待记录。

## 第二轮完成记录（2026-09-29）

已完成方案与流程文档拆分，并从同一隔离工作区受控整合至发布源。最终候选 candidate-03 含 501 个文件，manifest SHA256 为 c4fbf2160d79459fc5453c2d355077ff0ca18fb85e2b306c5ea589dd7dc4abef；本轮相对基线新增或修改 35 文件、删除旧 usage-modes.md 1 文件。SKILL 保持 3038 字节的阶段导航；Plan 正文进入 plan-guide，执行职责进入 workflow，CLI 和字段分别引用 controller-guide 与 state-schema。

原 reviewer 发现并关闭 DS-R1（三处旧入口残留），补入正式回归。60 项相关回归、13 项发布回归和最终 7 项入口定向回归通过；这些分组有重叠，不相加宣称独立用例总数。规则索引及文档路由校验通过。发布测试的旧 doctor 夹具已补当前包内合同示例，未放宽产品门禁；WSL 中文路径写入失败改用 Windows 文件 API 完成，原失败记录保留。

原 acceptor 发布前完成 18 项独立功能检查、35 条真实子进程命令。通过后仅同步 GTO、pre-dev-benchmark 和全局 AGENTS，安装 doctor 通过。publication/audit.json 确认源码/安装/receipt 一致，无关技能、运行环境、配置及 hooks 保持不变。发布后两项真实模型场景均完成并被独立判定 PASS；各用一个新进程、一个 ephemeral turn，连接重试原样保留。

本轮证据根为 .artifacts/gto-environment-hardening/document-split/；review-01.md、acceptor-01/report.md、acceptor-01/native-01/assessment.json、publication/audit.json 分别记录独立审查、功能验收、模型判定和发布核对。源码/候选、失败和成功输出均保留。本段及验收结论是候选后的事实补齐，不改变已验收技能、代码、规则或测试。没有提交或推送 Git，工作区继续保留。