# PROJECT_ADAPTER_IMPLEMENTATION_SEQUENCE

## 背景与目标

本文是 `Phase 7 实施批次评估/排序` 的正式文档。

输入真源：
- `C:\Users\72385\dev\ai-harness\docs\PROJECT_ENTRY_REFERENCE_PLAN.md`
- `C:\Users\72385\dev\ai-harness\docs\PROJECT_CLAUDE_LOCAL_SETTINGS_PLAN.md`
- `C:\Users\72385\dev\ai-harness\docs\PROJECT_HISTORY_LEGACY_REFERENCE_PLAN.md`
- `C:\Users\72385\dev\ai-harness\docs\PROJECT_LEGACY_CLAUDE_AGENT_PLAN.md`
- `C:\Users\72385\dev\ai-harness\docs\plans\AI_HARNESS_MASTER_PLAN.md`

目标：
- 基于已冻结的 B/C/D/E 方案，给出推荐实施批次分组
- 明确推荐顺序、排序原因与首批最小可执行范围
- 说明哪些批次暂缓，以及为什么不适合作为第一批

本批只做实施评估，不直接改项目文件、配置、runtime 或历史文档。

## 实施批次分组

### 批次 I-1：项目入口轻量收口

- 对应方案：
  - 子批次 B 的顺序 1
- 目标：
  - 先收口最外层项目入口
  - 让现行入口先从“重复正文”收敛为“项目增量 + 全局引用 / 索引”
- 范围：
  - `AGENTS.md`
  - `docs/ai/README.md`
- 前置依赖：
  - 子批次 B 方案已冻结
  - 不依赖 C/D/E 的真实实施
- 风险级别：低
- 类型：
  - 以文档改造为主
  - 不涉及代码
  - 不要求测试代码，但需要文档审查与入口核对

### 批次 I-2：项目文档标准与注册入口收口

- 对应方案：
  - 子批次 B 的顺序 2 与顺序 3
- 目标：
  - 收口项目标准入口与注册入口的重复说明
  - 统一“项目增量说明 vs 全局真源引用”的边界
- 范围：
  - `docs/ai/SUBAGENT_WORKFLOW.md`
  - `docs/ai/SESSION_PLANNING_STANDARD.md`
  - `docs/ai/MODULE_DOC_STANDARD.md`
  - `config/ai/registry/agents.json`
  - `config/ai/registry/workflows.json`
- 前置依赖：
  - I-1 完成后更稳妥
  - 需要先有项目入口口径作为上层约束
- 风险级别：中
- 类型：
  - 文档 + 配置
  - 不涉及业务代码
  - 需要最小回归核对 registry 与入口文档的一致性

### 批次 I-3：`.claude/settings.local.json` 本地化实施

- 对应方案：
  - 子批次 C
- 目标：
  - 纠正“个人本地配置却被版本控制”的状态
  - 把历史权限白名单迁回个人自管口径
- 范围：
  - `.claude/settings.local.json`
  - `.gitignore`
  - 如确需实施，再评估是否增加示例文件或文档模板
- 前置依赖：
  - 子批次 C 方案已冻结
  - 最好在 I-1、I-2 后执行，以减少入口口径尚未稳定时对本地配置的误伤
- 风险级别：中到高
- 类型：
  - 配置改造
  - 涉及本地权限与跟踪状态调整
  - 需要明确回滚方案

### 批次 I-4：legacy Claude agent 入口治理实施

- 对应方案：
  - 子批次 E
- 目标：
  - 对 `coder_agent.md`、`deploy_agent.md`、`tester_agent.md` 做 deprecation / wrapper / 退场实施
- 范围：
  - `C:\projects\pdf_ai\paddle_ocr\.claude\agents\coder_agent.md`
  - `C:\projects\pdf_ai\paddle_ocr\.claude\agents\deploy_agent.md`
  - `C:\projects\pdf_ai\paddle_ocr\.claude\agents\tester_agent.md`
  - 必要时补少量项目 docs / registry 说明
- 前置依赖：
  - 子批次 E 方案已冻结
  - 更适合在 I-1、I-2 完成后执行
  - `deploy_agent.md` 若要保留项目专属 wrapper，还依赖项目入口与运维口径先稳定
- 风险级别：中
- 类型：
  - 文档/角色入口改造
  - 不涉及 runtime 目录清理
  - 需要人工审查现有引用是否已完全切走

### 批次 I-5：legacy 引用新增约束与检测

- 对应方案：
  - 子批次 D
- 目标：
  - 先止增，再评估是否增加新增漂移检测
  - 把 legacy 路径限制在“历史事实允许保留”的范围内
- 范围：
  - 新增内容约束
  - 模板 / plan / work_order / session 留痕口径补充
  - 如后续需要，再单独增加检测/审计
- 前置依赖：
  - 子批次 D 方案已冻结
  - 更适合在 I-1、I-2 之后执行，以免在现行入口尚未收口时过早建立检测规则
