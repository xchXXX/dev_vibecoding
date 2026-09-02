# 隔离子代理双轮黑盒行为测试

Task ID: `20260902-083011-641226-blackbox-rule-routing`

## 要做什么

用五个完全隔离的新子代理执行普通任务，再用第二轮追问收集实际读取文件，并由独立 reviewer 评估行为。

## 不做什么

- 首轮提示不得泄露测试目的或包含用户禁止的提示词
- 不修改生产代码、当前文档或真实 runtime
- 不让 reviewer 继承本对话

## 改哪些地方

- .tmp/20260902-083011-641226-blackbox-rule-routing
- docs/ai/tasks/20260902-083011-641226-blackbox-rule-routing
- docs/tasks/20260902-083011-641226-blackbox-rule-routing

## 怎么实现落地

分批并行启动 fork_turns=none 子代理；首轮普通任务，第二轮只追问上一轮读取文件；独立 reviewer 对照任务、输出、读取清单和产物给出结论。

## 怎么验收

- 五个首轮提示不含禁止词且不继承本对话
- 五个代理均完成第二轮读取清单回报
- 独立 reviewer 覆盖过读、GTO、修复闭环、安全读取和 matcher 痕迹五类判断
- 临时夹具清理且生产文件无新增修改

## 有什么风险

- 子代理自报读取清单不等于底层工具审计日志，最终报告必须明确证据边界
- README 改字代理会写临时夹具，必须限制到精确路径并清理
- 并发槽位有限，需要分两批派发

## 当前状态

- status: `completed`
- current_phase: `review`
- next_action: `none`
