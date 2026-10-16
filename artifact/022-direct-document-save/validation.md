# 直接保存验证

状态：部分验证，完整CI/真实新栈收尾中；无原生GUI/IME验收。

- 新service专项7项通过：Git原字节/作者、同请求去重、同operation改内容冲突、并发一成一冲突、64KiB/非法Unicode/空文档、角色/加密/绑定、通知断线/ACK丢失/重建恢复、旧Agentoutbox隔离、raw mutation权限守卫。
- 前端完整80项、33文件1586块逐字节语料、性能预算、build通过；最后补全未决保存历史Back latest禁用和load ref守卫，精确CI复核。新增直接保存原payload重试、失败冻结、冲突保稿、pending receipt不当失败、64KiB/只读、human receipt导航回归。
- 独立review先发现4阻塞：DocumentError形参status重复、GitDocs stdout universal-newline把CRLF变LF、Retry仅缓存id导致载荷可变、legacy raw Matrix权限绕过。全部实修；reviewer最后无剩余阻塞，前端38专项和实际Python11项通过。其Python命令多列不存在模块导致总体importerror，明确为review命令错误，不是产品失败。
- 必要最小改gitdocs.py为字节subprocess+显式UTF8 decode，及server-derived可选author；未改#12扫描/索引逻辑或原脏草稿。request hash在无author时保持旧格式兼容，direct author进入幂等hash。
- 独立didadi-direct栈8026/9048初始化较慢，不能把up命令入队或healthy前copy state当E2E成功；初次state copy因基础smoke尚未生成文件失败，没有读/改其他栈。完整Python仍运行，结果以最终日志与PR/CI为准。
- 权限绑定与新DirectService不同于接受全部ADR0002；legacy协议兼容但增加实时授权/仓库房间绑定，不宣称生产租户授权、跨主机单写或CRDT完成。
