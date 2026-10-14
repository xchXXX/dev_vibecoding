# RULES_ENTRY

本文件只说明项目规则系统的运行时装配方式，不复制各条规则正文。

## Codex 读取顺序

1. 先读取项目根 `AGENTS.md`。
2. 再读取 `rules/registry/RULES_INDEX.json` 的元数据，不聚合所有规则正文。
3. 固定读取三条最小必读规则：`global.policy.变更约束`、`global.workflow.用户提问先回答再继续`、`global.style.说明默认使用中文`。
4. 对其余规则，由 Codex 结合对话语义、目标内容、风险、当前阶段和本轮实际操作自由选择；索引中的 `intents`、`paths`、`summary`、`linked_skill` 只是判断提示，不是强制映射。
5. 只有 Codex 判断某条规则与当前工作相关时，才读取对应规则正文；只有进一步判断其 `linked_skill` 确实适用时，才读取对应 `SKILL.md`。
6. 能自动校验的约束以 当前执行环境的 Python 脚本、测试或 doctor 为准，prose rule 只承担入口提示与非结构化约束。

正常交互链不调用 Python 解释自然语言、生成 `task_profile`、匹配本轮规则或拼装固定规则套餐。Python 只在离线维护和验收时生成、校验 `RULES_INDEX.json`；索引不承载规则正文，也不生成全正文聚合运行时视图。

## 项目与全局规则关系

- 项目规则真源位于 `rules/items/`，按 `kind` 分目录维护；当前仓库中除少量 architecture 入口外，绝大多数条目按全局规则维护。
- 全局规则真源位于 `<harness-root>/rules/`；在本仓中，`<harness-root>` 就是当前仓库根。
- 当前项目在装配时先应用项目本地规则；其他项目消费本仓全局规则时，必须显式传入 `--global-rules-root <harness-root>` 才纳入其中 `scope != project` 的条目。未传入时只处理项目本地规则，不自动发现其他 clone 或工作区。
- `RULES_INDEX.json` 是唯一机器可读规则元数据索引；人读视图可以离线生成，但不作为运行时选择真源。

## 冲突解析

- 默认先合并，不冲突则同时生效。
- 项目规则不能静默覆盖全局规则；发生覆盖时必须显式声明 `overrides` 与 `override_reason`。
- 若被覆盖规则 `overrideable=false`，则覆盖无效且应视为校验失败。
- 同层规则先按 `subject` 判断是否冲突；冲突时按 `priority` 排序，仍无法消歧则校验失败。
- `path` 规则可覆盖 `project/global`，`project` 规则可覆盖 `global`，反向覆盖无效。
- `override_mode=merge` 只有在脚本明确实现对应合并语义时，才能解读为“基于目标规则生成合并后的生效结果”；不要假定存在字段级深度 merge。

## 何时转 Skill

- Codex 判断规则与当前工作相关后，若进一步判断其 `linked_skill` 适用，再读取并执行对应 skill。
- 多步协作、失败恢复、编排式流程放在 `skills/*/SKILL.md`，不要在普通规则文件内重复抄写整段工作流。
- 普通规则只声明触发条件、边界和进入 skill 的时机。

## 运行时边界

- `RULES_ENTRY.md` 不承载完整规则正文，不代替 `RULES_INDEX`、脚本或测试，也不是每轮额外必读文件。
- 显式 GTO 任务的方案文档与施工文档固定字段以 `rules/registry/方案与施工文档字段规范.md` 及其校验脚本为准。
- 中文说明默认使用中文；字段名、路径、脚本参数、代码标识符保持原样。
- 已删除的旧 `rules/common/*` 与旧 `rules/*.md` 结构不恢复，统一以 `rules/registry/` 与 `rules/items/` 为准。
