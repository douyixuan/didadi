# 独立评审及整改

Reviewer `/root/review_didadi` 发现并复现以下阻塞，均已修复：

1. malformed mentions/content 可阻塞 mixed batch：逐事件验证类型并跳过，健康事件继续。
2. claim/validate 在网络检查期间 lease 可失效：检查后原子核验当前状态、lease和期限，claim检查CAS行数。
3. 新 failed 状态造成客户端永远保存中：保留草稿、解锁、展示固定原因、新操作显式重试。
4. complete 权限检查期间终止任务仍发送回复：复用 validate，网络后再核验，回归断言零 Matrix PUT。

最终独立复查无剩余阻塞；reviewer独立运行14项生命周期测试全部通过。原有草稿目录未修改。真实栈和完整套件由主流程另行验证。

边界：权限变化与 Git/Matrix IO无跨系统原子性，不能保证最后一次检查之后没有撤权；没有声称生产租户授权或 exactly-once 外部执行。
