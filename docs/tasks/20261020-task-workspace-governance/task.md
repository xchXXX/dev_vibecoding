# 普通任务、工作区与分支治理

状态：已通过公开入口完成，`status=completed`、`cleanup=report-only`，回执见 `.artifacts/task-workspace-governance/completion.log`。A01–A12 当前有效覆盖齐备、无未关闭问题。文档和测试先行，独立 review、真实 Codex 验收、定向安装及旧版本保护均已落实。

## 授权、归属和基线

用户批准本对话完整实施方案及新增要求，并要求本次先建立普通任务工件，不使用 GTO。同一任务继续当前工作区和 `codex/plan-execution-contract`，不为命名或子代理另建目录。协调会话见 task.json。

2026-10-20 开工核实：HEAD `33814ae55fc4bd1de067a5d5b802853c7c85e623`，Git 工作目录干净。已有四个 linked worktree 记录，其中一个跨宿主记录显示 prunable；均不属于本次清理范围。旧黑盒材料在 `.artifacts/git-workspace-blackbox/`、`.artifacts/git-workspace-reuse/`，保留原始事实。

## 目标、边界与已确认原因

- 普通任务缺少统一编号、写入归属、跨窗口交接工件；现有 Git 检查器只有 Git 事实，不能推断任务所有权。
- 全局模板明确“不强制生成施工文档”“不默认组织多代理审查”，与新要求冲突；需修改唯一真源和所有相关入口。
- 分支规则“并行修改使用独立 worktree”未区分同任务子代理与独立任务，导致过度隔离倾向；新规则按逻辑任务和真实写入冲突判断。
- `check_git_workflow.read_policy` 要求前缀以 `/` 结尾，不能声明用户要求的 `codex/feat-` 等分类前缀；新建检查与旧任务接续必须分别处理。
- GTO 已有 task_id、state.json 与目录绑定校验。本次接续其真源，不复制为普通状态，不搬迁活动状态，不改变旧冻结包。
- 现有定向发布入口只发布 Git 检查器和全局模板；需要按现有发布/生成机制纳入普通任务入口，保护其他安装。

非目标：业务产品修复、GTO 编排本次工作、自动提交推送合并、删除现有分支或目录、任意活动 GTO 迁移、常驻服务、新数据库、扫描其他 clone、全面改造环境系统。

## 已批准实施顺序

1. 文档：普通任务合同与入口、任务/工作区规则、核心工件与示例、GTO 接续、分支配置与接口、分发安装说明全部先同步，标明待实现。
2. 原独立测试/验收角色建立公开入口测试，证明旧实现缺口；准备真实 Codex 黑盒场景与原始事件采集。
3. 主协调器实现小型任务绑定和检查入口、复用决策、并发占用保护、交接、分支前缀与生成发布整合。禁止先实现再补测试。
4. 定向测试与相关回归通过后，由独立 reviewer 检查本次完整变更；原 reviewer 范围复审修复。
5. 原验收者执行真实 Codex + harness 黑盒、独立包运行及版本保护验证；问题只按影响范围闭环。
6. 定向发布、核实新会话实际加载及旧冻结包哈希，更新实际结果。最终按覆盖收口，不自动全量重跑。

主协调器负责本工作区 Git 操作；测试代理只写测试及隔离证据；review 只读。子代理继承此任务，不再派发整套流程。

## 最小验证合同

- minimal_repro：旧公开 Git 入口拒绝合法连字符前缀；普通任务公开入口不存在；旧真实 Codex 黑盒记录从单目录双代理产生三个目录，但已有明确分配可复用。历史测试不冒充新规则验收。
- hit_proof：公开入口返回正确复用/阻塞决策；真实模型事件无额外创建调用，同任务代理写入原路径；独立任务不能认领同一目录。
- diagnostic_checks：真实临时 Git 仓库、命令退出码、并发认领、dirty 保护、交接责任、无 GTO 状态改写、生成包独立执行。
- acceptance_checks：下列 A01–A12；使用真实平台会话/子代理及事件，不仅检查文案。
- review_evidence：预期失败、实现后通过、命中信号、相关回归、独立 review 与原验收者复验记录。

## 验收点与记录

