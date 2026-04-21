# PROJECT_HISTORY_LEGACY_REFERENCE_PLAN

## 背景与目标

本文是 `Phase 7 / 子批次 D：历史 run / legacy 引用治理方案` 的正式方案文档。

目标：
- 冻结历史 run 文档与现行入口之间的 legacy 引用治理边界
- 区分“允许保留的历史事实”与“后续禁止继续新增的现行 legacy 引用”
- 明确 `docs/ai/runs/` 与 `.ai/session/` 的不同治理口径
- 为后续可能的实施或检测批次提供最小顺序与验收口径

本批只定方案，不直接修改历史文档、代码、runtime 或任何 run/session 目录内容。

## 当前状态冻结

### 1. 当前 legacy 引用分布

- 旧绝对路径 / 旧 runtime 引用当前主要集中在 `C:\projects\pdf_ai\paddle_ocr\docs\ai\runs\`
- 当前盘点量约 `88` 条
- `.ai/session` 也存在这类 legacy 引用
  - 按当前同口径窄匹配盘点，约 `28` 条
  - 明显少于 `docs/ai/runs/`，但不是 `0`
- 已核实的 `.ai/session` 命中样例至少包括：
  - `C:\projects\pdf_ai\paddle_ocr\.ai\session\ai-harness-batch1-phase0-20260330-001\findings.md`
  - `C:\projects\pdf_ai\paddle_ocr\.ai\session\ai-harness-batch1-phase0-20260330-001\progress.md`
  - `C:\projects\pdf_ai\paddle_ocr\.ai\session\ai-harness-phase0-freeze-20260330-150836-m85l\findings.md`
  - `C:\projects\pdf_ai\paddle_ocr\.ai\session\global-task-orchestrator-v2-20260327-171554\findings.md`

### 2. 当前主要 legacy 引用类型

当前已知主要类型至少包括：
- 旧绝对路径引用
  - 例如 `C:/Users/72385/dev/ai-harness/*`
- 旧 runtime 路径引用
  - 例如 `C:\Users\72385\.codex\.ai-harness\...`
- 历史 runtime skill 直接引用
  - 例如 `C:/Users/72385/.codex/skills/global-task-orchestrator/*`
  - 例如 `~/.codex/skills/global-task-orchestrator`
- 历史 settings 路径引用
  - 例如 `~/.claude/settings.json`

### 3. 为什么这些内容当前属于历史留痕

- 这些命中当前主要位于 `docs/ai/runs/`，其角色是历史 run 留痕与验收记录
- `.ai/session` 中的相关命中则主要来自早期 planning / findings / progress 留痕，它们记录的是当时会话过程中的真实上下文
- 它们反映的是当时真实发生过的运行时路径、工具落点与配置口径
- 因而当前应先被视为“历史事实记录”，而不是“现行入口规范”
- 与之相对，现行入口对象应以项目入口文档、计划文档、registry、模板和 work order 为准，而不是以旧 run 文档或旧 session 留痕为准

### 4. 当前不存在的对象与边界

- 当前扫描未发现项目内新的 `SKILL.md` 镜像副本
- 因此当前 legacy skill 问题的重点不是“项目内新增镜像文件”
- 当前重点是“历史 run 文档和早期 session 留痕中的旧 runtime 直接引用”
- 这一定义不自动扩展到 `.system/*`、plugins 或第三方 runtime skill takeover

## 目标状态冻结

### 1. 允许保留的历史事实

以下内容允许继续保留在历史 run 文档和既有 session 留痕中：
- 当时真实存在的绝对路径引用
- 当时真实运行过的 runtime 路径
- 当时真实使用过的 skill / settings 位置
- 为了复盘、验收、回溯而保留的旧路径事实

前提是：
- 这些内容仅作为历史事实保留
- 不被重新解释为当前现行入口
- 不被复制到新的模板、计划、入口或 registry 中

### 2. 后续禁止新增的现行 legacy 引用

以下内容不应继续进入新的现行对象：
- 新的 run 模板中继续硬编码旧绝对路径
- 新的项目入口文档中继续把旧 runtime 路径当作现行入口
- 新的 plan / work_order / dispatch_packet 中继续把历史 runtime skill 直接路径写成推荐入口
- 新的 registry / 模板 / 标准文档中继续写入旧 settings 路径或旧 runtime 路径
- 新的 session / progress / findings 留痕继续把 legacy 路径写成当前默认入口

### 3. 引用出现范围的冻结口径

#### 可以继续留在历史 run 文档中的引用

- 旧绝对路径
- 旧 runtime 路径
- 历史 runtime skill 直接引用
- 历史 settings 路径引用

条件：
- 仅限已有历史 run 文档中的事实留痕
- 不以“当前推荐入口”或“当前标准路径”的口吻继续扩写

#### 可以继续留在既有 `.ai/session` 历史留痕中的引用

- 早期 planning / findings / progress / task_plan 中已经写入的旧绝对路径和旧 runtime 路径
- 作为当时工作上下文记录的一部分继续保留

条件：
- 仅限既有 session 历史记录
- 不追改旧内容
- 不再把这类路径用于新的 session 入口口径

#### 只允许出现在方案/验收说明中的引用

- 为解释迁移历史、治理边界、验收结果而引用的旧路径
- 为说明“为何该对象属于历史事实而非现行入口”而引用的旧 runtime 落点

条件：
- 只能作为说明材料出现
- 必须同时写清“这不是当前现行入口”

#### 不应再进入新的 run / 模板 / 入口文档的引用

- 把 `C:/Users/72385/dev/ai-harness/*` 这类旧绝对路径作为新模板默认值
- 把 `~/.claude/settings.json`、`~/.codex/skills/global-task-orchestrator` 等旧运行时路径作为新入口正文
- 把历史 runtime 目录写成新的项目标准操作口径

### 4. `docs/ai/runs/` 与 `.ai/session/` 的差异化治理口径

#### `docs/ai/runs/`

- 定位：历史 run 留痕与验收文档
- 口径：允许保留历史事实
- 治理重点：
  - 不批量改写旧正文
  - 只冻结“后续不再新增同类 legacy 引用”的规则

#### `.ai/session/`

- 定位：当前与近期会话级 planning / progress / work_order 留痕
- 已知现状：
  - 当前同样存在 legacy 引用
  - 按当前同口径窄匹配盘点，约 `28` 条
  - 典型命中来自早期 `findings.md`、`progress.md`、`task_plan.md`
- 口径：
  - 允许保留既有历史会话事实，不做批量追改
  - 但由于 `.ai/session` 更接近当前与近期执行面，后续应优先作为“禁止新增 legacy 引用”的约束对象
  - 其治理重点不是否认既有命中，而是阻止新的 session / plan / progress 继续把 legacy 路径写成现行入口

### 5. 三类对象的处理边界

#### 历史 run 文档

- 以保留历史事实为先
- 不做批量重写
- 不把历史路径清洗当成当前批次目标

#### 当前项目入口

- 不得把历史 run 或旧 session 留痕中的路径反向上升为现行入口
- 当前项目入口的收口，应以前面已冻结的子批次 B/C 文档为准

#### 未来模板 / registry / plan / work_order

- 从本批开始冻结为“不得继续新增 legacy 引用”
- 如确需引用历史路径，只能作为背景说明，不得作为默认入口

## 后续实施的最小顺序

本批只冻结方案。若后续进入实施，建议顺序如下。

### 顺序 1：先做新增口径收敛

- 先在模板、plan、work_order、入口文档约束中明确：
  - 历史事实允许保留
  - 现行新增 legacy 引用禁止继续出现
- 目标：
  - 先止增，不先追改存量

### 顺序 2：再补面向新增内容的约束

- 对新的 run 文档模板、session 留痕模板或实施规范补充约束
- 明确：
  - 何种引用只能出现在验收说明
  - 何种引用完全不得再进入现行入口或模板

### 顺序 3：最后再考虑是否新增检测/审计批次

- 如后续需要，可单独新增“历史/现行 legacy 引用检测批次”或等价审计批次
- 该批次仅负责发现新增漂移，不负责批量改写历史文档

## 本批明确不做的事

- 不批量改写 `docs/ai/runs/*` 历史正文
- 不修改 `.ai/session/*` 历史内容
- 不删除任何 run/session 目录
- 不清理 runtime
- 不实现 doctor/checker
- 不扩展到 `.system/*`、plugins、第三方 runtime skill takeover
- 不处理 `.claude/agents/*.md`

## 验收口径

### 1. 历史事实 vs 现行新增禁止项

- 必须明确哪些 legacy 引用可以继续作为历史事实保留
- 必须明确哪些 legacy 引用从现在起不得再进入新的现行对象

### 2. `docs/ai/runs/` 与 `.ai/session/` 差异化口径

- 必须明确 `docs/ai/runs/` 允许保留历史事实
- 必须明确 `.ai/session` 也存在既有历史命中，但后续重点是更严格地禁止新增，而不是批量追改存量
- 必须明确二者差异不在于“有没有命中”，而在于“历史验收留痕”和“近期执行留痕”的角色不同

### 3. legacy skill 镜像当前状态

- 必须明确当前未发现新增 `SKILL.md` 镜像副本
- 必须明确当前重点是历史 run 文档和早期 session 留痕中的旧 runtime 直接引用，而不是项目内 skill 镜像清理

### 4. 安全边界

- 必须明确不批量重写历史 run 文档
- 必须明确不删除历史目录
- 必须明确不清理 runtime、不开启 takeover、不实现 checker

## 后续批次建议

- 当前不新增新的 Phase 7 正式子批次
- 子批次 D 冻结完成后，下一步按既有路线进入子批次 E：项目内 legacy Claude agent 入口治理方案
- 如未来确需自动检测新增 legacy 引用，建议作为“子批次 D 的实施/审计批次”单独推进，不改写当前 D/E 语义

## 当前结论

- `Phase 7 / 子批次 D` 的历史 run / legacy 引用治理方案已冻结
- 当前已明确：
  - legacy 引用主要集中在 `docs/ai/runs/`，约 `88` 条
  - `.ai/session` 同样存在既有 legacy 引用，按当前同口径窄匹配盘点约 `28` 条
  - 当前未发现新增 `SKILL.md` 镜像副本
  - 历史事实允许保留，现行新增 legacy 引用应禁止继续出现
  - `docs/ai/runs/` 与 `.ai/session/` 的差异不在于是否命中，而在于“历史验收留痕”与“近期执行留痕”的治理优先级不同
- 下一步可进入子批次 E，继续冻结项目内 legacy Claude agent 入口治理方案
