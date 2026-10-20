# WSL 环境统一治理

Task ID: `20260905-030055-424575-wsl-environment-unification`

## 施工目标

Deliver the repository-side WSL environment unification system approved by the user so recurring cross-platform failures are prevented or stopped at task start.

## 前置条件

- 用户已确认六要点任务合同。
- 写入前已冻结范围、验收和风险。

## 执行顺序

按“机器公共工具 → 项目隔离依赖 → 按需能力 → Windows 外部能力”四层施工；公共工具只声明和诊断，项目依赖只读核验，不把 Python/Node 项目包全局安装。

## 文档先行清单

- 新增 WSL 分层环境合同、doctor 启动边界、Windows 附件路径桥接、代码地图和工程交付说明。
- 同步 `docs/CODEX_COMPAT.md`、`docs/INSTALL.md`、`scripts/README.md`、全局规则与 Codex 模板。

## 测试同步清单

- 先建立 Windows TEMP/PATH、Windows Python/Node 工件、Docker/Playwright、managed runtime hash、Windows 路径转换等最小 Red。
- 最终复审追加并命中依赖未恢复、伪 venv、Corepack 路线冲突、Node 空壳/错版本包、Windows npm symlink 等反例；每项均由原实现者 Green、同一 reviewer re-review。

## 实施批次

- config/ai
- schemas/wsl-tool-baseline.schema.json
- schemas/project-environment.schema.json
- scripts/provision-wsl.py
- scripts/doctor-core.py
- scripts/project-env-doctor.py
- scripts/resolve-wsl-path.py
- scripts/bootstrap-local.py
- templates/project
- templates/codex/AGENTS.global.md
- rules/items
- rules/registry/RULES_INDEX.json
- docs/modules/wsl-environment
- docs/CODEX_COMPAT.md
- docs/INSTALL.md
- scripts/README.md
- tests/harness
- tests/fixtures/wsl-environment

## 每批写入范围

- config/ai
- schemas/wsl-tool-baseline.schema.json
- schemas/project-environment.schema.json
- scripts/provision-wsl.py
- scripts/doctor-core.py
- scripts/project-env-doctor.py
- scripts/resolve-wsl-path.py
- scripts/bootstrap-local.py
- templates/project
- templates/codex/AGENTS.global.md
- rules/items
- rules/registry/RULES_INDEX.json
- docs/modules/wsl-environment
- docs/CODEX_COMPAT.md
- docs/INSTALL.md
- scripts/README.md
- tests/harness
- tests/fixtures/wsl-environment

## 验证命令

- `TEMP=/tmp TMP=/tmp TMPDIR=/tmp python3 -m unittest tests.harness.test_wsl_environment tests.harness.test_wsl_tools tests.harness.test_wsl_runtime`：`Ran 61 tests in 126.010s`，通过。
- `TEMP=/tmp TMP=/tmp TMPDIR=/tmp python3 -m unittest discover -s tests/harness -p 'test_*.py' -v`：`Ran 161 tests in 303.713s`，通过。
- `python3 scripts/validate_rules.py --repo-root <repo-root> --json`：25 条规则，无 error/warning。
- `python3 scripts/validate_doc_routing.py --repo-root <repo-root> --json` 与 `python3 scripts/validate_plan_docs.py --repo-root <repo-root> --json`：通过。
- `git diff --check`（本任务范围）：通过。

## 回退方案

- Stop before any system-level mutation not already represented as repository code or documentation.
- Stop if a scoped write path overlaps unrelated dirty content and cannot be isolated without user direction.
- Stop if implementation would require guessing an undocumented Codex Local Environment file format.
- Stop if the same blocking condition recurs three goal turns without a safe in-scope alternative.

## 审查与返工路径

独立 reviewer 共记录 7 个稳定 finding；全部由原实现者修复并由同一 reviewer 定向复审关闭。最终三轮集中证明项目依赖不是“目录存在即健康”，并阻断 Linux 表面路径背后的 Windows npm。

## 实际交付

- `config/ai/wsl-tool-baseline.json` 是 machine baseline 单一机器真源；`provision-wsl.py` 默认只给计划，显式 apply 也只处理 apt 缺口，`pnpm` 通过外部 handoff 交给用户授权安装。
- `doctor-core.py` 在任务启动边界检查 Linux 原生工具路径、managed runtime/receipt/hash、TEMP 与配置漂移。
- `project-env-doctor.py` 支持 Python-only、Node-only 或双栈声明；验证真实 venv、离线 requirements、Node 包元数据和离线 npm 树，并检查 Playwright/Docker 与 Windows 工件。
- `bootstrap-local.py` 原子同步受管运行时文件并写 hash receipt；不覆盖未托管 Codex 文件。
- `resolve-wsl-path.py` 仅转换用户明确给出的 Windows 路径值，拒绝 UNC、device path 与 traversal。
- 未执行 apt/pnpm 安装，未修改 `/etc/wsl.conf`、Docker Desktop、Codex GUI/Local Environment 或 live `config.toml`。

## 2026-09-09 纠偏施工记录

重启后的真实 Desktop 验收推翻了“受管 stdio 桥可以通过重启稳定生效”的假设。旧实现的桥本身能够转发协议，但 Desktop 在 agent turn 之前已经根据官方插件重新生成并启动 `node_repl.exe`；任务开始后的 bootstrap 无法热替换该进程。

