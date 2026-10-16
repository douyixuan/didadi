# 验证范围

部分验证。前置草稿恢复PR43提交190ee08已完成独立review与精确CI38890727195（100Python/101前端/全部Matrix），本修复另立分支叠加，不改旧预览源码目录。

## 本修自动化

- 用190ee08原App/sourcePlugin与新回归核对，两项失败如预期：完整YAML粘贴字节不符、房间轮询fetch失败未在重连清除。原代码临时替换仅发生于新worktree，Python finally恢复当前字节；日志 /tmp/didadi-gui-regressions-before.log。
- 首轮metadata实现的前导空白/纯空白undo回归2项失败，已改为弱引用不可变Fragment快照恢复对应source metadata，不修改serializer diff/性能算法。6项实际Crepe paste覆盖完整CRLF/中文/YAML字节、部分选择、只读、旧leading blank/纯空白/BOM的undo/redo。合成paste事件不是访问系统剪贴板。
- App覆盖后台rooms失败→timeline恢复触发rooms重试→固定原保存payload Retry成功清除旧fetch错误；无关建房失败仍保持。
- 最终4文件专项62项PASS，生产构建PASS；独立reviewer /root/review_runtime_transport另跑同62项PASS，有限复核无阻塞。日志 /tmp/didadi-gui-fixes-final62.log 与 /tmp/didadi-gui-fixes-final-build.log。精确head CI以PR为准。

## 前一轮真实GUI观察（由独立任务回报）

8806的保存、双标签旧base冲突/Load latest/Restore/手动合并、DevTools Offline冻结保稿→重连Retry、66017字节校验后缩短Retry，以及实际磁盘导出有观察。此前HTTP资产指纹d7a6f79be4bcf4fa7c728aebb235a8a31912c1544f7017eff21914a0ee58479d与526c45a构建字节一致；页面自身无SHA。不能把测试指定版本当页面自证或把旧GUI覆盖扩到本轮新代码。

指定100字节QA导出文件仅核对metadata/必要内容及SHA，未读其他下载。本轮确认的是“全选粘贴YAML后导出被围栏化”，不推断已有Git文档损坏。没有把该导出与输入做磁盘逐字节比较；本修回归是在编辑器序列化层的字节比较。

GUI链路已因独立任务的剪贴板异常停止，用户已由父任务告知。本执行者未操作GUI、读取剪贴板/历史/搜索或重演路径。真实中文IME候选、鼠标拖拽、完整光标/滚动稳定性、磁盘逐字节比较、新代码与草稿刷新关闭/WebLocks跨标签GUI仍待安全工具链确认后验证。不覆盖8806测试数据，无合并/ADR41/公网部署。
