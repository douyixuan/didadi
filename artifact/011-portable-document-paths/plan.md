# #24 跨平台文档名称

Issue #24 无其他认领，独立 worktree 实施。已有名称语法保持不变；在 write 的 repository lock 内、remote sync 后、Git tree更新前，遍历当前固定head路径，逐段比较 NFC(casefold)。同键不同拼写的文件或目录拒绝，异常说明冲突路径，Git内容不变。合法原名更新仍通过。

验证：文件大小写、目录大小写、Unicode casefold、合法更新、remote同步后碰撞；独立review；完整后端套件及CI。仅阻止新写入造成碰撞，不声称已清理外部仓库中原有碰撞。遍历文件树而非历史，目录规模性能未基准。
