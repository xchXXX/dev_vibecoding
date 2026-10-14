# Portable Harness 公共合同

状态：实施合同；通过情况只见任务验收记录。配置、包格式和生命周期字段以本文为唯一真源；任务计划引用本文。

## 配置与命令

Python >=3.11，基础安装、诊断只需标准库。配置仅接受 `codex_home`、`skills_dir`、`environment`；不接受项目级安装目标覆盖。优先级为 CLI > 用户 JSON > `CODEX_HOME` / `CODEX_SKILLS_DIR` / `HARNESS_ENVIRONMENT` > 默认。home 无隐式默认；skills 默认 home/skills；environment 默认 auto。JSON 内路径相对于 JSON 文件目录，CLI/环境路径必须绝对。空值、未知字段、非法环境与链接路径拒绝。同层配置不得静默覆盖：JSON 字段和 CLI 的 `--codex-home`、`--skills-dir`、`--environment`、`--config` 均只允许出现一次，重复时返回 `CONFIG_INVALID`，即使值相同也拒绝；不同来源仍按上述优先级解析。结果含 Path 类型安装根、实际 environment 和 sources（cli/config/env/default）。指定环境必须与当前运行解释器的系统类型一致；WSL 不自动转换未核实的 Windows 路径。

入口 `scripts/harness.py`：build 接受 --source-root、--output、--version、--source-commit；install/update 接受 --bundle；生命周期接受 --codex-home、--skills-dir、--environment、--config、--modules、--dry-run、--json（按动作适用）。modules 为逗号分隔高级可选项，省略表示完整安装。recover/doctor 不提供 dry-run。退出 0 表示结果 ok=true，其余非零。人读与 JSON 使用同一结果；未知参数不得忽略。

## 分发格式

固定来源构建只读取该提交的白名单文件；拒绝 HEAD/短哈希等可变或含糊的 source_commit。可构建工作区候选用于诊断，但必须先提交候选，不能将脏内容标成既有提交。输出目录必须不存在或为空。所有源文件为普通文件，不含链接、缓存、作者数据或历史任务。相同提交与版本产生字节一致的内容。

`manifest.json` 字段：schema_version=1、version、source_commit、modules、files、payload_files。modules 为已知模块列表（base、benchmark、fix、cfm、gto）。files 各项为 source/root/target/module/sha256；root 只允许 home、skills，source 和 target 均为无点段的 POSIX 相对路径。payload_files 为分发工具/文档的 source/sha256 清单，不安装为技能。所有文件须在清单内，哈希必须相符；路径大小写碰撞、设备名称、反斜线、冒号、重解析点、源文件链接和重复目标均拒绝。

清单另含 dependencies、build_entrypoint、support_matrix，缺失或结构无效时拒绝。dependencies 声明 Python >=3.11、Git 的 required_for（build/git_workflow/gto），以及 jsonschema 的 specifier（>=4.10.3,<5）和 required_for（gto）；基础 install/doctor 不因此新增第三方依赖。GTO requirements 与清单声明不一致时拒绝构建。build_entrypoint 为 scripts/harness.py build。support_matrix 对 windows/linux/wsl 分别声明 status=candidate、session_verified=false；这是候选目标与证据边界，不代替平台验收报告，也不声称已验证新的 Codex 会话。

base 安装到 home/.ai-harness/portable/runtime/ 下自包含规则、管理工具和基础模板；四技能分别映射各自目录到 skills 根。安装的管理 CLI 能在源仓库移走后运行。模块之间不隐式依赖；GTO 选择必须显式出现在会话任务授权中，安装 GTO 不等于启用编排。

## 所有权与 receipt

元数据目录 home/.ai-harness/portable/。receipt.json 含 schema_version=1、roots={home,skills}（规范绝对路径）、modules={模块:版本}、files=[{root,target,module,sha256}] 以及 agents_block（管理区块哈希或 null）。只有 manifest 中合法目标才能被写入；receipt 必须经过同等路径与归属验证，不以任意 JSON 文件列表获得删除权。

AGENTS.md 只拥有 `<!-- ai-harness:portable:start -->` 至 `<!-- ai-harness:portable:end -->`（含标记）的区块。受管区块外的所有字节保留；首次遇已有区块但无 receipt 拒绝。区块由 base 提供。更新与卸载预检受管文件和区块的当前哈希；缺失、漂移、未知同名资产均拒绝，整个操作不部分执行。普通用户文件包括 config.toml/hooks/MCP、其他技能和记忆不进入所有权。

单模块更新保留其他模块与版本；新包已删除的本模块文件在当前哈希匹配时删除。卸载模块保留用户数据、空目录、锁文件及运行快照；这些残留不算已安装模块。不递归删除目录。dry-run 不创建安装根、元数据、锁或临时文件。

## 互斥与恢复

home 与独立 skills 根分别持有固定 advisory 锁，按绝对路径排序获取；Linux/WSL 用 fcntl，Windows 用 msvcrt。锁元数据只用于诊断，OS 锁决定占用；崩溃后 OS 释放，不能通过删除 lock 文件强行解锁。此版本不承诺不同内核跨系统同时写同一共享文件系统的锁互通，检测到不同环境 receipt 应停止写入并要求在原环境管理。

先完整预检、在 journal 中保留原字节及目标哈希，再逐文件原子替换，receipt 最后写。journal.json：schema_version=1、roots={home,skills}、changes=[{root,target,before,after}]；before 是原字节 base64 或 null，after 为预期新内容 sha256 或 null。journal 允许的元数据目标仅 receipt.json；其他目标须由合法 receipt/候选归属清单证明所有权。journal 包含 transaction_files 和 before_receipt，以便从未完成首次安装恢复；验证一致性、所有权、路径和 before 哈希后才执行恢复。AGENTS 变化保留完整前后哈希供回滚，不恢复外部后来改过的内容。

后续写入发现 journal 必须返回 RECOVERY_REQUIRED；recover 反向逐项恢复，只有当前内容匹配 before 或 after 才可操作。检测外部变更时保留该文件、其余可安全项恢复，返回 RECOVERY_INCOMPLETE 并保留 journal。损坏元数据在任何写入之前失败。失败尝试安全回滚；完整回滚与不完整恢复分别报告，不宣称多文件事务整体原子。若 receipt 已提交且所有 after 匹配，recover 可完成清理而不撤销成功提交。

## 验证与证据边界

doctor 只读验证 receipt、区块、文件完整性，列出基础与可选依赖，并始终将未取得真实新会话证据的 session_verified 设为 false。ok 表示磁盘完整性；blocked_capabilities 单独报告缺依赖的能力：缺 git 为 git_workflow，已装 GTO 但缺 git 或当前解释器缺 jsonschema 时同时报告 gto。next_step 提供对应环境的依赖处理步骤及新会话检查建议，依赖可导入不等于该能力已经实际验收。Linux/WSL/原生 Windows 各自测试不能互相替代；单元测试、隔离安装和真实 Codex 新会话分别记录。

错误包含稳定 code 与可执行 message，至少区分 CONFIG_INVALID、UNSAFE_PATH、BUNDLE_INVALID、UNMANAGED_CONFLICT、MANAGED_DRIFT、LOCKED、RECOVERY_REQUIRED、RECOVERY_INCOMPLETE、ROLLED_BACK。错误不触发提权、全局修复、无限重试或个人数据迁移。