本轮按以下顺序继续，过程证据保留在本文件，不清理既有备份和 CFM 数据：

1. `docs-first`：把长期合同改为官方能力分流，不再声明接管内置插件。
2. `tests-first`：以隔离 `CODEX_HOME` 冻结官方 `node_repl` 不得被改写、doctor 不得报桥漂移、规则不得要求重启循环。
3. `TDD`：每个行为先观察 Red，再写最小实现得到 Green。
4. `first-review`：完整扫描全部范围并一次列全 findings。
5. `fix/re-review`：每个 finding 重新进入 Red/Green，随后做受影响范围验收。
6. `black-box`：用全新 Codex、自然任务提示且不提供桥接线索，验证自动路由和无旧错误；未通过则继续迭代。

当前状态：文档与 verification contract 同步中，尚未宣称实现或验收完成。

## 2026-09-09 首次完整 review findings

首次 review 已按合同、数据流、异常、兼容、安全、测试和文档七个面完成整轮扫描；以下问题在开始修复前一次性登记：

1. `REV-WEC-001`：`scripts/windows-external-bridge.py` 及其 managed runtime 映射仍存在，旧私有 transport 仍会被发布到新环境。
2. `REV-WEC-002`：若只从 managed 清单移除旧桥，已安装的 `bin/windows-external-bridge.py` 会被 doctor 判成 unexpected；bootstrap 缺少只针对这一历史受管文件的收口迁移。
3. `REV-WEC-003`：`templates/codex/AGENTS.global.md` 与 `global.policy.WSL工具分层与缺失依赖处理` 仍要求改写 MCP 表并重启，会让全新会话继续旧循环。
4. `REV-WEC-004`：测试尚未兑现 verification contract 中“全局入口自动选择 Browser/Windows-native 且不包含旧修复指令”的行为证明。
5. `REV-WEC-005`：外部能力声明可为空，能在 doctor 仍为 green 时静默丢失全部自动路由；schema 与运行时校验都应 fail closed。
6. `REV-WEC-006`：required HTTP MCP 即使配置 `enabled = false` 仍会被报告为 `configured`，不能代表任务可用。
7. `REV-WEC-007`：`fallback_capability` 没有限定适用语义，可能让 Windows GUI 操作被错误降级成 Browser；字段应明确为仅在存在等价网页路径时可用。
8. `REV-WEC-008`：`runtime_common.py` 仍保留三段只服务旧 TOML 改写的死代码，扩大维护面并可能诱导后续重新接管插件 transport。
9. `REV-WEC-009`：当前真实 `CODEX_HOME/config.toml` 仍可能保留上一版 bridge；仓库 bootstrap 按新合同不会改它，最终黑盒前必须做一次有备份、精确命中的本机恢复，并在重启后复验 Desktop 所有权。

处置规则：`REV-WEC-001` 至 `008` 各自先补或扩展最小失败用例，再实施并做范围复审；`REV-WEC-009` 只在仓库候选全绿后执行机器侧一次性迁移，不写成持续改写逻辑。

范围回归追加 finding：

10. `REV-WEC-010`：`scripts/README.md` 把受支持的 `notify` 与退役 hook 写在同一肯定式子句中，触发 active-truth 防回归闸门；应拆开语义，在不重新激活退役合同的前提下说明 bootstrap 保留 `notify`。

## 2026-09-09 review 修复与范围复验

- `REV-WEC-001/002/008`：先用 `test_retired_bridge_is_not_published_and_existing_runtime_copy_is_removed` 观察 Red；随后删除旧桥源码与发布映射，增加仅针对历史受管目标的精确清理，并移除旧 TOML 改写死代码。
- `REV-WEC-003/004`：先用 `test_global_agents_routes_capabilities_without_bridge_repair_loop` 观察 Red；随后同步全局模板与分层规则，明确 Browser、Windows-native Computer Use、HTTP MCP 三路分流并删除旧循环指令。
- `REV-WEC-005`：先用 `test_declaration_rejects_empty_routes` 观察 Red；随后 schema 和运行时校验同时拒绝空路由表。
- `REV-WEC-006`：先用 `test_required_http_mcp_route_rejects_disabled_server` 观察 Red；随后 doctor 将 required 且 `enabled=false` 的服务器分类为 `windows_external_http_mcp_disabled`。
- `REV-WEC-007`：`fallback_capability` 更名为 `web_equivalent_capability`，并在全局入口中限制为只有存在等价网页入口时才可使用 Browser。
- `REV-WEC-010`：范围回归首次运行命中 active-truth 闸门；CFM signature 为 `7220e476a929462e93d1256950ba20f251c241b9ba2bfaa61f6d8171742c4310`。拆分 `notify` 语义后，直接命中用例与两个依赖 strict doctor 的用例均通过，CFM 已成功回写。
- CFM 调用中误把 `scope-confidence` 写为 `high` 的操作错误也独立闭环，signature 为 `fa2ec810e465e6db75fd660b76de251fbba7777ffb4829e41eb8dc45595b2a50`；更正为浮点 `1.0` 后完成记录、查询和成功回写。
- 修复后范围回归：`TEMP=/tmp TMP=/tmp TMPDIR=/tmp python3 -m unittest -v tests.harness.test_windows_external_capabilities tests.harness.test_wsl_environment tests.harness.test_wsl_runtime`，`Ran 64 tests in 164.331s`，通过。

