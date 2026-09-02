# 任务摘要

## 基本信息

- `task_id`: `20260826-185451-portable-harness-bootstrap-8c51e6`
- `title`: 跨机器 Harness 动态路径与 Bootstrap
- `status`: `completed`
- `owner`: `main-coordinator`

## 目标

- 让仓库正式文档和规则保持机器无关，并由本机 bootstrap 动态生成全局 Codex 入口、选择唯一 harness 根、刷新本机生成物并通过 doctor 防止旧绝对路径回归。

## 范围

### Scope In

- 在当前 harness 仓库增加跨机器 bootstrap 与统一路径解析入口
- 以模板生成本机 CODEX_HOME/AGENTS.md，并安全处理已有未托管文件
- 定义 -HarnessRoot、AI_HARNESS_ROOT、脚本所在仓库的确定性选择顺序，不扫描磁盘猜测 clone
- 让受版本控制的活动态文档、模板和 rules registry 生成物不持久化用户名、盘符或机器绝对根
- 扩展 doctor、sync、rules 与 Windows 合同测试，覆盖迁移、重复执行、旧路径回归和多 clone 显式选择
- 在本机以当前仓库为选定根运行 bootstrap，修复 C:/Users/Laptop/.codex/AGENTS.md 中的旧用户路径

### Scope Out

- 不扫描整机寻找所有同远程 clone，也不自动判断哪个 clone 更权威
- 不覆盖或同步 D:/prj/dev_vibecoding 的未提交改动
- 不提交、推送、合并或 cherry-pick 两个 clone 的分支
- 不机械替换 docs/ai/runs、旧任务、benchmark、sandbox 等冻结历史证据中的绝对路径
- 不重写业务规则正文或扩展为跨平台安装框架
- 不读取或输出 auth.json、token、密钥和其他认证信息

## 验收标准

- 在任意测试目录复制 harness 后，bootstrap 能从显式 -HarnessRoot、AI_HARNESS_ROOT 或自身脚本根解析唯一 harness 根，优先级确定且无磁盘扫描
- CODEX_HOME 优先、USERPROFILE/.codex 回退；bootstrap 能生成带 managed marker 的简洁全局 AGENTS，并对未托管非空文件默认拒绝覆盖
- 显式授权覆盖未托管全局 AGENTS 时先创建可恢复备份，重复运行得到稳定内容且不会累积备份或漂移
- 全局 AGENTS 模板、项目活动态入口和受版本控制 rules registry 生成物不包含 C:/Users/<name>、C:\Users\<name> 或当前盘符绝对根
- doctor 能报告 harness 根选择不一致、managed 全局 AGENTS 漂移、目标根缺少规则入口和旧用户路径残留
- rules 生成与校验继续保持 local/global/resolved 语义和 scope != project 导入边界
- 新增行为测试完成 RED-GREEN 证据；相关集成测试、规则校验、计划文档校验、doc routing、strict doctor 与 git diff --check 全部通过
- 本机 C:/Users/Laptop/.codex/AGENTS.md 最终由当前选定 harness 生成且不再包含 72385

## 停止条件

- 发现目标文件存在无法归属或会被覆盖的用户未提交改动
- 全局 AGENTS 中存在无法安全迁移且用户未授权删除的独有内容
- rules registry 消费方实际依赖绝对 repo_root，无法在不破坏兼容的情况下改为逻辑路径
- 实现需要扫描磁盘、自动修改另一个 clone 或扩大到 scope_out
- 验证需要读取认证信息或执行未获授权的外部写入

## 关键决定

- 采用仓库内容机器无关、本机入口由 bootstrap 生成的分层方案；Markdown 本身不承担变量插值。
- harness 根选择顺序固定为显式 -HarnessRoot、非空 AI_HARNESS_ROOT、bootstrap 脚本所在仓库；不使用 sibling 或全盘扫描来选择 clone。
- Codex home 选择顺序固定为显式 -CodexHome、非空 CODEX_HOME、USERPROFILE/.codex。
- 仓库模板使用 managed marker；目标全局 AGENTS 缺失、空或已托管时可写，非空未托管时默认失败，只有显式 -ForceGlobalAgents 才备份后替换。
- codex sync receipt 属于本机状态，允许记录解析后的绝对路径；受版本控制的规则索引改用逻辑根标识，不保存机器绝对路径。
- 同机多 clone 由用户运行 bootstrap 的位置、显式参数或 AI_HARNESS_ROOT 决定；本任务不尝试自动合并两份 clone。
- 历史证据保留原路径；旧路径回归检查只覆盖活动态真源、模板、测试合同和生成物。

## 当前阶段

- `current_phase`: `review`

## 子任务

### READ-PORTABILITY-001

- `title`: 现有路径解析与安装链路只读审计
- `role`: `reader`
- `status`: `completed`
- `goal`: 核对现有脚本可复用的路径解析、全局 AGENTS 投放、rules 索引字段与 doctor 扩展点，为跨机器 bootstrap 规格提供证据。

### DOC-PORTABILITY-002

- `title`: 同步跨机器路径与 bootstrap 核心文档
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 先于代码同步机器无关路径、bootstrap 使用方式、选择优先级和安全覆盖边界。
- `dependencies`: `READ-PORTABILITY-001`

### TEST-BOOTSTRAP-003

- `title`: 冻结 bootstrap 与路径便携性行为测试
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 以真实临时仓库和临时 CODEX_HOME 冻结 bootstrap 选择、安全覆盖、幂等、doctor 与逻辑索引路径行为，并记录预期 RED。
- `dependencies`: `DOC-PORTABILITY-002`

### IMPL-BOOTSTRAP-004

- `title`: 实现共享路径解析、bootstrap、doctor 与逻辑索引路径
- `role`: `ops-runbook`
- `status`: `completed`
- `goal`: 用最小代码让 RED 行为测试转绿，并在本机安全生成全局 AGENTS。
- `dependencies`: `TEST-BOOTSTRAP-003`

### REVIEW-PORTABILITY-005

- `title`: 跨机器 bootstrap 独立复审
- `role`: `reviewer`
- `status`: `completed`
- `goal`: 独立核对设计、TDD、运行时、安全边界、跨机器路径与全局文件迁移，给出通过或不通过结论。
- `dependencies`: `IMPL-BOOTSTRAP-004`

## 更新时间

- `2026-08-26T21:20:40+08:00`
