# 标准 Markdown 交付

原设计要求标准.md导出；真实GUI复现 #23 新空段落把内部marker写入Git并暴露在读视图。独立worktree认领，无其他实现PR。

- Export Markdown 下载当前完整Markdown（包含未保存编辑或当前历史快照），不通过Read视图重建、不转HTML、不触发Git写入。
- 新空段落仅视图状态，序列化省略；旧marker继续解析，未改文档保持原字节，真实编辑后去除；保留合法CommonMark列表边界。
- 阅读层隐藏顶层旧marker，不隐藏代码块或用户其他注释。
- 测试：N空段落、旧marker未编辑/编辑、完整语料逐字节、未保存和历史导出；独立review；native下载另在排他GUI验收。
- 不声称导出等于完成Agent代码分析/主动WebSocket/取消/授权。
