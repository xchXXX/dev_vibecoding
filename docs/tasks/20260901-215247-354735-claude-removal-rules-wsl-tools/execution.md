# 清除 Claude、自由按需规则与 WSL 工具基线

Task ID: `20260901-215247-354735-claude-removal-rules-wsl-tools`

## 施工目标

先以 Red 证明 Claude/Windows 资产、21 条 always_on、全正文聚合和工具缺失；再并行实施清理、索引改造和工具部署。Codex 自由选读规则，Python 只离线生成与校验元数据索引。

## 每批写入范围

- agents
- hooks
- scripts
- tests
- docs
- templates
- rules
- skills
- 真实 /mnt/c/Users/Laptop/.claude
- Ubuntu WSL packages
- 真实 /mnt/c/Users/Laptop/.codex runtime

## 前置条件

- 用户 .claude 永久删除不可恢复
- 工作区高度脏且必须保护无关修改
- apt/npm 全局安装需要一次 sudo 密码
- 旧 PowerShell 测试删除前必须确认 Python 等价覆盖

## 执行顺序

1. `DOC-001` 同步长期真源合同。
2. `TEST-CLAUDE-001`、`TEST-RULES-001`、`TEST-TOOLS-001` 并行建立三个准确 Red。
3. `IMPL-CLEAN-001`、`IMPL-RULES-001`、`IMPL-TOOLS-001` 按互斥写入范围并行 Green。
4. `VERIFY-ALL-001` 统一执行全量、blind behavior、真实 runtime 和工具版本验收。
5. `REVIEW-001` 独立审查；finding 回原实现者，同 reviewer 复审，最新 hash final/pass 后 finalize。

## 文档先行清单

- 先同步 `AGENTS.md`、规则入口、Codex 模板和纯 WSL 架构/安装/审查合同。

## 测试同步清单

- `test_pure_codex_cleanup.py` 锁定活跃资产和入口清零。
- `test_rules_runtime.py` 锁定最小必读、无正文聚合、无 Python matcher。
- `test_wsl_tools.py` 锁定真实工具、Linux 路径和 doctor 审计。

## 实施批次

- 清理批次：Claude 与 Windows 旧入口。
- 规则批次：元数据索引与 Codex 自由选读。
- 工具批次：doctor 审计与一次性 Ubuntu 工具部署。

## 写入边界

- 清理包独占 `agents/`、`hooks/`、Claude 专属脚本/测试/文档与非 Python Windows 旧入口。
- 规则包独占 `rules/`、`scripts/rules_index.py`、规则生成/校验脚本、规则入口模板和规则专项测试。
- 工具包独占 WSL 系统包、工具检查代码、doctor 工具基线和工具专项测试。
- 三包都需要修改的总览文档先由 `DOC-001` 定稿，之后按各自专属章节更新，冲突由主协调器裁决。

## 验证命令

```bash
python3 -m unittest discover -s tests/harness -p 'test_*.py'
python3 scripts/generate_rules_index.py --repo-root "$PWD" --json
python3 scripts/validate_rules.py --repo-root "$PWD" --json
python3 scripts/validate_plan_docs.py --repo-root "$PWD" --json
python3 scripts/validate_doc_routing.py --repo-root "$PWD" --json
python3 scripts/doctor-core.py --root "$PWD" --codex-home /mnt/c/Users/Laptop/.codex --strict --json
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py --action validate --repo-root "$PWD" --task-id 20260901-215247-354735-claude-removal-rules-wsl-tools --json
```

附加验收：仓库活跃面 Claude 清零、用户 `.claude` 不存在、正式链无 `.ps1/.cmd`、最小必读集合、无 `RULES_RESOLVED.json`、四类自由选读 blind behavior、工具全部解析到 Linux 路径。

## 实际施工记录

