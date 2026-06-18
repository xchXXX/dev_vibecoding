# RULES INDEX

- local_rule_count: 21
- global_rules_mode: none
- warning_count: 1

| id | subject | kind | scope | activation | linked_skill | file |
| --- | --- | --- | --- | --- | --- | --- |
| global.architecture.通用文件存储位置 | shared-file-storage-layout | architecture | global | always_on |  | rules/items/architecture/通用文件存储位置.md |
| project.architecture.仓库目录边界 | repository-boundaries | architecture | project | always_on |  | rules/items/architecture/仓库目录边界.md |
| project.architecture.真源入口 | source-of-truth-entrypoints | architecture | project | always_on |  | rules/items/architecture/真源入口.md |
| global.policy.变更约束 | change-governance | policy | global | always_on |  | rules/items/policy/变更约束.md |
| global.policy.测试临时文件必须清理 | test-temp-cleanup | policy | global | always_on |  | rules/items/policy/测试临时文件必须清理.md |
| global.policy.核心文档与测试先于代码实现 | docs-tests-before-code | policy | global | always_on |  | rules/items/policy/核心文档与测试先于代码实现.md |
| global.policy.命令失败闭环 | command-failure-memory | policy | global | always_on | command-failure-memory | rules/items/policy/命令失败闭环.md |
| global.policy.平台噪音与任务失败判定 | platform-noise-vs-task-failure | policy | global | always_on |  | rules/items/policy/平台噪音与任务失败判定.md |
| global.policy.文件存储位置强制约束 | shared-file-storage-guardrails | policy | global | always_on |  | rules/items/policy/文件存储位置强制约束.md |
| global.policy.子代理慢任务非异常不得干预 | subagent-non-interference | policy | global | always_on |  | rules/items/policy/子代理慢任务非异常不得干预.md |
| global.policy.PowerShell7脚本基线 | pwsh7-baseline | policy | global | always_on |  | rules/items/policy/脚本运行基线.md |
| global.policy.Windows命令构造约束 | windows-command-construction | policy | global | always_on |  | rules/items/policy/命令构造约束.md |
| global.quality.方案与施工文档必填字段 | plan-doc-required-sections | quality | global | always_on |  | rules/items/quality/方案与施工文档必填字段.md |
| global.quality.提交与验证 | verification-and-commits | quality | global | always_on |  | rules/items/quality/提交与验证.md |
| global.style.说明默认使用中文 | response-language | style | global | always_on |  | rules/items/style/说明默认使用中文.md |
| global.workflow.落盘前先给简短计划 | plan-before-write | workflow | global | always_on |  | rules/items/workflow/落盘前先给简短计划.md |
| global.workflow.审阅返工固定路由 | review-rework-routing | workflow | global | always_on |  | rules/items/workflow/审阅返工固定路由.md |
| global.workflow.文档分流与实现前闸门 | document-routing-and-pre-implementation-gate | workflow | global | always_on |  | rules/items/workflow/文档分流与实现前闸门.md |
| global.workflow.修复闭环闸门 | fix-closure-verification-gate | workflow | global | always_on | fix-closure-gate | rules/items/workflow/修复闭环闸门.md |
| global.workflow.用户提问先回答再继续 | answer-before-resume | workflow | global | always_on |  | rules/items/workflow/用户提问先回答再继续.md |
| global.workflow.长任务实施顺序 | long-task-sequencing | workflow | global | always_on | global-task-orchestrator | rules/items/workflow/长任务实施顺序.md |

## Warnings
- 未发现同级 ai-harness/rules/items，已按空全局规则集处理: C:\Users\72385\dev\ai-harness\rules\items
