# 跨机器 Harness 动态路径与 Bootstrap 验收

## 验收目标

证明仓库正式内容可跨机器复用，本机绝对路径只存在于受控的 machine-local receipt 和渲染后的全局入口中；证明同机多 clone 的选择是显式、确定且不会自动覆盖另一份工作区。

## 验收标准

- 根选择优先级、无效根失败和不扫描磁盘行为均有真实集成测试。
- 全局 AGENTS 模板机器无关，目标文件受 marker 管理；未托管文件保护、force 备份和幂等均通过。
- tracked rules registry 使用逻辑根，规则导入和 scope 过滤没有回归。
- doctor 能给出稳定 bootstrap/path issues，并区分活动态旧路径与历史证据。
- 本机全局 `AGENTS.md` 无 `72385`，选定根存在且规则入口可读。
- 另一已知 clone 未被本任务修改；实际路径只保留在运行时证据中。
- 全部相关测试、校验、strict doctor 和 diff 检查通过。

## 必备证据

- bootstrap 测试的预期 RED 与实现后 GREEN 输出。
- rules index 逻辑根测试的 RED/GREEN 输出。
- Windows 全局入口合同迁移前 RED、迁移后 GREEN 输出。
- `bootstrap.receipt.json`、managed 全局 AGENTS 和备份的非敏感元数据与 SHA-256。
- strict doctor JSON 中 `ok=true` 且无 bootstrap/path issues。
- 活动态写入范围固定字符串搜索结果为零。
- 两个 clone 的 Git 状态和目标规则文件 hash 对比，证明另一 clone 未被本任务写入。
- reviewer 对五个 `verification_contract.review_evidence` slot 的独立结论。

## 未决项

- 两个 clone 的最终提交、合并和同步策略不属于本任务，验收后另行决定。

已完成证据摘要：bootstrap 8/8、rules-index 7/7、rules-validation 8/8、codex-sync 42/42、Windows 5/5、plan-docs 19/19；`validate-plan-docs`、`validate-doc-routing`、rules 校验均通过，strict doctor 返回 `ok=true` 且 `bootstrap_issues=[]`。三个 tracked artifacts 的盘符绝对路径模式命中为 0；本机 managed marker、receipt hash 与备份文件名 hash 一致，无旧用户名标记，备份数为 1。独立 reviewer verdict 为 `APPROVED`，原两项 Important 已修复，无新 Critical/Important；另一已知 clone 无本任务 bootstrap/helper/template/task state。

## 最终结论

已完成。跨机器 bootstrap 的根选择、受控全局入口、逻辑 rules 显示路径与同机多 clone 非自动化边界均已通过独立复审；本任务不包含两个 clone 的最终提交、合并或同步策略。
