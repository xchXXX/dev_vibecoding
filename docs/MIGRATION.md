# MIGRATION

## 当前已识别迁移来源

### 来自当前项目

- `config/ai/schemas/*.json`
- `config/ai/templates/*`
- `scripts/start_session.ps1`
- `modules/ops_tooling/debug/scripts/repo_doctor.ps1`
- `docs/ai/*` 中的通用控制面说明
- `.claude/agents/*.md` 中可复用的 agent 规范

### 来自 Codex 运行时目录

- `C:/Users/72385/.codex/skills/global-task-orchestrator/`

## 迁移原则

- 先复制到 `ai-harness` 真源
- 再建立同步脚本
- 最后逐步清理项目内或运行时目录中的重复真源

## 当前项目保留原则

以下内容继续留在项目层：
- 项目根 `AGENTS.md`
- `docs/ai/`
- `config/ai/`
- 项目专属 `.claude/`
- 项目业务模块与运维文档

## 风险

- 运行时目录与真源目录短期内会并存
- 历史 run 文件仍会引用旧的绝对路径
- 当前项目的 `.claude/settings.local.json` 仍被 git 跟踪

## 后续迁移顺序

1. 建立全局真源骨架
2. 复制现有真源
3. 建同步脚本
4. 验证运行时识别
5. 再清理旧引用
