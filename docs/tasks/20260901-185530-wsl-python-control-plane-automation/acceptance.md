# 验收目标

证明本次改造不仅完成脚本迁移，而且真实达到“普通任务更轻、大型任务不跑偏、review 可自动循环、WSL 正常链稳定、CFM 跨会话共享”的理想效果。

## 验收标准

- 问答不创建 GTO 工件、不派子代理；小任务等待确认但不误启完整 GTO；大型任务使用六要点和六工件。
- Codex 做语义判断，Python 不从用户自然语言关键词推断任务类型。
- 六工件职责分离且合同版本一致，state/task/events 不保存长日志、完整 diff 或聊天。
- same finding 可跨 review subtask 复用；每个 finding 独立最多三次实际返修；open finding 禁止完成。
- 正式 Codex 控制面命令全部使用 WSL Python/Linux 原生命令，不依赖 Codex hook。
- CFM 使用 Windows/WSL 同一物理目录，跨进程/会话共享，容量满不拒绝记录，未解决 pending 不丢。
- 独立 reviewer 对最新 scoped changes 给出 `final/pass`。

## 必备证据

- TDD Red 输出：same finding duplicate 与 CFM capacity limit。
- 目标 Green 输出和回退实现后的命中证明。
- Python 全量测试、规则/文档/GTO 校验和 `git diff --check`。
- 三类 blind behavior 结果。
- review→fix→re-review→final 的完整 fixture。
- CFM 两进程、跨会话、Windows/WSL 路径哈希一致证据。
- 正常验证链没有 Windows executable 和 Codex hook 的审计证据。
- `REVIEW-001` findings/re-review/final 结论。

## 未决项

- 本任务无未决实施项；仓库级 `git diff --check` 仍会命中任务前既有的无关 CRLF/空白脏基线，本任务显式文件清单的 scoped diff check 已通过。
- Claude hooks 明确不在本次范围，已验证保持现状。

## GTO R1 返修证据

- `python3 -m unittest tests.harness.test_control_plane`：10/10 通过，覆盖六工件、批准失效、v3 反向门禁、依赖/dispatch/result 矛盾、same-finding 生命周期、每 finding 独立 R3、真实 source manifest、final/fail 路由、final/pass 过期和 GNU CLI。
- 真实 GNU `validate` 对当前旧 bootstrap state 返回非零，明确报告非法 `current_phase` 与陈旧六工件投影；证明修复命中了 R1 所指出的假绿路径。全任务状态仍须由协调器结合其他代理结果和真实 workspace baseline 统一迁移，不能由 GTO 实现者伪造。
- 生成态和 review-ready 态均通过 `schemas/orchestrator-task-state.schema.json` Draft 2020-12 校验；schema/template JSON 与本地 `$ref` 完整。

## 最终验收证据

- 全量 Python harness：33/33 通过；R2 后核心组合 30/30 通过（GTO 12、CFM 11、WSL runtime 7）。
- GTO schema allowlist 的根层和嵌套未知字段探针均被拒绝；当前任务 `validate` 通过。
- 三类 isolated blind behavior 3/3：问答零工件、小任务短计划、大型任务六要点与六工件。
- 8 个 stable finding 全部关闭；仅实际 fix dispatch 增加轮次，6 个停在 R1、2 个停在 R2。
- CFM 使用同一 Windows/WSL 物理 Store；真实 1028+ case 的 inspect/query/record-success 均降至秒内，容量和未解决归档回归通过。
- 最新源码已同步到真实 `/mnt/c/Users/Laptop/.codex`；strict doctor `ok=true`，无 runtime、receipt 或 retired-hook 问题。
- Codex 用户 hooks 为空，退役 managed receipt/lock 不存在；自定义 hook 保留与 Claude hooks 不变由隔离测试覆盖。

## 最终结论

- 独立 reviewer `/root/final_review` 已对最新 `b7eba2b2fd87d66b612248a0f3cad609d5ab5aa607e3273649e86432ca2fb6f5` 给出 `final/pass`；控制器 finalize 成功，任务状态为 `completed`。

修复闭环证据要求：`verification_contract` 已写入 bootstrap state；实际 `review_evidence` 由完成的文档、测试、实施与 reviewer 子任务回填。

## 当前结论

独立 final/pass 已覆盖最新 scoped source manifest，任务完成。
