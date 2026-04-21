# 调度示例

示例 1：只出方案
- 用户：给出一个跨模块重构需求，但暂不实施。
- 路由：`reader -> planner`
- 结果：阅读委派 -> `plan` 草案 -> 用户答疑 -> 冻结 `plan` -> 结束。

示例 2：先补上下文再实施
- 用户：描述了一个后端问题，但调用链与影响面不清。
- 路由：`reader -> backend-implementer -> test-verifier`
- 结果：先由 `reader` 补齐证据路径，再进入实现与验证。

示例 3：文档、测试、代码并行后审查
- 用户：确认一个后端行为修复方案。
- 路由：`doc-curator` + `test-verifier` + `backend-implementer`（并行）-> `reviewer`（合流）
- 结果：
  - 文档工单
  - 测试工单
  - 代码工单（依赖测试边界明确后执行）
  - `reviewer` 输出 findings 与验收结论

示例 4：先文档后代码
- 用户：契约字段要先达成一致。
- 路由：`doc-curator -> backend-implementer -> reviewer`
- 结果：先更新文档与契约，再写测试与代码，最后审查验收。

示例 5：纯排查
- 用户：要求先定位线上问题。
- 路由：`reader`
- 结果：阅读/排查工单 -> findings -> 建议，不进入代码实施。

示例 6：高风险回退
- 用户：多模块改动后验收失败。
- 路由：`reviewer -> reader -> test-verifier`
- 结果：`reviewer` 判定证据不足并开出 findings，回退 `reader` 补证据，再由 `test-verifier` 复核。
