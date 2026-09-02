# WSL 工具分层与 GTO 运行时根治

Task ID: `20260902-103736-970530-wsl-gto-tooling-hardening`

## 施工目标

根治 WSL 下工具缺失分层、GTO 文件参数与运行时依赖缺失、旧会话真源漂移和 CFM 复发记录问题，并完成真实集成验收与独立 review。

## 前置条件

- 用户已确认六要点任务合同。
- 写入前已冻结范围、验收和风险。

## 执行顺序

先冻结最小复现并清空重建 CFM；三个隔离子代理按互斥文件范围并行完成 GTO 文件参数与 choices、同步后运行时自包含与重启提示、工具缺失系统层/项目层规则；主协调器整合后执行真实 WSL 同步运行、CFM 回放、全量回归和 review/fix/re-review。

## 文档先行清单

- 先同步长期真源和任务施工文档。

## 测试同步清单

- 先建立最小 Red，再实施 Green 和相关回归。

## 实施批次

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

## 每批写入范围

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

## 验证命令

- --result-json-file 与 --contract-json-file 从真实文件工作，旧内联参数被移除且失败不写状态
- --brief-kind 等固定参数由 argparse choices 直接拒绝非法值
- 隔离 CODEX_HOME 同步后的 GTO 能实际读取 schema 并运行 validate
- 新增工具缺失分层规则进入索引且普通交互不运行 Python matcher
- 全局 AGENTS 或 skill 更新后输出 restart_required，长任务平台冲突要求重新核对磁盘真源
- CFM 清空后只补录本轮真实 GTO 失败，query-before-retry 能命中且修复后 record-success 可验证
- 聚焦测试、完整 harness 回归、doctor strict、规则和文档校验、git diff --check 全部通过
- 独立 reviewer 覆盖最新变更，findings 经原实现者修复和同一 reviewer 复审至 final/pass

## 回退方案

- CFM 清空是破坏性操作，必须只作用于已确认的单一数据目录并在清空后重建结构
- 当前工作区已有大量未提交改动，子代理必须使用互斥写路径和窄补丁
- 移除旧 JSON 内联参数会影响仍使用旧命令的当前会话，需同步所有活动态文档和测试
- 当前长会话不会热加载新 AGENTS，最终黑盒验收必须使用全新 fork_turns=none 代理

## 审查与返工路径

独立 reviewer 记录稳定 finding_id；原实现者修复，同一 reviewer re-review，直至可验收。

## 实际施工记录

- CFM：旧目录按用户授权移入系统回收站，随后重建原路径空库；清空后补录上轮 5 个真实失败，全部完成 query-before-retry 和成功解法回写。施工期间新发生的真实错误也按同一闭环处理，没有另建数据库。
- GTO CLI：删除 `--result-json`、`--contract-json`，新增 `--result-json-file`、`--contract-json-file`；关闭 argparse 长选项缩写，`action/context-mode/brief-kind/phase` 使用 choices。
- GTO runtime：`sync-codex.py` 同步 canonical schema 到 `CODEX_HOME/schemas`；bootstrap 输出 `restart_required/restart_reasons`；strict doctor 真实运行安装版 GTO validate。
- 工具分层：新增 `activation=model_decision` 的全局规则，区分 WSL 官方系统包、项目 Python/Node 依赖和浏览器自动化运行时。当前任务确需且官方包、目标发行版、范围明确时可直接安装缺失包；第三方源、广泛升级、卸载、发行版变更或范围不清仍需确认。
- 主控复验：`test_control_plane` 37/37、`test_wsl_runtime` 11/11、`test_rules_runtime` 7/7 通过；规则索引生成和校验通过。
- 真实同步：bootstrap 已写入实际 `/mnt/c/Users/Laptop/.codex`，返回 `restart_required=true`，原因同时包含全局 AGENTS、skill 和 schema 变化；安装版 GTO 已成功 validate 当前任务，并从结果文件真实执行 `record-subtask-result`。

## 当前剩余步骤

- 完整 harness 首轮 75 项中 1 项失败：发现用户目录下重新出现一个 0 字节空 `.claude` 目录。按既有纯 Codex 清理授权移入回收站后，第二轮 `Ran 75 tests ... OK`；该失败已写入 CFM 并完成 query-before-retry 与成功回写。
- strict doctor 通过：4 个 managed skill、canonical schema、receipt、全局 AGENTS、hooks 空状态、安装版 GTO validate 和 WSL 工具清单均为 `ok=true`。
- 文档路由校验通过：12 个任务、36 份 Markdown，无错误和警告。
- 仓库级 `git diff --check` 被任务外既有 `.gitignore`、`.playwright-cli` 与旧 fixture 的 CRLF/尾随空格噪音阻断；没有改写这些用户既有脏文件。对本任务 tracked 写路径执行的窄范围 `git diff --check` 通过。
- 独立 reviewer 首轮给出 high finding `GTO-CONTRACT-FILE-ATOMICITY-001`：无效 init 合同在 schema 拒绝前留下半任务。finding 已按固定 lineage 返回 `/root/gto_cli_file_args`，fix round 1 将完整候选 state 校验提前到锁和任一工件写入之前，并新增原子性、锁目录无残留及 CLI 缩写拒绝测试。
- finding 修复后主控复验：聚焦 2 项通过，control-plane 40/40 通过，完整 harness `Ran 78 tests in 171.471s ... OK`；真实 CODEX_HOME 已再次同步，bootstrap 返回 `managed_skill_runtime_changed`。
- 记录 reviewer 的“re-review pass + 原 finding closed”时，控制器暴露语义矛盾：只要携带 finding 就强制 verdict=fail。已做最小修复，允许原 reviewer 用 `re_review/pass` 关闭全部既有 finding；仍拒绝 open/未知 finding 以及 task/final pass 携带 finding。
- 第二轮语义修复后主控复验：聚焦 3 项通过，control-plane 42/42 通过，完整 harness `Ran 80 tests in 171.477s ... OK`；finding 已由原 reviewer 的 pass 结果关闭，真实 CODEX_HOME 再次同步。
- 同一 reviewer 对最新增量再次复核，独立运行完整 harness 80 项并确认安装版与真源哈希一致；最终对 review target `9d96174da4a06703752fb62bf5ce608c0c24b639bac19cd29981569fdeabd606` 给出 `final/pass`，无新 finding。
