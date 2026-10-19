# Codex environment black-box adjudicated boundary closure v2

Task ID: `20260905-141409-274139-codex-blackbox-adjudicated-closure-v2`

## 施工目标

在用户明确人工授权后，以一个受管跟进任务关闭原黑盒任务达到三轮上限后仍开放的 F003、F004、F005、F007 四个边界，并在同一审查人通过后继续冻结候选和真实 Codex 黑盒验收。

## 前置条件

- 用户已确认六要点任务合同。
- 写入前已冻结范围、验收和风险。

## 执行顺序

继承原任务已通过的 49 项基线，只为四个最终复审反例补充确定性测试和最小实现：所有 EvidenceFormatError 保留已完成命令；所有已识别命令生命周期事件的字符串输出参与敏感环境预扫描；reap 内再次 BaseException 也保留原中断并传播 unreaped；未回收时拒绝 remover。

## 文档先行清单

- 先同步长期真源和任务施工文档。

## 测试同步清单

- 先建立最小 Red，再实施 Green 和相关回归。

## 实施批次

- tests/benchmarks/codex_environment_autocompliance.py
- tests/harness/test_codex_environment_autocompliance.py
- docs/ai/tasks/20260905-141409-274139-codex-blackbox-adjudicated-closure-v2
- docs/tasks/20260905-141409-274139-codex-blackbox-adjudicated-closure-v2
- .artifacts/wsl-environment-blackbox

## 每批写入范围

- tests/benchmarks/codex_environment_autocompliance.py
- tests/harness/test_codex_environment_autocompliance.py
- docs/ai/tasks/20260905-141409-274139-codex-blackbox-adjudicated-closure-v2
- docs/tasks/20260905-141409-274139-codex-blackbox-adjudicated-closure-v2
- .artifacts/wsl-environment-blackbox

## 验证命令

- 四个审查反例在修改前稳定 Red，且失败是目标断言而非环境错误。
- 修改后新增反例和完整 focused module 全绿，无真实 Codex、网络或安装命令。
- 同一 reviewer /root/blackbox_security_review 对当前哈希关闭四项 finding。
- 49 项以上 focused module 与 61 项 WSL 环境回归重新通过，然后冻结候选。
- 实际 CODEX_HOME、配置默认模型、ephemeral JSON read-only 模式下执行黑盒；机器预检失败则以 INFRASTRUCTURE_BLOCKED 留证，不伪装 PASS。
- 只清理精确的 /tmp/codex-env-blackbox-* 测试夹具；关键证据持续保留。

## 回退方案

- 四项边界涉及解析增量证据、敏感输出和多重中断，过宽修复可能误接受畸形事件或误杀合法输出。
- 当前实际 CODEX_HOME 可能仍缺受管 runtime 或继承 Windows TEMP，真实验收可能在零模型调用时被机器预检阻塞。
- 未回收子进程时必须保留隔离夹具，此时清理失败是正确结果，不能强删。
- 任何新高风险发现或范围扩张都停止并重新请求用户裁决。

## 审查与返工路径

独立 reviewer 记录稳定 finding_id；原实现者修复，同一 reviewer re-review，直至可验收。
