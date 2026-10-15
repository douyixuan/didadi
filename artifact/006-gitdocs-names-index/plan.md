# GitDocs 名称与派生索引

状态：实施中。权威需求：[Issue #17](https://github.com/douyixuan/didadi/issues/17)、[Issue #12](https://github.com/douyixuan/didadi/issues/12)。用户已授权实现及验证；不推送、不创建 PR、不合并。

名称：接收 NFC Unicode、点和空格，按 UTF-8 240 字节限制，拒绝遍历、Git 元数据、控制字符及 Windows 保留名称。测试实际读写、历史读取与拒绝路径。

索引：使用仓库内可删除 SQLite 派生缓存，记录已索引 head、operation 与 notification。批量读取增量 commit 消息；非祖先 head 变化重建。Git main 单 ref 仍为唯一提交点，notified refs 保持收据权威。测试删除/损坏缓存、提交后崩溃、外部快进及历史改写。脚本测量 0/1k/10k 历史的 write/pending 延迟，目标 write 比值 <=2。
