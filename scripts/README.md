# scripts

本目录保存 `ai-harness` 的脚本真源与脚本合同说明。

说明：

- 全局治理规则真源见 `docs/SUBAGENT_GOVERNANCE.md`。
- 当前仓库的项目级 rules system 真源见 `rules/registry/*` 与 `rules/items/<kind>/*`。
- 旧 `rules/common/SUBAGENT_RULES.md` 若仍出现在历史留痕中，仅按兼容/迁移语境理解。

## 当前已存在脚本

- `bootstrap-local.py`
- `sync-codex.py`
- `doctor-core.py`
- `start_session.py`
- `rules_index.py`
- `generate_rules_index.py`
- `validate_rules.py`
- `validate_plan_docs.py`
- `validate_doc_routing.py`
- `skills/global-task-orchestrator/scripts/orchestrator_ctl.py`
- `skills/command-failure-memory/scripts/command-failure-memory.py`

## 当前脚本责任边界

### Codex

当前 Codex 侧最小实现包含：

- `bootstrap-local.py` 负责新环境初始化和全局 `AGENTS.md` 托管。
- `sync-codex.py` 只同步固定白名单 skill，不接管插件或其他运行时目录。
- `doctor-core.py` 核对真源、运行时与 receipt 的文件哈希。
- `rules_index.py` 只负责解析规则 frontmatter 和构造索引元数据，不决定本轮应读取哪些可选规则。
- `generate_rules_index.py`、`validate_rules.py`、`validate_plan_docs.py`、`validate_doc_routing.py` 提供可独立执行的机械闸门。
- 除最小必读集合外，Codex 根据对话语义、目标内容与路径、风险、当前阶段和本轮实际操作五个维度自由选读规则；Python 不参与语义选择。
- 缺失命令、项目依赖或浏览器自动化运行时的安装层与授权边界由 `global.policy.WSL工具分层与缺失依赖处理` 说明；脚本不据此做运行时规则匹配或静默安装。
- 独立 skill 的全局命令失败经验库脚本：`skills/command-failure-memory/scripts/command-failure-memory.py`
- 开发前 benchmark skill 真源：`skills/pre-dev-benchmark`
- 修复闭环闸门 skill 真源：`skills/fix-closure-gate`

Codex 不托管 `PreToolUse` 命令安全 hook；校验由上述显式 Python 入口执行。

## 正式 CLI

参数统一使用 GNU 双横线写法：

```bash
harness_root="$PWD"
project_root=/path/to/project
python3 scripts/bootstrap-local.py --harness-root "$PWD" --codex-home "$CODEX_HOME" --json
python3 scripts/doctor-core.py --root "$PWD" --codex-home "$CODEX_HOME" --strict --json
python3 scripts/start_session.py --repo-root "$PWD" --task-id "$task_id" --json
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py \
  --action validate --repo-root "$PWD" --task-id "$task_id" --json
python3 scripts/generate_rules_index.py \
  --repo-root "$project_root" --global-rules-root "$harness_root" --json
```

`start_session.py` 只恢复并校验已经存在的 GTO 任务及其六份工件，不读取 `docs/ai/runs`，也不创建 `.ai/session` 或另一套状态文件。新任务由 GTO 的 `--action init-task` 使用 Codex 已确认的结构化六要点合同初始化。

GTO 当前 state 只接受 `version=3`，`events.jsonl` 与其余五份工件同为必备。action 与参数只以 `orchestrator_ctl.py --help` 当前公开并实际实现的 GNU 双横线接口为准。

其他项目只有在显式提供 `--global-rules-root` 时才合并本仓 `scope != project` 的规则；未提供时不自动发现其他 clone 或工作区。

`bootstrap-local.py` 会将用户级 `hooks.json` 中的 `hooks` 清空为 `{}`。文件内其他顶层字段原样保留；随后 strict doctor 核对托管全局 `AGENTS.md`、bootstrap/sync receipt，并拒绝用户或项目配置中的任何 hook 配置。

## `sync-codex.py` 责任冻结

- 只负责固定白名单源路径映射到 `~/.codex/skills/*`
- 当前最小托管模型是固定白名单多 skill：
  - `global-task-orchestrator`
  - `command-failure-memory`
  - `pre-dev-benchmark`
  - `fix-closure-gate`
- 当前固定源路径映射：
  - `skills/global-task-orchestrator -> ~/.codex/skills/global-task-orchestrator`
  - `skills/command-failure-memory -> ~/.codex/skills/command-failure-memory`
  - `skills/pre-dev-benchmark -> ~/.codex/skills/pre-dev-benchmark`
  - `skills/fix-closure-gate -> ~/.codex/skills/fix-closure-gate`
- 最小支持 install / sync 语义
- 默认不接管未托管运行时目录
- 不扩大到：
  - `.system/*`
  - 插件
  - 任意目录同步
- `codex-sync.receipt.json` 记录多 skill 合同：
  - `managed_skills`
  - 聚合后的 `managed_files`
- `command-failure-memory` 作为独立 skill 随同步链路分发，不再作为 `global-task-orchestrator` 的内嵌脚本被描述

## Codex doctor 责任冻结

后续最小 doctor / validate 只负责：

- 检查固定白名单真源 skill 存在
- 检查固定白名单运行时 skill 存在
- 检查每个受管 skill 的关键文件已同步
- 检查真源、运行时与 receipt 基本一致
- 以多 skill 结构输出 `codex_audit`，先逐 skill 审计，再给出聚合结论

其中 `command-failure-memory` 的脚本漂移、缺失与 receipt 目标偏差，`pre-dev-benchmark` 的模板/脚本漂移，以及 `fix-closure-gate` 的文档/metadata 漂移，都应在独立 skill 维度被检测。

本批次不把 doctor 扩展成更广泛项目 doctor，也不引入自动触发或事件桥接。

## 规则与文档闸门脚本

- `generate_rules_index.py`
  解析 `rules/items/**/*.md` 的 frontmatter，并机械生成 `rules/registry/RULES_INDEX.json` 与 `rules/registry/RULES_INDEX.md`。
- `validate_rules.py`
  机械校验规则字段、枚举、文件名、linked skill、显式 override、冲突及索引一致性。
- `validate_plan_docs.py`
  校验 `docs/tasks/<task-id>/plan.md|execution.md|acceptance.md` 是否具备长任务方案文档、施工文档与验收文档的必填章节。
- `validate_doc_routing.py`
  校验模块代码目录、模块长期真源目录与任务期文档目录之间的最小分流边界。

这些脚本只承担生成与机械校验；规则真源仍是 `rules/items/**/*.md`，Codex 自行判断可选规则的读取范围。正常使用方式是从 WSL 直接运行 `python3 scripts/<entrypoint>.py`，不经跨 shell wrapper、自动重试或 hook。
