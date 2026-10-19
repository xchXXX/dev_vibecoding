# Codex environment black-box adjudicated boundary closure

Task ID: `20260905-135110-264935-codex-blackbox-adjudicated-closure`

## 要做什么

在用户明确人工授权后，以一个受管跟进任务关闭原黑盒任务达到三轮上限后仍开放的 F003、F004、F005、F007 四个边界，并在同一审查人通过后继续冻结候选和真实 Codex 黑盒验收。

## 不做什么

- 不篡改或重开原任务 20260905-121534-602895-codex-environment-blackbox 的 blocked 状态和历史事件。
- 不修改 WSL 系统配置、安装依赖、联网获取包、提交推送或清理用户工作区。
- 安全复审通过和候选冻结前不启动真实 Codex。
- 不删除原任务关键证据、跟进任务证据或 .artifacts 下真实验收证据。

## 改哪些地方

- tests/benchmarks/codex_environment_autocompliance.py
- tests/harness/test_codex_environment_autocompliance.py
- docs/ai/tasks/20260905-135110-264935-codex-blackbox-adjudicated-closure
- docs/tasks/20260905-135110-264935-codex-blackbox-adjudicated-closure
- .artifacts/wsl-environment-blackbox

## 怎么实现落地

继承原任务已通过的 49 项基线，只为四个最终复审反例补充确定性测试和最小实现：所有 EvidenceFormatError 保留已完成命令；所有已识别命令生命周期事件的字符串输出参与敏感环境预扫描；reap 内再次 BaseException 也保留原中断并传播 unreaped；未回收时拒绝 remover。

## 怎么验收

- 四个审查反例在修改前稳定 Red，且失败是目标断言而非环境错误。
- 修改后新增反例和完整 focused module 全绿，无真实 Codex、网络或安装命令。
- 同一 reviewer /root/blackbox_security_review 对当前哈希关闭四项 finding。
- 49 项以上 focused module 与 61 项 WSL 环境回归重新通过，然后冻结候选。
- 实际 CODEX_HOME、配置默认模型、ephemeral JSON read-only 模式下执行黑盒；机器预检失败则以 INFRASTRUCTURE_BLOCKED 留证，不伪装 PASS。
- 只清理精确的 /tmp/codex-env-blackbox-* 测试夹具；关键证据持续保留。

## 有什么风险

- 四项边界涉及解析增量证据、敏感输出和多重中断，过宽修复可能误接受畸形事件或误杀合法输出。
- 当前实际 CODEX_HOME 可能仍缺受管 runtime 或继承 Windows TEMP，真实验收可能在零模型调用时被机器预检阻塞。
- 未回收子进程时必须保留隔离夹具，此时清理失败是正确结果，不能强删。
- 任何新高风险发现或范围扩张都停止并重新请求用户裁决。

## 当前状态

- status: `active`
- current_phase: `test_sync`
- next_action: `dispatch_ready_subtask`
