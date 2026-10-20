# PROJECT_ADAPTER_CLEANUP_PLAN

## 背景与目标

`ai-harness` 已完成：
- Claude agents install/sync/runtime
- Claude hooks / doctor / governance
- Codex 最小闭环、自动化测试与真实 runtime 投放

当前下一步不再是扩大全局运行时能力，而是冻结“项目适配与遗留清理”方案，明确：
- 当前项目层哪些内容继续保留
- 哪些对象应改成引用全局真源
- 哪些对象后续要移除、降级或本地化
- 哪些历史漂移项只记账，不在本批直接清理

本批只冻结方案与验收口径，不直接修改项目代码、项目配置、运行时目录或历史 run 文档。

## 当前项目层保留项

当前项目层仍应继续保留：
- `AGENTS.md`
- `docs/ai/`
- `docs/ai/runs/`
- `.ai/session/`
- `config/ai/`
- 项目专属 `.claude/`
- 项目专属 `.codex/`（若后续出现项目专属增量配置）
- 业务文档、部署文档、业务模块代码与项目专属脚本

这些对象仍属于“项目适配层”，不应被简单删除或并入全局真源。

## 当前遗留漂移项

截至当前扫描，已识别的主要遗留漂移项包括：

1. `C:\projects\pdf_ai\paddle_ocr\.claude\settings.local.json`
- 当前仍为项目本地控制面文件。
- 已知存在大量历史 `permissions.allow` 记录，且显著偏向旧项目执行上下文。
- 当前尚未冻结“保留字段 / 迁移字段 / 废弃字段”口径。

2. 项目内 `docs/ai/runs/*` 的旧绝对路径引用
- 已确认存在多处指向旧 runtime 或工作区外路径的历史引用，例如：
  - `C:/Users/72385/.codex/skills/global-task-orchestrator/*`
  - `C:/Users/72385/dev/ai-harness/*`
- 这些引用属于历史留痕的一部分，不能在本批直接清理或重写。

3. 项目侧 `config/ai/*` 与全局真源的重叠对象
- 按文件名与职责口径，以下对象与全局真源存在明显重叠风险：
  - `config/ai/schemas/*.json`
  - `config/ai/templates/*.example.*`
- 同时，以下对象仍明显承担项目适配职责：
  - `config/ai/registry/agents.json`
  - `config/ai/registry/workflows.json`

4. legacy skill 镜像或与全局真源重复的入口
- 当前扫描未发现项目内新的 `SKILL.md` 镜像副本。
- 但历史 run 文档中仍存在对旧 `~/.codex/skills/global-task-orchestrator/*` 的直接引用。
- 这类“项目内重复入口 / skill 镜像 / 旧 runtime 路径依赖”仍需纳入后续审计与分类。

## 分类清单

### 1. 保留

这些对象继续保留在项目层：
- `AGENTS.md`
- `docs/ai/`
- `docs/ai/runs/`
- `.ai/session/`
- `config/ai/registry/agents.json`
- `config/ai/registry/workflows.json`
- 项目专属 `.claude/` 中真正属于项目增量约束的内容

保留原则：
- 只保留项目增量规则、入口、留痕与项目专属执行边界
- 不再把全局通用规则全文复制到项目层

### 2. 替换为全局引用

这些对象优先冻结为“后续替换为全局引用”的候选：
- `config/ai/schemas/*.json`
- `config/ai/templates/*.example.*`
- `docs/ai/` 中若仍存在对全局 governance / review / testing 规则的重复正文
- 项目内任何未来被发现的全局 skill / template / rules 镜像副本

替换原则：
- 项目层优先保留引用、映射和增量说明
- 通用 schema / template / review/test 规范优先回指 `ai-harness` 真源

### 3. 移出共享真源

以下内容若被发现混入全局候选清单，应明确移出共享真源，而不是继续全局化：
- 仅适用于 `pdf_ai/paddle_ocr` 的部署脚本、运维口径、业务目录约束
- 项目专属权限白名单
- 项目专属 workflow 约束

原则：
- 这类内容应明确留在项目层，不纳入 `ai-harness` 共享真源

### 4. 本地化

以下对象默认按“本地化配置”处理，不在本批直接收敛：
- `C:\projects\pdf_ai\paddle_ocr\.claude\settings.local.json`
- 项目本地敏感权限、环境相关执行开关
- 任何与当前项目服务器、目录、部署路径强绑定的本地入口

原则：
- 只先冻结分类与迁移口径
- 不在本批直接改写字段、不直接删除权限、不直接做 merge/override

### 5. 延后处理

以下对象本批只记账，不直接实施：
- `docs/ai/runs/*` 中的旧绝对路径引用
- 历史 return/dispatch/work_order 中的旧 runtime 路径
- 项目内未来若发现的 legacy skill 镜像
- 项目侧与全局真源重复但尚未完成影响评估的入口文件

原则：
- 历史留痕优先保持可追溯
- 先定义“哪些是历史事实、哪些是现行入口”，再决定是否做归档、降级或只读保留

## 重点对象口径

### `C:\projects\pdf_ai\paddle_ocr\.claude\settings.local.json`
- 归类：`本地化`
- 当前处理：只冻结字段审计口径，不直接修改
- 后续目标：拆分为“必须保留的项目本地权限”与“可移出或废弃的历史遗留”

### 项目内 `docs/ai/runs/*` 的旧绝对路径引用
- 归类：`延后处理`
- 当前处理：保留历史事实，不批量替换
- 后续目标：建立“历史留痕允许项 / 现行入口禁止项”二分口径

