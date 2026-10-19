# 处置清单与恢复点

## 原位恢复包

- Windows：`C:/Users/Laptop/.codex/.ai-harness/backups/windows-native-transition-20260910-pre-switch/`
- WSL：`/mnt/c/Users/Laptop/.codex/.ai-harness/backups/windows-native-transition-20260910-pre-switch/`
- `manifest.json` 记录每个绝对路径、role、before_sha256、backup；交付前 seal 记录 after_sha256/after_copy。`role=reference` 仅为上下文快照，不自动恢复。
- `config.toml` 是不透明私有备份，可能含敏感配置，禁止打印、提交、上传、粘贴或整目录复制。没有读取/备份 auth.json 或任何项目密钥文件。
- 此包只覆盖本次改动的原有文件和相关参考文件，不是整仓库、Docker 数据或整机备份。此次新建任务文档及测试属于新交付物，恢复生效配置时保留作证据。

## 已准备的运行分工

| 项目 | Windows 路径 | WSL 路径 | 保留环境 |
|---|---|---|---|
| harness | D:/prj/harnesss/dev_vibecoding | /mnt/d/prj/harnesss/dev_vibecoding | .venv、requirements.txt、系统 Linux 工具 |
| drugsale | D:/prj/drugsale_practice_system | /mnt/d/prj/drugsale_practice_system | .venv-wsl、node_modules、项目锁文件 |

指定发行版：`Ubuntu-24.04`。`docker-desktop` 不是项目开发发行版。WSL 侧 Codex home 使用既有 `/mnt/c/Users/Laptop/.codex`，不复制经验库。

## 准备批次修改及保留（历史）

| 对象 | 处理 | 状态与后继职责 |
|---|---|---|
| scripts/bootstrap-local.py / sync-codex.py | 加维护标志前置停止 | 本批实现；不能为绕过提示直接删标志 |
| templates/codex/AGENTS.global.md 与 CODEX_HOME/AGENTS.md | 环境段改为 Windows 宿主 + WSL 命令 | 本批定向渲染；旧 bootstrap receipt 暂不改，维护期间明确失配 |
| 规则：命令构造、脚本运行基线、缺失工具分层 | 修正宿主/执行平台和维护期约束 | 本批更新，索引由正式生成器刷新 |
| drugsale_practice_system/AGENTS.md | 只改浏览器与环境入口 | 业务模型、数据、API 启动约束保留 |
| computer-use@openai-bundled | 现有 enabled=false → true | 本批配置，实际加载待 Windows 新进程 |
| mcp_servers.computer_use_wsl | 现有 enabled 缺省 → false | 本批停用，不删除代码 |
| mcp_servers.browser_use_wsl | 本机表不存在 | 不创建；仓库候选已有相关代码，不发布 |
| node_repl / cua_repl | 完整保留宿主所有字段 | Windows 重启后由 Desktop 自行生成；不得强行开 cua_repl |
| CODEX_HOME/.ai-harness/windows-native-transition.hold | 新增维护标志 | 阻止旧发布链回写；非后台任务或守护进程 |
| runtime_common.py、外部能力 JSON/schema、node-repl-wsl-compat.py | 保留进行中源码，不覆盖、不发布 | 后继审查归属后退役/简化，不能把本批当作它们的验收 |
| doctor-core.py、安装 runtime/receipts | 不用全量同步消除旧失败 | 后继完成平台适配与定向同步后由正式流程生成新 receipt |
| Windows/WSL 系统配置、Docker、服务、容器、数据库、项目依赖 | 不改 | 后继只读审查与业务保全验收；若发现冲突再提出精确变更 |
| GTO 及无关脏改动 | 不调用、不同步、不回滚 | 保持原样 |

## 恢复约束

恢复 role=modify 文件前，先确认当前 hash 仍等于 after_sha256；任何漂移先停下做差异合并，尤其 Desktop 会在重启后合法重建 config.toml。参考快照不可整体还原。恢复本次新增维护标志时按 manifest 中 before=null 处理，必须最后操作，以免中途重新允许旧安装器。

如切到 Windows 后要回到原宿主，恢复文件并不等于切换 Desktop 设置；需要用户在设置切回 WSL 后重启。数据服务从未改变，不需要回滚容器或数据。

## 切换前主协调复核（历史）