当前剩余：`REV-WEC-009` 的本机一次性迁移、完整 harness 和全新 Codex 黑盒验收；尚未宣称最终完成。

## 2026-09-09 首轮真实黑盒与第二轮迭代

- 网页黑盒：全新无历史 Agent 只收到“打开 `https://example.com` 并报告标题/首句”，一次返回正确标题与正文，未修改文件。
- 任务启动黑盒：全新无历史 Agent 只收到运行外部能力测试模块的请求；它自行先运行 project doctor，结果 green，随后 9/9 测试通过。
- Windows GUI 黑盒：全新无历史 Agent 只收到打开记事本、读取标题并关闭的请求；它自行运行 machine doctor（green）并选择 Computer Use，但 `node_repl` 在执行任何 JS 前连续失败，错误为 `sandboxCwd is not a local file URI: file:///mnt/d/prj/harnesss/dev_vibecoding`。黑盒判定失败，未宣称完成。
- 该真实失败已进入 CFM，signature 为 `97944f042498af7308e68017b5f7a0ee955fd144a284d2569f663e45f051c0d7`，并已完成 retry 前查询。
- 官方文档复核结果：Agent environment 是应用级 Windows native / WSL 二选一设置并需重启生效；Computer Use 没有公开的同任务自动跨环境迁移接口。

追加 finding：

11. `REV-WEC-011`：doctor 的 `requires_windows_native/use_windows_native_computer_use` 以及全局文字仍可能被理解为“当前 WSL 进程直接调用 Computer Use”，导致黑盒再次撞到已知 transport 错误。必须改成机器可读的 `unavailable_in_wsl/start_windows_native_agent`，并明确 WSL 中不得调用；交接说明应指向官方 Agent environment 设置，而不是修桥或重试。

第二轮黑盒仍失败：Agent 已读取 `available_in_current_process=false`，但插件 skill 的强制初始化合同仍令其调用 `node_repl`，同一 CFM signature 的 `failure_count` 增至 2。由此追加：

12. `REV-WEC-012`：只靠 AGENTS/doctor 提示无法阻止更高优先级插件 skill 初始化。WSL bootstrap 必须使用 Desktop 已有的官方插件 `enabled` 开关，窄化禁用声明列出的不兼容插件；doctor 必须检测其被重新启用。实现只能修改 exact plugin table 的 `enabled`，并保留备份、其他配置和 host-owned `node_repl` transport。

## 2026-09-09 第三轮实现、复审与待重启黑盒

- docs/tests first：声明为 `windows_native_only` 的 Computer Use 路由新增精确 `wsl_disabled_plugins`；schema、全局入口、分层规则、模块合同、安装与脚本文档同步说明插件开关及 Windows-native 交接。
- TDD 首轮：声明、bootstrap 定点禁用与 doctor fail-closed 三项先观察预期 Red，写入最小实现后 3/3 Green。
- 范围复审追加幂等、UTF-8 BOM/CRLF 保真、近似插件名不误伤、损坏 TOML fail-closed 三类测试，3/3 Green；没有扩大到创建插件或修改 `command/args/env`。
- 文档测试第一次范围运行出现旧措辞断言失败，CFM signature `22bc326a53fabc00b60aa35be9bc7e34a2790b98a298c9dd9e0fc8f22ca071c1`；更新为等价但更精确的合同断言后，外部能力模块 14/14 Green 并完成成功回写。
- 规则、文档路由、任务文档三道机械闸门均通过；WSL 受影响范围 `Ran 69 tests in 162.773s`，通过。
- 最新完整 harness：`TEMP=/tmp TMP=/tmp TMPDIR=/tmp python3 -m unittest discover -s tests/harness -p 'test_*.py' -v`，`Ran 224 tests in 605.052s`，通过。
- 真实配置施工前 SHA-256 为 `2a98163f0395bea917e11cb302aaff897a4065c4327ec53995fe2476974227ca`，两个官方 Computer Use 插件均为 `enabled=true`，`node_repl` 仍为官方 `node_repl.exe`、空 args 且保留 env。
- 首次真实 bootstrap 成功：只把 `computer-use@openai-bundled` 与 `unified-computer-use@openai-bundled` 设为 `false`；原配置备份路径为 `<CODEX_HOME>/.ai-harness/backups/config.2a98163f0395bea917e11cb302aaff897a4065c4327ec53995fe2476974227ca.toml`，备份哈希与施工前一致。施工后配置 SHA-256 为 `098dce1f980dee1563aa04ecac02b71269a3c66a66f0749820b919c20769b3a5`，host-owned `node_repl` 结构保持不变。
- 第二次真实 bootstrap 成功且幂等：`changed=false`、`restart_required=false`、`restart_reasons=[]`，没有新增备份或再次改写。
- 第三轮无提示黑盒仍由施工前已启动的 Codex 宿主执行；该旧进程继续持有启动时注入的 Computer Use skill，因此再次复现 `sandboxCwd is not a local file URI`。新 CFM signature 为 `508fc08c890d61c41aa8d894bfdc9dd430cf53c490da1f1d330a5ff8f777b054`，已完成 retry 前查询。此结果不否定磁盘策略，但证明插件开关不热加载；必须重启 Desktop 后由全新进程重验，当前不得判定最终通过。

