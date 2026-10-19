# 验收记录

状态：通过本次约定范围内的独立验收及发布后验证。实现者、reviewer、acceptor 分离；本报告汇总实际证据，不用开发测试代替独立验收。

## 固定版本和证据分类

功能验收对象是 `candidate-06`；之后 `candidate-09` 仅新增 doctor、相关测试和说明三文件差异，GTO 包字节不变。最终 500 文件清单 SHA256 为 `a2d201499766e805096b37a629c777f91be50df4d071a2a23595c0552c8106c9`。acceptor 已独立核实增量、安装包 17 个文件及最终全局 doctor。

独立 CLI 功能验收为合成任务前置条件下的 35 项检查、109 条真实子进程命令；真正的能力探针、运行器与退出状态均有原始输出。这不是完整真实 AI 项目交付验收。另以全新 Windows 原生进程运行两个真实模型场景，模型为实际返回的 `gpt-6-astra`，两个 ephemeral 会话均完成，没有创建侧栏持久任务。

| 需求 | 结果与证据 |
|---|---|
| REQ01 职责边界 | 新进程目录确认九禁用、四方法保留、GTO 启用。普通任务未启动 GTO；显式 GTO 任务读取新 SKILL 与 usage-modes 并完成 Plan。均未调用被禁用流程技能。 |
| REQ02 并发隔离 | 复制 state 到另一 checkout 后真实 CLI 拒绝，原任务工件不变。worktree 不隔离服务资源，共享安装单发布者的责任写入现行入口。 |
| REQ03 当前证据正确性 | 空候选无崩溃；登记历史批次后删除当前候选会拒绝 validate，历史批次和 attempt 保留；已完成任务的候选或证据变化仍被拒绝。 |
| REQ04 阶段阅读 | GTO 入口按阶段引用唯一正文；真实显式 GTO 模型轨迹读取新入口和流程说明。 |
| REQ05 固定验收版本 | 非快照入口、被篡改运行包、候选归档删除、异轮身份均拒绝；恢复原字节后合法链路通过。 |
| REQ06 证据留存 | 实际 passed、failed、interrupted、invalidated 分开留存；缺清单、篡改 stdout/业务报告、失败冒充通过均拒绝。 |
| REQ07 能力提前验证 | 实际探针成功/失败/恢复、会话和依赖变化、重放、真实等待超过 15 秒时效均符合门禁；无该依赖的子任务继续可用。 |

## 可复核入口

- [独立 Review 及回执增量复审](../../../.artifacts/gto-environment-hardening/review-04.md)
- [doctor 增量复审](../../../.artifacts/gto-environment-hardening/review-05.md)
- [独立功能验收报告](../../../.artifacts/gto-environment-hardening/acceptor-01/report.md)
- [发布后真实模型路由结果](../../../.artifacts/gto-environment-hardening/acceptor-01/native-01/assessment.json)
- [最终候选、安装包和 doctor 独立复核](../../../.artifacts/gto-environment-hardening/acceptor-01/native-01/final-verification.json)
- [受控发布审计](../../../.artifacts/gto-environment-hardening/publication/audit.json)
- [开发回归索引](../../../.artifacts/gto-environment-hardening/checks/development-results.json)

原生目录测试使用官方 app-server 的显式 Superpowers extraRoots 注册，与发布前保持同一加载上下文；不将 plain CLI 的默认插件发现等同于 Desktop。模型连接出现 TLS EOF，宿主自动重连后完成，两场景的原始事件均保留。没有修改认证、代理或平台配置来掩盖问题。

本次没有运行 L6 整轮长程、真实 Browser/外部业务服务或灾难恢复测试；没有配置异地备份。已存在的会话不保证热加载新的技能配置，后续工作使用新会话。

## 第二轮验收范围与状态

待验收：新入口内容归属及可发现性、旧入口删除、现行引用和锚点、Plan 语义源校验、init 六工件与只读恢复、相关回归、独立 review、独立功能验收、安装一致性及两个新进程定向黑盒。上一轮通过结论不自动覆盖本轮；全 GTO 完整交付与 L6 不在本轮范围。

## 第二轮最终结论（2026-09-29）

本轮批准范围通过，前述“待验收”为本轮开始时记录，已由以下证据闭环：

| 验收内容 | 结果与证据 |
|---|---|
| 内容拆分、唯一正文、当前引用、旧入口删除 | 原 reviewer 审查通过；DS-R1 已修复复审关闭，见 document-split/review-01.md。 |
| 新流程源校验、init 六工件、只读恢复与相关门禁 | 相关开发回归通过；入口/发布定向回归通过，见 green-01.json、references-03、sync-02。 |
| 独立 CLI 功能验收 | 18 项检查、35 条真实子进程命令；冻结快照含新文档，篡改拒绝且不改状态，恢复原内容后沿同一任务继续，见 acceptor-01/report.md。 |
| 实际发布与版本一致性 | 两个相关技能定向同步，全局入口按模板刷新；doctor 及 publication/audit.json 全通过。 |
| 新进程 GTO Plan 黑盒 | PASS：实际读取方案指南，输出职责、并行分支、汇合、独立审查和验收及两类返工，停在 Plan，未写入或派发。 |
| 新进程在途恢复黑盒 | PASS：读取自身工件和冻结流程/控制器指南，准确识别 active/review、未派发验收尝试及下一步；识别合成证据限制，未重建控制面，工件哈希不变。 |

两项黑盒使用真实 gpt-6-astra 模型、新进程及 ephemeral 会话，提示不含目标文档名或预期阶段答案。验收者独立比对实际读取轨迹、最终输出与事前保存的任务真值；原始事件、提示、输出、身份及哈希见 document-split/acceptor-01/native-01/。原生 app-server 显式设置既有插件 extraRoots；此结果不等同于所有 Desktop 自动发现环境。连接中断由同一轮自动重连恢复，未重启一轮以隐藏失败。

这证明本次拆分涉及的入口路由、方案理解、在途恢复及机械合同。恢复场景为真实 CLI 创建的合成任务，不是完整 AI 交付；未执行整轮 Plan→实施→Review→返工→验收、全部 GTO 黑盒、Browser/外部服务或 L6。证据仅承诺本地留存，没有外部备份。本轮正式代码、测试、规则、技能及安装包固定为 candidate-03；最后仅 execution.md 与本文件追加事实结论。