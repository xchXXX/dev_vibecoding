<!-- ai-harness:managed-global-agents:v1 -->
# AGENTS

本文件是跨项目使用 Codex 时的全局入口，只保留稳定协作约定与 harness 发现方式。

## 沟通与协作

- 说明性内容默认使用中文；代码标识、命令、路径和配置键保持原样。
- 用户提出问题时，先回答问题，再继续手头工作。
- 准备修改文件前先给简短计划；完成后说明结果、验证和剩余风险。
- 对 quiet long-run 保持耐心；没有异常证据时不催促、不打断、不重复启动。
- 优先给出简洁、直接的回复，不要无意义铺陈或过度分类。

## 变更流程

- 涉及代码交付、Git 分支或发布管理时，读取 `<harness-root>/rules/items/workflow/分支与发布管理.md` 与项目 `config/ai/git-policy.json`（若存在），按当前操作执行关键节点检查；既有任务继续原分支，保留其他任务的工作，不把提交、推送、合并和部署混为同一状态。

- 问答、只读检查以及用户明确要求的普通 Git 提交、推送等日常操作直接执行；Git 操作先核实分支和提交范围，不额外要求方案确认。强制推送、覆盖历史或删除资源须核实影响与授权，不按普通推送处理。
- 普通施工任务也须先查清可核实事实；bug 先有复现和根因证据，再报告方案、流程、范围及验收点。初始“请修好”等目标请求不等于批准后来提出的具体方案；无既有具体方案批准时，报告后结束本轮等待回复，不创建/切换实施分支、正式任务工件或修改交付文件，隔离诊断留证仍可进行。批准后首次交付写入前建立 `docs/tasks/<task-id>/task.md` 与 `task.json`；已有具体方案批准且范围未变的不重复确认。纯问答、临时只读及明确授权的普通 Git 操作免施工工件。唯一流程和公开入口见 `<harness-root>/docs/modules/git-workflow/contract/task-workspace.md`，按其实施状态及实际安装版本执行，不虚报尚未可用的入口。
- 准备投入较长时间前，按 `<harness-root>/rules/items/workflow/关键前提先验证.md` 优先核实会导致后续大面积返工的少数前提；已有有效证据直接复用。
- 在拿到足够上下文后，优先直接推进，不要长时间停留在宽泛分析阶段。
- 用户明确要求 quiet long-run 时，压缩常规进度播报，保留内部进度跟踪，只在真实阻塞、高风险决策或最终完成时打断。
- 普通施工默认按“相关文档全部同步 → 独立测试/验收代理更新测试并证明预期失败 → 实现与定向测试通过 → 另一独立 reviewer 审查 → 原测试/验收者验收”执行；主协调器组织闭环，原角色只复验修复及实际影响，不默认整轮重跑。纯文档使用适用检查，不编造 TDD Red。子代理只执行分配职责，不递归派发整套流程。GTO 阶段与门禁仅由其冻结合同定义，不叠加普通流程。方法 skill 不另建控制面或重复审批。
- 先认任务再认目录：子代理继承父任务，跨窗口携带原任务号；GTO Plan/Execute 沿用同一任务。同任务默认共用工作区与分支，独立任务并行写入才隔离。dirty 不触发另建，clean 不证明无人占用；先查绑定与现有目录，必要时才创建。共享工作区按写入范围分工，同文件/共享生成物串行，Git 操作由主协调器统一执行。交接先停止原写入安排再转交；worktree 不隔离端口、数据库和全局安装，共享安装单发布者。
- GTO 仅在用户显式要求使用时启动；任务复杂时可以建议，不因工作量、风险、服务器操作或需要方案而自行启动。用户已批准采用 GTO 的在途任务继续沿用原任务流程，不重建控制面或擅自取消门禁。
- 仅对已选择 GTO 的任务，Plan 编制与交接见 `<harness-root>/skills/global-task-orchestrator/references/plan-guide.md`；阶段、六工件和分工规范见 `<harness-root>/skills/global-task-orchestrator/references/workflow.md`。普通任务遵循上面的核心工件及独立 review/验收，不初始化 GTO。
- 验证按目标行为选择能提供可信证据的最低成本方式；仅在 GTO 任务中，分层黑盒测试、场景卡、报告与验收流程要求遵循 `<harness-root>/skills/global-task-orchestrator/references/blackbox-methodology.md`。普通任务不因验证而创建 GTO 控制面。
- 仅在 GTO 任务中，用户批准后至六工件成功创建、校验并通过首次交付 preflight 之间，只允许在消费项目自身 `.tmp/` 写入一次性合同 JSON。此期间禁止业务代码、正式测试、正式文档、`.gitignore`、manifest/lockfile/requirements、环境配置、脚手架、构建和部署资源等交付写入；控制器不能拦截平台文件工具，主协调器须在首次派发交付任务或首次交付写入前执行 preflight。

- 普通任务与 GTO 均按验收点保存结果、按实际影响范围复验，保留任意历史轮次中仍有效的通过结果；完成检查完整覆盖，不默认重跑。通用正文见 `<harness-root>/skills/global-task-orchestrator/references/acceptance-points.md`；普通任务使用简洁清单，不创建 GTO 控制面。

## 实现约束

### 唯一真源

- 每项规则、流程、字段定义和任务事实只指定一个可编辑真源；其他入口引用真源，不另写一份需要独立维护的同义内容。
- 索引、安装副本和展示文档可以由真源生成，但必须明确来源并通过对应脚本刷新，不手工维护第二套定义。
- 迭代时先修改真源，再更新引用和生成物；历史记录保留当时事实，不作为现行规则入口。

### 实现方式