## 2026-09-09 重启后最终黑盒

- 重启后的根任务能力清单不再包含 Computer Use；machine doctor 返回 `ok=true`，Computer Use 路由为 `unavailable_in_wsl/start_windows_native_agent`，`enabled_incompatible_plugins=[]`，无 findings/errors。
- 最终黑盒 `/root/blackbox_windows_gui_round4` 使用隔离上下文，只收到自然请求“打开 Windows 记事本、确认标题、关闭且不触碰用户文件”，没有收到 doctor、WSL、插件、修复方案或预期结论提示。
- 黑盒没有初始化 Computer Use，没有暴露 `node_repl`、`sandboxCwd` 或 bridge/restart-loop 错误；直接说明当前为 WSL Agent environment，并给出 `Settings > Agent environment > Windows native`、重启、新开任务的受支持交接。未打开、创建或修改用户文件。
- CFM signature `508fc08c890d61c41aa8d894bfdc9dd430cf53c490da1f1d330a5ff8f777b054` 已以该重启后黑盒证据完成成功回写。
- 更新最终验收记录后重新执行完整 harness：`Ran 224 tests in 709.051s`，`OK`、退出码 0；规则、文档路由、任务文档和 scoped `git diff --check` 同轮通过。

## 2026-09-09 WSL 直连方案研究与施工重开

- 用户指出“每次切换 Agent environment、重启并重新启用插件”不能接受；原 `pass` 已撤销。
- 官方运行时协议探针直接启动当前 Desktop 生成的 `node_repl.exe`，`initialize` 与 `tools/list` 成功，工具为 `js/js_add_node_module_dir/js_reset/turn_ended`。
- 同一无害 `js` 调用使用 `file:///mnt/d/prj/harnesss/dev_vibecoding` 时精确复现 `sandboxCwd is not a local file URI`；使用 `file:///D:/prj/harnesss/dev_vibecoding` 并保留完整沙箱元数据后通过。
- 通过当前官方 runtime/env 执行 `@oai/sky` 的 `sky.list_apps()` 成功，返回 40 个应用；完全不发送 sandbox meta 时也成功。由此确认能力和 native pipe 正常，错误只在跨主机 URI 边界。
- `node_repl.exe --help` 显示 `--disable-sandbox`，但官方仓库同类问题及既有重启证据表明 Desktop 会恢复受管 `args=[]`；该路线不作为持久方案。
- 一次无关诊断误调用缺失的 `powershell.exe` 返回 127，已按 CFM 记录并查询，signature `d11f73980570796e45114d3549792f6f50e76c038ecdef85e580b9087fe530b9`；不再沿换平台诊断分支重试。
- 用户已批准独立 `computer_use_wsl` MCP + 最小全局 skill 方案。施工从 docs/tests first 开始，不调用 GTO。

## 2026-09-09 WSL 直连方案首次完整 review findings

本轮在修复前一次性扫描协议、权限、安全、进程生命周期、配置漂移、doctor 真实性、自动发现、文档和测试，登记如下：

13. `REV-WEC-013`：`schemas/README.md`、`scripts/README.md` 与 `docs/modules/wsl-environment` 多处仍把 Computer Use 写成 `windows_native_only` 或要求切换 Agent environment，会让维护者和新任务遵循已经撤销的合同。
14. `REV-WEC-014`：doctor 仅检查磁盘 TOML，却输出 `available_in_current_process=true`；bootstrap 后尚未重启的旧进程并未加载新 MCP，这一字段会制造错误的现场结论。
15. `REV-WEC-015`：兼容代理只在正常控制流中 `terminate` 子进程，收到 SIGTERM 或等待超时时可能遗留 `node_repl.exe`；清理逻辑也没有 kill 兜底。
16. `REV-WEC-016`：代理只读取官方 stdio 条目的 `command/args/env`，未处理 Codex 官方配置支持的 `cwd`、`env_vars` 与 `enabled=false`，Desktop 后续生成这些标准字段时可能静默改变启动语义。
17. `REV-WEC-017`：doctor 对官方真源只检查可执行文件名，不检查文件存在、参数和环境结构；对兼容表只检查三个字段而接受未知字段或遗留子表，可能把实际不可启动或被污染的路由判为可用。
18. `REV-WEC-018`：不可映射路径虽会 fail closed，但当前 stderr 只有异常类型；skill 承诺报告精确阻塞，现有实现无法区分“Linux-only 工作目录”“畸形协议消息”和“子进程故障”。非对象 JSON 还会以未捕获 `AttributeError` 退出。
19. `REV-WEC-019`：skill 把“关闭测试应用”笼统视为非破坏操作，没有要求只关闭本任务新建且无未保存内容的窗口；黑盒可能误关用户原有记事本。
20. `REV-WEC-020`：bootstrap 先写插件/兼容 MCP 配置、后同步 skill 与代理 runtime；中途失败或被打断时会留下半安装状态，而且失败响应没有完整披露已经发生的写入、备份和重启要求。
21. `REV-WEC-021`：当前证据只覆盖假子进程协议测试，尚未通过兼容入口连接本机真实官方 runtime 执行 `sky.list_apps()`，不能证明修复点真实命中。
22. `REV-WEC-022`（Critical）：声明没有禁止 `mcp_server == source_mcp_server`；误配后 reconcile 会直接把官方 `node_repl` 表替换成代理表，违反核心所有权边界。
23. `REV-WEC-023`：声明暴露可变 `source_mcp_server`，但代理硬编码读取 `node_repl`，doctor 与真实启动目标可能分裂。当前能力的两个名字应冻结为 `computer_use_wsl` / `node_repl`，并在写入前再次防御性校验。
24. `REV-WEC-024`：skill 示例的 `nodeRepl.emitImage(...)` 缺少 `await`；兼容表幂等测试夹具又缺少官方源 MCP，实际没有覆盖 reconcile 幂等路径。

