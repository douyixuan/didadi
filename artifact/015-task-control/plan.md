# 原设计：任务取消与持久执行轨迹

原会话确定要求持久Task、幂等、取消、审计和原Thread回复。现有#27仅failed终态，没有用户取消或可查看执行轨迹。

范围：单一Agent、可信loopback开发身份，不扩展生产授权。取消仅通过现有认证worker端点；本地adapter在CSRF/Origin/Host、room allowlist之后验证请求事件确属当前fixture用户，才代理取消。用户不能取消其他用户或其他room的任务。

- 新cancelled终态；claim/validate/complete拒绝取消的租约，重复取消幂等，done不改为cancelled。
- SQLite同事务记录accepted/leased/result_ready/retry_scheduled/completed/failed/cancelled，仅任务ID/时间/attempt/固定原因，不记录消息正文、结果、token或lease。
- Git outbox对cancelled任务abandon并保留已有提交。
- 客户端取消/查看执行轨迹，保留保存草稿并解锁；synthetic仅明确browser sample。
- 回归：取消前/租约中/授权网络期间/完成后，重启轨迹、越权/CSRF、Git已提交保留与outbox清理，独立review、真实Matrix和最终CI。

边界：取消是协作式，无法撤销已完成Git写入或正在进行的外部IO；执行轨迹是开发用持久记录，不声称不可篡改或合规审计。没有生产grants、主动WebSocket或代码仓库分析。