| 编号 | 必需行为 | 当前结果与证据 |
|---|---|---|
| A01 | 普通写入任务先方案与核心工件；只读免创建 | 通过：真实模型两方向复验；首场失败保留在 `blackbox/ordinary/A01-red.json` |
| A02 | 同任务追加、dirty 续接、子代理共享工作区和分支 | 通过：普通真实三角色流程、真实 dirty 交接与 CLI |
| A03 | 独立任务隔离；干净但被占用不可接管；未知归属不认领 | 通过：公开 CLI 占用与未知 dirty 负例；没有外推为额外模型并行实验 |
| A04 | 已有绑定优先复用；错目录定位；失效绑定不偷建 | 通过：真实 B 从另一 checkout 定位原任务，坏绑定由 CLI 验证 |
| A05 | 跨窗口明确交接；并发认领最多一个成功；不靠心跳回收 | 通过：两个真实身份交接及旧身份拒绝，并发/残留锁由 CLI 验证 |
| A06 | GTO Plan/Execute 同 ID/目录/分支/冻结版本，无普通重复状态 | 通过：真实 register/resume 选择原 frozen；前序是合成夹具，不是完整业务施工 |
| A07 | 配置分类前缀；旧任务不强改名；清理保持 report-only | 通过：前缀、有效 adopt 绑定及 Git/发布回归 |
| A08 | 方案前调查与根因证据；文档→测试预期失败→实现通过 | 通过：真实诊断与完整执行顺序，A01 单独修复 |
| A09 | 自动真实委派独立 review/验收；子代理不递归编排 | 通过：自然提示触发两个真实子线程，原 tester 回到同线程验收 |
| A10 | 原角色范围复验；记录修复不重跑业务；失败完整留证 | 通过：TW-R1/R2 定向 Red/Green、原角色延续、真实登记修复与历史保留 |
| A11 | 相对路径/独立目录/生成包可用；无固定机器/项目/代理名 | 通过：独立 bwrap 消费项目、系统 Python、无源仓库/home 挂载及 strace 核对 |
| A12 | 定向安装、新进程加载；旧冻结版本和无关安装保持 | 通过：真实新进程加载，41 个旧安装文件及 37 个 GTO 原文档/冻结文件保持 |

上表展示独立验收的范围结论；机器登记及逐点证据通过 task.json 引用原验收者的 `final-independent-acceptance.json`，不另造执行记录。

## 证据与接续

原始输出落在 `.artifacts/task-workspace-governance/`；一次性测试工程和辅助脚本落在 `.tmp/task-workspace-governance/`。公开测试进入 `tests/harness/`，正式合同进入 `docs/modules/git-workflow/contract/`。没有证据不得把未执行改成通过。

工件先于实现人工建立；实现后已通过公开 adopt 入口核验采用，仍为原目录/分支。此前人工登记不冒充自动回执。

### 本次执行记录

