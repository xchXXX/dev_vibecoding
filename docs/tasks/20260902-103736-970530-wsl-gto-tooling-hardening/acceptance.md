# WSL 工具分层与 GTO 运行时根治

Task ID: `20260902-103736-970530-wsl-gto-tooling-hardening`

## 验收目标

根治 WSL 下工具缺失分层、GTO 文件参数与运行时依赖缺失、旧会话真源漂移和 CFM 复发记录问题，并完成真实集成验收与独立 review。

## 验收标准

- --result-json-file 与 --contract-json-file 从真实文件工作，旧内联参数被移除且失败不写状态
- --brief-kind 等固定参数由 argparse choices 直接拒绝非法值
- 隔离 CODEX_HOME 同步后的 GTO 能实际读取 schema 并运行 validate
- 新增工具缺失分层规则进入索引且普通交互不运行 Python matcher
- 全局 AGENTS 或 skill 更新后输出 restart_required，长任务平台冲突要求重新核对磁盘真源
- CFM 清空后只补录本轮真实 GTO 失败，query-before-retry 能命中且修复后 record-success 可验证
- 聚焦测试、完整 harness 回归、doctor strict、规则和文档校验、git diff --check 全部通过
- 独立 reviewer 覆盖最新变更，findings 经原实现者修复和同一 reviewer 复审至 final/pass

## 必备证据

- 最小复现、命中证明、相关回归和独立审查证据齐全。

## 未决项

- 已通过：GTO 文件参数和旧参数拒绝、argparse choices、隔离与真实安装版 schema/validate、工具分层规则和三条 always_on 固定数量、bootstrap restart 信号、CFM query-before-retry 与 pending 清零。
- 已通过的聚焦测试：`test_control_plane` 37 项、`test_wsl_runtime` 11 项、`test_rules_runtime` 7 项。
- 已通过：两轮修复后的完整 harness 80 项、control-plane 42 项、最终 strict doctor、计划文档与文档路由校验、本任务 tracked 路径差异检查。
- 已知任务外噪音：仓库级 `git diff --check` 仍会报告既有 `.gitignore`、`.playwright-cli` 和旧 fixture 的 CRLF/尾随空格；本任务没有扩大范围清洗用户既有脏文件。
- 已完成首轮独立 review、fix round 1、同一 reviewer 的 re-review pass 与最新哈希 final/pass；原 high finding 已关闭，没有新 finding。

## 最终结论

独立 final/pass 已覆盖最新 scoped source manifest，任务完成。