- `DOC-001`：源规则 `always_on` 从 21 条收敛为批准的 3 条，合同明确 Codex 按对话语义、目标内容或路径、风险、阶段和本轮操作自由选读。
- `TEST-CLAUDE-001`：改造前 3 个预期失败，准确命中 11 个活跃 Claude 资产、35 个正式 `.ps1/.cmd` 入口和真实用户 `.claude`。
- `TEST-RULES-001`：改造前 7 个预期失败，准确命中旧索引的额外 18 条 `always_on`、`RULES_RESOLVED.json` 和 4 个 Python matcher/profile API。
- `TEST-TOOLS-001`：改造前 2 个预期失败，准确命中固定工具缺失、Windows `corepack` 路径泄漏和 doctor 缺少工具审计字段。
- `IMPL-CLEAN-001`：删除活跃 Claude 运行时、已由 Python 等价覆盖的 PowerShell/CMD 正常入口和 Claude 专属测试/模板；保留历史任务与运行留痕。
- 精确删除 `/mnt/c/Users/Laptop/.claude` 前已确认真实路径和一级内容仅为 `backups/`、`sessions/`；删除后复核目录不存在，CFM Store 仍位于原路径。
- `IMPL-RULES-001`：删除运行时语义 matcher/profile API 与 `RULES_RESOLVED.json`；正式生成器只产出元数据 `RULES_INDEX.json` 和 Markdown 视图。
- `IMPL-TOOLS-001`：doctor 增加固定 WSL 工具审计；Ubuntu 24.04 安装冻结清单，Linux npm 安装 `corepack@0.36.0`、`pnpm@11.25.0`。由于可见 sudo 终端未能挂载，本次一次性部署使用宿主 `wsl.exe -d Ubuntu-24.04 -u root`，该入口未写入项目运行链。
- Node 工具首次验收发现 Linux npm 前缀为 `/opt/node-v24.19.0-linux-x64`，但 `/usr/local/bin` 只暴露 `node/npm`；补齐 `corepack/pnpm` 两个 Linux 符号链接后，同一工具测试转绿。

## 当前验证结果

- `python3 -m unittest discover -s tests/harness -p 'test_*.py' -v`：43/43 通过，确认不是零测试或空发现。
- `python3 scripts/validate_rules.py --repo-root . --json`：23 条规则，0 errors，0 warnings。
- `python3 scripts/validate_plan_docs.py --repo-root . --json`：9 个任务、27 份文档通过。
- `python3 scripts/validate_doc_routing.py --repo-root . --json`：9 个任务、27 份 Markdown 通过。
- 真实 `bootstrap-local.py`：`global_agents / sync / rules_generate / rules_validate / doctor` 全部完成。
- 真实 `sync-codex.py`：4 个受管 skill、18 个文件同步完成，0 warnings。
- 真实 strict doctor：`ok=true`，`missing_tools=[]`，`windows_path_tools=[]`；仓库与真实 runtime controller SHA 同为 `273ff3bbcb48c92f437c474bcaf4ab3f4609ffaa0935fb01a387ace55f48a709`。
- 清理专项 3/3、规则专项 6/6、工具专项 2/2 通过。
- isolated blind behavior 在四种场景中按五维语义分别自由选择 0/4/4/7 条可选规则，15 次叶子元数据核对均与 frontmatter 一致；发现的 README 命令和过时 matcher 文案已由原实现者修复并由同一盲测 reviewer 复审通过。
- 独立终审产生 `FINAL-WSL-001`、`FINAL-GTO-002`、`FINAL-SCOPE-003` 三个 finding；前两项各 1 轮闭环，`FINAL-SCOPE-003` 第 2 轮根治，均由原 reviewer 关闭。
- 最新 63 项 scoped source 审阅目标为 `d42e599e9eecd56e5c90e0feca524d03ee431c077d488a867a0b99d75ecea84a`；独立 reviewer 已返回 `final/pass`，无新增 finding。

## 回退与停止

- 删除前对精确目标做只读存在性核对；只删除用户明确授权的 `.claude`，不扩大到 `.codex`。
- apt 或 npm 安装需要 sudo 交互时停止自动输入，由用户在可见终端输入一次密码。
- 发现旧 PowerShell 文件仍承载无 Python 等价行为时，不直接删除，先补 Red/Green 等价覆盖。
- 不使用 `git reset --hard`、`git checkout --` 或其他破坏无关改动的命令。

## 回退方案

- 仓库改动按互斥文件边界返修，不重置无关 dirty 内容。
- 系统安装失败时保留实际包状态，修复根因后只重试失败步骤。
- 用户 `.claude` 为明确授权的永久删除目标，不提供虚假的可恢复承诺。

## 审查与返工路径

独立 reviewer 使用稳定 `finding_id`；每个 finding 的 `max_fix_rounds=3` 单独计数，原实现者修复，同 reviewer re-review，最新 scoped source 通过 final review 后才能完成。
