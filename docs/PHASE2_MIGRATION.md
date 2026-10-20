# PHASE2_MIGRATION

本文件记录 Phase 2 已迁入全局真源的对象，以及它们与项目层、运行时层的关系。

## 已迁入全局真源

### skills
- `skills/global-task-orchestrator/**`
  - 来源：`C:/Users/72385/.codex/skills/global-task-orchestrator/**`
  - 角色：长期真源
  - 运行时对应：`C:/Users/72385/.codex/skills/global-task-orchestrator/**`

### schemas
- `schemas/plan.schema.json`
- `schemas/work_order.schema.json`
- `schemas/dispatch_packet.schema.json`
- `schemas/return_packet.schema.json`
  - 来源：`C:/projects/pdf_ai/paddle_ocr/config/ai/schemas/*.json`
  - 角色：长期真源
  - 项目层保留：`config/ai/schemas/*.json` 作为当前项目镜像/覆盖层

### templates
- `templates/plan.example.json`
- `templates/work_order.example.json`
- `templates/dispatch_packet.example.json`
- `templates/return_packet.example.json`
- `templates/task_plan.session.example.md`
- `templates/findings.session.example.md`
- `templates/progress.session.example.md`
  - 来源：`C:/projects/pdf_ai/paddle_ocr/config/ai/templates/*`
  - 角色：长期真源
  - 项目层保留：`config/ai/templates/*` 作为当前项目镜像/覆盖层

### scripts
- `scripts/start_session.ps1`
  - 来源：`C:/projects/pdf_ai/paddle_ocr/scripts/start_session.ps1`
  - 角色：全局 bootstrap 真源
  - 项目层保留：项目兼容入口，后续可包装调用全局版本
- `scripts/doctor-core.ps1`
  - 来源：`C:/projects/pdf_ai/paddle_ocr/modules/ops_tooling/debug/scripts/repo_doctor.ps1` 抽出的通用核心
  - 角色：全局 doctor core 真源
  - 项目层保留：项目专属 `repo_doctor.ps1`，后续应组合调用 global core + project checks

## 真源边界声明

- `C:/Users/72385/dev/ai-harness/**` 是后续长期维护真源。
- `C:/Users/72385/.codex/skills/**` 是运行时投放层，不再作为长期真源维护。
- `C:/projects/pdf_ai/paddle_ocr/config/ai/**` 与 `scripts/start_session.ps1`、`modules/ops_tooling/debug/scripts/repo_doctor.ps1` 暂时继续保留项目层副本，但后续应降级为镜像、覆盖层或项目包装器。

## 本 phase 未做的事

- 未实现 sync/install/doctor 完整链路。
- 未实现 Claude hooks。
- 未编写全局 agents 正式内容。
- 未修改运行时目录行为逻辑。