当前 Agent 仍是 WSL，CODEX_HOME=/mnt/c/Users/Laptop/.codex。配置结构相对封存唯一变化为 model_reasoning_effort；computer-use=true、unified-computer-use=true，browser 配置项及标准缓存目录未发现，computer_use_wsl=false、browser_use_wsl 表不存在。未修改配置、未重新 seal。配置当前 SHA256=32d6d54eeed3aadcdc0576e25e8eeb6d180d4782f92320254e333fa00e05e77b。

23 项备份全部完整；除 config.toml 外当前内容与封存一致。check-restore.py 返回 exit 2 / safe_for_scoped_restore=false 是当前真实结果，禁止整体覆盖配置。恢复应先保存当前私有前像，再只合并迁移的 enabled 键，保留 model_reasoning_effort 及宿主生成字段。原始包继续保留，不以重封存抹去漂移。

正式解除维护与定向发布顺序以 plan.md 的受控解除段为准；维护标志当前内容是早期条件摘要，不能解释为真实 receipt 必须先于正式同步生成。解除前仍必须有隔离闭环证据与冻结候选。

恢复本迁移开关时须区分 before 中 enabled 缺省与显式布尔值：原本不存在的 enabled 应仅删除本次新增的键，不能用显式 true 代替；原值已存在时恢复原值。仍需写前检查当前前像并复核脱敏结构差。

补充证据：主协调另行只读核验 manifest 全部 before 与存在的 after_copy，其 hash 均匹配，23 项材料完整。该结果独立于 snapshot.py verify；原工具不检查 after_copy，且 ok=false 时仍可能 exit 0，消费方必须检查 JSON。

## Windows 原生接续实时结果（2026-09-10）

用户报告已切换；实际 Win32NT / Windows PowerShell 路径已确认，Windows codex.exe PID 27720、28412 均来自 C:/Users/Laptop/AppData/Local/OpenAI/Codex/bin/8e5b6932251c2c1c/codex.exe。未借助 CIM 获取父进程；该检查被环境拒绝，没有伪称进程父子关系已证明。

CODEX_HOME 环境变量为空；Windows 用户目录 C:/Users/Laptop/.codex 的任务 hold、恢复包及 config 存在。只输出允许字段的结构核对显示：computer-use、browser、unified-computer-use enabled=true；computer_use_wsl=false。node_repl/cua_repl 的 enabled 键不存在，此结果不能解释成禁用。Browser 标准缓存现已存在。

当前所有可调用工具中不存在 node_repl/cua_repl/Browser/Computer Use 操作工具。已读 Computer Use 技能，要求通过官方 node_repl 导入 @oai/sky；当前缺少该入口，不能启动自造客户端代替。Browser manifest 要求使用内置 Browser，未通过 shell 或 web.run 冒充点击。

当前任务 cwd=C:/mnt/d/prj/harnesss/dev_vibecoding 不存在；真实 D:/prj/harnesss/dev_vibecoding 存在，应用项目登记也指向 D:/。之后所有命令显式指定真实 workdir，未创建镜像或搬库。

裸 wsl.exe 不在当前 PowerShell PATH。C:/Windows/System32/wsl.exe 确实存在；受限沙箱首次调用返回 Wsl/EnumerateDistros/Service/E_ACCESSDENIED，只读提权调用成功；随后用户将权限设为完全访问，重新列举成功。Ubuntu-24.04 和 docker-desktop 均存在。切换后 harness 已安装 project doctor 通过（ok=true/findings=[]/errors=[]），不代表 ACC-05 的两项目代表性测试/构建通过。

CFM：CASE-7bd1e169f71a4672（错误 cwd，显式真实路径验证）、CASE-f5efc1124c7bd74e（WSL 绝对路径）、CASE-4550f51e4ef2a7df（沙箱服务访问边界）已记录查询与成功。首次纠正读取/沙箱回退早于补记，未倒填合规顺序。CIM 失败 signature b8757d3031d6b54c9e16c53184f042812edb37ee88917138663c85cff3810f97 已记录/查询，未重试或伪称修复。

本批仅更新任务事实；不改 config/transport、不全量发布、不解除 hold。P5 GUI 能力缺失阻塞优先插件验收，ACC-01/02/04 blocked；其余 pending，migration_accepted=false。
## P6 原生源码候选

