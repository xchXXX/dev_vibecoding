# 任务摘要

## 基本信息

- `task_id`: `20260831-144630-wsl-first-legacy-preserved-16fc6f`
- `title`: WSL优先，旧脚本保留
- `status`: `active`
- `owner`: `main-coordinator`

## 目标

- WSL优先、旧脚本保留，完成最小规则适配、验证及独立审查；不搬仓库、不迁移记忆

## 范围

### Scope In

- skills/global-task-orchestrator/scripts/orchestrator_ctl.ps1
- skills/global-task-orchestrator/SKILL.md
- skills/global-task-orchestrator/references/state-schema.md
- tests/harness/control-plane.integration.ps1
- tests/harness/README.md
- templates/codex/AGENTS.global.md
- rules/items/policy/脚本运行基线.md
- rules/items/policy/命令构造约束.md
- rules/items/policy/命令失败闭环.md
- docs/CODEX_COMPAT.md
- tests/harness/wsl-boundary.integration.ps1
- rules/registry/RULES_INDEX.json
- rules/registry/RULES_RESOLVED.json
- docs/tasks/20260831-144630-wsl-first-legacy-preserved-16fc6f
- docs/ai/tasks/20260831-144630-wsl-first-legacy-preserved-16fc6f

### Scope Out

- 不重写旧脚本/搬仓库/改业务项目
- 不迁移记忆或全量复制.codex
- 不改Docker/代理/安全配置

## 验收标准

- 设置保持desktop.runCodexInWindowsSubsystemForLinux=false（智能体Windows原生）和desktop.integratedTerminalShell=wsl；明确后者只控制集成终端，不宣称智能体自动进入WSL
- 全局已部署规则要求：Windows智能体在工具和项目支持时显式使用wsl.exe -d Ubuntu-24.04执行Linux原生文件操作、Git、Python、Node、测试和构建；旧.ps1/.cmd明确保留Windows后端
- Ubuntu-24.04普通用户uid1000、Linux原生Git/Python/rg/Node/npm、中文空格参数、cwd/UTF8/退出码及Windows旧入口的混合路线验证通过
- 不搬仓库、不复制或迁移.codex/记忆、不混用Linux/Windows依赖、不改网络/Docker；各项目不支持WSL的命令保留原平台
- Hook仅是独立命令安全门禁，不负责Windows/WSL路由；其信任和真实deny状态作为独立遗留风险记录，不阻塞WSL优先混合方案的完成

## 停止条件

- 需用户密码或应用重启
- 未经授权的控制器或系统扩围
- 未知dirty改动冲突

## 关键决定

- 用户已批准WSL优先及Ubuntu安装、初始化最小修复
- 此前恢复派发见保留原事件归档，不伪造正式brief
- overlap裁决接口缺口另请用户授权，尚不实施

## 当前阶段

- `current_phase`: `review`

## 子任务

### GTO-ACCEPT

- `title`: 初始化修复真实恢复验收与必要返工
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 核对已独立审查的恢复增量和实际同任务初始化证据，处理限定范围findings

### ADAPT-001

- `title`: WSL优先规则及长期调用说明
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 在保留旧脚本的条件下同步WSL优先规则、路径和Windows后端调用说明

### VERIFY-001

- `title`: Linux与Windows旧入口边界验收
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 用最小可复用验收覆盖真实WSL工具、中文空格路径、旧脚本和故障记忆Windows后端
- `dependencies`: `ADAPT-001`, `GTO-ACCEPT`

### REVIEW-001

- `title`: 最终独立增量审查
- `role`: `reviewer`
- `status`: `blocked`
- `goal`: 审查本次完整变更及真实验收证据，区分可完成实施与用户端未闭合门禁
- `dependencies`: `GTO-ACCEPT`, `ADAPT-001`, `ADAPT-FIX-001`, `VERIFY-001`

### ADAPT-FIX-001

- `title`: 修正文档F001并交回原reviewer
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 仅修F001，准确保留简单launcher后端选择和复杂参数Windows Python前提
- `dependencies`: `ADAPT-001`

### GTO-OVERLAP-001

