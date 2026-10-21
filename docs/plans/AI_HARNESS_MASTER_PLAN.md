# AI Harness 总纲

## 文档定位

本文只描述 `ai-harness` 当前活跃架构、运行合同和持续验收路线。已经归档的 task、run、旧方案和迁移记录只保存历史事实，不参与当前实现路由，也不在本文继续维护为并行真源。

## 总目标

建立一套可跨项目复用的纯 Codex/WSL 协作控制面：

- Codex 负责理解对话语义、选择相关规则、使用 skill、派发代理和作出非机械判断。
- WSL Python 3脚本负责索引生成、结构校验、状态持久化、同步、doctor 与确定性状态推进。
- Linux 原生命令负责日常文件操作、Git、测试、构建与诊断。
- 当前合同不保留其他代理平台、事件拦截器、Windows launcher 或旧控制面兼容路径。

## 三层边界

### 全局真源层

`<harness-root>/` 是长期维护真源，包含：

- `AGENTS.md` 与 `docs/` 当前入口。
- `rules/items/` 规则正文和 `rules/registry/RULES_INDEX.json` 元数据索引。
- `skills/`、`schemas/`、`templates/`、`scripts/` 与 `tests/`。

仓库内部只维护相对路径或 `<harness-root>` 占位；机器绝对路径不进入通用合同。

### Codex 运行时投放层

受管运行时只包含：

- `CODEX_HOME/AGENTS.md`
- `CODEX_HOME/skills/<managed-skill>/`
- `CODEX_HOME/.ai-harness/` 中的 receipt、备份与审计状态

运行时是受管副本，不是长期设计真源。sync 只更新明确白名单，不接管 `.system/*`、插件或任意第三方内容。

### 项目适配层

接入项目只维护：

- 项目 `AGENTS.md`、模块入口、项目增量规则与项目私有配置。
- 项目代码、长期模块文档、任务文档和 AI 任务状态。
- 本项目特有的构建、测试与部署入口。

跨项目通用的 orchestrator、schema、模板、skill 和全局规则正文不复制成项目第二真源。

## 规则系统唯一合同

Codex 每轮固定读取：

1. 全局与项目 `AGENTS.md`。
2. 当前可用的 `RULES_INDEX.json` 元数据。
3. 恰好三条 `activation=always_on` 规则：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。

其余规则由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮实际操作自由决定是否读取。索引中的 `summary`、`intents`、`paths` 和 `linked_skill` 只提供相关性提示，不组成固定套餐，也不自动触发 skill。

Python 只在离线维护和验收时生成、校验索引；正常交互链不调用 Python 解释自然语言或替 Codex 选择规则。

其他项目消费本仓全局规则时，必须显式传入 `--global-rules-root <harness-root>`。未提供该参数时只处理目标项目自己的规则，不承诺扫描 sibling clone、用户目录或其他工作区来发现全局规则根。

## GTO v3 唯一合同

- `global-task-orchestrator` 是长任务唯一控制面，当前 state 只接受 `version=3`。
- 每个长任务必须同时维护六份工件：`docs/ai/tasks/<task_id>/state.json|task.md|events.jsonl` 与 `docs/tasks/<task_id>/plan.md|execution.md|acceptance.md`。
- `state.json` 是唯一机器状态真源；`task.md` 是人读摘要；`events.jsonl` 是必备的 append-only 关键事件流；其余三份分别冻结方案、施工和验收。
- 控制器只接受 `orchestrator_ctl.py --help` 当前公开且实际实现的 action；文档、模板和角色说明不得发明 action。
- CLI 参数统一使用 GNU 双横线形式。单横线 PascalCase 别名不是当前接口。
- 执行合同保存在 `state.json.subtasks[].assignment`，执行结果保存在 `state.json.subtasks[].result`；不生成承担当前状态职责的第二套 package 或会话状态。
- 派发必须绑定平台返回的真实代理身份和真实隔离参数；revision 3 的代码 finding 返回原整合责任者；review finding 由原 reviewer re-review，验收 finding 直接由原验收者复验；旧 revision 2 保留原实现者返工。
- 当前通用流程和普通返工、skill 黑盒出口统一见 [GTO 流程真源](../../skills/global-task-orchestrator/references/workflow.md)；字段和可用接口核对同候选 schema 与实际 CLI，在途任务使用其冻结运行版本和同一合同；当前包不兼容旧合同。

## WSL 正常链

正式命令只使用 WSL `python3`、Linux 原生命令和 GNU 双横线参数。以下维护命令在 harness 根执行；GTO 则使用实际加载的 skill 绝对位置，并单独传入业务项目根：

