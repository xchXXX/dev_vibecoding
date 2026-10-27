# Harness 性能根治（普通任务，三批实施）

## 目标、批准与归属
2026-10-27 用户批准上一轮完整方案，要求三批完整实施，文档和独立测试先行，独立 review/验收循环，有问题返工，不削弱门禁，不使用 GTO 管理本任务。
任务 20261027-harness-performance；协调者 /root；分支 codex/fix-harness-performance；独立工作区由 Codex 创建。原 D:/prj/harnesss/dev_vibecoding 的 codex/fix-gto-readiness 和未提交改动不写入、不切换、不提交。为组合验证，复制原三项已改文件和两项 readiness 测试作为继承基线；不复制在途 task/state。基线哈希与源码保存在 .artifacts/20261027-harness-performance/。
本任务不提交、推送、合并、发布到共享 CODEX_HOME，不更新旧冻结运行包；验收通过的是本工作区与隔离安装制品。

## 方案与步骤
- [x] 只读复盘与最小探针：482 声明/38 文件产生 482 次读取，摘要 964 次；pyc 改变指纹。
- [x] 建立普通 task.md/task.json，核实并隔离工作区，保存继承基线。
- [x] 全部相关合同与文档先同步；独立测试者为三批补测试并证明预期 Red（29例，26预期Red，3保护负例通过）。
- [x] 第一批：候选范围先归并和剪枝、物理文件单次读取、摘要与运行包清单单次计算；操作内验证上下文；证据 bytes 同时验哈希/解析；依赖闭包记忆化；批次校验复用；控制器和证据计数。
- [x] 第二批：只读动作不进入写锁/回滚备份，写动作计算与提交分离且重检状态/输入；历史运行精确索引与紧凑因果证明；普通任务发现与证据哈希复用；CFM 精确分区、短事务；历史审计与当前强校验分离。
- [x] 第三批：探针 deadline/进程组清理；no-op sync；doctor 清单复用；发布准备移出锁、代际核对和回滚；整体回归与隔离分发验收。
- [x] 独立 reviewer 审查，每个问题由原实现者返工、原 reviewer 复审；原测试者最终验收和实测前后性能。

## 约束与接口
共享缓存仅限一次稳定读取阶段；不可永久信任 mtime/size。路径检查先于缓存命中；内容变更、文件增删、链接换向、状态变更不得被缓存掩盖。当前采用的旧证据、后续失败屏障、角色独立、批准、预算、任务绑定保持。
候选优化保留 kind 优先级、logical/target、missing/empty directory、越界/循环拒绝；默认排除 Python 缓存及本任务控制文件，不泛用 gitignore。纯算法去重保持原记录摘要；排除缓存是新策略行为，旧 frozen 包保持。
只读计算用明确快照，写提交复核状态版本和必要的候选稳定性；锁不代表业务文件被冻结。计算可以重用，不可跨独立前后检查重用。JSON 从同一 raw bytes 哈希和解析。大文件流式摘要。
运行因果新协议必须自证 start 前完成，与墙钟无关；旧 v1/v2 不补字段。历史索引可重建，不另建任务状态真源。缺失/损坏因果证据保守拒绝覆盖失败。历史警告拆分不能隐藏当前采用证据或失败屏障。
普通任务索引不能因漏项宣称空闲；活动占用仍核验，来源不完整时保守发现。CFM 不丢归档、不截断 pending、不迁移真实共享库；升级仅在隔离 fixture 验证。

## 验证合同（fix-closure-gate / pre-dev-benchmark）
minimal_repro: 独立测试覆盖重复声明、摘要两套清单、共享日志/JSON、菱形依赖、历史扫描、长锁、工作区/CFM规模、无变更sync和挂起探针。
hit_proof: 统计实际 read/hash/scan/subprocess/lock 次数与字节；每个稳定阶段唯一输入最多一次内容读取；无关历史不增加精确查询读量；no-op发布零替换；超时可控。
diagnostic_checks: 小规模确定性夹具的精确计数、并发冲突、原始日志和基线/修复版对比；计时不作为单独正确性证明。
acceptance_checks: 公开CLI实际运行、现有篡改/身份/预算/路径/因果负例、三批定向回归、组合readiness回归、隔离安装制品、固定小中大夹具端到端指标。
non_goals: 不改业务任务、原共享安装、原任务状态、真实CFM库；不迁移项目目录；不删历史；不承诺固定28倍收益。
review_evidence: repro_before_fix, pass_after_fix, hit_proof_observed, relevant_regression_ok。

