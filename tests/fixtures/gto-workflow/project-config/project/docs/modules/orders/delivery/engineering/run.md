# 运行

Python 3 标准库即可运行，无第三方依赖。

本地策略保存在 `config/local/order-policy.json`，结构及默认值由 `config/order-policy.example.json` 定义，不提交本地配置。
从仓库根运行 `python3 -m modules.order_cli.main`，输入订单 JSON。
测试入口为 `python3 -m unittest discover -s tests -v`。