```bash
GTO_SKILL_DIR=/absolute/path/to/the/loaded/global-task-orchestrator
GTO_CONTROLLER="$GTO_SKILL_DIR/scripts/orchestrator_ctl.py"
repo_root=/absolute/path/to/the/consumer-project
python3 scripts/generate_rules_index.py --repo-root .
python3 scripts/validate_rules.py --repo-root .
python3 scripts/validate_plan_docs.py --repo-root .
python3 scripts/validate_doc_routing.py --repo-root .
python3 scripts/bootstrap-local.py --harness-root . --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --json
python3 scripts/sync-codex.py --harness-root . --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --json
python3 scripts/doctor-core.py --repo-root . --codex-home "${CODEX_HOME:?set verified Windows Codex home WSL path}" --strict --json
python3 "$GTO_CONTROLLER" \
  --action validate --repo-root "$repo_root" --task-id "$task_id" --json
```

普通非零退出码按 Command Failure Memory 闭环处理；不能因为失败而自动跨平台重跑、扫描其他 clone、创建 wrapper 或切换到另一套实现。

## 当前受管能力

当前同步白名单包含：

- `global-task-orchestrator`
- `command-failure-memory`
- `pre-dev-benchmark`
- `fix-closure-gate`

bootstrap、sync 和 doctor 只处理受管 Codex 入口、上述 skill、规则索引结构和批准的工具基线。机器级安装状态必须在目标机器上重新验证，不能由历史机器的 receipt 推断。

## 文档与实施路线

见 [GTO 流程真源](../../skills/global-task-orchestrator/references/workflow.md)。本文只保留架构入口与历史证据，不另维护施工顺序或强制全量投放步骤。

### 历史实现证据（非当前候选验收）

此前批次已关闭七项 findings；在授权移除 `/mnt/c/Users/Laptop/.claude` 后，全量 harness 回归 `106/106` 通过，耗时 `421.377` 秒。候选目标为 `e0f68c62afc9b9f05780ba85f8692e5b7f48457556802202dd638dd9a6980e9b`；真实外部昂贵验收不适用，`real_call_count=0`。这些是历史证据，不构成本次候选通过：仍需独立 reviewer 对最新变更给出 `final/pass`。

## 历史与退役边界

- 历史 task/run、旧方案和 sandbox 证据不改写，不作为当前实现真源。
- 当前入口不路由历史 packet、旧会话目录、已退役 runtime、事件拦截配置或旧 launcher。
- 禁止为了兼容历史样例恢复第二套状态、旧参数别名、自动发现规则根或跨平台回退。
- 需要引用历史证据时，必须明确其只读和历史性质，并回到当前入口核对现行合同。

## 持续验收

- 活跃真源只陈述纯 Codex/WSL 正常链。
- `always_on` 始终恰好三条，其余规则保持 Codex 自由选读。
- 规则索引可重复生成且通过 `validate_rules.py`。
- 六份 GTO 工件全部存在、相互一致且 `events.jsonl` 非可选。
- 文档中的 action 与参数均可由真实 CLI 验证。
- v3 schema、当前模板、bootstrap、sync、strict doctor 和全量测试全部通过。
- 当前通用流程和普通返工、skill 黑盒出口统一见 [GTO 流程真源](../../skills/global-task-orchestrator/references/workflow.md)；字段和可用接口核对同候选 schema 与实际 CLI，在途任务使用其冻结运行版本和同一合同；当前包不兼容旧合同。

## 停止条件

出现任一情况时停止推进并交回主协调器裁决：

- 需要写入未授权路径或覆盖来源不明的 dirty 内容。
- 当前文档、schema、模板与真实 CLI 无法对齐。
- 目标机器运行时同步会扩大已批准边界。
- 验证失败原因不清、review 仍有 open finding，或最新候选缺少适用版本要求的有效审查/验收证据。

## GTO revision 3

- 当前通用流程和普通返工、skill 黑盒出口统一见 [GTO 流程真源](../../skills/global-task-orchestrator/references/workflow.md)；字段和可用接口核对同候选 schema 与实际 CLI，在途任务使用其冻结运行版本和同一合同；当前包不兼容旧合同。

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](../../skills/global-task-orchestrator/references/acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

普通任务最小工件和默认实施顺序唯一见 [任务与工作区合同](../modules/git-workflow/contract/task-workspace.md)，不自动升级 GTO。新流程只适用于包含该入口的版本，历史记录不回写为新规范已通过。
