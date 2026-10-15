# #10/#11 任务隔离与终止恢复

用户授权核心闭环与数据安全。沿用 #10 的接口与验收要求，复制既有 didadi-client 未提交草稿到独立 worktree，原目录不改动。外部委托未产生 PR/分支，issue 已记录恢复范围。

- per-event eligibility；永久拒绝跳过，临时失败 durable unverified；旧 echo best effort 隔离。
- 幂等 SQLite migration，attempt cap、指数 lease/backoff，typed completion/fail errors。
- claim recheck；document worker 在 Git side effect 前额外 validate 当前 lease/room。
- failed outbox 通过 Git receipt abandon，保留已存在提交，不撤销历史。
- 单元测试覆盖 mixed batch、临时失败恢复、kick、attempt cap、旧DB、stale lease和abandon。
- 真实 Synapse kick/mixed room 验证，已有 Matrix/Git crash/SDK integration 不回归。
- 独立review、draftPR、合入后最终主线CI和本地验收各自记录。

边界：Matrix membership 与 Git 无跨系统原子事务；validate 缩小窗口，不声称消除检查后的权限变化。无生产 grants/租户系统，非 exactly-once 执行。

评审整改：malformed event 类型验证逐事件跳过；claim/validate 网络回查后原子核验当前 lease/status/expiry；客户端 failed 状态保留草稿并解锁，新操作显式重试；真实 kicked-room smoke 加入CI且安排在持久化恢复检查之后。
