# AGENTS

本文件是全局 Claude agents 真源设计说明。

## 目标

建立一套面向所有本机项目复用的 Claude agents 真源目录，满足以下约束：

- 长期真源只维护在 `ai-harness/agents/`
- 运行时识别目录仍是 `~/.claude/agents/`
- 项目专属 agent 继续留在各项目自己的 `.claude/agents/`
- Phase 3 只定义目录规范与首批 agent 文件，不做同步、安装、hook、doctor、运行时接线
- 全局协作治理规则另行收口到 `docs/SUBAGENT_GOVERNANCE.md`，本文件不重复承载主协调器 / 审查 / 测试规则正文

## 角色委派入口

- 委派入口为“角色优先”：先选角色，再查 `agents/codex-role-map.json`，再生成合同并派发执行。
- `reader` / `reviewer` 已启用，与执行型角色并列可用。
- 协作治理、回收口径与质量门禁统一引用 `docs/SUBAGENT_GOVERNANCE.md`，本文件仅保留目录与角色真源说明。

## 目录边界

### 全局真源层

- 路径：`ai-harness/agents/`
- 职责：保存跨项目可复用的 Claude agent 定义
- 要求：一个 agent 一个 Markdown 文件，文件本身已经是未来可直接投放到 `~/.claude/agents/` 的格式

### 运行时投放层

- 路径：`~/.claude/agents/`
- 职责：接收未来同步脚本投放后的 agent 文件
- 说明：本 phase 不直接写入该目录

### 项目适配层

- 路径：`<project>/.claude/agents/`
- 职责：保留项目专属角色、项目覆盖版角色、项目私有路径约束
- 示例：绑定具体仓库目录、服务器、部署服务名、模块名、团队流程的 agent 只能放这里

## 目录规范

`agents/` 当前采用平铺目录，避免过早引入子目录扫描或分层装配：

```text
agents/
  README.md
  _schema.example.md
  planner.md
  doc-curator.md
  test-verifier.md
  backend-implementer.md
  frontend-implementer.md
  ops-runbook.md
```

规则：

- 文件名使用小写英文加短横线
- 一个文件只描述一个角色
- 文件名应尽量和角色标识一致，避免目录名和 frontmatter `name` 漂移
- 首批先保持平铺；是否拆子目录，留到后续 agent 数量显著增长时再评估

## 文件规范

为兼容未来投放到 `~/.claude/agents/`，首批 agent 文件采用“最小 frontmatter + 结构化正文”：

### 必填 frontmatter

- `name`
- `description`
- `tools`

### 可选 frontmatter

- `model`

说明：

- 现阶段不把自定义控制字段塞进 frontmatter，避免未来运行时识别出现不必要兼容风险
- 路径范围、输入、输出、停止条件等约束统一写在正文固定小节中

### 正文最小结构

每个 agent 正文至少包含：

1. `角色目标`
2. `负责范围`
3. `不负责`
4. `输入`
5. `输出`
6. `工作规则`
7. `停止条件`
8. `协作交接`

## 首批角色策略

首批 agent 以“先覆盖当前 registry 的核心角色口径”为原则，优先对应当前项目中已存在的角色注册表：

- `planner`
- `reader`
- `reviewer`
- `doc-curator`
- `test-verifier`
- `backend-implementer`
- `frontend-implementer`
- `ops-runbook`

说明：

- 这不是项目专属注册表的镜像，而是借它先冻结一组当前已验证过的通用角色口径
- 旧项目样例中的 `coder_agent`、`tester_agent`、`deploy_agent` 只作为提炼素材，不原样搬运
- `reader` / `reviewer` 已纳入首批口径，后续角色仍按 phase 渐进引入

## 全局与项目的拆分规则

必须放全局真源层的内容：

- 可跨项目复用的角色职责
- 与具体业务仓库无关的协作方式
- 通用的输入输出契约表述
- 通用的停止条件与交接规则

必须留在项目适配层的内容：

- 具体仓库路径
- 具体模块名、服务名、环境名
- 具体服务器地址、SSH 别名、systemd 单元名
- 项目私有流程顺序、项目私有验收条件、项目私有术语
- 仅对单仓库成立的写入路径约束

## Phase 3 边界

本 phase 明确不做：

- 不实现 `agents/` 到 `~/.claude/agents/` 的同步脚本
- 不修改 `~/.claude/settings.json`
- 不修改项目 `.claude/settings.local.json`
- 不改造 `start_session.ps1`、`doctor-core.ps1`、`repo_doctor.ps1`
- 不引入 hooks 对 agent 的自动接线
- 不处理全局与项目层的 merge / override / 优先级策略

## 验收口径

Phase 3 通过的标准是：

- `ai-harness/agents/` 已有明确 catalog 规范
- 首批 agent 文件可独立阅读，且未来可直接投放
- 内容不硬编码当前项目私有信息
- 目录边界、项目边界、非目标边界都已写清楚

只要还需要依赖运行时目录来证明可用，就不算 Phase 3 完成。