- `title`: 最小dirty overlap正式裁决接口
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 在用户明确授权的前置恢复批次内补上窄裁决接口，保留既有安全边界和未提交内容
- `dependencies`: `GTO-ACCEPT`

### DEPLOY-001

- `title`: 生成规则索引和最小托管AGENTS部署
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 正式overlap裁决解除门禁后，仅通过已有生成脚本刷新三份索引，通过bootstrap刷新Windows托管AGENTS及receipt
- `dependencies`: `GTO-OVERLAP-001`

### HOOK-READ-001

- `title`: 核对WSL Hook入口的最小兼容边界
- `role`: `reader`
- `status`: `completed`
- `goal`: 只读判断切换WSL后既有Hook安装入口需何种最小适配，区分可提前准备和实际home/信任后才能执行

### HOOK-ADAPT-001

- `title`: 最小Hook WSL可选入口与隔离验证
- `role`: `backend-implementer`
- `status`: `completed`
- `goal`: 保留旧Windows安装行为，增加显式可选WSL命令生成参数，完成隔离测试；不安装到真实CodexHome
- `dependencies`: `GTO-OVERLAP-001`, `HOOK-READ-001`

### RESTART-DOC-001

- `title`: 重启后环境诊断与文档续接
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 仅同步本次重启的只读验收证据及最小用户操作，不修改源码或配置

### RESTART-REVIEW-001

- `title`: 重启诊断与续接记录独立审查
- `role`: `reviewer`
- `status`: `blocked`
- `goal`: 独立核对本轮重启诊断、文档准确性和用户步骤；不是整任务final/pass
- `dependencies`: `RESTART-DOC-001`

### MIXED-DOC-001

- `title`: 混合模式合同和回退证据同步
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 更新三文档顶部合同为Windows联网代理+显式WSL优先；保留Hook实际信任门禁和历史，不改源码

### MIXED-HOOK-READ-001

- `title`: Windows活动Hook真实门禁读取及验证设计
- `role`: `reader`
- `status`: `completed`
- `goal`: 只读核对Windows活动home、Hook启动条件、信任和无害真实验证设计，不直接启动新运行时

### MIXED-VERIFY-001

- `title`: 混合模式开发命令与旧入口验收
- `role`: `test-verifier`
- `status`: `completed`
- `goal`: 仅复跑既有套件，不改源码；write_paths仅声明原测试归属，结果记planned_files_not_changed。确认Ubuntu uid1000原生工具与Windows旧脚本
- `dependencies`: `MIXED-DOC-001`

### MIXED-RUNTIME-001

- `title`: Windows当前配置安全Hook真实生命周期验收
- `role`: `test-verifier`
- `status`: `blocked`
- `goal`: 仅执行一次普通认证现有Windows配置的ephemeral JSON运行，不改源码；write_paths是测试归属，记planned_files_not_changed。核对Hook真实allow/deny及可能用户信任阻塞
- `dependencies`: `MIXED-DOC-001`, `MIXED-HOOK-READ-001`, `MIXED-VERIFY-001`

### MIXED-CLOSE-DOC-001

- `title`: 混合模式实测结果及最终边界回填
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 仅在现有execution/acceptance当前段补本轮主路线和真实Hook运行结果，保留历史，不建立新报告；等root提供runtime终态后编辑
- `dependencies`: `MIXED-VERIFY-001`

### MIXED-SCOPE-CORRECTION-001

- `title`: 纠正Windows原生与WSL显式路由验收口径
- `role`: `doc-curator`
- `status`: `completed`
- `goal`: 按用户截图和纠正意见更新三文档当前段：Windows原生是代理后端，WSL设置只控制集成终端；最终效果来自全局规则要求显式wsl.exe路由，Hook与路由解耦。保留全部历史正文

### MIXED-SCOPE-REVIEW-001

- `title`: 独立复核WSL显式路由与Hook解耦
- `role`: `reviewer`
- `status`: `completed`
- `goal`: 独立复核最终口径与已实现证据：Windows原生代理显式调用WSL、旧脚本Windows；Hook安全门禁独立，不作为路由完成条件
- `dependencies`: `MIXED-SCOPE-CORRECTION-001`

## 更新时间

- `09/01/2026 10:35:43`
