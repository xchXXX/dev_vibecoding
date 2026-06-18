# RULES_ENTRY

本文件只说明项目规则系统的运行时装配方式，不复制各条规则正文。

## 装配顺序

1. 先读取项目根 `AGENTS.md`，获取最高优先级入口约束与规则系统入口说明。
2. 再读取 `rules/registry/RULES_ENTRY.md`，确认本项目的规则装配、冲突解析与 skill 转交口径。
3. 加载项目级 `RULES_INDEX` 中 `activation=always_on` 的规则，并按 `scope` 区分全局基线与项目增量。
4. 根据当前任务的 `intents` 继续命中按需规则。
5. 若规则声明 `activation=path` 或 `scope=path`，再按目标路径匹配 `paths`。
6. 若命中规则携带 `linked_skill`，转去读取对应 `SKILL.md`。
7. 能自动校验的约束以脚本、测试、hook 或 doctor 链路为准，prose rule 只承担入口提示与非结构化约束。

## 项目与全局规则关系

- 项目规则真源位于 `rules/items/`，按 `kind` 分目录维护；当前仓库中除少量 architecture 入口外，绝大多数条目按全局规则维护。
- 全局规则真源位于 `C:/Users/72385/dev/ai-harness/rules/`。
- 当前项目在装配时先应用项目本地规则；若调用时显式传入全局规则根，或脚本成功自动发现可用的全局规则根，再把其中 `scope != project` 的条目纳入当次解析。
- `RULES_RESOLVED.json` 输出的是按当前调用上下文解析后的生效视图；若当次没有可用的全局规则根，则其全局部分应退化为空。

## 冲突解析

- 默认先合并，不冲突则同时生效。
- 项目规则不能静默覆盖全局规则；发生覆盖时必须显式声明 `overrides` 与 `override_reason`。
- 若被覆盖规则 `overrideable=false`，则覆盖无效且应视为校验失败。
- 同层规则先按 `subject` 判断是否冲突；冲突时按 `priority` 排序，仍无法消歧则校验失败。
- `path` 规则可覆盖 `project/global`，`project` 规则可覆盖 `global`，反向覆盖无效。
- `override_mode=merge` 只有在脚本明确实现对应合并语义时，才能解读为“基于目标规则生成合并后的生效结果”；不要假定存在字段级深度 merge。

## 何时转 Skill

- 命中 `linked_skill` 的规则，应优先读取并执行对应 skill。
- 多步协作、失败恢复、编排式流程放在 `skills/*/SKILL.md`，不要在普通规则文件内重复抄写整段工作流。
- 普通规则只声明触发条件、边界和进入 skill 的时机。

## 运行时边界

- `RULES_ENTRY.md` 不承载完整规则正文，不代替 `RULES_INDEX`、脚本或测试。
- 长任务下方案文档与施工文档的必填字段以 `rules/registry/方案与施工文档字段规范.md` 及其校验脚本为准。
- 中文说明默认使用中文；字段名、路径、脚本参数、代码标识符保持原样。
- 已删除的旧 `rules/common/*` 与旧 `rules/*.md` 结构不恢复，统一以 `rules/registry/` 与 `rules/items/` 为准。