- 环境：项目 doctor 通过，machine environment-only 审计通过；后者不证明 GUI 实际加载。
- 文档先行快照：`.artifacts/task-workspace-governance/documentation-baseline.json`，当时任务实现入口不存在。
- 独立测试：`/root/acceptance_tests` 同步 19 项公开 CLI 测试，最小 4 项 Red 分别命中缺入口、连字符前缀被拒绝和两处文档旧三文件要求。原始记录 `tdd-red.log`、`tdd-red-summary.json`，不覆盖失败证据。
- 第一版实现：19 项通过，日志 `tdd-green-attempt-1.log`。运行期间对便携入口关闭 Python bytecode 写入、resume 输出分支作局部校正；该次完成日志通过，相关入口将在独立验收再次核验，不将此称为不可变代码快照证明。
- Git/定向发布相关回归：18 项通过，`git-regression.log`；规则元数据 7 项通过。streamlining 使用包路径启动发生导入错误，已 CFM 留证，改 discover 只运行该组，未重复前述 7 项。
- 原始黑盒 runner 的 7 项事件回放通过，0 模型调用，见 `runner-event-check.json`。真实模型尚未启动，不以回放替代验收。
- 独立 review：`/root/independent_review` 完成首审，发现 TW-R1（新实现后旧覆盖仍能完成）及 TW-R2（历史角色可被替换）。先同步合同，再由原测试者新增 5 项 Red，随后实现修复；8 项定向 Green 通过（5 新用例 + 3 关联回归）。原 reviewer 仅复审对应影响，其他首审结论保留。首审及失败证据均未覆盖。
- GTO 恢复与登记回归：12 项通过，`entry-regression-streamlining.log`，未重跑此前已通过的规则检查。
- 独立目录：生成工具在不挂载原仓库或用户 home 的 bwrap 环境中通过；初次 17 次 CLI 验证路径、dirty 续接及交接。修复后仅补阶段与完成检查 19 次 CLI（其中 6 次预期拒绝），没有重复前述路径检查。两个阶段均 0 业务调用、0 模型调用；原 completed 任务字节及历史证据保持。见 `portable/` 和 `portable-revision/` 的独立验收记录。
- 生成分发：使用既有 build_release.py 刷新 standalone GTO 文档与 SOURCE；未替换旧冻结版本。定向安装前保护文件哈希见 `protected-install-before.json`。
- 范围复审：`review-scoped.md` 关闭 TW-R1/TW-R2，无新增阻断。未重复其他已通过审查或测试。
- 定向安装：既有 `bootstrap-local.py --git-workflow-only` 成功发布全局模板和两个 Git/任务工具；`installation.receipt.json` 记录范围。两个已安装脚本与真源哈希一致，41 个旧 GTO/CFM/环境受保护文件全部保持。已安装公开入口对本任务返回 `reuse`，仍为原分支/工作区。此项是安装与 CLI 证明，真实模型加载及行为另行验收。
- 真实 Codex 首场：自然缺陷请求未提醒具体流程，实际完成文档 → 独立测试 Red → 实现 → 另一 reviewer → 原 tester 验收 → complete，worktree 新增 0。实际主模型 1 turn、2 子线程共 3 turn，35 条 shell 命令、4 次业务进程、11 个测试用例、10 次业务函数调用。TLS 自动重连在同一 turn 恢复；模型全部正常完成，闲置 runner 等待第二提示时受控关闭的 EOF 独立说明，不冒充模型失败。
- 首场 A01 失败：唯一初始请求没有批准具体方案，模型报告后即创建分支/工件和正式文件。原验收者固定 `A01-red.json` 及独立评分，原 reviewer 核实“已有授权”的对象歧义。先同步合同/示例，后更新全局模板；只复验未批准等待、批准后接续两方向，保留首场其他通过证据。
- A01 范围闭环：`review-approval-boundary.md` 通过；实际模板定向发布后，新进程两 turn 验证未批准时零正式写入、明确批准后沿用原诊断只登记和同步文档。没有重跑首场业务全链，原失败保留。
- 真实交接：A/B 为两个平台实际线程，B 从 main checkout 找回已绑定目录，dirty 字节不变，旧协调身份被拒；新增 worktree 0，业务调用 0。
- GTO 接续：真实模型通过 register-gto 定位后调用原 start_session，实际选择原 frozen；同 ID/目录/分支/HEAD，37 个原控制文档及冻结包文件不变，无普通重复状态和新增业务调用。
- 最终独立验收：`final-independent-acceptance.md/.json` 确认 A01–A12 当前有效覆盖通过、open_issues 为空。合计 5 个真实根会话、6 个主 turn 和 3 个子 turn，89 条 shell 命令；业务共 5 进程、12 次函数调用，含原失败场景和复验诊断；夹具及评分业务调用 0、模型新增 worktree 0。
- 最终保护：`final-protection.json` 独立确认 41 个旧安装文件不变，两个 CLI 源码/安装/回执相同。`workspace-preservation.json` 确认本仓分支、HEAD 和全部既有 worktree 记录未变，没有提交、推送、合并或清理别的任务。

## 使用及版本边界

- 操作合同及可复制示例见 `docs/modules/git-workflow/contract/task-workspace.md`、`task-workspace-example.md`。新普通施工使用两个核心工件；纯问答、临时只读及明确授权的日常 Git 操作免建。
- 新生成/安装版本包含并列的 task_workspace.py 与 check_git_workflow.py；本次任务入口 SHA256 为 `fb0c681430e278e2d370089bad3474b4fdd04d9c8328f4fe08c6acef96f712a6`。既有普通任务通过明确归属 adopt 接续，旧 GTO 使用自己的冻结入口。
- 可移植性证明覆盖本次通用工具、示例和生成入口；不依赖原 harness 工作区运行。活动任务仍绑定原 checkout，复制或搬动活动目录不是自动迁移入口。
- 真实模型覆盖普通流程、批准边界、交接与 GTO 冻结接续。并发争抢/损坏索引等由 CLI 证明，GTO 前序治理为合成夹具，未宣称完整 GTO 业务验收。指令和公开工具不拦截所有任意 shell/文件操作。
- 首场批准失败、TW-R1/TW-R2、网络重连、模型命令调用错误与夹具依赖缺口均保留并分类；最后汇总只核对覆盖与证据，没有附加整轮重跑。
