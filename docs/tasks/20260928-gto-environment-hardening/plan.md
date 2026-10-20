# GTO 本地环境与验收链路加固

用户已批准实施。当前任务按普通任务执行，被修改的 GTO 不承担本次编排。主代理实施和集成；独立 Review、独立验收各由一名无历史继承的子代理执行，发现问题后分别复用原 reviewer/acceptor。所有当前文档和测试同步；不增加旧版兼容分支。

## 范围与落地

| 需求 | 改动与验收 |
|---|---|
| REQ01 职责边界 | AGENTS 是普通协作入口；显式 GTO 才启用控制面。按官方 path 配置禁用重复流程 skill，保留方法 skill；实际新进程验证。 |
| REQ02 并发隔离 | 每项独立任务独立 worktree/状态/证据；共享安装单发布者；验收资源按需独占。不得同时推进复制的 state。 |
| REQ03 证据正确性 | 复现并修复空候选崩溃及候选删除后验证放行；历史证据保留，当前适用性重新计算。 |
| REQ04 按阶段阅读 | 精简 SKILL 路由，命令及详细合同仅维护一个正文；保留所有门禁。 |
| REQ05 固定验收版本 | 提取 receipt 校验快照模块，冻结工具、schema、skill 与候选；显式快照入口运行、接收前检查版本绑定。 |
| REQ06 长期证据 | 每次运行原始输出直接写入 .artifacts，追加 run，不覆盖失败；manifest 校验内容与引用，清理 .tmp 前确认留存。仅承诺本地留存。 |
| REQ07 能力预检与性能 | 合同声明任务依赖能力，真实最小探针提供绑定证据；preflight/bind 只消费证明，变化使证明失效。测量后仅缓存 schema/validator，动态事实仍每次校验。 |

## 顺序和退出条件

现场基线 → 最小 Red → 实现/文档/Green → 候选冻结 → 独立 Review → 修复与原 reviewer 复审 → 独立分层验收 → 受控发布及新进程验证 → 留存证据与结论。L6 整轮长程验收不在默认范围，需要另行具体授权。

## 修复验证合同

- minimal_repro：current_candidate=null 调 current_coverage；登记历史批次后删除候选文件再 validate。
- hit_proof：真实函数/CLI 命中，核对具体异常或拒绝原因；拒绝不得改变六工件。
- diagnostic_checks：schema、候选哈希、历史/当前覆盖、运行版本、能力绑定、只读 preflight。
- acceptance_checks：正向合法路径、负向污染/失效/缺证据路径；独立运行真实 CLI，必要的新 Codex 场景验证技能路由。
- non_goals：不改其他项目业务，不自动安装通用能力，不扩大生产权限，不上传证据，不重写历史任务，不以旧 GTO 驱动本次任务。
- review_evidence：继承基线、任务差异、Red/Green 原始日志、冻结候选、真实代理 ID、独立审查及验收报告。

## 工作区与发布

当前源工作区保留既有改动。隔离目录由 Codex 原生工具创建，HEAD c79d58cb0345a0cb879b2be06073a1ef04962c36；继承当前 488 个非忽略文件作为基线，归档位于 .artifacts/gto-environment-hardening/baseline。审查相对此基线。WSL 使用显式 Git 元数据路径，不能把 Windows .git 指针误当 Linux 路径。全局安装只在当前源无冲突整合、验收完成后受控更新；新进程验收前不宣称已加载新规则。

## 第二轮：方案与流程文档拆分（用户已批准）

本轮按普通任务继续。新增 plan-guide（方案编制与交接），usage-modes 拆为 workflow（任务流程与职责）；CLI 归 controller-guide，字段与证据归 state-schema。删除旧入口，不做重定向或兼容。同步控制器、现行引用、相关测试与安装包，历史任务和冻结证据保持原样。

顺序：保存本轮基线 → 新路径与工件回归 Red → 拆分并同步引用 → Green 与候选冻结 → 原 reviewer 独立审查 → 原 acceptor 功能验收 → 受控发布 → 新进程 Plan 与在途恢复两项黑盒 → 事实收口。独立黑盒提示不给目标文档名、预期读取路线或评分答案；只证明本次路由和理解，不代表全 GTO 或 L6 通过。

证据位于 `.artifacts/gto-environment-hardening/document-split/`；发布前逐文件核对原源与本轮基线，无关改动保留。共享安装仅主代理发布；新文件随包分发，旧文件从包中移除。
