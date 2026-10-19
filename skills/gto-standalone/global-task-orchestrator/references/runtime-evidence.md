# 运行、能力与证据合同

## 时间倒退与执行先后

新运行 manifest 使用 `schema_version=2`。保留原始带时区 `started_at/finished_at`，即使墙钟倒退也不改写；`elapsed_ns` 为本次运行单调时钟测得的非负整数，仅用于耗时，不比较不同运行的单调读数。`completed_before` 为启动业务进程前已终结的同任务 manifest 原字节 SHA256 集合；从消费项目 `.artifacts` 下收集，跨准备/正式运行子目录及候选，排除其他任务、未完成记录和符号链接，不在结束时补扫。沿用现有证据文件，不新增服务、数据库或计数账本。

只有 A 的原始 manifest 摘要出现在 B 的 `completed_before` 中，才能用该关系认定 B 后于 A；准备采用沿用原 manifest，不因登记刷新先后。新协议无因果边、并行或来源无法核验时，不使用 UTC 猜测顺序，真实失败保守阻挡通过。双方均为旧 v1 时仅沿用合法 UTC 顺序；新旧混合须有摘要因果边。协议版本及新字段必须完整有效，不能缺字段就降级。墙钟倒退在诊断中可见，但有完整新协议证据时不否定真实功能观察。

旧倒序 manifest 没有单调耗时和前驱证明，继续保留无效原因与原始输出，不能补造字段、改原时间或回执哈希来转成功。后续新观察若核验该旧来源原字节及绑定、且自身启动前包含它的摘要，可以证明自己晚于该旧失败；这不恢复旧通过的有效性。现有冻结任务不静默迁移；旧失败现场只用于诊断，不反复重跑旧示例来覆盖历史。

本页是 GTO 的并发、能力证明、运行快照与证据留存操作说明真源。字段结构以同包 schema 为准，流程见 [任务流程](workflow.md)。普通任务是否采用这些机制，由主代理按授权和实际风险判断，不据此创建 GTO 控制面。

## 两个任务同时工作

独立任务各用一个工作区、一个 task_id 和一份可写 state；优先复用已空闲的工作区，再用 Codex 原生 worktree 工具创建隔离目录。不得把同一 state 复制到两个工作区后同时推进。初始化将实际 checkout 的规范路径哈希写入 `checkout_binding` 并绑定批准指纹；读取状态时检查，复制到别处后拒绝执行。工作区迁移须显式处理交接，不能靠手改绑定绕过原批准。控制器锁仅保护同一任务目录，不能防止副本或无关工具越权写文件。

每个工作区明确负责的文件、端口、数据库/队列和进程。共享服务允许复用只读资源；有数据写入或启动/停止冲突时使用独立实例，或排队使用一套全量验收环境。两个 worktree 本身不会隔离端口、数据库、全局安装或凭据。不得停止无法确认归属的进程。

共享 CODEX_HOME 由一个发布者按顺序更新；sync 的锁防止同时发布，但不替代任务级资源约定。开发树通过已批准的变更范围整合回 receipt 声明的发布真源后才发布，不改 receipt 冒充另一个真源。先验证各任务，再对组合候选做相关回归；不自动合并其他任务。

Windows 原生 worktree 的 Git 指针可能是 Windows 路径。WSL 必须先验证 Git 可达；必要时对该工作区 Git 命令显式指定 `--git-dir`、`--work-tree`，不要把这些环境变量泄漏给使用独立 Git 仓库的测试。工作区归档前检查活动进程、未提交工作和忽略证据；原生归档不保证保留 `.artifacts` 等忽略文件。

## 提前验证任务依赖能力

Plan 在相应子任务 `assignment.required_capabilities` 中声明确实需要的能力；无依赖则不声明。每项包含 `capability_id`、实际工具名 `tool`、最小操作 `probe`、相关配置/依赖文件 `binding_paths`、有效期 `max_age_seconds`（1–86400）。该声明进入批准指纹，不能派发时临时放宽。

