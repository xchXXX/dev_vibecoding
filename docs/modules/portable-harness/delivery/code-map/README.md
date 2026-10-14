# 代码入口

- modules/harness/config.py：配置来源及执行环境。
- modules/harness/paths.py：路径和文件边界验证。
- modules/harness/bundle.py：固定提交白名单构建与 manifest 校验。
- modules/harness/lifecycle.py：所有权预检、模块生命周期、事务恢复、doctor。
- modules/harness/errors.py：稳定错误合同。
- scripts/harness.py：分发与生命周期命令入口。
- tests/portable/：独立公共行为测试。

字段与安全约束唯一见 ../../contract/README.md；实施状态见 ../../../../tasks/20261014-portable-harness/execution.md。
