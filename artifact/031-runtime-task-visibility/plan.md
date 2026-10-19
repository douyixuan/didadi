# 任务阶段与 runtime 连接可见性

实施中。父任务授权本切片实现/隔离runtime停止重启/幂等协议验收/独立review/draft/原Library更新，并要求原始MVP差距收敛；不GUI/剪贴板/合入绕过。基线5ebdc2c/PR47，mainf0ab205；PR31–47未出现新重叠，独立ADR41仍7067385，本执行者不接管；暂停Issue12、不改旧worktree或runtime。独立worktree didadi-task-visibility/feat/runtime-task-visibility。collaborative-workflow/truth继续用于记录，用户已授权的可逆工程直接推进。

原始来源：README@7861f29四模块、ADR0001、Issue1/2/3；仓库无独立原PRD。当前Gateway durable status为pending/unverified/done/failed/cancelled，lease/attempts/available/last_error已存在；客户端未完成均显示queued。保留这些控制状态，新增派生presentation phase与有界调度元数据：waiting/verifying/running/retry_wait及原terminal；不发送lease/session token。claimed_at记录授权确认后的租约，不把预留权限检查当运行；不将lease当进度证明。

仅观测现有单Agent WebSocket连接，不新增生产注册或grant。桥接器以随机会话和既有固定Agent凭据报告连接/周期心跳/关闭，Gateway只存会话元数据。closed会话不可被晚到心跳复活；多连接一条关闭不抹掉另一条。TTL过期显示unknown而非确定离线，已观察关闭显示disconnected；HTTP轮询runtime不纳入WS连接证明，UI明确范围。状态接口只向现有授权房间用户返回聚合观测，不泄露凭据/会话ID/正文。连接断开不提前释放租约或证明旧副作用停止。

客户端文档pending和Agent activity统一阶段/attempt/原因/服务端时间提示；连接与任务阶段分离。轮询失败单独显示重连、保留草稿和任务，成功清除该项错误，不清掉无关错误或新造task。取消/审计/结果不变。

测试：派生阶段时间/旧DB迁移/授权确认/无token泄露；session late heartbeat、多连接关闭、过期unknown、auth/schema；客户端阶段/恢复/保稿和轮询错误归属。真实Synapse+HTTP/WS：本轮独立runtime子进程claim并Git提交后停止，旧lease有效期间不重复claim；连接关闭不释放lease；60秒原策略到期后重启重取同task，显式retry/backoff，再重启完成；Git一次/Matrix一次，旧lease不能complete，重复complete幂等，outbox恢复。只停止自己创建的子进程，新Compose/预览8818（Matrix8040/Gateway9080/WS9081/Doc9082），旧所有服务不动。独立review、完整测试、最终pushheadCI。Library原身份expected9/10 guard更新。

交付MVP清单按原始1/2/3及四模块逐项区分main/candidate/自动化/GUI/生产范围。主线尚未合入是验收差距，不靠新增功能掩盖。下一步优先验收/收敛现有清单，生产注册/grant、CRDT、网络远端、任意Markdown/GUI均不自动扩成当前MVP。
