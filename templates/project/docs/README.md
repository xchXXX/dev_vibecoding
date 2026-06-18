# project/docs

项目模板中的文档落点。

最小接入时至少应有：
- `docs/modules/`
- `docs/tasks/`
- `docs/ai/README.md`
- `docs/ai/SUBAGENT_WORKFLOW.md`
- 项目业务与运维文档

其中 `docs/ai/README.md` 作为 role-first 委派入口，声明项目增量边界并引用全局治理真源。
其中 `docs/modules/` 负责模块长期真源文档，`docs/tasks/` 负责任务期文档。

其中通用协作规则统一引用全局 `ai-harness` 真源，不在项目内复制整套副本。

文档分流默认口径：

- 业务主文档与总体架构文档优先收口在 `docs/` 根
- 当前任务的方案、施工、验收收口在 `docs/tasks/<task-id>/`
- 模块长期有效的契约、设计、工程说明收口在 `docs/modules/<module-name>/`

`docs/tasks/` 不替代 `docs/modules/`。任务完成后仍长期有效的内容，应同步回写到模块真源目录。
