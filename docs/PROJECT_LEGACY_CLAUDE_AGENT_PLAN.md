# PROJECT_LEGACY_CLAUDE_AGENT_PLAN

## 背景与目标

本文是 `Phase 7 / 子批次 E：项目内 legacy Claude agent 入口治理方案` 的正式方案文档。

目标：
- 冻结项目 `.claude/agents/` 目录中 legacy Claude agent 入口的逐文件去留判断
- 明确项目专属 wrapper、跳转入口与退场候选的边界
- 冻结 legacy 命名与当前新 catalog 命名不一致时的处理口径
- 为后续可能的实施批次提供最小执行顺序与验收口径

本批只定方案，不直接修改项目 `.claude/agents/*.md`、不改运行时 `~/.claude/agents/*`、不改 registry、template 或 workflow 内容。

## 当前状态冻结

### 1. 当前 legacy 文件清单

项目当前 `.claude/agents/` 目录中仅有以下 3 个 legacy 文件：
- `C:\projects\pdf_ai\paddle_ocr\.claude\agents\coder_agent.md`
- `C:\projects\pdf_ai\paddle_ocr\.claude\agents\deploy_agent.md`
- `C:\projects\pdf_ai\paddle_ocr\.claude\agents\tester_agent.md`

它们的当前 frontmatter / 名称分别为：
- `coder-agent`
- `linux-devops`
- `tester-agent`

### 2. 当前主线角色源

当前项目 registry / template / workflow 已走新角色体系：
- `planner`
- `doc-curator`
- `test-verifier`
- `backend-implementer`
- `frontend-implementer`
- `ops-runbook`

当前真实 `~/.claude/agents/` 运行时也已经是上述新 catalog，不包含 legacy 三件套。

结论：
- 当前主线角色源已经转向“项目 registry + 全局 Claude agents”
- 当前项目内这 3 个 `.claude/agents/*.md` 更像遗留入口，而不是当前主线角色真源

### 3. 逐文件现状冻结

#### `coder_agent.md`

- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.claude\agents\coder_agent.md`
- 当前名称：`coder-agent`
- 当前职责：
  - 历史项目 coder 入口
  - 仍承载旧“测试先行编码”风格的角色描述
- 与当前项目 registry 的脱节点：
  - 当前 registry 中没有 `coder-agent`
  - 当前实现角色已拆分为 `backend-implementer`、`frontend-implementer`、`test-verifier` 等新角色
- 与真实全局 runtime agent catalog 的关系：
  - `~/.claude/agents/` 当前无该 legacy 角色
  - 因此它不是当前全局 runtime catalog 的有效同步对象

#### `deploy_agent.md`

- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.claude\agents\deploy_agent.md`
- 当前名称：`linux-devops`
- 当前职责：
  - 历史项目 deploy / devops 入口
  - 仍承载旧服务器、Bash 运维类职责
- 与当前项目 registry 的脱节点：
  - 当前 registry 中没有 `linux-devops`
  - 运维角色已转向 `ops-runbook`
- 与真实全局 runtime agent catalog 的关系：
  - `~/.claude/agents/` 当前无该 legacy 角色
  - 它不是当前全局 runtime catalog 的现行角色定义

#### `tester_agent.md`

- 当前路径：`C:\projects\pdf_ai\paddle_ocr\.claude\agents\tester_agent.md`
- 当前名称：`tester-agent`
- 当前职责：
  - 历史项目 tester 入口
  - 仍承载旧 unittest 写作职责
- 与当前项目 registry 的脱节点：
  - 当前 registry 中没有 `tester-agent`
  - 测试相关职责已转向 `test-verifier`
- 与真实全局 runtime agent catalog 的关系：
  - `~/.claude/agents/` 当前无该 legacy 角色
  - 它不是当前全局 runtime catalog 的现行角色定义

## 目标状态冻结

### 1. 项目 `.claude/agents/` 目录的正式边界

未来项目 `.claude/agents/` 目录只允许保留以下类型的文件：
- 项目专属角色
  - 只有当角色职责无法由全局通用 agent catalog 表达，且明显绑定项目私有路径、服务器、流程或合规边界时，才允许存在
- 项目覆盖角色
  - 仅当需要对全局角色增加非常小的项目增量约束，且无法仅靠 registry / docs 表达时，才允许存在
- 临时 deprecation wrapper / 跳转入口
  - 仅用于实施期过渡
  - 必须有明确退场目标

未来不允许继续保留的内容：
- 与全局通用 agent 重复定义的旧角色正文
- 与当前 registry / workflow 已脱节的历史角色
- 仅因历史命名惯性保留、但已不再被 registry / runtime 使用的重复入口

### 2. legacy 命名与新 catalog 命名不一致的冻结口径

- `coder-agent` 不再作为现行命名保留
  - 对应的新角色语义已拆分到 `backend-implementer`、`frontend-implementer`、`test-verifier`
- `linux-devops` 不再作为现行命名保留
  - 对应的新角色语义已收敛到 `ops-runbook`
- `tester-agent` 不再作为现行命名保留
  - 对应的新角色语义已收敛到 `test-verifier`

结论：
- legacy 名称不能继续与新 catalog 并列作为现行角色源
- 若确需过渡，只能作为短期 deprecation wrapper / 跳转入口存在，并明确指向新角色体系

### 3. 逐文件未来目标状态

#### `coder_agent.md`