独立审查与主审查结论合并后，共确认 1 个 Critical、9 个 Important 和 3 个 Minor，未在首个 finding 停止。处置规则：`REV-WEC-013` 至 `020`、`022` 至 `024` 先补最小 Red 后统一修复并做范围复审；`REV-WEC-021` 在候选静态与范围测试全绿后执行真实只读协议 smoke。最终 GUI 黑盒仍必须在安装后重启的新进程中完成，不以 doctor 或 smoke 代替。

## 2026-09-09 WSL 直连方案复审迭代与安装候选

- 第二轮独立复审登记并修复：官方源缺失/损坏时残留兼容表、doctor 把磁盘配置冒充当前进程可用、skill 缺少官方精确窗口 API、可选能力完全缺失与配置漂移混淆。5 个最小反例先 Red，修复后 5/5 Green。
- 完整范围首次回归暴露 2 个旧夹具用不存在路径冒充健康 `node_repl.exe`；按 CFM signature `4d29c5979636d3c9af985c618ac584d35fbe3ee81e654c8c2c07fd383dca3b0f` 完成失败记录、查询和成功回写。修复方式是健康夹具创建实际临时 PE 结构文件，缺失源用例继续使用不存在路径；同一 78 项命令随后通过。
- 第三轮独立复审发现并修复：skill 使用不存在的 `app.name/windowState.text`、冲突插件动作优先级、缺失 `env_vars` 与伪可执行文件假绿、非法 JSON 缺少标准 JSON-RPC 错误、声明允许多 bridge。6 个最小反例先 Red，修复后 6/6 Green。
- 第四轮独立复审发现并修复：0 bridge 声明与 reconcile 冲突、PE 检查只有 `MZ+长度`、冲突插件与损坏源组合仍给错动作、窗口刷新只比较 `id`。4 个最小反例先 Red，修复后 4/4 Green。
- 最终范围复审未发现新的 Critical / Important / Minor，允许进入机器安装。当前桥接/外部能力 43/43、WSL 环境 42/42、skill 校验、规则校验、文档路由和任务文档校验均通过。
- 真实只读协议 smoke 由当前候选代理动态读取本机官方 `node_repl`，对 `file:///mnt/d/prj/harnesss/dev_vibecoding` 完成唯一字段转换后执行 `sky.list_apps()`，结果 `ok=true`、应用数量 40、响应 id 为 1/2、stderr 为空；未输出应用名、窗口名或环境值。
- 保留的最终硬闸门：真实 bootstrap 后只需一次新进程加载；全新无提示黑盒必须实际打开、读取并关闭唯一的任务新建记事本窗口，同时证明该次新增 Windows `node_repl.exe` PID 在 MCP 退出后消失、既有 PID 未被误杀。在此之前 acceptance 继续为 `pending`。

### 机器安装与旧宿主黑盒

- 为避免发布并行脏 GTO，新增并通过 scoped publish 合同：`sync-codex.py` 和 `bootstrap-local.py` 支持 `--skill windows-computer-use-wsl`；scoped doctor 只把选中 skill 与当前源比较，未选 skill/schema 与既有 receipt 及安装文件比较。该链经历 2 个预期 Red、对应 Green、49 项范围回归和独立复审；默认全量 doctor 仍保留原行为。
- 首次本机窄 bootstrap 成功，完成 `global_agents / sync / wsl_environment_runtime / plugin_policy / compat_mcp / receipt / doctor`；只同步 `windows-computer-use-wsl`，没有同步 GTO。配置施工前哈希为 `9dcb736492a7d06eeefc54258098e2d24dba18dcb84080408404339c5444b24b`，对应内容寻址备份存在且哈希相同。
- 安装后结构核对：官方 `mcp_servers.node_repl` 与备份逐字段相同；`computer_use_wsl` 指向已安装 Python 代理且 timeout 为 120；两个官方冲突插件继续为 `enabled=false`；已安装 GTO 与当前脏源不同但与既有 receipt 完全一致，证明窄安装未发布 GTO。
- 第二次相同 bootstrap 为 `restart_required=false`、`restart_reasons=[]`、所有 reconcile `changed=false`，证明安装后幂等。已安装代理再次经真实官方 runtime 执行 `sky.list_apps()`，返回 40 个应用、响应 id 1/2、stderr 为空。
- 安装后立即创建的无提示子代理仍继承当前 Desktop 宿主启动时的旧 AGENTS 与旧工具清单，看不到 `computer_use_wsl`，因此没有打开记事本并按旧合同返回 Windows-native 交接。该轮判失败，证明“同一宿主内新子代理”不等于“重新加载磁盘配置的新 Codex 进程”；必须完成本次安装唯一一次宿主重启后再验，不能把它写成日常每次调用都需重启。
- 进程核对首版按完整 cmdline 搜索时自匹配扫描命令，CFM signature `adb40d680b00da6c89423e8d5c27166d971029c509703d1533183012757b4e77` 已闭环；改为只比较 NUL 分隔的 `argv[0]` basename 后，失败黑盒结束时没有真实 `node_repl.exe` 遗留。

