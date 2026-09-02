# Rules Index

本文件由 `python3 scripts/generate_rules_index.py` 生成；不要手工编辑。

- source fingerprint: `e3c059e465c79a61c51d3e46ac7c1dcf01a32de2ff1f06b64c0b54e2fe2cdbdc`
- local rules: 24

| id | scope | activation | priority | source |
|---|---|---|---:|---|
| `global.architecture.通用文件存储位置` | `global` | `model_decision` | 100 | `rules/items/architecture/通用文件存储位置.md` |
| `global.policy.WSL命令构造约束` | `global` | `model_decision` | 100 | `rules/items/policy/命令构造约束.md` |
| `global.policy.WSL工具与脚本基线` | `global` | `model_decision` | 100 | `rules/items/policy/脚本运行基线.md` |
| `global.policy.WSL工具分层与缺失依赖处理` | `global` | `model_decision` | 100 | `rules/items/policy/缺失工具分层与依赖处理.md` |
| `global.policy.变更约束` | `global` | `always_on` | 100 | `rules/items/policy/变更约束.md` |
| `global.policy.命令失败闭环` | `global` | `model_decision` | 100 | `rules/items/policy/命令失败闭环.md` |
| `global.policy.子代理慢任务非异常不得干预` | `global` | `model_decision` | 100 | `rules/items/policy/子代理慢任务非异常不得干预.md` |
| `global.policy.平台噪音与任务失败判定` | `global` | `model_decision` | 100 | `rules/items/policy/平台噪音与任务失败判定.md` |
| `global.policy.文件存储位置强制约束` | `global` | `model_decision` | 100 | `rules/items/policy/文件存储位置强制约束.md` |
| `global.policy.核心文档与测试先于代码实现` | `global` | `model_decision` | 100 | `rules/items/policy/核心文档与测试先于代码实现.md` |
| `global.policy.测试临时文件必须清理` | `global` | `model_decision` | 100 | `rules/items/policy/测试临时文件必须清理.md` |
| `global.quality.提交与验证` | `global` | `model_decision` | 100 | `rules/items/quality/提交与验证.md` |
| `global.quality.方案与施工文档必填字段` | `global` | `model_decision` | 100 | `rules/items/quality/方案与施工文档必填字段.md` |
| `global.style.说明默认使用中文` | `global` | `always_on` | 100 | `rules/items/style/说明默认使用中文.md` |
| `global.workflow.修复闭环闸门` | `global` | `model_decision` | 100 | `rules/items/workflow/修复闭环闸门.md` |
| `global.workflow.复杂任务全局编排` | `global` | `model_decision` | 100 | `rules/items/workflow/复杂任务全局编排.md` |
| `global.workflow.子代理委派与协作` | `global` | `model_decision` | 100 | `rules/items/workflow/子代理委派与协作.md` |
| `global.workflow.审阅返工固定路由` | `global` | `model_decision` | 100 | `rules/items/workflow/审阅返工固定路由.md` |
| `global.workflow.文档分流与实现前闸门` | `global` | `model_decision` | 100 | `rules/items/workflow/文档分流与实现前闸门.md` |
| `global.workflow.用户提问先回答再继续` | `global` | `always_on` | 100 | `rules/items/workflow/用户提问先回答再继续.md` |
| `global.workflow.落盘前先给简短计划` | `global` | `model_decision` | 100 | `rules/items/workflow/落盘前先给简短计划.md` |
| `global.workflow.长任务实施顺序` | `global` | `model_decision` | 100 | `rules/items/workflow/长任务实施顺序.md` |
| `project.architecture.仓库目录边界` | `project` | `model_decision` | 100 | `rules/items/architecture/仓库目录边界.md` |
| `project.architecture.真源入口` | `project` | `model_decision` | 100 | `rules/items/architecture/真源入口.md` |
