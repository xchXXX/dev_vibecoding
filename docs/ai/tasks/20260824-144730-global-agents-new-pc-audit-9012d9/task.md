# 任务摘要

## 基本信息

- `task_id`: `20260824-144730-global-agents-new-pc-audit-9012d9`
- `title`: 全局 AGENTS 与新电脑迁移审计
- `status`: `completed`
- `owner`: `main-coordinator`

## 目标

- 基于当前 harness 生成简洁高效的全局 AGENTS.md，并详细检查新电脑上的路径、配置、依赖与 Codex 集成迁移问题。

## 范围

### Scope In

- 审计当前仓库中会影响新电脑运行的旧绝对路径与 Codex 配置
- 在当前 Codex home 生成简洁、跨项目复用的全局 AGENTS.md
- 修正当前仓库少量直接影响规则发现和全局入口的活动态路径约定
- 运行 harness 的最小同步、doctor、规则与指令发现验证
- 形成按优先级分类的迁移后续事项

### Scope Out

- 机械替换历史 run、复盘、benchmark 夹具和已归档任务中的旧路径
- 接管或覆盖未由本仓库托管的第三方 Codex skills、plugins 与 MCP 配置
- 修改 Codex 认证文件、密钥或账号配置
- 未经需要执行大范围 Claude 运行时迁移

## 验收标准

- 当前 Codex home 下存在非空且简洁的 AGENTS.md，并且不存在同层 AGENTS.override.md 遮蔽它
- 全局 AGENTS.md 只保留跨项目工作约定、harness 发现入口和安全边界，不复制项目规则正文
- 活动态入口不再依赖 C:/Users/72385 或旧仓库绝对路径
- 规则索引、文档路由、计划文档、Codex sync/doctor 的最小相关验证通过
- 迁移审计明确区分必须修复、建议修复和仅历史留痕三类问题

## 停止条件

- 目标 Codex home 无法安全解析或存在非空 AGENTS.override.md 且用户未授权处理
- 现有全局 AGENTS.md 包含无法判断归属的用户内容，覆盖会造成数据丢失
- 修复需要修改认证信息、系统级安全策略或仓库外大范围文件

## 关键决定

- 以 CODEX_HOME 为优先、USERPROFILE/.codex 为回退解析全局文件位置
- 历史证据中的旧路径保留原貌；只修正活动态真源、生成物和当前测试合同
- 全局 AGENTS.md 除一行本机 harness 真源定位外保持机器无关，具体项目规则由各仓库 AGENTS.md 与 rules registry 叠加
- 本轮不扩展规则发现脚本；跨项目规则解析由全局入口给出当前 harness 根，并在调用时显式传 GlobalRulesRoot

## 当前阶段

- `current_phase`: `review`

## 子任务

### READ-PATHS-001

- `title`: 旧路径与迁移风险审计
- `role`: `explorer`
- `status`: `completed`
- `goal`: 区分会影响运行的旧路径与仅作历史证据的旧路径。

### READ-DESIGN-002

- `title`: harness 设计与安装链路审计
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 确定全局 AGENTS.md 的最小内容及新电脑安装、同步、doctor 顺序。

### READ-ENV-003

- `title`: 本机 Codex home 与工具链审计
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 确认新电脑实际目标路径、遮蔽文件、运行时 skills 与必要工具可用性。

### DOC-SYNC-004

- `title`: 活动入口与现行合同文档便携化
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 把仍作为现行入口或长期合同的旧机路径改为 repo-relative、<harness-root>、~/.codex、~/.claude 等便携表达，并把 Codex 受管 skill 口径同步为脚本实际的四个。
- `dependencies`: `READ-PATHS-001`, `READ-DESIGN-002`, `READ-ENV-003`

### TEST-SYNC-005

- `title`: 动态全局 AGENTS 路径合同与基线测试
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 让全局 AGENTS 合同按 CODEX_HOME 优先、USERPROFILE/.codex 回退解析，并在全局文件写入前证明其余 Windows 规则基线稳定。
- `dependencies`: `DOC-SYNC-004`

### IMPL-GLOBAL-006

- `title`: 写入全局 AGENTS、刷新规则索引并同步 Codex skills
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 写入约 25 至 35 行的简洁全局 AGENTS.md，包含当前 harness 根定位；通过项目脚本生成当前规则视图，并正式投放四个受管 Codex skills。
- `dependencies`: `TEST-SYNC-005`

### REVIEW-007

- `title`: 迁移闭环独立审查
- `role`: `reviewer`
- `status`: `completed`
- `goal`: 独立判断全局文件、路径迁移分类、运行时同步与验证证据是否完整，给出通过/不通过结论。
- `dependencies`: `IMPL-GLOBAL-006`

## 更新时间

- `2026-08-24T17:40:58+08:00`
