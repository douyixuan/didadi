# 非重叠合并验收与模块状态

部分验证：实现、自动化和本地API/SDK；真实GUI仍停止。权威为本分支Git与对应draft PR。最终SHA/CI/交付指纹在PR和交付manifest，不能把旧CI冒充本次结果。

## 具体证据

- 最终本机完整Python110项PASS；App52＋真实编辑器工作流1共53项PASS；生产build PASS。独立reviewer另跑合并10项/App52项PASS，无剩余阻塞。新增两进程同base分段修改保留两边，strict默认仍冲突；重启重试同commit；重叠无写入且有UTF8有界冲突文本；其他文件/历史symlink/未知base/大blob/无效UTF8/NUL拒绝；CRLF/中文；合并结果超限拒绝；服务冲突仅取blob元数据。
- 复核发现并关闭：合并后UI原稿配新blob可能丢更新；历史base普通mode/size/UTF8；409错误路径snapshot重新读坏正文。新回归包含merge成功后refresh失败再保存保留另一人修改、缺合并正文保持未决并原请求重试。冲突详情只读，加载最新成功清除，不替换草稿。
- 新自有Compose didadi-merge，Matrix8034/Gateway9068，合成身份/房间/卷，与旧预览数据隔离。scripts.concurrent_merge_smoke实际两独立HTTP客户端、真实Matrix权限检查，非重叠合并、重叠409、提交正文、重启幂等、Matrix仅metadata回执全部PASS。两session使用同一个已授权合成Matrix身份，无新增权限；不声称跨用户生产权限验收。
- 初次默认沙箱全量109项出现16项loopback bind PermissionError，未当产品通过；随后允许本地回环测试的环境完整110项PASS。日志本机/tmp/didadi-merge-python-final.log、merge-front-final.log、merge-build-final.log；新隔离预览私有.local/merge-preview/logs。运行日志/令牌/数据库不入交付包。
- GitDocs.write opt-in默认strict；仅人类直接保存启用。完整Git远端分叉合并、CRDT、通用Agent grant和legacy Matrix正文退出不在本轮。

## 原始模块与负责人

仓库没有独立PRD/原始用户故事文件；按7861f29 README四模块、Accepted ADR0001与Issue15 step1映射，不能计算虚构完成百分比。

| 模块 | main f0ab205 | 候选（draft31–44＋本轮） | 负责人/下一步 |
| --- | --- | --- | --- |
| Matrix/Synapse/Postgres/AS消息与重放 | 已合入运行基础 | 真实Matrix/保留卷/拒绝与重放已有自动化 | 本执行者维护；标准客户端GUI兼容未验 |
| 外部Agent鉴权/持久任务/幂等 | 基础HTTP runtime已合入 | 取消/轨迹/WS/结构化结果/scoped API已实现且自动化验收 | 本执行者；通用多Agent注册/生产grant未实现，不能冒称runtime echo为真实模型 |
| Git文档并发/refs/恢复 | 锁/CAS/本地remote/outbox基础已合入 | 直接人类保存/scoped Agent IO/本地草稿；本轮非重叠人类合并已实现并API验收 | 本执行者；远端普通分叉合并/生产Git传输仍未验，Issue12另暂停不抢活 |
| React/Matrix SDK/文档与任务 | 文档/编辑/引用基础已合入 | 源报告/展示/导出/本地草稿/GUI窄修及合并提示已实现；部分旧GUI观察，当前新代码未真实GUI验收 | 本执行者实现；GUI需安全工具链确认，IME/拖拽/光标滚动/磁盘字节/新草稿关闭多标签仍未验 |
| ADR0002 | main尚无 | 独立PR41 Proposed7067385，不包含在候选 | 另一执行者负责设计评审；不接管、不当已接受运行能力 |

本轮交付为draft源码和loopback预览，不是main发布/公网部署。合入权限拒绝保持暂停，不重试绕过。安全GUI路径未恢复，不读剪贴板/历史/搜索。未触碰ModelBench。下一步优先完成本轮最终CI/交付，再由父任务统一小时汇报并分派下一切片。
