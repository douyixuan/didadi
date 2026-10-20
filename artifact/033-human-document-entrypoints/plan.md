# 人类文档入口仅走Document API

授权与来源：2026-10-20原始需求持续完成授权，Issue14“人类无worker保存、Matrix不接收平台文档正文”。本切片与ADR41设计无关，复用已接受的DocumentService/Git模型，不改Gateway旧任务兼容或历史。

缺口：scripts/gateway_preview.py的旧HTMLdoc-save仍发全文Matrix任务，src/client_server.py代理仍接受全文写命令。现代React正常路径已直接保存，但不能据此称所有平台入口达标。

计划：旧HTML保存改为DocumentService.save，UUID操作随表单提交，复用Matrix用户授权、64KiB UTF8上限、CAS、真实作者、Git通知意图和幂等。旧只读任务仍为metadata。代理在发送Matrix前拒绝write动作（指向直接API），read只允许action/commit，拒绝嵌入content。普通讨论用户引文不改变。

兼容边界：外部旧Matrix正文任务继续被Gateway接受；无法撤回已发送历史。现代React和synthetic adapter已有直接save；自定义旧adapter不由本切片升级。后续应明确彻底移除旧协议的迁移窗口，不宣称Matrix服务器能阻止任何外部客户端手写正文。

完成标准：代理拒绝测试证明无/send调用；旧HTML表单实际执行无worker直接保存、同UUID返回同Git版本、越权/冲突保留原版，Matrix时间线只有元数据回执而无合成正文；原讨论/读取和真实SDK回归不变。独立review、完整测试和最终SHA CI后正常合入。
