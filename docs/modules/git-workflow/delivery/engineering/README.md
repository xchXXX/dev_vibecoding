# 发布、接入与验证

源码和配置接口见 `../../contract/README.md`。普通任务不创建 GTO 控制面。

1. 根据项目实际参数创建 `config/ai/git-policy.json`，参考 `templates/project/config/ai/git-policy.example.json`；保留分支负责人只能来自用户指定。
2. 从 harness 运行 `scripts/sync_git_workflow.py --project-root <项目>`，生成离线可运行检查器，纳入项目 Git。再次 `--check` 必须通过。配置与 CI 为项目自己的真源，不由生成器覆盖。
3. 项目 AGENTS 引用配置和项目运行说明。CI 根据项目既有锁定依赖、测试入口接入 `--phase ci`；不得执行 PR 内容中的生产部署或注入生产凭据。
4. 先测试 `PYTHONPATH=tests/harness .venv/bin/python -m unittest test_git_workflow test_git_workflow_publication test_rules_runtime -v`，再通过 `scripts/generate_rules_index.py` 刷新索引、`scripts/validate_rules.py` 校验。
5. 核对模板原始基线与已安装入口一致后，运行 `scripts/bootstrap-local.py --codex-home <已核实路径> --git-workflow-only --json`。本模式保存旧入口与回执、共享发布锁、拒绝 receipt 漂移和维护 hold，保留其他运行时。
6. 在新 Codex 运行中使用只读场景验证：识别实际生效规则、保留分支归属、主分支起点、在途未提交文件与清理限制。静态测试和口头复述不足以证明所有后续任务永不违规；远端 CI/保护独立验收。

没有 merge/push/deploy/delete 自动执行器，不新增 shell hook、规则 matcher 或守护进程。清理仍是 report-only。远端网络不可用则保留 pending，不把缓存 refs 当实时远端。
