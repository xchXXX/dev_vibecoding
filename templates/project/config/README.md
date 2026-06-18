# project/config

项目模板中的配置落点。

最小接入时至少应有：
- `config/ai/`
- `config/ai/README.md`
- `config/local/`
- 项目专属配置覆盖

`config/ai/README.md` 用于说明项目侧配置覆盖边界与 role-first 相关约束。
`config/local/` 用于本地值与敏感覆盖入口，默认应加入忽略规则。
