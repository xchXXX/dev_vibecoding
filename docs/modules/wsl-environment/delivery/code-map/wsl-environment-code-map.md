# WSL 环境逻辑到代码路径映射

本映射冻结 DOC-001 交给后续测试和实现批次的职责边界。列出的入口是本任务的目标实现路径；实现批次应以本表和对应 schema 为准，不另造第二个控制面。

| 逻辑职责 | 代码路径/入口 | 说明 |
| --- | --- | --- |
| 机器公共工具基线 | `config/ai/wsl-tool-baseline.json` | 唯一机器可读基线；不承载项目库或私有配置 |
| 基线结构约束 | `schemas/wsl-tool-baseline.schema.json` | 约束包、命令和版本/来源表达 |
| 项目运行时声明 | `schemas/project-environment.schema.json` | 约束 requirements/pyproject 二选一的 Python 依赖层、Node 依赖层和可选 capability |
| 新项目样例 | `templates/project/config/ai/environment.example.json` | 不含本机绝对路径、密钥或任意 shell |
| 机器层计划/显式 apply | `scripts/provision-wsl.py` | 默认 plan；明确 apply 才安装已声明的最小包 |
| Codex/机器 doctor | `scripts/doctor-core.py` | 审计 Linux 工具路径、受管 runtime hash 与 WSL 正常链边界 |
| 项目环境 doctor | `scripts/project-env-doctor.py` | 只读解析 requirements 或 pyproject 依赖并分类 TEMP、Python、Node、项目工件和可选 capability；不构建项目 |
| Windows 路径转换 | `scripts/resolve-wsl-path.py` | 只转换明确路径值并做存在性检查 |
| Windows 原生插件声明 | `config/ai/windows-external-capabilities.json`、`schemas/windows-external-capabilities.schema.json` | v3 windows_native/required_plugins，只读检查插件配置 |
| Windows 外部能力检查 | `scripts/runtime_common.py`、`scripts/doctor-core.py` | 不解析或改写官方 transport；磁盘检查与 GUI 验收分开 |
| Docker Desktop 安全启动源 | `modules/wsl-environment/tooling/docker-desktop-safe-start.ps1` | 用户明确安装后，按白名单备份残留 socket 目录、注册 HKCU Run 登录入口和开始菜单入口；不进入 WSL 正常链 |
| bootstrap 接线 | `scripts/bootstrap-local.py` | 投放受管 runtime 并在需要时调用机器层检查；不恢复项目依赖 |
| 基线/项目/路径回归 | `tests/harness/test_wsl_environment.py`、`tests/fixtures/wsl-environment/` | 用隔离 fixture 命中每个分类和 CLI 输出 |
| Docker 安全启动回归 | `tests/harness/test_docker_desktop_safe_start.py` | 在隔离 Windows 临时目录验证白名单修复、fail-closed、备份保留和 receipt hash 审计 |

## 关键写入边界

DOC-001 只维护长期合同、设计、工程说明、相关入口文档、规则和模板文字。后续测试批次只改 `tests/harness/test_wsl_environment.py` 与 `tests/fixtures/wsl-environment/`；实现批次只改上表中的 config/schema/script/template 路径及其明确的既有接线点。

Windows 原生 Agent 负责文件、Browser、截图与 Computer Use；项目 Git/Python/Node/测试/构建继续通过指定发行版的 wsl.exe --exec 执行。外部能力声明 v3 只列 windows_native 与 required_plugins；bootstrap/doctor 不写插件配置或官方 transport，不创建 WSL GUI 桥。磁盘 enabled 不等于 GUI 验收。

## 相关测试入口

```bash
python3 -m unittest discover -s tests/harness -p test_windows_native_environment.py
python3 -m unittest discover -s tests/harness -p test_windows_native_transition.py
python3 -m unittest tests.harness.test_docker_desktop_safe_start
python3 scripts/validate_doc_routing.py --repo-root "$PWD" --json
python3 scripts/validate_plan_docs.py --repo-root "$PWD" --json
```

## Windows 原生迁移的限定维护入口

维护标志存在时发布入口拒绝写入。先在隔离目标验证，再冻结候选、受控解除、正式定向发布，失败恢复标志。

- `python3 scripts/bootstrap-local.py --environment-only --harness-root <root> --codex-home <home> --json`：只投放环境 runtime 并更新其真实 receipt；不改动 AGENTS、hooks、插件 config、其他技能和 schema。
- `python3 scripts/sync-codex.py --retire-legacy-gui --harness-root <root> --codex-home <home> --json`：旧桥 MCP 已明确停用且技能符合既有 receipt 时，仅将旧技能移入私有恢复目录并更新该技能记录；未知改动拒绝退役。
- `python3 scripts/doctor-core.py --environment-only --root <root> --codex-home <home> --json`：只审计环境 runtime/receipt、Linux 工具和原生插件配置；不执行 GTO 或其 schema，不等价于全局 doctor 通过。

bootstrap/doctor 不修改原生插件配置。一次性迁移在私有备份和定点核对后删除旧 WSL GUI 桥配置、代码与技能；完成后不保留旧运行或发现入口。Windows 调用 WSL 时使用 `wsl.exe -d <distro> --cd <project> --exec python3 <script>`；复杂内容先写脚本文件，避免默认 shell 解释反引号、重定向或变量。

迁移回归为上述两个原生测试入口。test_wsl_environment.py 保留 Linux 环境治理回归，但整套含 GTO 依赖；本迁移只运行明确无 GTO 的目标方法，不执行整套。
