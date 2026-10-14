# Portable Harness 实施计划

状态：2026-10-14 本轮可执行的实施与补验完成。最新固定候选5a0606ac6b11包含经授权的中断身份恢复修复，独立测试、Review及清洁ZIP核验通过；Windows GTO隔离依赖、初始化/校验、恢复成功链和Linux容器生命周期补验通过。完整真实GTO单场景已在原任务通过独立Review/验收并原生finalize至completed，最终validate通过。追加Docker启动故障修复已完成官方升级、恢复命中及两轮重启验证。用户明确本轮仅自用／内部交付。外部环境和新会话缺口仍单列，不宣称全部规格验收完成。
执行者：本任务 /root 持续实施、自检和纠偏；父会话仅必要过程核验及最终复查。
工作区：D:/prj/harnesss/dev_vibecoding/.worktrees/portable-harness-design，分支 javirs。
起始 HEAD：87d7255dc5c1ed4fe0b59c6cda36150f8c59b507。
规格：../../modules/portable-harness/design/portable-harness-design.md。

## 目标与范围
按已批准规格 R01–R13 完成单仓库模块解耦：base 基础规则、benchmark/fix/cfm 独立技能、gto 可选编排、统一跨平台安装适配、用户数据隔离。默认完整安装；模块选择是可选高级参数，不增加必填配置。目标为 Windows 原生、Linux、WSL 实际验证；真实云端和新 Codex 会话无法取得时分别标记未验收。
本工程不用 GTO 编排；GTO 是产品被测对象。保留原始脏 checkout、全局安装和用户数据。用户于后续直接授权将代码提交推送到Git，供dots云端从Git拉取并验收：沿用javirs，补齐仓库云接入、独立测试/Review与干净Git接收者验证后推送。仍不合并main、不对外发布、不读取凭据、不改真实全局配置、不自动迁移在途任务、不复制作者记忆。

## 结构与接口
正式代码位于 modules/harness/，脚本入口 scripts/harness.py，测试位于 tests/portable/。配置、接口、包格式与生命周期字段唯一维护在 [公共合同](../../modules/portable-harness/contract/README.md)，本计划不复制定义。合同调整需通知独立测试者并保留行为验证。

## 实施顺序与责任
- [x] P0 根代理更新规格、控制文档、模块合同和验收表；文档代理更新全部受影响入口/规范/技能文档。文档准备不伪称 TDD Red。
- [x] P1 独立测试代理依公共行为合同建立 fixture 与初始测试；共同确认接口，记录最小有效 Red 后才放行对应产品实现。
- [x] P2 根代理实现配置、安全路径、可重复 bundle；每个行为 Red → Green → 相关回归。
- [x] P3 根代理实现所有权、AGENTS 块、模块安装/更新/卸载、锁、事务恢复、doctor 与 CLI。
- [x] P4 根代理统一 GTO 真源及分发生成；保留已有 receipt 核验、运行快照、Unicode 和超时树清理；方法技能可独立消费；消除默认 hooks 清空和非受管覆盖入口。
- [ ] P5 组合回归、引用闭合、分发包和隔离消费者验证；实测 Windows/Linux/WSL，分别记录实际环境，不以 mock 抵扣真实平台。
- [x] P6 新的无历史独立 Reviewer 核查完整候选；PRV-01–11由同一Reviewer复验，bb17固定包及冻结后HOOKS文档差异Review通过，报告保留验收边界。
- [ ] P7 新的无历史独立验收代理按规格逐项验收；问题根代理返工，同一验收者复验。不能让实现者冒充独立验收。
- [ ] P8 根代理最终自检全部证据、文档、范围和剩余限制；提交父会话最终复查，不等待父会话代替日常跟进。

P5/P7/P8的未完成边界：现有Windows/WSL验证、原身份验收报告及根复查已完成；新增Linux容器Python3.11生命周期和真实GTO同场景全流程通过。内部交付许可范围已确认；独立Linux主机、新会话/真实接收者、云端与父会话最终复查尚未取得证据。保留未勾选状态，不因部分平台通过伪称全部规格完成。

续接裁决：上述许可边界已由用户缩为仅自用／内部交付，保留来源审核，不新增对外许可证。Windows依赖缺口通过本任务隔离venv解决，不改bundled Python。真实GTO为被测产品的一次隔离add-one任务，场景BB17-GTO-ADDONE-001、formal_round=1；本工程仍不采用GTO编排。Docker追加范围为定位并修复实际反复启动故障，保存数据与配置恢复边界，采用根因/命中证明及重启验证，不以一次启动成功代替根治。新会话不能用继承上下文的子代理或手工读取技能替代。

## 受影响文档与测试
当前入口 README、AGENTS、docs/ARCHITECTURE、CODEX_COMPAT、INSTALL、HOOKS、EVALS、PROJECT_TEMPLATE、SUBAGENT_GOVERNANCE、总纲；全局 AGENTS 模板；WSL 运行/命令/测试/文档/长任务规则；四技能及 GTO 包内 references；standalone 来源和生成说明；测试 README。历史证据不改写。规则索引由生成器更新，不手工维护第二份索引。
新 tests/portable/test_config.py、test_bundle.py、test_lifecycle.py、test_recovery.py、test_cli.py、test_module_independence.py；现有 GTO、CFM、发布范围、环境与 standalone 测试按行为合同同步。测试作者先说明将导致失败的生产行为，不以源码字符串取代结果检查。

## 验证合同
contract：引用闭合、模块元数据、包清单/生成一致性；只证明结构。
component：临时 home 下真实文件生命周期，用户字节保全，篡改/碰撞/链接拒绝。
forward：CLI 完整安装→doctor→更新→恢复→卸载，源目录移走仍可用，模块互不覆盖。
platform：原生 Windows/Linux/WSL 分别检查锁、进程树、Unicode/空格/CRLF、退出码。
session/blind：干净接收者仅按说明，无作者提示地加载规则/技能；普通与 GTO 分流；真实代理身份和独立审查。缺能力如实阻塞。
修复合同：minimal_repro 为隔离 home 中预置 hooks/同名未知技能后调用候选默认入口；hit_proof 为到达对应预检/保护路径且用户文件哈希不变；diagnostic 为定向用例；acceptance 为完整生命周期和相关旧回归；non_goals 为真实全局迁移；review_evidence 保留原失败、命中、通过和回归日志。
证据目录 .artifacts/portable-harness/20261014/，逐条记录命令、退出码、候选哈希、环境、身份及原始输出，不重写失败为成功。测试使用自有临时目录并清理。
命令：python -B -m unittest discover -s tests/portable -p 'test_*.py'；python -B -m unittest discover -s tests/harness -p 'test_*.py'；python -B tests/gto-standalone/run_regression.py。使用实际可用的同环境解释器并记录，不静默安装依赖。

## Review 重点
首次未知同名资产；受管文件之外的用户改动；恶意/损坏 receipt 和 journal；链接、大小写和路径逃逸；中断与恢复失败；跨模块更新；主版/分发版漂移；当前会话缓存冒充新会话；跨环境共享写入者锁语义；真实平台未测仍宣称可用。

## 执行方法裁决
采用 writing-plans、pre-dev-benchmark、TDD 和执行计划方法。用户最新批准覆盖旧待确认文字；无需再设阶段审批。仓库任务目录约定优先于 skill 默认目录；使用这三份控制文档，不建重复账本。用户要求原审查者复验，优先于技能的一次修复不复审建议；保留证据，不删除本任务工作区。