实际执行者在依赖任务开始前执行一次真实最小操作，例如 Browser 打开测试页面并读取内容，或 CLI 查询实际服务并保存输出。配置文件存在和 doctor 的 configured_on_disk 不能代替这次操作。所有会消费该证明的 CLI 调用设置 `GTO_SESSION_ID` 为实际宿主/工具会话标识；新会话或工具重新连接必须换标识，不能为了继续使用旧证明沿用虚构 ID。绑定文件应包括工具版本/依赖锁定与相关配置；不包含秘密正文。

先调用 `capture-capability-context --subtask-id <id> --platform-agent-id <actual_executor_id>` 取得每项能力的 `context`、`observed_at`、`declaration_sha256`，随即执行真实探针。不得在探针结束后重新捕获上下文来绑定旧输出。原始工具输出及操作证据直接留在 `.artifacts`。探针 JSON 索引至少写实际 `tool`、`probe`、`session_id`、`status=passed|failed`、`operation`、`observed`，以及本次捕获的 `context`、`observed_at`、`declaration_sha256`，并链接实际原始输出。将索引的 `path/sha256` 与 `capability_id` 作为结果调用：

```bash
python3 "$GTO_CONTROLLER" --action record-capability-probe --repo-root "$repo_root" \
  --task-id "$task_id" --subtask-id "$subtask_id" --result-json-file "$probe_result_file" --json
python3 "$GTO_CONTROLLER" --action preflight --repo-root "$repo_root" \
  --task-id "$task_id" --subtask-id "$subtask_id" --json
```

记录动作还须绑定实际执行者 executor_id，bind-dispatch 核对它与真实派发身份一致；不能拿主协调器的可用能力替代子代理能力。记录动作核对探针捕获时的宿主、实际 Python 解释器、Python 版本、会话和依赖文件哈希，并沿用捕获时间计算有效期。按内容 hash 去重，换文件路径重复登记同一证明也会被拒绝；观察时间不晚于该能力最近记录的证明同样拒绝，不能刷新时间或覆盖后来的失败。preflight 与 bind-dispatch 只校验最新证明、时效和绑定，不重复启动工具。全任务 preflight 返回各子任务能力问题及可继续的列表；具体子任务 preflight 和派发只阻塞该任务。失败证明保留并使旧成功失效。输入格式和哈希证明不等于工具真的执行；主协调器和独立验收仍须核对原始输出，不能自写成功字段充当探针。

验收前 preparation 仍需重新确认实际部署版本、环境、输入/会话与证据捕获条件；前置事实不贡献业务验收覆盖，已实际执行且符合正式证据要求的观察可引用原始运行登记，无须重复执行。相关资源变化后重新执行受影响的探针，无关任务可继续。

## 固定验收版本

`freeze-candidate` 同时冻结声明的产品候选和正在使用的 GTO 包；指纹包含工具、schema、skill 和 references 的逐文件哈希。候选清单与字节存入 `.artifacts/gto/<task_id>/candidates/<candidate_id>/`，运行包存入同任务的 `runtimes/<sha256>/`。state 中 `current_candidate.runtime_snapshot` 指向该包，`candidate_archive` 指向带哈希的候选归档清单；消费时重新校验归档清单和内容。不得修改快照内容。每个 attempt 保存创建时的 `runtime_sha256`，verification receipt 的历史候选指纹使用该值与当时的覆盖记录共同计算，不读取后来安装的运行包代替。

冻结后的控制器明确使用 `runtime_snapshot.path/scripts/orchestrator_ctl.py`。`start_session.py` 恢复任务时验证快照并选择此入口。共享安装或源码随后更新不改变该快照；用另一版本提交结果会因候选指纹不匹配而拒绝。产品输入变动要求重新整合/审查或验收 delta，再冻结新候选；历史快照和失败不覆盖。

安装态隔离实验共用 `runtime_evidence.copy_installed_gto`，先核对 receipt、精确文件清单与哈希，再复制已读字节。正式代码不反向导入 tests。其他环境工具按原声明单独验证；模型和外部服务只能记录实际版本/设置，不能声称由文件快照冻结。