### 项目侧 `config/ai/*` 与全局真源的重叠对象
- 归类：
  - `config/ai/registry/*` -> `保留`
  - `config/ai/schemas/*` / `config/ai/templates/*` -> `替换为全局引用`
- 当前处理：只冻结清单与验收口径
- 后续目标：做逐文件映射，判断引用替换与项目增量保留边界

### 项目内 legacy skill 镜像或与全局 `ai-harness` 真源重复的入口
- 归类：`延后处理`
- 当前处理：把“未发现新增镜像，但必须持续审计”写入方案
- 后续目标：一旦发现重复入口，按“镜像 / 引用 / 项目增量”三分法处理

## 本批非目标

本批明确不做：
- 不直接修改 `C:\projects\pdf_ai\paddle_ocr\.claude\settings.local.json`
- 不直接删除项目文件
- 不直接清理 `docs/ai/runs/` 历史文档
- 不清理 `.system/*`
- 不清理 plugins
- 不清理 Claude/Codex 运行时目录
- 不扩到业务模块代码
- 不直接实施新的 doctor、sync、cleanup 脚本

## 建议分 phase / 子批次顺序

### 子批次 A：项目适配层资产盘点与映射冻结
- 目标：
  - 逐类盘点项目层 AI 控制面对象
  - 形成“保留 / 替换为全局引用 / 移出共享真源 / 本地化 / 延后处理”映射表
- 验收口径：
  - 关键对象盘点齐全
  - 每类对象都有明确归属与非目标
  - 不直接改文件内容

### 子批次 B：项目入口与全局引用收口方案
- 目标：
  - 明确 `AGENTS.md`、`docs/ai/*`、`config/ai/*` 的引用化目标
  - 基于“保留 / 替换为全局引用 / 移出共享真源 / 本地化 / 延后处理”五类正式分类，冻结入口对象在实施层的未来目标状态
  - 明确哪些对象应仅保留项目增量说明，哪些对象应收敛为全局引用或索引入口
- 验收口径：
  - 形成逐入口替换策略
  - 子批次 B 的目标状态与子批次 A 的五类正式分类存在显式映射，不出现口径漂移
  - 不直接删除项目文件
  - 不把全局通用正文继续复制进项目层

### 子批次 C：`.claude/settings.local.json` 本地化治理方案
- 目标：
  - 冻结字段分类、风险分级、迁移优先级
  - 明确哪些字段必须保留本地化，哪些字段后续可收缩
  - 明确与用户级 `~/.claude/settings.json`、项目共享 `.claude/settings.json` 的职责边界
- 验收口径：
  - 有字段级分类口径
  - 有风险分级或高/中/低风险归档
  - 与官方“个人项目本地配置、不进版本控制”语义一致
  - 有禁止直接改写的安全边界
  - 不直接改动真实配置

### 子批次 D：历史 run / legacy 引用治理方案
- 目标：
  - 区分历史留痕与现行入口
  - 冻结旧绝对路径、旧 runtime 引用、legacy skill 镜像的处理原则
  - 明确 `docs/ai/runs/` 与 `.ai/session/` 的差异化治理口径
- 验收口径：
  - 明确“允许保留的历史事实”与“后续不再新增的现行禁项”
  - 明确 legacy skill 镜像当前状态与边界
  - 不把 `.ai/session` 与 `docs/ai/runs/` 混成同一治理口径
  - 不批量改写旧 run 文档

### 子批次 E：项目内 legacy Claude agent 入口治理方案
- 目标：
  - 专门承接 `.claude/agents/*.md` 这类项目内 legacy Claude agent 入口的去留判断与后续治理策略
  - 区分仍需保留的项目 wrapper、可降级为引用入口的对象与可退场对象
- 验收口径：
  - `.claude/agents/*.md` 的后续去向不再与子批次 D 混用
  - 逐文件目标状态明确，不只给目录级结论
  - 项目专属 wrapper 与全局通用 agent 的边界明确
  - 明确只冻结治理口径，不直接删除项目 agent 文件

## 停止条件与不允许越界的边界

出现以下任一情况时，本批应停止并回到方案层，不继续实施：
- 需要直接修改 `.claude/settings.local.json`
- 需要直接删除项目文件或历史 run 文档
- 需要清理 `.system/*`、plugins、Claude/Codex runtime 目录
- 需要扩到业务模块代码
- 需要在未完成逐项分类前直接做全量替换或清理

本批不允许越界到：
- `.system/*`、plugins、运行时目录清理
- Claude/Codex 运行时 takeover 策略扩展
- 项目业务代码改造
- 广义项目 doctor 或 cleanup 脚本实现

## 当前结论

- “项目适配与遗留清理”已形成正式方案冻结文档。
- 当前只冻结分类、子批次顺序与验收口径。
- 子批次 A 已完成，已形成项目适配层资产盘点与映射冻结文档。
- 子批次 B 的项目入口与全局引用收口方案已冻结，并已与子批次 A 五类正式分类对齐。
- 子批次 C 的 `.claude/settings.local.json` 本地化治理方案已冻结，并已明确当前真实字段、风险分级与本地化边界。
- 子批次 D 的历史 run / legacy 引用治理方案已冻结，并已按真实盘点修正 `.ai/session` 既有命中事实，明确历史事实保留边界、现行新增禁项与 `docs/ai/runs/` / `.ai/session` 的差异化口径。
- 子批次 E 的项目内 legacy Claude agent 入口治理方案已冻结，并已完成 3 个 legacy 文件的逐文件目标状态判断。
- Phase 7 的 A/B/C/D/E 方案冻结已全部完成。
- 下一步进入实施批次评估/排序；是否进入具体实施，仍以前置方案与验收口径冻结为准。
