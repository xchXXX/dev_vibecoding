# WSL 工具分层与 GTO 运行时根治

Task ID: `20260902-103736-970530-wsl-gto-tooling-hardening`

## 要做什么

根治 WSL 下工具缺失分层、GTO 文件参数与运行时依赖缺失、旧会话真源漂移和 CFM 复发记录问题，并完成真实集成验收与独立 review。

## 不做什么

- 不引入 PowerShell、cmd、hook、Node 控制面、守护进程、通用 wrapper 或自动重试
- 不保留 --result-json 与 --contract-json 的双轨兼容逻辑
- 不把项目 Python/Node 依赖安装到 WSL 系统层，也不把系统工具塞进项目依赖
- 不覆盖任务范围外现有未提交改动

## 改哪些地方

- skills/global-task-orchestrator
- schemas/orchestrator-task-state.schema.json
- scripts/bootstrap-local.py
- scripts/sync-codex.py
- scripts/doctor-core.py
- rules/items
- rules/registry
- templates/codex/AGENTS.global.md
- docs/ARCHITECTURE.md
- docs/CODEX_COMPAT.md
- docs/INSTALL.md
- scripts/README.md
- tests/harness
- <CODEX_HOME>/memories/command-failure-memory

## 怎么实现落地

先冻结最小复现并清空重建 CFM；三个隔离子代理按互斥文件范围并行完成 GTO 文件参数与 choices、同步后运行时自包含与重启提示、工具缺失系统层/项目层规则；主协调器整合后执行真实 WSL 同步运行、CFM 回放、全量回归和 review/fix/re-review。

## 怎么验收

- --result-json-file 与 --contract-json-file 从真实文件工作，旧内联参数被移除且失败不写状态
- --brief-kind 等固定参数由 argparse choices 直接拒绝非法值
- 隔离 CODEX_HOME 同步后的 GTO 能实际读取 schema 并运行 validate
- 新增工具缺失分层规则进入索引且普通交互不运行 Python matcher
- 全局 AGENTS 或 skill 更新后输出 restart_required，长任务平台冲突要求重新核对磁盘真源
- CFM 清空后只补录本轮真实 GTO 失败，query-before-retry 能命中且修复后 record-success 可验证
- 聚焦测试、完整 harness 回归、doctor strict、规则和文档校验、git diff --check 全部通过
- 独立 reviewer 覆盖最新变更，findings 经原实现者修复和同一 reviewer 复审至 final/pass

## 有什么风险

- CFM 清空是破坏性操作，必须只作用于已确认的单一数据目录并在清空后重建结构
- 当前工作区已有大量未提交改动，子代理必须使用互斥写路径和窄补丁
- 移除旧 JSON 内联参数会影响仍使用旧命令的当前会话，需同步所有活动态文档和测试
- 当前长会话不会热加载新 AGENTS，最终黑盒验收必须使用全新 fork_turns=none 代理

## 当前状态

- status: `completed`
- current_phase: `review`
- next_action: `none`
