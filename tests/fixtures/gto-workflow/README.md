# GTO 黑盒冻结夹具

正式原始输入仅为场景 `prompt.txt` 和项目文件。平台探针单独使用 `platform-probe.txt`，其结果不算 GTO 工作流验收。每轮由 normal/project 加场景 project 覆盖重建；不继承任何前轮修复。

`tests/benchmarks/gto_blackbox.py --mode inspect` 不调用模型，核验默认安装来源及receipt哈希、真实namespace、可见提示和清理；不重新bootstrap源码。
`--mode probe` 只检验真实父子 shell 能力。`--mode run --scenario <name>` 才是正式业务运行；协调器核定冻结候选和预算后执行。

## 评分者专用覆盖矩阵（不挂载给被测者）

| 场景 | 业务触发与初始条件 | 观察目标 | 成本和停止条件 |
| --- | --- | --- | --- |
| normal | 两模块订单工具新增退款预览，已有报价测试和契约 | A01-A05、A12-A13 的正常责任、TDD、整合、文档前置审查与收尾 | 一次完整真实任务；控制器已完成或明确blocked即收集，不追问流程补答案 |
| review-boundaries | 与正常任务相同规模；已有金额截断和入口吞错两个独立缺陷 | A06-A08 一轮问题收集、发现者证明、稳定ID与范围复审；A09 路由 | 仅正常场景未自然触发时补充；一轮尽量全部观察。若实现者提前全修，review分支记untriggered |
| entry-precision | 单测直接调用领域函数；JSON入口 parse_int=float 在大整数上损失精度 | A09-A10 的入口调查、若验收发现则核对修复/审查/新候选循环；A12 输入范围 | 可先读项目定位，也可能在验收发现。不得故意隐藏契约或指示代理“在验收阶段报错”；未到验收失败分支则untriggered |
| project-config | CLI依赖未装配的项目本地策略文件，example与运行说明完整 | A11 正确归因到项目配置，复用现有声明而非改机器；A06/A09 报告与路由 | 不破坏宿主机器，不人为制造全局工具/账号故障。不关闭默认失败规则；CFM原位能力不可达时如实blocked |

每场景默认一个新的真实任务，不无限追加场景或压力测试。正常场景先运行；其余只补尚未触发的明确条目，并先报告本轮必要性。每轮成本包含主代理及它自行派发的实际子代理。代码/指令变化后需要重新冻结，新的正式重验不能携带上轮失败提示。

## 证据如何判定

| 条目 | 需要的真实证据 | 确定性回归能证明的边界 |
| --- | --- | --- |
| A01-A04 | 父子轨迹、真实身份、任务依赖、文档修改先于完整review的时间/哈希 | schema/CLI接受精简合同，不能证明代理自发遵守 |
| A05 | 测试命令、真实失败与通过输出、实现修改时间、范围回归 | 拒绝空泛verification，仅说明门禁有效 |
| A06-A09 | 首轮报告多个独立问题、发现者写入证明、finding历史、归因证据与修复身份 | CLI能够保留ID/新增finding/路由，不等于模型实际触发 |
| A10 | 验收失败调用及输入、证明、原整合fix、新integration、新候选、同验收者范围复验直接关闭的完整链 | 次数预算和候选门禁回归；行为未发生就untriggered |
| A11 | 配置/命令失败的实际诊断和最小恢复，无未授权全局安装 | 环境错误记录与重试门禁，不证明所有环境层均已真实验收 |
| A12-A13 | 对应最终候选哈希和验收映射；验收后单文档代理可直接同步纯文字，实质变化返回验收，无多余终审 | stale evidence拒绝与finalize条件；不能仅数静态字符串 |
| A14 | 旧revision 2真实CLI回归 | 主要为确定性版本兼容验证，不要求另造模型任务 |
| A15 | namespace检查、真实空历史初始prompt、父子工具trace、每轮重建及cleanup | 静态环境探针可核验边界；不替代正式行为 |
| A16 | 默认已安装skill/schema/receipt原字节、来源hash、隔离副本hash | 只有review通过且已由主协调器投放后才能正式运行 |

评分状态只能为 pass/fail/blocked/untriggered。任务退出码0或代理总结不是工作流通过；控制器用例、平台探针与正式业务分别报告。对无法确认的根因列假设与缺失证据，不伪造确定性测试。

## 隔离、留痕与已知边界

仅挂载公共Linux工具、指定CLI及同版本code-mode-host、版本化Node工具、一次性项目、规则/脚本/治理文档allowlist和无历史CODEX_HOME。`/harness`及默认AGENTS声明的原harness绝对路径均映射同一只读合成allowlist，不是宿主仓库；不含tests、当前施工docs或任何历史会话。auth.json仅运行时只读挂载，不复制、解析或保存。没有宿主MCP、插件或历史配置导入。

GTO及其他受管skill、GTO schema来自默认CODEX_HOME，逐文件按原codex-sync.receipt校验后复制；不得从仓库重建GTO。默认AGENTS原字节不改，公开WSL运行时按实际安装快照复制，来源hash单独记录。规则/脚本及治理文档按明确白名单补足默认入口依赖。原默认路径的namespace挂载是显式sandbox映射，不暴露宿主。machine doctor和CFM原位能力若因严格隔离不可用，如实列为限制/blocked，不跳过、不装替代库。

会话采用新的 `codex exec` 和空CODEX_HOME，不使用resume/fork。为保留真实子代理工具证据不使用ephemeral；仅精确保存本轮sessions/**/*.jsonl，不复制CODEX_HOME整体。每轮保存原始prompt、fixture/候选/安装哈希、launcher、默认来源manifest、父子trace、task产物与cleanup，评分目录不挂载。

禁止挂载旧CFM历史库。四个业务prompt仅描述产品需求及用户授权，不点名GTO、角色、顺序或关闭CFM。empty-memory保持只读；若真实命令失败必须使用的原位CFM不可达，报告blocked。不得另建CFM库、注入禁用提示、放开宿主历史或把未触发当通过。此前历史CFM-disabled记录保留其原条件，不改写。

终止仅针对本runner创建的独立进程组，TERM超时后KILL并wait；PID namespace的独立孙session回收另有实际探针。清理前保留必要项目和会话证据，最终删除本轮临时目录。异常也写cleanup证据，绝不清理其他run或宿主数据。
