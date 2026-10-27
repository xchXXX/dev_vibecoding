# Doctor 与启动边界设计

## 设计目标

在最早且足够少的时点发现环境错误，使项目测试不再被错误平台、错误临时目录或错误依赖伪装成业务失败；同时避免把检查扩张成常驻服务或每条命令的拦截器。

## 启动时序

```text
新 worktree 已就绪
        |
        v
Linux 项目环境检查（维护期按任务合同，平时核对机器基线）
        |
        +-- 不通过 -> 报告分类与人工/显式 apply 交接；不运行项目测试
        |
        v
任务首次触及运行时
        |
        v
project doctor（项目依赖、TEMP、Python/Node 工件、声明的 capability）
        |
        +-- 不通过 -> 报告项目或外部能力缺口；不自动修复
        |
        v
项目测试、构建或验收
```

## 何时运行

machine doctor 是一次快速启动检查，而不是每条命令的 wrapper。它应在以下时点运行：

- Codex 新 worktree setup 完成后；
- GTO 长任务第一次准备运行代码前；
- Linux 项目任务第一次真正触及 Python、Node、项目自动化测试或 Docker 运行时前；
- Linux 项目运行出现新的机器环境差异时；
- 已有运行时错误证据，且需重新判断机器层/项目层归属时。

project doctor 的输入是项目环境声明和当前项目目录，只负责 Linux 项目运行。官方 Browser/Computer Use 请求不依赖 harness 发布、machine doctor 或 project doctor 通过。迁移 hold 存在时，暂停全局 bootstrap/sync 和旧 machine doctor 修复链，按指向任务接续；项目 doctor 与正常原生插件操作可继续，GUI 证据单列。它不接管未声明项目，也不扫描同机其他 clone。

## 诊断责任

| 诊断对象 | 首选入口 | 结果与动作 |
| --- | --- | --- |
| WSL 公共工具、Linux 路径、受管 Codex runtime hash | `scripts/doctor-core.py` | 报告 machine/runtime 问题；由显式 provision 或 runtime sync 处理 |
| 基线包是否满足声明 | `scripts/provision-wsl.py` | 默认输出计划；显式 apply 才能变更已批准的机器层包 |
| `TEMP`、Python、Node、Windows 工件、可选 capability | `scripts/project-env-doctor.py` | 从 requirements 或 pyproject 只读核对项目依赖并输出分类；项目维护者恢复自身依赖或完成外部设置 |
| 明确的 Windows 文件路径 | `scripts/resolve-wsl-path.py` | 仅转换该值并检查存在性；不改命令文本或环境变量集合 |
| Windows 原生插件 | `config/ai/windows-external-capabilities.json`、`scripts/doctor-core.py --environment-only` | 只读检查声明中的插件开关；真实点击、截图及窗口生命周期由主协调另行验收 |
| 已确认的 Docker Desktop 残留 socket 复发 | `modules/wsl-environment/tooling/docker-desktop-safe-start.ps1` | 用户单独安装；登录或手工触发时按白名单备份，不进入项目命令链 |

## 关键决策

1. **machine doctor 和 project doctor 分开。** 公共工具可用不等于项目依赖、浏览器或 Docker 已就绪；反之项目 lock 完整也不能掩盖 Windows 路径泄漏。
2. **只在任务开始的最小边界检查。** 常驻 daemon、hook、逐命令 preflight 与自动重试会隐藏失败原因、增加延迟并扩大权限，因此不属于本设计。
3. **分类先于修复。** 诊断 JSON 应指出错误层、证据和建议所有者；实际变更需要明确命令或人工确认。
4. **Codex runtime 与项目 runtime 分开。** managed `AGENTS.md`、skills/schema receipt 的 hash 一致性属于 bootstrap/doctor；Python/Node/Playwright/Docker 状态属于项目声明和 project doctor。
5. **Docker 修复是窄化的 Windows 外部例外。** machine doctor 只读审计 receipt 和 hash；真正的 Windows 修复只由已授权的 HKCU Run/开始菜单入口触发，且不能处理白名单以外的内容。
6. **Windows 原生能力与 Linux 项目命令分开。** Windows 原生 Agent 使用官方 Browser 和 Computer Use；WSL 保留项目命令与 Linux 依赖。harness 只读检查原生插件配置，不改写官方 transport、插件开关或注册 WSL GUI 桥；磁盘配置不等于真实 GUI 验收。
7. **插件缺失或配置异常只报告。** 由 Desktop 的官方插件管理处理；不根据 PE、环境变量或缺省 enabled 字段推断 transport 损坏，不运行 bootstrap 改写插件。

## 边界条件

- 普通命令非零退出进入 Command Failure Memory 闭环；不得改在另一平台自动重跑。
- `TEMP`、`TMP`、`TMPDIR` 指向 Windows 挂载路径，或 Node/Python 工件来自 Windows 时，应在项目测试之前归类为环境问题。
- Docker Desktop WSL Integration、Windows 浏览器和账号/网络访问默认只能检查必要证据或提示交接。经用户明确授权安装的 Docker 安全启动器仅可修改它自己的 HKCU Run/按用户安装位置键、脚本副本和已知残留 socket 目录，不修改 Docker Desktop UI 设置。
- 受管 `AGENTS.md`、skills 或 schema 变更后，已启动会话不会热更新；需依据 bootstrap receipt 结论新建任务或重启 Codex。


## 20261027 性能改进

性能合同（20261027）：外部探针具有分项deadline和总预算，超时清理子进程组并返回明确类别；同轮manifest复用但不跨命令盲信守护进程健康。源侧准备与测试不持发布锁，发布锁内核对预期代际并原子提交；故障保持回滚。

入口预算使用 `runtime_common.probe_budget(seconds)` 的操作级绝对单调时钟期限。project doctor 一轮以及 machine doctor 的 `audit` / `audit_environment` 各共享 120 秒探针预算；每个普通探针仍至多 30 秒，后续探针只能使用剩余预算。machine doctor 的 strict 源侧合同测试另有 300 秒预算，不占用或缩短环境检查预算；组合入口这两个阶段的探针预算合计至多 420 秒，不将文件 I/O 或发布回滚宣称为可强制中断。

`run_probe` 取显式 deadline、当前操作预算和单探针 timeout 的最早边界。预算耗尽不再启动新进程；运行中耗尽会杀进程组。预算异常兼容 `subprocess.TimeoutExpired`，明确标记 `probe_budget_exhausted`；doctor 对该类别单独报告，不能误报成缺依赖或声明无效。上下文退出恢复此前预算，嵌套预算不能延长外层期限。
