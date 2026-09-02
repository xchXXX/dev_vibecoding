# 全局 AGENTS 与新电脑迁移审计验收

## 验收目标

确认全局 Codex 指令已在新电脑的实际运行位置生效，当前 harness 的活动态路径可移植，并向用户给出完整但不过度改写历史的迁移结论。

## 验收标准

- 实际 Codex home 下存在符合分层原则的简洁 `AGENTS.md`。
- 不存在未说明的 `AGENTS.override.md` 遮蔽，且文件不绑定旧用户名或旧仓库路径。
- 活动态项目入口和规则索引可从当前仓库正确解析。
- 最小相关验证与独立审查通过。
- 遗留项按优先级、影响和建议命令列清楚。

## 必备证据

- Codex home：`C:/Users/Laptop/.codex`；`AGENTS.md` 为 32 行、2011 bytes，`AGENTS.override.md` 不存在，未读取 `auth.json`。
- 活动态 16 个入口、合同与生成物中的 `72385` 命中为 0；历史 run、旧 task、迁移方案和 sandbox 证据保留原路径。
- `generate-rules-index` 与 `validate-rules`：21 条本地规则、21 条生效规则，通过。
- `sync-codex` 与 strict doctor：四个受管 skill 的 source/runtime/receipt issues 均为空。
- Windows 全局指令合同：4/4 通过；plan-docs：6/6；doc-routing：2/2；`git diff --check` 通过。
- reviewer 结论：通过；`state.json` 中三个 review evidence slot 均由执行/测试结果覆盖。

## 未决项

- P1：安装系统级 Python 3（当前 `python/py/pip/uv` 均不可用），否则 `pre-dev-benchmark` 的 Python 入口无法运行。
- P1：首次提交前配置 Git `user.name` 与 `user.email`。
- P1：如需脱离 Codex Desktop 独立运行 harness，安装系统级 PowerShell 7，并确认 `rg`、`pnpm` 位于普通终端 PATH。
- P2：当前跨项目规则发现不依赖 sibling 猜测；消费项目必须显式传 `-GlobalRulesRoot D:/prj/harnesss/dev_vibecoding`。仓库移动后需同步更新全局 AGENTS 并重跑 sync/doctor。
- P3：历史 run、旧 task、迁移复盘和 sandbox 中的旧电脑路径作为证据保留；是否另行归档由用户决定。

## 最终结论

通过。全局 Codex 指令、活动态路径迁移、四个受管 skill 投放、规则生成视图和最小验证链路均已闭环；独立 reviewer 无阻断 finding。未决项均为系统工具安装、Git 身份或未来路径治理，不阻断当前 Codex harness 使用。
