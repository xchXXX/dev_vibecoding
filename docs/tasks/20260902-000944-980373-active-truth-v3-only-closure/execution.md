# 活跃真源 v3-only 全量收口

Task ID: `20260902-000944-980373-active-truth-v3-only-closure`

## 施工目标

把仓库当前活跃真源、命令、规则、AGENTS.md、skills、schema、模板、测试与真实 Codex runtime 全量收口到纯 Codex、WSL Python 3、规则由 Codex 语义自由选读、GTO 仅支持真实 action 且只接受 v3 的唯一逻辑，并完成独立 review、返修和 re-review。

## 前置条件

- 用户已确认六要点任务合同。
- 写入前已冻结范围、验收和风险。

## 执行顺序

先用失败测试冻结活跃真源、CLI、schema、模板和 runtime 的唯一合同；随后按互不重叠写入边界并行修正文档规则、控制器与 schema、模板与 benchmark；再运行 bootstrap/sync/doctor 和全量测试，最后由独立 reviewer 审查，finding 按同一 finding_id 返给原实现者修复并 re-review。

1. TEST-RED-001 写入测试并运行单测，确认失败命中真实旧残留。
2. Red 固定后并行执行 DOC-001、IMPL-CONTROL-001、IMPL-TEMPLATE-001。
3. 三个实现面各自先跑最小相关测试，再由主协调器运行合并回归。
4. SYNC-VERIFY-001 在源码全部通过后执行 bootstrap、sync、strict doctor 和全量 unittest。
5. REVIEW-001 独立审查；存在 finding 时停止 finalization，路由返修并 re-review。

## 文档先行清单

- 先同步长期真源和任务施工文档。

## 测试同步清单

- 先建立最小 Red，再实施 Green 和相关回归。

## 实施批次

- AGENTS.md、README.md 与当前 docs 真源
- rules/registry 与活跃 rules/items
- skills/global-task-orchestrator、skills/command-failure-memory、skills/pre-dev-benchmark
- schemas、templates、agents
- scripts 与 tests/harness 自动门禁
- 真实 /mnt/c/Users/Laptop/.codex 受管 runtime

## 每批写入范围

- TEST-RED-001：`tests/harness/`
- DOC-001：`AGENTS.md`、`README.md`、当前 `docs/`、`rules/`、`scripts/README.md`
- IMPL-CONTROL-001：`skills/global-task-orchestrator/`、`skills/command-failure-memory/`、`schemas/`、`agents/`
- IMPL-TEMPLATE-001：`templates/`、`skills/pre-dev-benchmark/`
- SYNC-VERIFY-001：必要的 `scripts/`、`tests/harness/` 和真实 Codex 受管 runtime
- REVIEW-001：只写任务 review 状态和验收证据，不修改生产文件

## 验证命令

- `python3 -m unittest discover -s tests/harness -p 'test_*.py' -v`
- `python3 scripts/validate_rules.py --repo-root .`
- `python3 scripts/validate_plan_docs.py --repo-root .`
- `python3 scripts/validate_doc_routing.py --repo-root .`
- `python3 scripts/bootstrap-local.py --repo-root .`
- `python3 scripts/sync-codex.py --repo-root . --json`
- `python3 scripts/doctor-core.py --repo-root . --strict --json`
- GTO/CFM 旧单横线参数必须失败，GNU 双横线参数必须成功。
- `templates/task-state.example.json` 和 `templates/orchestrator/state.template.json` 必须通过 v3 schema。

## 回退方案

- 现有工作树包含大量用户未提交改动，若与本任务写路径重叠必须保留原内容并做窄范围修改
- 移除 CLI 和 schema 兼容会让旧调用立即失败，这是本次明确目标但必须由测试证明错误信息清楚
- 历史证据中的旧词不能被误判为当前兼容层，自动门禁必须限定当前活跃范围
- sync 会写入真实 Codex runtime，只能在源文件验证通过后执行并复核哈希

## 审查与返工路径

独立 reviewer 记录稳定 finding_id；原实现者修复，同一 reviewer re-review，直至可验收。

## 实际执行结果

- 首轮并行完成文档规则、控制器 schema、模板 benchmark 与 runtime 门禁收口。
- 独立 review 首轮登记 5 个稳定 finding；第 1 轮关闭 2 个，第 2 轮关闭其余 3 个，所有 fix 均返回原实现者并由同一 reviewer re-review。
- 控制器最终以 Git 实际改动和删除反查 review manifest，不再只信实施者自报；完整执行 Draft 2020-12 schema 和容量限制。
- v2 role map、Claude runtime、旧 Windows 正式入口与任意 hook 当前合同均已移除；项目模板、活跃规则和当前文档同步到真实机制。
- fresh 全量验收为 69 项 unittest 通过、3 类 validator 通过、strict doctor 9/9 通过、runtime 18/18 文件哈希一致。
- 独立 final reviewer 覆盖 317/317 个任务范围 Git dirty path 和 35/35 个删除项，最终 `final/pass` 绑定 `3220cf956c47bc6cee076abe57f6c7fa7b8b5040a60a23b2deae2fb10cdfe357`。
- 本任务临时 JSON 与 Python cache 已通过 `gio trash` 做可恢复清理；一次 `rm -rf` 被宿主安全策略拒绝，随后已按 Command Failure Memory 闭环记录、查询并回写安全解法。
