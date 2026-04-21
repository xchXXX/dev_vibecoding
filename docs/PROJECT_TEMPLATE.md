# PROJECT_TEMPLATE

## 目标

定义项目接入 `ai-harness` 时的最小适配层，确保项目仓库只保留入口、增量规则和运行留痕，不复制全局通用规则真源。

## 全局与项目的分层

全局统一规则、review 输出模板、测试用例模板和代码子代理迭代清单，统一维护在：

- `docs/SUBAGENT_GOVERNANCE.md`
- `rules/common/SUBAGENT_RULES.md`
- `templates/review_report.example.md`
- `templates/review_testcases.example.md`
- `templates/code_worker_iteration_checklist.example.md`

项目仓库只保留：

- `AGENTS.md`
- `docs/ai/`
- `config/ai/`
- 项目专属 `.claude/` / `.codex/`
- 项目业务文档、部署文档与本仓特有脚本

## 项目入口应承担的职责

### `AGENTS.md`

- 只写高层强制规约、禁忌与入口
- 引用全局 `ai-harness` 协作规则真源
- 记录本仓额外约束，例如语言、目录、部署口径

### `docs/ai/`

- 只写本仓增量规则
- 记录 run/session 留痕和会话规划标准
- 不再复制通用 subagent / review / testing 规则全文

### `config/ai/`

- 只保留本仓任务单、schema、注册表、样例
- 不重复保存全局 review/testcase/worker 模板副本，除非项目明确需要局部覆盖

## 推荐最小骨架

```text
<project>/
  AGENTS.md
  .claude/
  .codex/
  docs/ai/
  config/ai/
  scripts/
```

## 项目接入检查点

- 已在 `AGENTS.md` 写入全局规则真源入口
- 已在 `docs/ai/README.md` 写明“本仓只保留增量规则”
- 已在 `docs/ai/SUBAGENT_WORKFLOW.md` 写明本仓增量口径
- 已为 run/session 留痕预留 `docs/ai/runs/` 与 `.ai/session/`