## 2026-09-10 重启后黑盒与窗口身份兼容修复

- 重启后 machine doctor 返回 `ok=true`；Computer Use 为 `configured_for_wsl/use_computer_use_wsl`，受管 skill/runtime/receipt、插件策略和 WSL 工具基线均无 issue。
- 完全无桥接提示的黑盒 `/root/blackbox_notepad_after_restart` 只收到“打开 Windows 记事本、确认标题、关闭且不触碰用户文件”。它通过真实 `list_apps` 启动记事本，识别唯一新增窗口 `85920060`，读到标题 `无标题 - 记事本` 和空白编辑区，只向该窗口发送 `Alt+F4`；结束后原有 4 个窗口保持不变，新增窗口为 0。
- 黑盒前后的精确 PID 扫描只读取 `/proc/<pid>/cmdline` 的 NUL 分隔 `argv[0]`，并按 basename 严格匹配 `node_repl.exe`；前后均为空，没有遗留 Windows runtime 子进程。
- 黑盒同时暴露真实兼容差异：`list_apps.id` 为 shell 应用 ID，而 `list_windows.app` 为 `process:C:\\Windows\\System32\\notepad.exe`。旧 skill 示例将二者直接比较，现场结果会得到 0 个窗口；黑盒代理靠全窗口前后差集自行安全纠正，因此行为通过但候选未提前判定最终完成。
- 按 skill 文档 TDD 先扩展 `test_skill_limits_cleanup_to_task_owned_safe_window`，观察到旧 `window.app === targetApp.id` 的预期 Red；随后只改为复合窗口身份集合差，并要求唯一新增窗口继续通过标题或可访问性确认，目标用例和 skill validator 转绿。
- 修复后范围回归：外部能力 30/30、同步范围 5/5、兼容代理 14/14、WSL 环境 42/42 全部通过。`sync-codex.py --skill windows-computer-use-wsl` 只同步该 skill；源与安装副本 SHA-256 均为 `c074e1bea505accde110a50f350314253540f10f33db494a7cdd410350d1d2bf`。同步后的 machine doctor 与已安装 skill validator 均通过。
- 当前仍保留最后两道闸门：针对这次最小修复的独立只读 review，以及同步后第二次无提示记事本黑盒。两者完成前不把本轮迭代写成最终通过。
- 独立 review 判定 `Not Ready` 并登记 `REV-WEC-025`（Important）：`get_window_state` 后直接覆盖 `targetWindow` 会丢失最初由差集证明的复合身份，后续 rehydrate 可能只证明错误对象与自身一致。
- `REV-WEC-025` 先扩展目标测试并观察缺失不可变所有权锚的预期 Red；修复后把最初 `{app,id}` 冻结为 `targetWindowIdentity`，状态读取返回值必须先与该身份一致，每次 mutation 前的 `get_window` 和返回值校验也只引用该冻结身份。两个过时的可变 `targetWindow` 测试断言在 Green 阶段暴露，均按 CFM 记录、查询、修正和成功回写。
- 修复后目标用例与外部能力 30/30 再次通过，skill validator 和 scoped diff-check 通过；本机再次只同步 `windows-computer-use-wsl`。源与安装副本的新 SHA-256 均为 `290df0bc4a3e45e30cda34ee772055e5db4b598afe2b7b532780c352f5f4983e`，machine doctor 仍为 `ok=true` 且无 findings/errors。
- 同一 reviewer 范围复审确认 `REV-WEC-025` 关闭，未发现新的 Critical / Important / Minor，允许进入黑盒。
- 第二次无提示黑盒实际打开并关闭了唯一任务记事本，冻结身份为 `process:C:\\Windows\\System32\\notepad.exe` / `13109836`，标题为 `无标题 - 记事本`；没有 `sandboxCwd`、插件、权限或归属错误，前后精确 `argv[0]` PID 扫描仍均为空。
- 该轮第一次紧邻 `Alt+F4` 的只读枚举仍看到窗口，下一次独立只读枚举才确认消失；没有重复 mutation。黑盒按 CFM 记录为 `CASE-5aa3f5883afef8a8`。这证明 Windows 窗口关闭存在异步完成窗口，若立即把首个快照判为失败会产生可避免的假报错。
- 以该现场行为作为 skill TDD Red，新增“最多 3 次独立只读条件检查、首个仍存在视为 pending、不得重复 mutation、3 次后才失败”的最小指引；目标用例与外部能力 30/30 通过，validator 通过并再次窄同步。源与安装副本 SHA-256 均为 `8fa7910510c38e9c1f02ff281241bb8d5a94b6e4f3746f779c9b3aa697e00f28`，doctor 继续全绿。
- 异步指引复审发现 1 个 Minor 测试缺口：未锁定“冻结身份 + 新鲜状态”及“最终失败包含最后观测”。仅补目标测试断言后 1/1 和 diff-check 通过，同一 reviewer 确认 Minor 关闭且无新增 finding，最终 verdict 为 `Ready`。
- 第三次最终无提示黑盒 `/root/blackbox_notepad_final_clean` 仍只收到自然记事本请求。它自动加载已安装 skill，唯一启动本任务窗口 `process:C:\\Windows\\System32\\notepad.exe` / `28249748`，确认标题 `无标题 - 记事本`、空白编辑区“第 1 行，第 1 列”，只发送一次 `Alt+F4`；首次独立只读条件检查即确认消失。没有保存/模态对话框，没有触碰用户原窗口或文件。
- 最终黑盒前后精确 `argv[0]` 扫描均无 `node_repl.exe`，没有遗留 runtime 进程；本轮未出现 `sandboxCwd`、插件、权限、身份归属或异步假失败。
- 最终记录落盘后复跑：外部能力 30/30、源与安装 skill validator、26 条规则校验、59 份文档路由、18 个任务文档、scoped `git diff --check` 全部通过；源与安装副本 hash 仍一致。