- 风险级别：中
- 类型：
  - 文档规范为主
  - 可扩展到检测脚本，但不建议在首批实施中引入

## 推荐顺序与原因

### 推荐顺序

1. I-1：项目入口轻量收口
2. I-2：项目文档标准与注册入口收口
3. I-3：`.claude/settings.local.json` 本地化实施
4. I-4：legacy Claude agent 入口治理实施
5. I-5：legacy 引用新增约束与检测

### 排序原因

#### 依赖关系

- I-1 是最上游入口收口，后续 I-2/I-3/I-4/I-5 都受它的现行入口口径影响
- I-2 进一步稳定项目标准与 registry 入口，为 I-4 的 legacy agent 退场判断提供现行角色基线
- I-3 涉及本地配置与跟踪状态调整，应该放在主入口与标准入口稳定之后
- I-4 对 legacy agent 的处理依赖前面入口和角色口径已经稳定，否则容易过早删错或包错
- I-5 最适合作为“在现行入口基本收口后再止增”的批次

#### 回滚难度

- I-1 纯文档、范围小，回滚最容易
- I-2 仍以文档和少量配置说明为主，回滚难度可控
- I-3 涉及 `.gitignore` 与本地配置跟踪状态，回滚成本更高
- I-4 一旦处理 legacy agent 入口，容易影响人工习惯路径，回滚成本高于文档收口
- I-5 如果直接引入检测，误报会影响后续批次推进，因此不适合先做

#### 对当前主线的扰动大小

- I-1 对当前主线扰动最小，却能最快把最外层入口收口
- I-2 有一定扰动，但仍聚焦现行文档/注册入口
- I-3、I-4 都会动“当前仍可能被个人或团队习惯使用”的对象
- I-5 会改变新增内容的约束方式，属于治理面变更，适合后置

#### 是否先做低风险入口收口再动本地配置/legacy 清理

- 结论是“应该”
- 因为当前最需要的是先把现行入口和角色口径收紧，再去处理本地配置和遗留入口
- 否则容易在现行入口仍漂移时，提前触发本地配置或 legacy 清理的二次返工

## 第一实施批次冻结

### 第一批名称

- I-1：项目入口轻量收口

### 第一批目标

- 把最外层项目入口收口为“项目增量正文 + 全局引用 / 索引”
- 先统一当前主线入口口径，再为后续批次提供稳定上游

### 第一批最小范围

- `AGENTS.md`
- `docs/ai/README.md`

### 为什么先做这一批最合理

- 它范围最小
- 不涉及 runtime、权限、本地配置和 legacy 删除
- 直接作用于当前主线入口，收益高于成本
- 即使发现口径还需微调，回滚和重做成本也最低

### 第一批串行顺序

1. 文档
   - 先按子批次 B 的已冻结方案改写 `AGENTS.md` 与 `docs/ai/README.md`
   - 目标是删除重复通用正文、保留项目增量说明、补清全局真源引用
2. 测试
   - 做文档级核对，而不是代码测试
   - 至少核对：
     - 入口链接是否完整
     - 项目增量说明是否仍可独立阅读
     - 全局真源引用是否清晰
3. 代码/配置
   - 本批不涉及代码/配置改动
   - 固定为 `N/A`
4. 审查/验收
   - 以文档 review 为主
   - 验收点：
     - 主入口是否完成收口
     - 是否未越界到 runtime / settings.local / legacy agent / 历史 run 文档

## 暂缓项

### 子批次 C 为什么不适合作为第一批

- 它涉及 `.claude/settings.local.json` 跟踪状态、`.gitignore`、权限白名单迁移
- 回滚难度高于入口文档收口
- 当前更适合在主线入口稳定后再动

### 子批次 D 为什么不适合作为第一批

- 它本质上是“先止增、再约束”的治理批次
- 在现行入口和标准文档尚未先收口时，过早建立检测/约束容易误伤当前迁移过程
- 更适合作为后置治理批次

### 子批次 E 为什么不适合作为第一批

- 它会触碰 legacy Claude agent 入口的 deprecation / wrapper / 删除候选判断
- 需要前面入口、registry、角色口径已经稳定
- 尤其 `deploy_agent.md` 是否保留项目专属 wrapper，依赖主入口与运维入口先收敛

### I-2 为什么不抢在 I-1 前面

- I-2 涉及对象更多，且包含 registry / 标准入口的同步
- 如果最外层入口还没先收紧，I-2 的改法会缺少上层口径约束

## 当前结论

- 推荐的实施顺序是：
  - I-1：项目入口轻量收口
  - I-2：项目文档标准与注册入口收口
  - I-3：`.claude/settings.local.json` 本地化实施
  - I-4：legacy Claude agent 入口治理实施
  - I-5：legacy 引用新增约束与检测
- 第一实施批次已冻结为 `I-1：项目入口轻量收口`
- 第一批的最小执行范围固定为：
  - `AGENTS.md`
  - `docs/ai/README.md`
