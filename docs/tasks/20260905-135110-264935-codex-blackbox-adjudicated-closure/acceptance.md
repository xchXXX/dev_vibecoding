# Codex environment black-box adjudicated boundary closure

Task ID: `20260905-135110-264935-codex-blackbox-adjudicated-closure`

## 验收目标

在用户明确人工授权后，以一个受管跟进任务关闭原黑盒任务达到三轮上限后仍开放的 F003、F004、F005、F007 四个边界，并在同一审查人通过后继续冻结候选和真实 Codex 黑盒验收。

## 验收标准

- 四个审查反例在修改前稳定 Red，且失败是目标断言而非环境错误。
- 修改后新增反例和完整 focused module 全绿，无真实 Codex、网络或安装命令。
- 同一 reviewer /root/blackbox_security_review 对当前哈希关闭四项 finding。
- 49 项以上 focused module 与 61 项 WSL 环境回归重新通过，然后冻结候选。
- 实际 CODEX_HOME、配置默认模型、ephemeral JSON read-only 模式下执行黑盒；机器预检失败则以 INFRASTRUCTURE_BLOCKED 留证，不伪装 PASS。
- 只清理精确的 /tmp/codex-env-blackbox-* 测试夹具；关键证据持续保留。

## 必备证据

- 最小复现、命中证明、相关回归和独立审查证据齐全。

## 未决项

- 按当前任务状态持续更新，未完成项不得提前宣称通过。

## 最终结论

任务尚未完成，不得宣称 final/pass。
