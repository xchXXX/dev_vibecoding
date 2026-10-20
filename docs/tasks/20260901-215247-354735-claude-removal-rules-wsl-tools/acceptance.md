# 清除 Claude、自由按需规则与 WSL 工具基线

Task ID: `20260901-215247-354735-claude-removal-rules-wsl-tools`

## 验收目标

证明本机正式开发环境已经成为纯 Codex/WSL 轻量控制面，并且规则自由选读与工具基线有可重复机械闸门。

## 验收标准

- 仓库活跃入口和用户目录无 Claude 运行时资产
- 正式 Codex 控制面和验收链不调用 ps1/cmd
- RULES_INDEX.json 是唯一机器元数据索引且不含正文，RULES_RESOLVED.json 不存在
- always_on 仅为批准的最小必读集合，其他规则由 Codex 自由选读
- WSL 常用工具和 Linux pnpm 可用且 doctor 可审计
- 全量 Python、盲测、真实 runtime、独立 final/pass 通过

## 最终结论

独立 final/pass 已覆盖最新 scoped source manifest，任务完成。

## 必备证据

- 改造前 Claude/Windows 资产、21 条 `always_on`、正文聚合和工具缺失的准确 Red。
- 改造后同一检查 Green，证明命中原问题而非绕过。
- `RULES_INDEX.json` 不含规则正文，且不存在运行时 Python 语义匹配入口。
- isolated Codex blind behavior 展示实际读取路径，并证明非必读规则由 Codex 自由选择。
- `/mnt/c/Users/Laptop/.claude` 不存在；CFM Store 路径和内容仍存在。
- WSL 工具版本、Linux 路径来源、pnpm 可执行性和 strict doctor 证据。
- 全量 Python 回归、规则/文档校验、独立 review/fix/re-review/final 证据。

## 未决项

- 无阻塞未决项。
- 历史任务留痕和非活跃 `.artifacts` 内容按审计用途保留，不属于正式开发入口。
- 工作区原有未提交改动保持不动；本任务未执行 commit、merge、push 或清理。

## 已通过证据

- 改造前三组 Red 均准确命中原问题；改造后清理专项 3/3、规则专项 6/6、工具专项 2/2 Green。
- 全量 Python harness：43/43 Green，运行结果明确为 `OK`。
- `RULES_INDEX.json` 中 `always_on` 精确为三条批准规则；索引无正文，`RULES_RESOLVED.json` 不存在，Python 无运行时语义 matcher/profile API。
- isolated blind behavior 四个场景分别自由选出 0/4/4/7 条可选规则，15 次叶子元数据核对零不一致；README 两项 finding 已修复并复审通过。
- `/mnt/c/Users/Laptop/.claude` 已永久删除；`/mnt/c/Users/Laptop/.codex/memories/command-failure-memory` 仍在原位。
- 真实 bootstrap、sync、strict doctor 全部 `ok=true`；doctor 报告无缺失工具、无 Windows 路径泄漏，source/runtime controller SHA 一致。
- 规则校验 23 条零错误零警告；方案文档和路由校验覆盖 9 个任务、27 份 Markdown，全部通过。
- `FINAL-WSL-001` 与 `FINAL-GTO-002` 各 1 轮关闭，`FINAL-SCOPE-003` 第 2 轮关闭；`max_fix_rounds` 按各自 `finding_id` 单独计数。
- 最终 source manifest 已覆盖 controller、回归测试及 `fix_delta.changed_files`；任一纳入文件变化都会改变审阅目标哈希。