用户确认插件可用，GUI 主协调证据缺口不阻塞清理。v3 声明只支持本机实际使用的 Windows 原生插件，移除未使用旧 WSL/HTTP 路由类型；runtime 检查纯只读。源码桥及旧桥专属技能/测试按 P6 前像退役。原 .tmp/apply-config.py 是历史施工证据，依赖已退役 API，不可再执行；它不是恢复入口。

环境限定 bootstrap/doctor 不执行技能或 GTO schema；限定发布不改 config/AGENTS/hooks。原机器全局 doctor 仍包含其他任务检查，本迁移只使用 --environment-only，不能声称全局通过。旧停用 config 表保留到插件使用之外的收口窗口；不会因它停用而判功能不可用。

## P6 实施期间事实（历史）

当前 P6：已完成 Windows 原生切换，用户确认 Computer Use、Browser 和 unified-computer-use 正常使用。PRE-01..07 已通过，不重做。主协调继续定向清理；GUI 工具在本会话未暴露，仅对应证据 pending，不阻塞其余实施。

实际项目 D:/prj/harnesss/dev_vibecoding；WSL /mnt/d/prj/harnesss/dev_vibecoding。应用携带的 C:/mnt/d 路径无效，不复制仓库。命令指定真实 workdir，并使用 C:/Windows/System32/wsl.exe -d Ubuntu-24.04 --cd <Linux项目> --exec <命令>；复杂内容先写脚本，禁止将 Markdown 反引号嵌入默认 shell 的 python -c。

原生声明 v3、只读诊断、environment-only 发布与 receipt 驱动的旧技能退役已实现，尚未发布。独立 Carver 正在做完整迁移首次 review；有修复则同 reviewer 范围复审。维护 hold 仍存在；发布前先冻结私有 installed 前像和候选 hash。仅正式 environment-only 与 retire-legacy-gui 入口可用于本任务，不全量发布、不调用 GTO/schema、不改正在使用的插件配置。

ACC-05：两个项目 project doctor 均通过；harness 原生环境回归12项及维护守卫4项通过；drugsale Linux pnpm typecheck 通过。ACC-06：现有五容器均 healthy，未重启或改服务。ACC-01 用户确认可用但待主协调操作证据；ACC-02/03/04 pending；ACC-07/08待定向正式发布与恢复演练。migration_accepted=false。

Docker 只读基线：worker 72a22f7b9905、api 29bca7421b41、web d36f57799fea、postgres 863919c56230、redis aa66ea23c3af，全部 healthy。后续复核相同容器与 StartedAt，不能以此替代 GUI。

## P7 当前最终事实

Windows 原生迁移的源码与安装清理已完成，当前 P7，剩余 GUI/新附件证据待补。用户已确认 computer-use、browser、unified-computer-use 正常使用；无需再次切换或重复准备。

Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；Git、Python/Node、测试构建、Linux 依赖和服务继续在 Ubuntu-24.04。实际项目 D:/prj/harnesss/dev_vibecoding；WSL /mnt/d/prj/harnesss/dev_vibecoding。Windows 调用使用 C:/Windows/System32/wsl.exe 指定发行版和 --exec，工作目录用真实 D:/，不创建 C:/mnt/d 镜像。

已删除旧 GUI 桥源码/技能/旧测试、installed node-repl-wsl-compat.py、installed windows-computer-use-wsl 技能，以及 config.toml 中停用的 computer_use_wsl 表（browser_use_wsl 原本不存在）。不保留旧运行兼容层；私有恢复材料不参与技能发现。bootstrap/doctor 只读原生插件配置，所有原生插件与官方 transport、其余配置语义保持不变。

正式 environment-only 发布和 retire-legacy-gui 各执行两轮，第二轮无变；10个环境运行文件源/安装/receipt吻合，AGENTS/template receipt一致，无关sync记录保持不变。限定环境doctor通过，hold已受控解除。没有全量发布、调用GTO或读取其schema，未改业务依赖/服务/数据。

独立reviewer Carver首次完整审查与同reviewer范围复审已完成，P6-001..012全部关闭；最后5处文档原则修订复审通过。主协调22项原生回归、4项hold守卫、1项目模板测试通过；配置成功/失败边界4组通过。两项目project doctor发布后再次通过，drugsale Linux pnpm typecheck通过；五容器ID/StartedAt/healthy不变。

