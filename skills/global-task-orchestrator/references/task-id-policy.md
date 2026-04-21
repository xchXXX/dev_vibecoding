# 任务 ID 规则

`task_id` 必须唯一，不能只使用日期。

推荐格式：
- `<topic>-<yyyyMMdd>-<HHmmss>-<rand4>`

要求：
- 只使用小写字母、数字、连字符
- 保留任务主题可读性
- 同一天内多任务仍可区分
- 可直接用作目录名

示例：
- `control-plane-upgrade-20260327-171554-a8k2`
- `batch-parse-recovery-20260327-172301-m4t9`