## 验收点
- scan：482/38夹具读取38文件，重复/嵌套声明不放大I/O；摘要清单同源；缓存噪音不影响候选；真实变化检出。
- evidence：共享证据单次读取、稳定JSON字节；旧有效通过保留、真实后续失败屏障/篡改拒绝；DAG闭包不重复展开。
- locks：只读摘要/能力采集不排写锁、不备份历史日志；并发状态/文件变化拒绝混合提交；失败恢复。
- history：无关任务不扫描、因果元数据不二次增长、并发/时钟倒退/旧协议保持保守。
- workspace：精确定位/同轮Git和证据复用；漏索引/损坏/重复占用仍拒绝。
- cfm：按签名定位且保留所有历史pending；跨项目并发不丢失；迁移计数/哈希一致。
- tooling：deadline杀进程组；无变更sync零复制；doctor不重哈希；发布锁不跨源侧测试且冲突/回滚正确。
- preservation：原工作区哈希和在途任务未改；旧冻结包未升级；独立review/验收完成。

## 分工、风险与恢复
/root 主协调/文档/GTO实现；独立qa只写tests与验收证据，不改正式实现；辅助实现者仅在文档和Red通过后修改分配的非GTO工具；另一独立reviewer只读审查。共同文件串行，Git由主协调执行。
风险：缓存错误放行、缩锁竞态、因果协议转换、索引漏项、安装代际混合。按对应负例验收；任何未闭环点不标完成。原始证据保留 .artifacts/20261027-harness-performance/；临时夹具放 .tmp/ 并清理。
状态：三批实现、独立四轮审查与八点独立验收全部通过；普通任务 record-stage、check、complete 均退出 0，task.json 已为 completed。每批实际结果与复验写入本记录并引用原始证据。
## 独立证据与最终结果

- 独立 QA 的三批初始 Red：29 个用例，26 个预期失败与 3 个保护负例通过；见 `.artifacts/20261027-harness-performance/qa/red-report.md`。
- 同一 WSL 工作区、同固定夹具、分进程加载基线与新实现的候选扫描：40/4 声明/文件读 40→4，482/38 读 482→38，1500/100 读 1500→100；单次耗时分别 0.905→0.449s、17.546→3.490s、38.466→11.761s。环境负载未隔离，仅证明该夹具的扫描改善，不代表原在途业务完整任务倍率。
- 首轮 review 的 CFM 批量复活容量与 init 遗留事件原像回滚两项 P2 已由最小 Red 命中、原实现者修复、原 QA Green、原 reviewer 关闭。
- 第二轮 Git 故障拒绝与 venv 总预算异常分类均经独立 Red/Green 与原 reviewer 复审关闭；超时遗留子进程也完成同样闭环。固定源 WSL 发布回归 7/7、固定包组合回归 12/12、最终串行定向 5/5 全部通过。最后差异 round-4 审查通过；原 QA 八点验收通过。一次 preparation 40 秒超时在原限制下串行复验通过，首次根因未证实，保留为环境/尾延迟风险。
- 原工作区五项继承文件重新核对全部未变，见 `.artifacts/20261027-harness-performance/preservation-check.json`。没有共享安装、提交、推送、合并或部署。
## 最终收口

- 最终独立验收：`.artifacts/20261027-harness-performance/qa/stage-acceptance.json`，8 点 pass、open_issues 为空；完整证据与实际性能见 [性能报告](performance-report.md)。
- 源码/文档/测试等最终 38 项摘要均经 QA 前后复核不变；最终隔离运行包 30 文件匹配当前源码。不同日志有重叠，不相加宣称唯一测试总数，也不声称跑过仓库全套测试。
- 最后 review：`.artifacts/20261027-harness-performance/review/round-4.md`；完成收据：`.artifacts/20261027-harness-performance/closure-complete.json`。
- 原工作区五项继承文件哈希保持，其他在途任务未写入；本次仅完成独立源码与隔离制品验收，未提交/推送/合并/共享安装。工作区及证据保留，cleanup=report-only。