CLI 快照通过只证明脚本版本；全局 Skill 配置与安装发布后，还必须新建实际进程/会话验证加载目录、可见能力和行为，不能用磁盘配置代替。

## 直接保留原始证据

临时输入、一次性脚本放 `.tmp`；所有验收运行从第一条输出开始直接写 `.artifacts/gto/<task_id>/runs/`。`runtime_evidence.run_command` 每次分配独立 run，保留精确 argv、候选/工具绑定、实际解释器与宿主信息、时间、退出码、stdout/stderr 哈希。不把秘密放入 argv、绑定或日志。通过、失败、中断都保留；进程被外部强杀后留下 running 的记录须调查，不得改写为通过。

`verify_run` 复核绑定、文件完整性和哈希；它验证完整留存，不把 failed/interrupted 当成业务通过。验收结果必填 `expensive_acceptance.run_evidence={path,sha256}`，引用相应 manifest；控制器验证 task、candidate、runtime、attempt、subtask 和实际验收代理身份与本轮一致，并复核 stdout/stderr 和 `evidence_files` 所列全部业务证据哈希；结果引用不在清单内会被拒绝。pass/partial_pass 只接受退出码 0 的 passed 运行，失败运行可作为失败事实留存。提交及当前结论消费均重新校验，state 仍是结论和覆盖真源。追加的新运行使用新目录，业务报告也使用每轮独立的文件路径；不能覆盖旧失败来获得通过。自动更新的控制文档不能作为不可变原始验收报告，报告须单独留存。分批历史记录保留与当前候选可用性分别判断。

清理前先校验归档清单、哈希及 state 引用，且只清理本次自有临时文件。任何证据路径及父目录不得使用符号链接绕过留存边界。任务仍引用的证据不能被通用 `.tmp`/worktree 清理删除。迁移证据先建立旧引用到新路径的映射，不修改历史观察或结论。`.artifacts` 是本地留存；没有独立备份目的地和恢复验证时，不声称灾难恢复。不要为了留存向未授权外部服务上传材料。

## Schema 缓存边界

恢复脚本与工具定位入口的版本摘要、来源和 unknown 状态见 [简化合同](streamlined-execution.md#版本分发与验证)。展示复用现有 tree_manifest 和安装 receipt，不增加版本状态，不覆盖本页的冻结校验；旧快照仍由其原控制器执行。

仅缓存当前 schema 字节对应的解析结果和 validator，限进程内、有限容量；文件字节改变即重新编译。任务 state、候选、能力上下文、证据哈希和批准状态每次重新检查。性能报告分别列冷启动与同进程重复调用，不把微基准当端到端节省。


固定入口执行并留存命令输出：

```bash
python3 "$frozen_skill/scripts/runtime_evidence.py" --action run --repo-root "$repo_root" \
  --task-id "$task_id" --subtask-id "$acceptance_subtask_id" --timeout 120 --evidence-path .artifacts/business-report.json -- python3 candidate_check.py
python3 "$frozen_skill/scripts/runtime_evidence.py" --action verify --repo-root "$repo_root" \
  --task-id "$task_id" --subtask-id "$acceptance_subtask_id" --run-dir "$actual_run_dir"
```

参数取自实际任务，不提交示例值。run 前验证当前候选，结束后再查变化；期间发生变化记为 invalidated，保留输出，不能贡献通过结论。verify 返回留存完整性及实际 status，failed/interrupted/invalidated 均不是验收通过。

## 范围复验变更入口

现行行为与版本边界见[按验收点保留结果与范围复验](acceptance-points.md)。首次验收可分范围登记；保留任意历史轮次中仍有效的结果，最终检查完整覆盖，不要求额外整轮全绿。普通任务使用简洁清单，只有显式选择 GTO 才使用控制面。

## 恢复与登记精简

新增恢复摘要、精确工具入口、原始证据登记草稿及无文档差异的事实收尾，合同唯一见[恢复、登记与收尾](streamlined-execution.md)。现有安全门禁和旧冻结版本保持；新增入口仅适用于包含它们的运行包，实际安装以发布回执为准。
