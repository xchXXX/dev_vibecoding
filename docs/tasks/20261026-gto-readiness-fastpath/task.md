# GTO 就绪推进的提前扫描纠正

这是用户已授权 GTO 就绪修复的性能遗漏修正，产品仍沿用 20261026-140342-385582-admin-mcp-chat，不复制控制面。沿用 codex/fix-gto-readiness，保护前次未提交文件及历史记录；不提交、推送、合并或部署。

## 根因与范围

真实 T01 登记约9分钟，阶段推进约5分钟。只读调用探针确认 current_candidate=null 时，_refresh_subtask_readiness 为 C01 调用完整验收检查并扫描候选。既有结果指纹扫描仍必须保留；不将近似墙钟耗时当作分摊计时。

最小修复只在 final_documentation 的未完成验收依赖例外前确认存在 status=frozen 且带 candidate_id 的候选；否则保持未就绪。冻结候选仍走原完整门禁，不引入事实缓存、不修改指纹、候选路径或原产品合同。

## 验证合同

- minimal_repro：无候选正常状态写入时仍触发候选扫描。
- hit_proof：独立测试追踪实际刷新入口，未冻结时完整门禁/候选扫描零调用，普通后继仍ready。
- diagnostic_checks：冻结候选覆盖不完整不放行，完整覆盖仍通过原检查。
- acceptance_checks：原qa安装态验证；原reviewer审查；既有就绪/身份/preflight结果按影响保留。
- non_goals：不优化既有结果指纹或重写候选遍历，不改产品state，不伪造墙钟性能指标。
- review_evidence：独立Red、Green、安装态调用次数及真实源/安装哈希。

## 文档判断

现行 workflow.md 已定义就绪与完整验收语义，本改动纠正多余执行而不改变合同，无需改写此前已归档文档。

## 分工

/root 实现；原 /root/qa 独立测试及安装验收；原 /root/reviewer 审查。范围只含controller的必要条件与新增独立测试。