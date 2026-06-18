# RULE_CLASSIFICATION

项目规则只允许以下主类，且每条规则只能归入一个主类。

## 主类列表

- `policy`
- `workflow`
- `architecture`
- `quality`
- `stack`
- `style`

## 主类判定优先级

当一条候选规则同时像多个分类时，按以下优先级判断主类：

`policy > workflow > architecture > quality > stack > style`

## 判定口径

- `policy`：必须、禁止、闸门、不可绕过的边界约束。
- `workflow`：处理顺序、回合流程、执行编排要求。
- `architecture`：真源入口、目录边界、层级关系与归属说明。
- `quality`：验证、测试、review、验收与提交质量要求。
- `stack`：语言、框架、工具链或平台专属规范。
- `style`：说明口径、表达方式、输出语言等风格约束。

## 拆分要求

- 如果一段规则同时包含“必须/禁止”和“执行顺序”，优先拆成 `policy` 与 `workflow` 两个文件。
- 如果一段规则同时包含“目录归属”和“提交验证”，应拆成 `architecture` 与 `quality`。
- 不通过目录表达 `scope`，作用域统一由 frontmatter 的 `scope` 字段表达。