## 2026-09-10 Browser 插件边界回归

- 用户在当前任务打开内置 Browser 后要求实际操作；工具清单只有 `computer_use_wsl`，没有 Browser/CUA 入口。官方本地插件清单确认 `unified-computer-use` 的职责是 `App-managed browser automation runtime`，其 Browser 资源明确支持 `@Browser` 与 in-app browser `iab`。
- 根因是旧声明把 `computer-use@openai-bundled` 和 `unified-computer-use@openai-bundled` 同时列入 `wsl_disabled_plugins`。前者会让 WSL 误选原生 `node_repl`，后者却是 Browser 自动化入口；一刀切策略错误地跨越了两个产品边界。
- TDD Red 精确命中：声明缺少 Browser 插件要求、bootstrap 不会恢复该插件、doctor 对已禁用 Browser 插件仍报 `preferred_in_wsl`。实现新增声明式 `wsl_enabled_plugins`，只将 `unified-computer-use` 设为 `true`，并把原生 `computer-use` 保持为 `false`。
- 首次范围回归 31 项中 1 项失败：旧 doctor 夹具未包含真实 Desktop 的 Browser 插件表。CFM `CASE-946082e5a21e80a1` 已闭环；夹具补齐后 31/31 通过。另有一次 CFM 参数误用和一次未筛选旧文档镜像路径，分别以 `CASE-fa2ec810e465e6db`、`CASE-1d2e6c6cee17940b` 闭环。
- 扩大范围验证完成：外部能力、兼容代理、WSL 环境/runtime 与同步范围共 106/106 通过；26 条规则、1 个模块及 18 个任务文档校验通过。独立 reviewer 另行复跑当前外部能力套件 32/32、规则/文档 validator 与 scoped diff-check，确认主分流正确。
- 真实 bootstrap 前 `config.toml` SHA-256 为 `6840f9afe3f3bd3364a120e7dfb482bd977be25088998d0088e551191129a204`，内容寻址备份哈希与其一致；安装只把第 52 行 `unified-computer-use` 的 `enabled = false` 改为 `true`。解析后的 `node_repl` 和 `cua_repl` 表逐字段未变，`computer-use` 继续为 `false`，`computer_use_wsl` 未改写。
- 第二次相同 scoped bootstrap 为 `updated=false`、`restart_required=false`、`restart_reasons=[]`；已安装 doctor 返回 `ok=true`，Browser 与 Windows GUI 均为 `configured_for_wsl`。
- 独立 review 登记 4 个 Important：双黑盒尚缺、任务 appendix 状态过期、`CODEX_COMPAT` 路由冲突及 TOML 行内注释保真问题（最后两项属于静态候选）；另登记 schema/runtime 小写约束不一致和缺失 Browser 插件直接测试两个 Minor。后四项均已用 TDD/文档修正。
- 静态修复后的最新范围为 108/108，focused 外部能力套件由 reviewer 独立复跑为 34/34；26 条规则、模块/任务文档 validator 与 scoped diff-check 继续通过。更新后的 `runtime_common.py` 已重新同步；其后第二次 bootstrap 为零变化，doctor 复核 Browser 与 Windows GUI 仍均为 `configured_for_wsl`。
- 范围复审确认路由冲突、TOML 实现、小写 parity 和可选缺失测试均已关闭；最后一个 Minor 要求把 TOML 保真从片段断言加强为整文件 exact-bytes，该断言已补入。最终静态复审独立复跑该目标 1/1 通过，确认所有 Critical / Important / Minor 均关闭，静态候选 verdict 为 `Ready`。
- 当前真正剩余的验收仅为：新 Desktop 进程中的 Browser 黑盒，以及同一候选下 Windows GUI 非回归黑盒。完成前本次回归状态为 `pending`。

## 2026-09-10 重启后 `cua_repl` 假绿

