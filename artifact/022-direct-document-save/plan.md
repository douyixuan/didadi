# Document Service直接保存

用户明确授权本轮直接保存闭环及权限/保稿/去重/并发、独立review/CI/实际E2E，合入保持暂停。最新fetch无新协作者PR，31–37仍draft；新隔离分支基于8e1c9b7，不改gitdocs.py或原暂停草稿。仓库无.agents/skills条目。

新Python DocumentService是现有开发架构的最小迁移，不冒称拟议TS/CRDT已接受。Git仍唯一正文/版本/通知intent数据源，已有flock+CAS和operation replay复用。固定demo.md与种子room；服务端会话身份，实时join/power>=50/未加密失败关闭。64KiB UTF8，严格UUID+base_blob，HTTP支持JSON转义开销。

人类save直接PUT API，不发正文/不建Agent任务；metadata-only Matrix receipt稳定txn，Git提交成功后receipt失败返回saved+pending，成功ACK后才关Git outbox，重启读/保存恢复。按kind/version/author/seedroom隔离outbox，Agent恢复跳过direct项。

客户端保留同一payload/UUID重试；冲突保稿，无自动覆盖；通知pending不当写失败。单workspace文档绑定种子room，讨论切房不切文档。新增direct receipt版本/线程导航。

完整回归+真实Matrix无worker保存、并发两个base只一成功、ACK丢失/重启去重、读者/撤销权限拒绝、正文不入Matrix、实际新预览；独立review及精确commit CI。原生编辑器/IME仅在工具可用时实测。
