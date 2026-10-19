# MVP 产品验收差距核对

范围：原始 README `7861f29` 的四条 roadmap、Accepted ADR0001，以及后续工作区/块编辑/标准 Markdown/版本引用/任务控制/直接保存计划。仓库没有独立 PRD、原始用户故事或完整 MVP checklist，以下是据这些来源整理的验收映射，不是新增产品承诺，也不计算“完成百分比”。

验收基线：`df4ca78`。本轮只修复直接保存的本地校验 Retry 路由和草稿保留提示；最终候选 SHA、CI 和预览指纹见对应 draft PR 与交付 manifest。自动化通过不等于真实界面验收。

## 原始 roadmap 与用户路径

| 原要求 / 派生用户故事 | 分类 | 已有证据与边界 |
| --- | --- | --- |
| 自部署 Synapse/PostgreSQL/AS，双向消息及事务重放 | 已实现且自动化验收 | 干净 ZIP 和最终源码独立冷启动；真实 Matrix smoke、重放、保留卷重建。未验第三方 Matrix 客户端界面兼容。 |
| 开发者提及外部 Agent，持久任务、鉴权、去重分发 | 已实现且自动化验收 | 真实外部 HTTP/WS worker、重连、lease、取消/轨迹/重启与越权拒绝。仅受信单 runtime 的开发边界；不是生产 per-agent grant 或真实模型接入。 |
| Git 文档锁、版本比较、远端 refs、崩溃恢复 | 已实现且自动化验收（受限） | 人类无 worker 保存、Agent API 写入、旧 base 冲突、幂等/outbox/崩溃与本地裸 remote 测试。SSH/HTTPS Git、普通分叉三方合并不在已验范围。 |
| React + Matrix SDK，文档与任务视图 | 已实现、界面未验收 | 真实 SDK 通过同源 adapter；组件覆盖视图/状态/引用。当前候选未做真实浏览器界面验收。不能据测试数宣布此用户故事完整通过。 |
| 用户用实际块编辑器编辑、撤销、重开 | 已实现、界面未验收 | 真实 Milkdown 在 jsdom 的编辑器事务和往返、语料逐字节检查；App 部分测试隔离编辑器。布局、鼠标拖拽、焦点、剪贴板和物理 IME 未验。 |
| 导出当前未保存或历史 Markdown | 已实现、界面未验收 | App 测试检查传给下载函数的完整文本；该函数在 App 测试中被 mock。不能证明浏览器已下载文件或其实际磁盘字节。 |
| 冲突/失败保留草稿并显式恢复 | 当前页面内已实现、界面未验收 | API 冲突/不覆盖和组件 preserve/restore 已验；保留卷恢复的是已提交 Git/身份/房间。草稿仅 React 内存，刷新、关闭、崩溃后的未提交草稿恢复未实现。 |
| 错误提示及 Retry 执行当前操作 | 已实现、界面未验收 | 网络未知结果固定 UUID/payload、冲突保稿等已有测试。本轮复现并修复“超长本地校验后 Retry 重复上一 source 任务”；前后回归证据，不把它当作 GUI 验收。 |