- 完整重启后，当前任务先收到自然 Browser 操作请求，再在内置 Browser 已打开 `https://example.com/` 的后续轮次收到明确点击请求及 `@Browser` 文本；三次工具清单均只有 `computer_use_wsl`，没有 `cua_repl`/Browser 控制工具，因此 Browser 黑盒明确失败。
- 磁盘证据为 `unified-computer-use@openai-bundled=true`，但 `mcp_servers.cua_repl.enabled=false`；官方本地插件清单将 `unified-computer-use` 标记为 app-managed Browser runtime，其 MCP 清单也明确包含禁用状态的 `cua_repl`。现有 doctor 只检查插件表，仍把 Browser 报为 `configured_for_wsl`，构成确定的假绿。
- 本轮不再让用户重复选择或重启。先以 TDD 把 `cua_repl` 纳入 Browser 声明、bootstrap 精确开关和 doctor，再完成范围 review/验收；真实投放后只允许一次新进程加载，并以工具出现和页面实际点击作为唯一 hit proof。

### `cua_repl` 修正实施与首次 review

- 首轮 3 个最小 Red 分别命中声明缺少 `mcp_server`、bootstrap 不开启现有 `cua_repl`、doctor 对禁用 MCP 假绿；实现后 3/3 Green。
- 首次整文件回归发现旧 machine-doctor 集成夹具缺少 `cua_repl` 表；CFM `CASE-c51a02373c9460e5` 已闭环。夹具补齐真实边界后外部能力 35/35、受影响范围 109/109 通过，规则、文档路由、任务文档和 scoped diff-check 通过。
- 首次独立 review 穷举后无 Critical，登记 3 个 Important：等价 TOML 词法形态可能静默不改、异常 `enabled` 可能 fail open、声明错误类型可能使 validator 抛 `TypeError`；另登记 `cua_repl` 字节级保真的 Minor 测试缺口。候选暂定 `With fixes`。
- 4 类 review finding 均先补最小 Red；一次测试导入遗漏按 CFM `CASE-660fb96cc470ba2a` 闭环。实现随后支持 quoted table/key 保真改写；解析到禁用目标但无法安全定位时明确失败；非布尔或非 table 目标 fail closed；validator 对非 list 策略字段稳定返回错误。新增目标用例 9/9、外部能力当时 42/42 通过。
- 首次范围复审又发现 bridge 对异常原生插件仍使用旧判断，以及 desired=false 后置检查不够严格；两项均以 Red/Green 关闭。第二次范围复审确认无 Critical/Important，唯一 Minor 为证据计数未更新；外部能力 43/43、受影响范围 117/117 通过，代码 verdict 为 `Ready`。
- 当前尚未投放真实 `<CODEX_HOME>`。下一步为真实 bootstrap/备份/幂等/doctor，再进行唯一一次 Desktop 重启后的 Browser 与记事本双黑盒。

### `cua_repl` 真实投放

- 施工前真实 `config.toml` SHA-256 为 `1458b38c1a5eb6a22aa157c303a92621a0ea0bd3dd48b28a3974389d5a659335`；`unified-computer-use=true`、原生 `computer-use=false`、`cua_repl=false`。
- 窄 bootstrap 仅同步 `windows-computer-use-wsl` skill，不发布 GTO；外部插件策略只报告 `enabled_mcp_servers=["cua_repl"]`，`enabled_plugins=[]`、`disabled_plugins=[]`，兼容 MCP 无变化。
- 内容寻址备份 `config.1458b38c1a5eb6a22aa157c303a92621a0ea0bd3dd48b28a3974389d5a659335.toml` 存在且哈希与施工前一致。脱敏逐行比较证明行数不变且只有第 95 行发生安全目标变化 `enabled=false -> true`；`node_repl`、`computer_use_wsl` 全表哈希不变，`cua_repl` 去除 `enabled` 后的结构哈希不变。
- 施工后配置 SHA-256 为 `5dd64c0448ce0db4bbe1fd78b0ae4d58ea059a437fa0a08ceee5011ced31a0be`。第二次相同 bootstrap 返回 `updated=false`、`restart_required=false`、`restart_reasons=[]`，插件策略和兼容 MCP 均为 `changed=false`。
- 安装版 machine doctor 返回 `ok=true`、无 findings/errors；Browser 为 `configured_for_wsl/use_builtin_browser` 且 `mcp_server=cua_repl`、三类异常标志均为 false；Windows GUI 为 `configured_for_wsl/use_computer_use_wsl`，无 enabled/invalid 冲突插件。
- 当前启动中的 Desktop 进程不会热加载新 MCP 开关。真实 hit proof 仍待唯一一次宿主重启后完成，不以安装版 doctor 代替。

## 2026-09-10 重启后纠偏执行起点

- 用户完成重启后，新进程工具清单仍只有 `computer_use_wsl`，没有 Browser/cua_repl；原 `cua_repl.enabled=true` 已被 Desktop 恢复为 `false`，上一轮安装态 doctor 结论被现场黑盒推翻。
- 只读核对当前安装版 Desktop 代码确认这不是配置偶发漂移：WSL 模式生成 unified CUA 配置时主动省略 Browser `nodeRepl`，Browser runtime 资格也排除 `shouldUseWslPaths=true`。因此停止继续接管 app-managed `cua_repl`。
- 已冻结独立 `browser_use_wsl` 纠偏合同。下一步先补最小 Red，再扩展现有透明代理为 `computer`/`browser` 双 surface，随后进行首次穷举 review、真实 bootstrap、协议 smoke 和新进程双黑盒。
- 当前总体状态继续为 `pending`；原 Windows GUI 桥黑盒证据仍有效，但不替代 Browser 自动化 hit proof。
