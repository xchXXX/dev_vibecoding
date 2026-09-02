# RULE_SCHEMA

项目级 rule 文件统一使用 YAML frontmatter，字段口径如下。

## 必填字段

```yaml
id: project.policy.命令失败闭环
title: 命令失败闭环
subject: command-failure-memory
scope: project
kind: policy
priority: 100
activation: model_decision
paths: []
intents: ["shell", "test", "build", "retry"]
owner: ai-governance
status: active
summary: 命令失败后先记录，重试前先查询，成功后回写。
linked_skill: command-failure-memory
enforcement: advisory
overrideable: true
override_mode: replace
overrides: []
override_reason: ""
```

## 字段定义

- `id`：全局唯一规则标识，建议格式为 `<scope>.<kind>.<中文标题>`。
- `title`：规则标题，应与文件主题一致。
- `subject`：规则主题键，用于冲突识别、覆盖解析与索引聚合。
- `scope`：规则作用域，合法值为 `global | project | path`。
- `kind`：规则主类，合法值为 `policy | workflow | architecture | quality | stack | style`。
- `priority`：同层冲突时的辅助优先级，数值越大优先级越高。
- `activation`：供 Codex 判断读取优先级的提示，合法值为 `always_on | model_decision | path | manual`；`always_on` 仅用于入口批准的最小必读集合。
- `paths`：相关路径提示；仅在 `scope=path` 或 `activation=path` 时填写具体项，不由 Python 自动匹配本轮规则。
- `intents`：相关语义或操作提示，供 Codex 结合当前上下文判断，不组成固定任务套餐。
- `owner`：维护人或维护域。
- `status`：规则状态，合法值为 `active | deprecated | draft`。
- `summary`：单句摘要，用于唯一机器元数据索引和人读视图。
- `linked_skill`：供 Codex 进一步判断是否适用的 skill 名称；无 skill 时填空字符串，不自动触发 skill。
- `enforcement`：执行方式，合法值为 `advisory | executable_backed`。
- `overrideable`：是否允许被更小作用域规则覆盖。
- `override_mode`：覆盖模式，首版支持 `merge | replace`。
- `overrides`：显式覆盖的 rule id 列表；未覆盖时为空数组。
- `override_reason`：覆盖理由；未覆盖时为空字符串。

## 约束说明

- 每个规则文件只允许一个主类，目录也必须与 `kind` 一致。
- 文件名一律使用中文，frontmatter 字段名保持英文。
- `summary` 应保持短句风格，不复制正文。
- `linked_skill`、`overrides`、`override_reason` 即使为空也建议显式保留，便于统一校验。
- 规则正文应聚焦单一语义，不在一个文件里混入多个独立约束。
