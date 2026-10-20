# 任务摘要

## 基本信息

- `task_id`: `20260828-150316-command-safety-gateway-c498ea`
- `title`: Codex Command Safety Gateway
- `status`: `active`
- `owner`: `main-coordinator`

## 目标

- 在命令执行前消除可预测失败，降低 Command Failure Memory 新增真实失败，并保持低延迟、低维护复杂度。

## 范围

### Scope In

- hooks/codex/command-safety/**
- scripts/install-command-safety-gateway.ps1
- skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1
- tests/harness/command-safety-gateway.integration.ps1
- tests/harness/control-plane.integration.ps1
- docs/tasks/20260828-150316-command-safety-gateway-c498ea/**
- docs/ai/tasks/20260828-150316-command-safety-gateway-c498ea/**

### Scope Out

- 不扫描磁盘或其他 clone/worktree
- Hook 热路径不读取 Command Failure Memory、不运行 git、不扫描父目录
- 不自动修复无法确定意图的命令
- 不接管用户已有的非本方案 Hook 条目
- 不引入常驻服务、MCP server 或新的包依赖

## 验收标准

- 路径缺失、PowerShell 管道、危险清理和 raw GTO state patch 在执行前被确定性拒绝或路由到安全入口
- expected-red 只在声明的失败类型命中时转为结构化成功，意外环境或基础设施错误仍非零退出
- 安全命令保持原输入并快速放行
- 安装保留 hooks.json 非托管内容，变更前创建内容寻址备份并写 machine-local receipt
- 目标回放、相关回归和新进程 smoke test 通过，独立 reviewer 给出 final/pass

## 停止条件

- 目标文件与既有脏改动存在无法安全合并的语义冲突
- 官方 Hook 合同无法表达 deny 或 updatedInput
- 当前 runtime 禁用了 hooks 且需要扩大系统配置权限
- 性能回放 p95 超过 80ms 且无法在无常驻服务前提下降低

## 关键决定

- 使用无第三方依赖的 Node 单文件网关
- Hook 只处理高置信度前置判断，不确定时返回一个安全入口
- CFM 只保留真实未知失败闭环，不进入预执行热路径
- 全局安装只管理带稳定 id 的自身条目，并要求脚本哈希信任审核
- 先覆盖历史高频错误族，不构建通用 shell parser

## 当前阶段

- `current_phase`: `test_sync`

## 子任务

### DOC-001

- `title`: 冻结设计、施工与验收合同
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 把已批准设计整理为可执行、可审查的最小文档合同。

### TEST-001

- `title`: 建立命令失败前置防护回放测试
- `role`: `test-verifier`
- `status`: `pending`
- `goal`: 先写最小失败回放，证明实现前缺少目标能力。
- `dependencies`: `DOC-001`

### IMPL-001

- `title`: 实现轻量 Hook 网关与安全安装器
- `role`: `backend-implementer`
- `status`: `pending`
- `goal`: 实现 Hook 判定、expected-red、contained cleanup、project verify 和安全全局安装。
- `dependencies`: `TEST-001`

### IMPL-002

- `title`: 补齐 GTO 结构化状态更新动作
- `role`: `backend-implementer`
- `status`: `pending`
- `goal`: 新增带 subtask_id、状态校验和原子写入语义的结构化结果更新 action。
- `dependencies`: `TEST-001`

### VERIFY-001

- `title`: 执行集成、性能与隔离安装验证
- `role`: `test-verifier`
- `status`: `pending`
- `goal`: 用新进程和隔离 CodexHome 验证命中、回归、安装合并与延迟。
- `dependencies`: `IMPL-001`, `IMPL-002`

### REVIEW-001

- `title`: 独立最终复审
- `role`: `reviewer`
- `status`: `pending`
- `goal`: 独立审查安全性、正确性、性能证据与脏工作区边界。
- `dependencies`: `VERIFY-001`

## 更新时间

- `2026-08-28T15:21:00+08:00`
