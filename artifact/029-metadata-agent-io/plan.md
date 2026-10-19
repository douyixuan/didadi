# Agent 正文退出自动 Matrix 回执

实施中。main仍f0ab205，draft31–45未合入；基线e4c7282。ADR41独立7067385 Proposed且无人新增重叠PR，本轮不修改其设计或权限模型。负责人本执行者，独立reviewer复核。

目标：平台生成的文档/源码任务结果不再把正文放进Matrix；Git是已保存正文权威，runtime通过既有task/lease授权Document API取得resource正文、提交新正文。Gateway在最终发送边界构造仅metadata结果，旧runtime传入/旧未完成result含正文也不回灌。普通Agent聊天文本不改。

执行：read/report/legacywrite兼容，read正文在API resource侧栏，Matrix只版本/固定元信息；源码read的typed outcome携带有界repository/path/commit/blob引用。新增POST documents/write只接受id/lease/content，room/path/base来自持久task，严格CAS，当前授权/lease重检，现有operation id/outbox重放。元数据write任务没有正文；旧content任务继续兼容但弃用，不声称能撤回用户旧客户端已投递的Matrix输入或历史。新示例使用正文API，历史兼容fixture明确区分。

安全边界：不增加Agent身份/凭据/权限；不能把read/report任务变write，不能覆盖base/room/path，不反向从任意API回复复制正文到Matrix。固定旧result语义及stabletxn保留；旧body可替换为同outcome安全display，不从英文推断控制状态；旧已done Matrix历史不改。API读取/写入错误、取消/租约/权限、幂等/重启恢复回归和真实HTTP/WS协议检查。新隔离预览8814；不触碰8806/GUI/剪贴板/历史/搜索，不合并或接管ADR。

不宣称：已清理Matrix历史、禁止任意人手动发文档文字、生产多Agent grant、物理singlewriter或CRDT。原Library身份更新，最终精确head CI与交付范围记录。
