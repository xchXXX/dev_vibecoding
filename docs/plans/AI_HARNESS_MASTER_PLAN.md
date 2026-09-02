# AI Harness 总纲

## 文档定位

本文只描述 `ai-harness` 当前活跃架构、运行合同和持续验收路线。已经归档的 task、run、旧方案和迁移记录只保存历史事实，不参与当前实现路由，也不在本文继续维护为并行真源。

## 总目标

建立一套可跨项目复用的纯 Codex/WSL 协作控制面：

- Codex 负责理解对话语义、选择相关规则、使用 skill、派发代理和作出非机械判断。
- WSL Python 3 标准库脚本负责索引生成、结构校验、状态持久化、同步、doctor 与确定性状态推进。
- Linux 原生命令负责日常文件操作、Git、测试、构建与诊断。
- 当前合同不保留其他代理平台、事件拦截器、Windows launcher 或旧控制面兼容路径。

## 三层边界

### 全局真源层

`<harness-root>/` 是长期维护真源，包含：

- `AGENTS.md` 与 `docs/` 当前入口。
- `rules/items/` 规则正文和 `rules/registry/RULES_INDEX.json` 元数据索引。
- `skills/`、`schemas/`、`templates/`、`agents/`、`scripts/` 与 `tests/`。

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
- 派发必须绑定平台返回的真实代理身份和真实隔离参数；review finding 返回原实现者，并由原 reviewer re-review。
- 最终完成需要独立 reviewer 对最新 `HEAD` 或最终变更哈希给出 `final/pass`。

## WSL 正常链

正式命令只使用 WSL `python3`、Linux 原生命令和 GNU 双横线参数。例如：

```bash
python3 scripts/generate_rules_index.py --repo-root .
python3 scripts/validate_rules.py --repo-root .
python3 scripts/validate_plan_docs.py --repo-root .
python3 scripts/validate_doc_routing.py --repo-root .
python3 scripts/bootstrap-local.py --harness-root . --codex-home "$CODEX_HOME" --json
python3 scripts/sync-codex.py --harness-root . --codex-home "$CODEX_HOME" --json
python3 scripts/doctor-core.py --repo-root . --codex-home "$CODEX_HOME" --strict --json
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action validate --repo-root . --task-id "$task_id" --json
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

1. 先冻结六要点、六份任务工件、写入边界和验收命令。
2. 以最小失败测试证明当前缺口。
3. 先同步当前长期真源与测试，再修改实现、schema 和模板。
4. 运行最小相关验证，再运行 bootstrap、sync、strict doctor 与完整回归。
5. 由独立 reviewer 审查全部变更；finding 经原实现者修复并由原 reviewer 复审。

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
- 最终审查覆盖全部实际变更并对最新版本给出 `final/pass`。

## 停止条件

出现任一情况时停止推进并交回主协调器裁决：

- 需要写入未授权路径或覆盖来源不明的 dirty 内容。
- 当前文档、schema、模板与真实 CLI 无法对齐。
- 目标机器运行时同步会扩大已批准边界。
- 验证失败原因不清、review 仍有 open finding，或最终版本尚未获得独立 `final/pass`。
