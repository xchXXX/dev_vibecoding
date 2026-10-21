# 关键前提先验证

## 目标与范围
将“先识别会导致大面积返工的关键未知，再做最小真实验证，成立后展开依赖工作”沉淀为跨项目工作顺序规则。

用户在本会话批准“就按照这个方案落实”，并明确“允许沿用当前目录和分支，仅追加本次改动”。本任务独立于已完成的 20261020-task-workspace-governance；当前分支 codex/plan-execution-contract 为用户批准的沿用例外。旧未提交改动保留，不接管、不提交、不切换分支。

交付范围：新增 rules/items/workflow/关键前提先验证.md；全局模板一句提醒；普通任务合同“调查先于方案”与 GTO plan-guide 两处引用；使用既有生成器刷新 RULES_INDEX.json 与 RULES_INDEX.md。任务工件和原始证据按既有普通流程留存。

非目标：新增 skill、控制器阶段、schema 字段、固定风险表、全量测试、安装发布、Git 提交/推送、修改既有冻结包。证据复用正文继续引用 acceptance-points.md。

## 实施步骤
调查与用户批准已完成；主协调器 /root 保存修改前基线、建立任务记录并同步规则及引用。独立测试/验收者 /root/acceptance 制定文档检查清单，不伪造 TDD Red；主协调器运行既有索引生成器；另一独立 reviewer 审查固定增量，原测试/验收者执行最小检查和逐点验收。

关键前提：既有脏工作区须有明确授权（已取得）；GTO 独立包不携带 rules（已检查分发脚本，外部引用使用明确的 harness-root 入口，未加载该入口时沿用独立包既有合同）；索引生成器同时生成 JSON 与 Markdown（已查代码）。

验证使用规则校验、现有规则读取边界和引用检查、独立包链接检查，以及索引内存重建比较。只读基线覆盖 582 个既有文件；源文件按基线增量审查，不把旧差异作为本次修改。

## 验收点与证据
- RULE: 正文覆盖关键未知优先级、真实且有代表性的最小探测、授权边界、失败调整、有效证据复用；不增加固定仪式。
- ENTRY: 三处入口引用唯一正文；普通任务和 GTO 既有流程保持，GTO 独立包链接可达。
- INDEX: 新条目 global/workflow/model_decision，三条 always_on 不变；两份索引与生成器一致且确定。
- PRESERVE: 旧文件的非本任务内容和其他文件保持，未修改安装副本、控制器或冻结包。

结果唯一记录在 task.json 引用的阶段证据及最终覆盖报告；原始证据目录为 .artifacts/20261021-key-premises-first/。

## 未解决事项与接续
本次六文件增量已通过独立 review 和原测试/验收者的 RULE、ENTRY、INDEX、PRESERVE 四点验收，完整结果见 task.json 所引用的 acceptance.json 与 acceptance-report.md。6 项定向规则/链接单测通过，索引内存重建与磁盘一致；582 个基线文件的范围外内容无变化。

保留的既有问题：整包链接单测失败，4 条外部坏链位于 controller-guide.md、governance-essentials.md、workflow.md，三文件与本次修改前哈希相同；未重试或扩修。本次 plan-guide 的 13 条本地链接均在包内可达，新增文字入口未引入外部强制依赖。WSL 项目环境检查通过；全局 doctor 在修改前检出既有 GTO 安装哈希及回执差异，未修复、不报告全局通过。

交付仅在当前仓库，未提交、推送或安装发布，不宣称新会话加载或实际耗时改善已验收。一次性脚本留在规则允许的 .tmp/key-premises-first/，原始证据留在 .artifacts/20261021-key-premises-first/。