- 可用少量、直接、低复杂度代码完成时，优先选择更短、更易审阅和维护的实现。
- 保持逻辑干净、简洁、边界清晰；没有真实兼容负担或明确要求时，不主动增加兼容分支、过渡层、双轨逻辑或历史包袱。
- 新增文件必须遵守 `<harness-root>/rules/items/architecture/通用文件存储位置.md` 与 `<harness-root>/rules/items/policy/文件存储位置强制约束.md`；临时文件、临时脚本、测试隔离目录和一次性分析产物必须清理或留在规则允许的临时落点。
- 存在不确定点时，先调研真源或请求澄清；未经确认不得实施范围外改动。
- 未明确要求改动的内容默认不动；额外改动必须先说明并得到同意。

## 全局规则引导

- 全局默认使用规则系统，不只依赖当前对话的临时理解。
- 固定读取本全局 `AGENTS.md`、项目 `AGENTS.md` 和可用的 `RULES_INDEX.json` 元数据。
- 固定规则正文仅有三条：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。
- 其余规则由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮实际操作自由决定是否读取；索引提示和 `linked_skill` 不组成固定规则套餐，也不自动触发 skill。
- 项目没有规则索引时，使用 `{{HARNESS_ROOT}}/rules/registry/RULES_INDEX.json` 作为全局元数据索引。
- `{{HARNESS_ROOT}}` 指向同一仓库；按下文 Windows/WSL 路径约定读取，不搬库、不复制规则真源。
- 其他项目消费 harness 规则时，只导出 `scope != project` 的条目，不把项目私有规则外溢。
- Python 只离线生成、校验索引；正常交互链不运行 matcher、不生成 `task_profile`、不拼装按任务类型固定规则套餐。

## 实施与安全

- 尊重现有未提交改动，只修改任务范围内文件；未知内容不覆盖、不删除。
- 优先使用仓库已有脚本和最小相关验证；生成物只由对应生成脚本刷新。
- 不读取或输出认证信息、token、密钥；涉及系统配置、外部写入或破坏性操作时先确认边界。

## Windows Agent 与 WSL 开发环境

- Windows 原生 Agent 负责文件工具、Browser、截图和 Windows 插件；项目 Git、Python、Node、测试、构建、CFM 和 Linux 服务命令继续在 WSL 原位执行。WSL Agent 中直接用 Linux 命令；Windows Agent 中先核实发行版，再通过 `wsl.exe -d <发行版> --cd <Linux项目路径> -- bash -lc '<项目命令>'` 调用；Windows 集成终端设置不等于 Agent 环境。
- `{{HARNESS_ROOT}}` 是同一仓库的 WSL 路径；Windows 文件工具只使用其已核实的等价盘符路径（例如 `/mnt/d/prj` 对应 `D:/prj`）。Linux-only 路径不得猜映射，不搬库、不复制规则源。命令参数避免多层引号，目标退出码如实保留。
- 机器 Linux 工具仍由 `config/ai/wsl-tool-baseline.json` 声明；项目使用自己的 manifest、lockfile、Linux venv/node_modules，不换成 Windows 依赖。项目首次运行/测试/构建前，在 WSL 中执行已安装 `project-env-doctor.py --project-root <Linux项目路径> --environment <项目路径>/config/ai/environment.json --json`。安装脚本和 CFM 使用实际 Windows CODEX_HOME 的已核实 WSL 等价路径；不假设 WSL 的 `$HOME/.codex` 与 Windows 相同。
- Windows Browser、Computer Use 使用当前宿主实际暴露的官方能力，不调用 `computer_use_wsl`/`browser_use_wsl`，不修改 app-managed `node_repl`/`cua_repl` 的 command、args、env 或插件缓存。Desktop 重建的字段不能被当作配置漂移反复改回。工具未加载则报告，不靠强制 enabled、临时桥或切换平台掩盖失败。
- 若 `CODEX_HOME/.ai-harness/windows-native-transition.hold` 存在，表示环境迁移维护中：暂停 bootstrap/sync 及旧 machine doctor 的修复链，读取标志指向的任务记录接续；旧声明与 receipt 待迁移收口，不能声称全局 doctor 通过。正常插件请求和 WSL 项目命令可继续，仍执行项目环境检查。无维护标志时按当前发布版 machine doctor 合同检查一次。
- 路径先查实存在；允许无匹配的探索型 `rg` 用 `rg ... || test $? -eq 1` 单独执行。真实命令失败继续在 WSL 按 CFM record-failure → query-before-retry → record-success 闭环；预先声明、最小且类型相符的 TDD Red 例外。受管指令和插件配置须新进程加载，磁盘配置不等于实际能力验收。

## 工具

- 涉及图片生成或编辑时，优先使用当前会话内建的图片能力，不要静默切换到外部脚本或 API 路径。

## 工具定位与任务接续

项目环境检查的精确安装入口是 `<实际 CODEX_HOME>/.ai-harness/runtime/wsl-environment/bin/project-env-doctor.py`。只核对此公开入口；缺失时报告，不递归搜索 CODEX_HOME、其他工作区、备份、会话或记忆。Windows 与 WSL 路径仍需实际核实，不猜发行版或用户名。

GTO 新版恢复摘要、证据生成登记和简短收尾的实施状态及合同见 `<harness-root>/skills/global-task-orchestrator/references/streamlined-execution.md`；普通任务继续使用简洁清单。

项目接入要求与配置缺口处理见 `<harness-root>/docs/PROJECT_TEMPLATE.md`，最小操作见 `<harness-root>/docs/harness-usage-examples.md`；版本与诊断只读展示沿用上述 GTO 合同，不替代检查、授权或真实会话加载证明。
