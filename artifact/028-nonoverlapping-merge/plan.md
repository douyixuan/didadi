# 非重叠并发编辑合并

实施中。原始README四模块之一Git并发文档服务、Issue15 step1明确的未完成用户路径。远端main仍f0ab205；draft31–44未合入，最新73effbf。ADR41另执行者docs-only7067385不接管，Issue12性能工作及既有脏目录不碰。仓库没有独立原始PRD，不能冒称完整PRD验收。负责人：本执行者实现，独立reviewer复核；Git/PR为权威。

范围：GitDocs新增显式opt-in非重叠三方合并，默认仍严格CAS；仅人类直接DocumentService启用。base必须是同一文档可达历史中的普通blob，不允许任意repo对象进入合并。Git merge-file处理文本，合并结果仍≤64KiB。重叠返回409及有界冲突文本，不提交；无base/未知base/二进制/超限保守冲突。保存元数据记录merged标志保证幂等重试同commit；原请求hash不因服务端策略升级改变。

客户端成功提示合并，不通过Matrix传正文；服务端照旧授权/作者/固定room/demo.md/outbox。不是CRDT、远端分叉合并、生产权限或ADR迁移。现有草稿、失败恢复和strict legacy路径保持。

证明：同base不同段落同时保存保留两边；重叠不写commit并有hunks；伪造其他文档blob不泄露；保存幂等/重启/outbox；合并UTF8容量/CRLF边界；真实Matrix双客户端HTTP验收脚本与CI。独立新预览8812/自有隔离状态，不读剪贴板或历史、不操作GUI、不改冻结8806。完成后draft PR、精确CI、原Library身份更新；每小时进展供父任务统一汇报。
