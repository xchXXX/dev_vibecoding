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

- 任何会落盘的改动，先给出具体方案；只有用户明确同意后，才进入相应方案与施工文档的落盘流程。
- 在拿到足够上下文后，优先直接推进，不要长时间停留在宽泛分析阶段。
- 用户明确要求 quiet long-run 时，压缩常规进度播报，保留内部进度跟踪，只在真实阻塞、高风险决策或最终完成时打断。
- 长复杂任务批准前先锁定六要点：要做什么、不做什么、改哪些地方、怎么实现落地、怎么验收、有什么风险；并保留 `state.json / task.md / events.jsonl / plan.md / execution.md / acceptance.md` 六份工件。

## 实现约束

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
- `{{HARNESS_ROOT}}` 必须解析为当前 WSL 进程可直接访问的同一仓库根；不搬库、不复制规则真源。
- 其他项目消费 harness 规则时，只导出 `scope != project` 的条目，不把项目私有规则外溢。
- Python 只离线生成、校验索引；正常交互链不运行 matcher、不生成 `task_profile`、不拼装按任务类型固定规则套餐。

## 实施与安全

- 尊重现有未提交改动，只修改任务范围内文件；未知内容不覆盖、不删除。
- 优先使用仓库已有脚本和最小相关验证；生成物只由对应生成脚本刷新。
- 不读取或输出认证信息、token、密钥；涉及系统配置、外部写入或破坏性操作时先确认边界。

## WSL 工具与控制面

- Codex 正常链固定运行在通用 WSL 开发发行版中，使用 Linux 原生文件工具、Git、Python、Node、测试和构建；不使用 Docker 专用发行版承担开发任务。
- 规则离线生成/校验、文档校验、GTO、bootstrap、sync、doctor、CFM 和测试统一使用 WSL `python3` 与 Linux 原生命令；正式入口和验收链不调用 `.ps1`、`.cmd` 或 hook。
- 运行前确认 WSL 工作目录和依赖，不因普通非零退出码切换平台重跑；不增加通用 wrapper、逐命令 preflight、守护进程或自动重试。
- 不擅自搬仓库、复制运行时或重装项目依赖。
- 新进程的实际 `CODEX_HOME` 与规则加载位置必须核对，不能猜测或整目录复制 `.codex`。
- 已启动的长会话不会热更新受管 `AGENTS.md`、skills 或 schema；遇到平台边界冲突时，先核对磁盘上的 `AGENTS.md` 与 `.ai-harness/codex-sync.receipt.json`，再新建任务或重启 Codex。
- Command Failure Memory 简单和复杂参数都直接交给 WSL Python，并继续使用 `/mnt/c/Users/Laptop/.codex/memories/command-failure-memory`；只在原目录内升级格式、锁和 active/archive，不迁移或另建数据。
- WSL 工具基线包含 `git`、`rg`、`curl`、`wget`、`rsync`、`file`、`lsof`、`python3`、`python3-venv`、Linux `node`/`npm`，以及 `jq`、`unzip`、`zip`、`tree`、`strace`、`shellcheck`、`shfmt`、`fzf`、`fd`、`sqlite3`、`dos2unix`、`build-essential`、`pkg-config`、`cmake`、`ninja`、`python3-pip`、Linux 原生 `pnpm`。
- 将多个候选路径传给 `rg`、测试或构建前，可选路径先确认存在，不让一个缺失目录使整条命令失败。
- `ghost snapshot` / `NUL` 索引失败先按平台噪音候选核对；以目标命令退出状态和产物完整性判断任务是否失败。
- 执行前已明确声明、只运行最小目标测试且实际失败类型与预期一致的 TDD 预期红不触发命令失败闭环；意外的命令、环境或基础设施错误仍照常记录。
- 命令失败后先记录失败；重试前查询历史；验证成功后立即回写可复用解法。
- WSL 失败通过当前 WSL Python CFM 记录到上述同一物理库；后端不可达时报告阻塞，不另建记忆库。
- 最终结论以实际命令输出、测试结果与产物证据为准。

## 工具

- 涉及图片生成或编辑时，优先使用当前会话内建的图片能力，不要静默切换到外部脚本或 API 路径。