ACC-05/06/07/08通过。ACC-01用户确认可用、主协调实操证据待补；ACC-02 Browser真点击/title/URL、ACC-03用户新附件、ACC-04自建窗口生命周期仍pending。本会话工具清单没有官方Browser/Computer Use操作工具，不能用HTTP、doctor或用户确认替代这些证据。migration_accepted=false；这是证据缺口，不是清理实施被阻塞。

验证报告：p6-publication.json、p6-final-audit.json、p6-verification.json、p6-cleanup.json。私有恢复包：/mnt/c/Users/Laptop/.codex/.ai-harness/backups/windows-native-transition-20260910-p6-085320；原始pre-switch包保留，不能整份覆盖当前配置。过程脚本及p6-before原像已移至 process-materials；旧 .tmp 路径仅为历史位置。

恢复：先重建任务hold；对需恢复目标比较当前hash与p6-publication/最终审计的after证据，漂移则停止覆盖并定点合并。installed文件与receipt可从私有 files 前像按目标恢复；原生config只按迁移键做合并，不能用整份旧config覆盖Desktop后续字段。16文件演练仅证明隔离字节恢复，不证明整机/业务数据恢复。

## 全面扫描后的当前结论（覆盖此前清理完结表述）
当前全面扫描已完成，结论为仍需整改，不能宣称全部环境产物已扫净。新的独立reviewer Fermat发现11项：P1=0、P2=6、P3=5，详见environment-scan-review.md。上一轮P6-001..012关闭仅保留为当时范围的历史证据，不覆盖此次新发现。

已证明的内容继续成立：Windows原生宿主与三插件正常配置；正式安装中的旧WSL GUI桥运行时/技能已删除，10个环境文件源/安装/receipt一致；限定环境doctor通过，五容器ID/StartedAt/healthy不变。维护hold当前已解除。

需要整改：默认Codex home/CFM目标可能误落WSL home；strict合同错误拒绝合法Windows PowerShell；健康测试夹具缺原生插件；架构/附件/Browser/药品项目长期文档旧分工与当前事实冲突；遗留一个旧桥测试bytecode；测试临时父目录及导航未收口。所有ENV-SCAN-001..011仍开放，尚未实施新修复。

Windows负责Agent文件、Browser、截图、Computer Use；WSL保留Git/开发命令/Python/Node/测试构建/Linux依赖和服务。当前Ubuntu CODEX_HOME未设置、HOME=/home/laptop，与C:/Users/Laptop/.codex不同；不得靠删除Linux用户目录掩盖目标选择问题。

继续按既有迁移授权定向修复、验证并由同一reviewer做影响范围复审。禁止GTO/orchestrator_ctl/GTO schema、全量发布、覆盖混合dirty、改原生插件transport、误删历史/恢复包/业务依赖数据。GUI与新附件证据仍pending，migration_accepted=false。

## ENV-SCAN 整改最终事实（覆盖此前整改中状态）

同一独立reviewer Fermat两轮范围复审关闭ENV-SCAN-001..011：首次关闭10项，最后四文件入口/metadata delta复审关闭001。未新增兼容桥；旧运行时、技能及孤立测试bytecode已不在活跃路径，测试不再遗留固定任务父目录。Windows负责Agent文件与GUI，WSL保留开发命令、依赖和服务。

主协调验证：native28项、CFM12项、hold4项、合同fixture2项通过；26条规则元数据校验通过。最终候选隔离和实际正式发布均限定environment-only与CFM-only，各两轮、第二轮无变化；源码/安装/receipt真实hash一致，插件config及AGENTS字节未改、无关receipt行未改。两个项目doctor及限定环境doctor通过，5容器ID/StartedAt不变且healthy。17文件隔离恢复通过，29份源快照校验完好。维护hold已解除。详细证据见envscan-isolated-publication.json、envscan-live-publication.json、envscan-postpublish-verification.json、envscan-final-audit.json。

本次审查与验证边界排除GTO实现/schema/专项测试、全局strict及真实GUI验收；没有全量发布。ACC-05..08通过，ACC-01..04保留主协调GUI/新附件证据缺口，用户插件可用事实保留，migration_accepted=false。这些证据缺口不表示插件不可用，也不表示环境清理仍未施工。历史记录及私有恢复包仅作证据，不作为活跃兼容实现。