- 未来目标状态：`退场/删除候选`
- 原因：
  - 当前职责已被新 catalog 拆分吸收
  - 既不在项目 registry 中，也不在真实 runtime catalog 中
  - 继续保留原样正文只会制造“旧角色仍有效”的误导
- 可接受的过渡形态：
  - 若实施期需要，可短期降级为 deprecation wrapper / 跳转入口
  - 但目标仍应是退场，而不是长期保留

#### `deploy_agent.md`

- 未来目标状态：`降级为项目增量包装或跳转入口`
- 原因：
  - 它与新 catalog 中的 `ops-runbook` 存在最接近的职责映射
  - 同时又最可能携带项目专属服务器、运维约束与运行口径
- 冻结判断：
  - 若正文中仍存在不可由 registry / docs 替代的项目专属运维约束，可收缩为项目专属 wrapper
  - 若无这类不可替代增量，则应降级为跳转入口并最终退场

#### `tester_agent.md`

- 未来目标状态：`退场/删除候选`
- 原因：
  - 其测试职责已由 `test-verifier` 承接
  - 当前不在 registry，也不在真实 runtime catalog
  - 继续保留原样正文会与新测试角色体系重复
- 可接受的过渡形态：
  - 若实施期需要，可短期降级为 deprecation wrapper / 跳转入口
  - 但不应作为长期项目专属 wrapper 保留

## 后续实施的最小顺序

本批只冻结方案。若后续进入实施，建议顺序如下。

### 顺序 1：先处理最明确的退场候选

- 先处理：
  - `coder_agent.md`
  - `tester_agent.md`
- 原因：
  - 这两个对象与新 catalog 的重复和脱节最明确
  - 最适合作为第一批 deprecation / 跳转治理对象
- 允许的动作顺序：
  - 先改为短期 deprecation wrapper / 跳转入口
  - 确认无入口再依赖后，才允许进入删除候选

### 顺序 2：再处理可能保留项目增量的运维入口

- 再处理：
  - `deploy_agent.md`
- 原因：
  - 该文件最可能仍含项目专属服务器、流程、远程运维约束
  - 需要先判断这些约束是否只能留在 `.claude/agents/` wrapper 中

### 顺序 3：同步 docs / registry 的引用说明

- 在真正实施时，应同步检查：
  - 项目文档是否仍把 legacy agent 名称当作现行入口
  - registry / workflow 是否需要补充“已切换到新 catalog”的说明
- 本顺序只允许补说明，不要求当前批次直接改 registry JSON

### 何时允许删除 legacy 文件

- 只有同时满足以下条件，才允许删除对应 legacy 文件：
  - 已确认项目入口、registry、workflow、当前操作手册不再依赖该 legacy 名称
  - 如曾短期保留 deprecation wrapper，已完成过渡期说明
  - 已确认真实 runtime catalog 无需兼容该旧文件

### 是否需要临时 deprecation wrapper / 跳转入口

- `coder_agent.md` 与 `tester_agent.md`
  - 如担心仍有人工习惯入口，可短期保留为 deprecation wrapper / 跳转入口
- `deploy_agent.md`
  - 若存在不可替代的项目专属运维增量，应优先收缩为项目专属 wrapper
  - 若不存在，则同样先降级为跳转入口，再评估退场

## 本批明确不做的事

- 不直接删 `C:\projects\pdf_ai\paddle_ocr\.claude\agents\*.md`
- 不修改 `~/.claude/agents/*`
- 不修改 registry JSON 内容
- 不新增真实 agent 文件
- 不清理 runtime

## 验收口径

### 1. 逐文件目标状态清单

- 必须逐文件给出未来目标状态
- 不能只给目录级结论

### 2. 项目专属 wrapper 与全局通用 agent 的边界

- 必须明确什么情况下允许保留项目专属 wrapper
- 必须明确什么情况下应判定为与全局通用 agent 重复定义而进入退场候选

### 3. 命名/目录规范口径

- 必须明确 legacy 名称不能继续与新 catalog 并列作为现行角色源
- 必须明确项目 `.claude/agents/` 目录未来允许和不允许保留的文件类型

### 4. 安全边界

- 必须明确本批不改 runtime
- 必须明确本批不直接删除 legacy 文件
- 必须明确本批不新增真实 agent 文件

## 后续路线建议

- Phase 7 的 A/B/C/D/E 方案冻结在本批完成后即全部闭合
- 下一步不建议立刻再开新的 Phase 7 子批次
- 建议进入“实施批次评估/排序”：
  - 先评估哪些子批次需要先落实施
  - 再决定是否把 `.claude/agents/*.md` 的 deprecation / wrapper 调整纳入优先执行序列

## 当前结论

- `Phase 7 / 子批次 E` 的项目内 legacy Claude agent 入口治理方案已冻结
- 当前已明确：
  - 项目 `.claude/agents/` 目录只有 `coder_agent.md`、`deploy_agent.md`、`tester_agent.md` 这 3 个 legacy 文件
  - 当前主线角色源已转向“项目 registry + 全局 Claude agents”
  - 真实 `~/.claude/agents/` runtime catalog 已是新角色体系，不包含 legacy 三件套
  - `coder_agent.md`、`tester_agent.md` 当前更适合定义为退场/删除候选
  - `deploy_agent.md` 当前更适合优先评估是否收缩为项目专属 wrapper 或跳转入口
- Phase 7 可在本批后视为“方案冻结完成”，下一步进入实施批次评估/排序
