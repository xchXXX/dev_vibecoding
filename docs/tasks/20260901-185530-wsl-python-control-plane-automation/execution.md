# 施工目标

按文档同步、测试 Red、并行实现、统一验证、review 循环的顺序完成 WSL Python 控制面迁移，并保护当前工作区已有未提交内容。

# 前置条件

- 用户已明确批准六要点和施工图。
- `task_id=20260901-185530-wsl-python-control-plane-automation` 六工件已建立。
- 正式 code_impl 前由新 Python GTO 捕获精确 dirty overlap 和 SHA-256。
- verification contract 已写入 bootstrap `state.json`。

# 执行顺序

1. `DOC-001` 先同步长期真源。
2. 三个 test-verifier 并行写并执行预期 Red。
3. 三个 implementer 并行完成 GTO、CFM、Rules Python 主链。
4. 迁移 Ops 入口并安全移除 Codex hook。
5. test-verifier 统一执行 WSL、blind、review、CFM 验收。
6. `REVIEW-001` 初审；findings 回原 implementer；同 reviewer 复审直至 final/pass。

# 文档先行清单

- 规则系统的语义/机械分工。
- 六工件职责与一致性。
- `max_fix_rounds` 按 `finding_id` 的精确定义。
- WSL-only 正式入口与 Codex hook 移除。
- CFM 同物理 Store 和 WSL 单写者边界。

# 测试同步清单

- `test_control_plane.py`：六要点、六工件、next_action、same finding lifecycle。
- `test_command_failure_memory.py`：锁、容量、active/archive、同 Store。
- `test_rules_runtime.py`：结构化 profile 匹配，不进行自然语言推断。
- `test_wsl_runtime.py`：无 Windows 正常链、无 Codex hook。
- blind/benchmark：问答、小任务、大型任务与长上下文恢复。

# 实施批次

- D1：核心文档合同；依赖 bootstrap；收口为规则和长期真源一致。
- T1：三路 Red；依赖 D1；收口为目标失败类型与预期一致。
- I1：GTO/CFM/Rules 三路 Green；依赖各自 Red；收口为目标测试通过。
- I2：Ops 与 hook removal；依赖 I1；收口为正式入口 WSL-only。
- V1：统一验收；依赖全部实现；收口为理想行为证据齐备。
- R1..Rn：review 循环；同 finding 最多三次实际返修；收口为 final/pass 或 blocked。

# 每批写入范围

- D1：`AGENTS.md`、长期规则/文档、skill 文档、模板、本任务工件。
- T1：新 Python 测试和 fixtures，不写生产代码。
- I1-GTO：GTO schema/controller/templates。
- I1-CFM：CFM backend/schema。
- I1-Rules：规则与文档校验 Python 脚本及生成物。
- I2-Ops：bootstrap/sync/doctor/session 和对应测试。
- I2-Hook：仅 Codex hook 与 managed installer/tests/docs；不碰 Claude hooks。
- V1：测试、benchmark 和验收短证据。
- R1..Rn：finding 原始责任人的原 write_paths。

# 验证命令

```bash
python3 -m compileall -q scripts skills hooks tests
python3 -m unittest discover -s tests/harness -p 'test_*.py'
python3 scripts/generate_rules_index.py --repo-root "$PWD" --json
python3 scripts/validate_rules.py --repo-root "$PWD" --json
python3 scripts/validate_plan_docs.py --repo-root "$PWD" --json
python3 scripts/validate_doc_routing.py --repo-root "$PWD" --json
python3 skills/global-task-orchestrator/scripts/orchestrator_ctl.py --action validate --repo-root "$PWD" --task-id 20260901-185530-wsl-python-control-plane-automation --json
python3 scripts/start_session.py --repo-root "$PWD" --task-id 20260901-185530-wsl-python-control-plane-automation --json
git diff --check
```

附加验收：CFM 两进程并发/跨会话、1024+ case、same finding R1/R2、双 finding 独立 R3、blind behavior 和正常链 Windows executable 审计。`start_session.py` 只能 resume/validate 既有六工件任务；bootstrap 后 strict doctor 必须覆盖全局 `AGENTS.md`、bootstrap/sync receipt 和退休 hook 清理，并证明非托管 hook 与 Claude hooks 内容不变。

# 回退方案

- 不执行 Git destructive 命令。
- 每个重叠文件以派发前 SHA-256 为保护边界，漂移即停止。
- CFM 原地升级失败时恢复内容寻址备份，禁止双写。
- Python 等价入口未通过前不删除旧完整实现；退出旧入口由独立 reviewer 确认。

# 审查与返工路径

- 初审和后续复审统一使用 `REVIEW-001`。
- finding 使用稳定 `finding_id`，回到 `lineage.original_implementer`。
- re-review 复用 `lineage.original_reviewer`。
- 每次实际 implementer fix dispatch 才递增 `fix_round`；补证据不递增。
- 第三轮仍失败进入 blocked 或人工裁决。
- 所有 finding 关闭后执行独立 final review，覆盖最新 HEAD 或 scoped change hash。

# 实际执行结果

- 文档、GTO、CFM、规则运行时、Ops 和 Codex hook 退役按互斥写入范围并行完成；Claude hooks 未修改。
- GTO 以 v3 schema、六工件、`next_action` 和稳定 finding 状态机为唯一控制面；`validate` 直接执行正式 schema 的根层与嵌套 allowlist。
- CFM 保持 `/mnt/c/Users/Laptop/.codex/memories/command-failure-memory` 原物理目录，使用 Linux 文件锁、原子写、轻量索引、active/archive 和按需正文读取。
- `start_session.py` 只 resume/validate 六工件；Codex managed command-safety hook、receipt 和 lock 已退出，未新增替代 runner。
- 初审发现 6 条、集成补发现 1 条，加上性能审查 1 条，共 8 个 finding；全部由原实现者修复并由原 reviewer 关闭。实际 fix round 分布为 6 条 R1、2 条 R2，无 finding 达到 R3。

# 实际验证结果

- 全量 Python harness：33/33 通过；最终核心组合在 R2 后 30/30 通过，其中 GTO 12/12、CFM 11/11、WSL runtime 7/7。
- 三类 isolated blind behavior：问答、小改、大型任务 3/3 符合分流合同。
- CFM 真实 1028+ case 性能：inspect 约 0.27 秒、完整 query 约 0.658 秒、临时大库 record-success 约 0.394 秒。
- 真实 `/mnt/c/Users/Laptop/.codex` 在最新源码同步后 strict doctor `ok=true`，runtime、receipt、retired hooks 均无问题。
- GTO 反向探针会拒绝根层和嵌套未知字段；review manifest 排除当前任务控制工件、保留真实源码且无 missing 项。
