# GTO-evidence-receipts

Task ID: `20260920-101849-507587-gto-evidence-receipts`

## 验收目标

修复GTO验收证据登记与关闭脱节：受控追加终态证据引用、提前检查、单一证据真源，并发布后恢复原聊天任务。

## 验收标准

- EVIDENCE-01：原作者可追加合同要求的缺失证据引用，原终态结果和历史保持不变；来源、身份、哈希、候选、引用错误均拒绝且零修改。
- GATE-01：验收登记时核对所属证据关联，CLOSE前汇总所有必需证据；引用已登记证据，无业务键硬编码或第二份事实。
- RELEASE-01：独立测试和审查通过，受控同步GTO安装副本与receipt一致，安装版CLI验收与幂等同步通过。

## 必备证据

- 独立测试先建立最小Red；原整合者完成修复，当前证据合同19/19、相关回归5/5通过。原reviewer发现并以四条真实Red证明跨template/kind证据归属缺口，round1修复后本人4/4 Green及新旧attempt识别检查通过，finding已正式closed。
- 冻结候选为 `candidate-54d2d55b2f6ba2ea`，完整指纹 `54d2d55b2f6ba2ea9ea4c89bcda8d1114e74392ce83301f454555a49b7658469`。同一原tester `/root/test_001` 的 `ACCEPT-001-attempt-1` 已正式登记pass，EVIDENCE-01、GATE-01、RELEASE-01均有独立证据映射。
- 安装版定向CLI验收15/15 passed，310.836秒，0失败/0错误/0跳过/0模型调用；261次审计调用全部指向已安装绝对入口，覆盖11类action。证据为 `.artifacts/20260920-101849-507587-gto-evidence-receipts/ACCEPT-001-attempt-1/installed-cli-summary.json` 和 `installed-cli-audit.jsonl`。
- 合法receipt追加、幂等和原结果不改；身份、哈希、候选漂移、引用、跨template/kind非法补录拒绝；blocked状态保持、assigned遗漏提前拒绝和CLOSE汇总均有真实CLI检查。
- 限定发布的11个GTO文件source/install/receipt一致，其他12条发布记录、宿主config.toml和AGENTS.md未变；第二次sync无改动，strict doctor 9项合同检查通过。原tester独立核对发布证据，见 `ACCEPT-001-attempt-1/release-verification.json`。

## 未决项

- 本工具产品修复、独立复审、安装验收和四文件正式文档同步均已完成。CLOSE已正式登记，18个链接无断链，文档delta及schema校验通过；收尾后的限定发布、source/install/receipt一致性、strict doctor 9项检查及幂等同步再次通过。没有未关闭的GTO finding。任务完成状态由下方控制器结论生成。
- 安装验收首次外层tee因目录创建时序未保存聚合stdout；Python runner实际完整完成15项，261条逐动作审计与结构化summary保留，未重跑，日志路径检查及CFM闭环已记录。这一证据限制不隐去。
- 一条范围外旧CoordinatorBlocking测试因合同夹具位于消费者.tmp外而在setUp失败，冻结修复前基线同样失败；没有修改旧测试或降低路径门禁。本修复的blocked补录真实CLI检查已通过。
- 原业务任务恢复时检测到另一个授权任务已经修改候选，真实补录被正确拒绝且无写入；旧20/20与25/25只对应原冻结候选。保留新版并补做受影响验收的范围决策已交用户，本工具修复三项验收不受该外部改动影响。
- 不修改业务项目受保护模块，不重跑已通过AI黑盒，不Git提交或推送。

## 最终结论

最新候选已通过完整独立审查覆盖及真实验收，事实已同步，任务完成。

## 要求验证索引

- REQ-01
- REQ-02
- REQ-03