源码入口：[App](../../client/src/App.jsx)、[真实编辑器测试](../../client/src/BlockEditor.test.jsx)、[工作流与导出测试](../../client/src/App.test.jsx)、[真实编辑器工作流测试](../../client/src/DocumentsEditor.test.jsx)、[下载实现](../../client/src/downloadMarkdown.js)、[完整启动指南](../../docs/LOCAL_WORKSPACE.md)。后端和干净启动基线的[精确 CI](https://github.com/douyixuan/didadi/actions/runs/38885676050)仅证明其列出的自动化范围。

## ADR41 接口一致性，只读核对

当前核对：main `f0ab205`；独立 [PR41](https://github.com/douyixuan/didadi/pull/41) `7067385`，Status Proposed，仅 ADR0002 与 ARCHITECTURE 两个文件。本轮不修改或接管其分工。

| Proposed 边界 | 当前候选 |
| --- | --- |
| Matrix 只承载通信/回执，Document API 承载正文 | 人类直接保存与 metadata-only 回执已实现。旧 Agent write/read 仍经 Matrix 传递正文；该完整边界未实现。 |
| 每仓库一个服务写入 owner | Agent 写入已收敛到 scoped API；human/Agent Python 服务仍是两个可写进程，依赖 flock/CAS。跨服务单 owner/fencing、普通分叉 merge、durable CRDT 未实现。 |
| Matrix 派生授权 | 固定 room/demo.md，live join/power/未加密检查；不是 space/prefix 继承、投影失效与生产多租户授权。 |
| Agent 是同一 Document API 的 scoped client | 已有 task ID + 当前 lease 的服务端范围核验、结构化结果和幂等。人类和 Agent 路由不同；通用 issued/expiring/revocable per-agent grants 尚未实现。 |

TypeScript/共享 schema、CRDT、三方合并、生产 grant、全量正文退出 Matrix 都不能因 PR38–40 或本轮测试而标完成。保留 PR41 的设计评审和迁移顺序。

## main 与候选的差异

已核对 main 仍未合入 draft31–40。当前候选基于该 stack，额外含本轮小修；包含取消/轨迹、源码 grant、WS、源报告 UI、性能/展示、结构化结果、直接保存、scoped API、干净启动等。main 没有这些整合候选能力，也没有 ADR0002；候选不包含独立 PR41。可复现候选不等于已发布 main。

## GUI 最小验收，供协调

入口使用本轮交付说明指定的当前候选本机 URL；旧基线为 http://127.0.0.1:8804/。只用其合成 demo.md，开始前导出当前内容备份，不碰真实账号/权限。需要 starlabs-112 上能交互并截图的真实浏览器，以及系统中文输入法；预计一个约15分钟的独占窗口。

1. **编辑与焦点**：Edit 中改标题/段落/列表/代码块；斜杠插块、鼠标拖拽、Undo/Redo。保存再重开，检查内容、光标、滚动与块位置。截图正常编辑态。
2. **物理中文 IME**：系统拼音逐字组词、候选词选择、回车/空格确认，再粘贴中英混合。检查无重复、丢字、光标跳跃；保存重开。合成 composition 或粘贴中文不能替代此项。
3. **实际导出**：在含 front matter/中文/转义符的未保存草稿点 Export Markdown；检查真实下载文件包含该草稿且没有新增 Git commit。再打开 History 导出，核对下载的是该历史版本。下载路径交给执行者做字节比较，不公开私人 Downloads 内容。
4. **冲突恢复**：两个标签从同版本开始；B 修改保存，A 修改另文并保存。A 应看到冲突、原草稿仍在；Load latest 后出现 Preserved draft；Restore 再手动合并保存。检查提示“仅当前页面保留”；不要在导出前刷新。
5. **错误与未知结果**：用浏览器自带 Offline 对合成工作区制造一次保存网络失败；检查草稿、冻结/Retry 状态，恢复网络后重试，确认一次版本与正确提示。再读一次源码，输入超长内容保存，缩短后 Retry 应直接保存，不发新 source 任务。

实际工具阻塞：当前仅有命令执行与仓库 Vitest/jsdom、HTTP/SDK。无 callable 浏览器/Playwright/CUA/桌面控制或系统 IME 工具；package 没有已配置的真实浏览器测试框架。`open_in_codex` 可展示链接但不能完成点击/截图/IME 验收。未安装浏览器/扩展，未用系统脚本或调试端口绕过既有限制。以上五项未执行的必须保持未验收，请协调工具或人工窗口。

## 优先级与独立推进边界

最高优先级是完成上述真实编辑、导出和恢复 GUI gate，尤其物理 IME 与实际下载。刷新/关闭后的未提交草稿恢复是明确未实现项，需要先确认产品要求与持久化/隐私边界，不能当作已有恢复能力。

可独立推进：对已确认的失败做窄修、复查类型化 API/拒绝/幂等、复用 PR41 做接口迁移差距和证据衔接。本轮已有一个可复现 Retry 缺陷，已处理；当前没有第二个被证实且必须新增功能解决的阻塞。缺 GUI 工具时应停在这个验收边界，不继续扩 TS/CRDT/登录或新权限。
