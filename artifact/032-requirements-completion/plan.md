# 原始需求核对与实现计划

状态：实施中。授权：2026-10-20要求持续对照原始需求完成；2026-10-19已授权仓库操作、ready及合入。Git为本计划与代码的权威，不等待重复确认。

## 来源与完整范围核对

未发现独立PRD文件。原始需求来源为README@7861f295、Accepted ADR0001、Issue1/2/3；后续用户故事见Issue11–18、22–25及artifact/004设计。当前main e3e6f64，原Library速查v10/source13/report18仅作当前交付索引，不能替代需求。

| 需求/验收 | 实现与测试 | 当前证据/缺口 |
|---|---|---|
| #1 Compose/持久卷 | compose.yaml、matrix_smoke/persistence | 最终main CI及独立v12保留卷已验 |
| #1 两用户消息 | matrix_smoke真实Synapse | 已验，合成身份 |
| #1 AS事件/托管Agent回复 | matrix_as、matrix_smoke | 已验，无homeserver fork |
| #1 启动注册文档/CI | LOCAL_WORKSPACE、MATRIX_QUICKSTART、workflow | 已验，新包v13云端结构及源码比对通过 |
| #2 ACK前耐久txn/event | gateway、test_gateway | 已验单节点SQLite |
| #2 replay一task/重启保留 | gateway、test_gateway_lifecycle、lifecycle smoke | 已验 |
| #2 Agent凭据与Matrix身份绑定 | gateway、runtime/socket tests | 单Agent开发凭据已验，多Agent注册无原始MVP验收定义 |
| #2 仅授权未加密Room | document_access、lifecycle/access smoke | 已验；E2EE自动授权不在Accepted MVP范围 |
| #2 外部环境/outbound/原Thread | runtime_socket、websocket_worker、websocket_smoke | 已验；不要求内置LLM运行环境 |
| #3 独立进程无静默覆盖 | gitdocs_hardening/concurrent_merge | 已验 |
| #3 外部分支更新非force处理 | remote_recovery及本地bare smoke | 保留分叉/显式恢复已验；自动远端语义合并属#18 Proposed |
| #3 Git提交至通知崩溃恢复 | Git outbox/document_smoke | 已验；本轮提交元数据修复必须保持 |
| #3 路径/symlink/固定commit | gitdocs/source-reader硬化测试 | 已验 |
| 第四模块 React/SDK文档讨论任务视图 | App、api、SDK smoke | 已验HTTP/DOM；物理GUI/IME/鼠标/实际下载未验 |
| #11 失败终态/退避/撤权不写Git/abandon | gateway lifecycle/task control | 已有实现与真实集成，不因Issue仍open重复实现 |
| #12 0/1k/10k历史性能、删除索引恢复 | 另一暂停的gitdocs-recovery工作区 | 明确暂停，不能覆盖；不是已完成 |
| #13 局部源码保留/零额外改写 | sourceMarkdown、pinned corpus | 已验33固定语料，不宣称任意Markdown或1010全集 |
| #14 人类无worker保存/结构化结果 | document_service/task_result | 已验 |
| #14 Git作者/无正文Matrix入口 | 人类已有作者；Agent默认服务作者；旧正文兼容入口仍存在 | 作者本轮修复；彻底拒绝旧入口/历史迁移需单独兼容策略，不能以新推荐API当全部入口达标 |
| #15 非重叠合并/重叠hunks/幂等 | concurrent_merge、App tests | Step1已验；CRDT/live cursors明确为later且#18设计未接受 |
| #16 可读且归属真实编辑者/无roomID推送/双格式恢复 | 当前新提交仍JSON、Agent为Doc Service | 本轮直接实现，不接管ADR41设计 |
| #17/#24 可移植名称/碰撞 | GitDocs._name/_portable_name | 已验CJK/dots/spaces/NFC/casefold |
| #22 5ms/16ms与零改写 | sourcePerformance/optimized.json | 固定样本与现有main测试已验，不是全设备指标 |
| #23 空段标记/#25 properties/H1 | sourceMarkdown/readMarkdown | 已合入且有回归 |
| #18 ADR0002/单writer/TS/CRDT/生产grants | PR41 Proposed，原贡献者operation-ID P2未解决 | 保留负责人范围；不以此阻塞#16；不可自行把Proposed当Accepted |
| 搜索/附件/多端/公网生产 | 原始四模块与验收未定义 | 不能凭速查“待对照”扩展成新产品需求 |

## 当前切片：Issue16

新commit使用可读subject和只含hash/path的trailers；完整通知与operation放在不推送的本地Git intent refs，必须先于唯一main分支提交点写入。提交失败的孤立intent不产生通知。旧JSON commit仍读取。远端普通main导入通过hashed operation保持幂等，只有匹配原请求的重试可重建其本地通知意图。作者对人类沿用已认证Matrix用户，对Agent取权威Gateway task的托管Agent身份。内容与版本仍只在Git，不另建正文数据库。正常push只发送main，不发送私有refs；备份必须包含完整bare仓库，丢失私有refs不能声称无损恢复通知。旧commit的已泄露元数据不重写。

修改src/gitdocs.py、src/agent_document_api.py及对应测试/运行smoke/文档。保留请求hash旧格式兼容；不引入#12索引改造，不改operation ID作用域，不改ADR41。

完成标准：新远端git log可读/正确author，无合成room/task marker；旧JSON与新格式崩溃/通知恢复、远端同请求重试和不同请求拒绝、main CAS前失败无幽灵通知均有测试；真实Matrix→Agent→Git→回执smoke验证；完整Python、前端与最终SHA CI通过；独立review无阻塞；正常expected-head合入后核验新main CI。

## 真实验收边界

当前工具列表无受支持浏览器/GUI工具，未发现已安装playwright/chromium。禁止旧native GUI/剪贴板路径，不读系统剪贴板/历史、不改权限。后续只评估可隔离合成fixture的受支持headless路线；物理IME/拖拽等不能用jsdom或截图代替。生产发布、TLS/真实账户/持久访问不属于此轮仓库授权。

## 2026-10-20范围纠正与下一实际切片

父端恢复原对话V0.2场景与技术V0.1清单，证实附件/搜索/多文档/消息转文档/Agent注册能力授权/真实进度/Git关联引用等属于原规划。上方“未发现独立PRD文件”只是仓库检索结果，不能推出原产品无PRD；“搜索附件多端未定义”的旧判断被新来源覆盖。V0.3全文及MVP分级仍待恢复。完整当前代码对照原位更新docs/MVP_ACCEPTANCE.md。

选择消息历史分页：客户端原最近50条截断，后端已有限定room的Matrix游标转发；实现timelinePage与加载更早消息，去重、稳定游标重试、迟到房间响应隔离、加载旧消息保留滚动。真实Synapse新合成room发送65条后取两页/重试/期间第66条并去重验证；接入现有CI SDK步骤。保持单身份/单文档等实际缺口，不把分页称完整thread或搜索。未触碰Issue12/ADR41，原拟inline source切片尚无代码变更即改选确认优先项，未创建第二执行者。

## 完整线程与正文搜索（2026-10-20 续轮）

用户明确继续完整Thread后正文搜索。线程以SDK relations读取固定root与m.thread消息，独立于已加载时间线；50条反向分页、流序、去重、空页游标、错误原游标重试和房间/线程迟到隔离。现有房间白名单不变；仅增加固定v1 relations GET代理，强制limit50/dirb，拒绝身份覆盖和其他relation路由。保留synthetic旧接口兼容说明，不将其当真实后端验收。验证包括旧root在最近50之外、超过50回复、重试、滚动锚点、切房间及真实Matrix/隔离浏览器。

#52–54依赖/审查/贡献范围已复核，全部精确CI通过；尝试按本轮合入授权将52转ready被自动审批拒绝，理由是旧“新PR保持draft”约束。停止该动作，无替代合入路径。该阻塞不停止线程与搜索实现。Issue12和PR41仍不接手。

正文搜索：Matrix固定当前allowed room/content.body/recent/20，Opaque token分页，不接受客户端filter/identity。Git regular Markdown固定可达main历史snapshot，literal大小写不敏感匹配正文行；50文件scan/20匹配文件分页，超64KiB/非文本显式跳过，不能把未扫完空页当无结果。UI独立搜索弹窗，query/cursor/commit稳定重试、去重、context/seq隔离；打开文档匹配版本沿用现有草稿保护，消息结果打开独立thread。无持久索引，不恢复12，不改41授权设计。


## Message attachments candidate (2026-10-20)

The message composer uploads a file of up to 5 MiB as m.file. The server uses the current Matrix identity and checks joined, unencrypted room access and message power levels. Downloads require a canonical file event in an allowed room and a CSRF token. Only local-homeserver media is accepted. Downloads use attachment disposition, application/octet-stream and nosniff. No remote redirects or inline HTML rendering are allowed.

An uncertain send keeps the original bytes, operation UUID and thread root. A retry reuses the cached media URI and Matrix message transaction. Losing an upload response before the URI is recorded can leave an orphan media object; exactly-once media storage is not claimed. Markdown embedding, inline images, encrypted files and remote media remain pending.

161 full Python tests and 155 frontend tests plus build passed. Final targeted76 frontend tests/build passed after the file-message selection guard. Actual Matrix protocol proved byte-exact download, one message on retry, conflicting bytes409 and ungranted room403. Isolated installed Chrome used the real file input, injected a lost response after server commit, retried the same operation/root, downloaded57 exact bytes and did not execute HTML. Evidence: .local/attachments/protocol.log, browser-proof.json and preview.png. CI runs attachment-smoke.mjs; final commit CI must be checked separately.


## Message quotes candidate (2026-10-20)

Quote is separate from Reply in thread. It sends m.in_reply_to metadata and the user's own text, without copying source text or adding implicit mentions. A quote of a threaded message retains its thread root. The existing server validates relation fields and reads each referenced event through the current allowed room. Canonical quoted text loads independently of the recent timeline, with retry and room/request isolation. The source is rendered as text and can open in the existing thread reader. Legacy reply fallback is removed only with its recognized sender header; ordinary user blockquotes and leading blank lines remain.

Unknown send results retain original room, content, quote, thread and transaction. Editing and cancelling are disabled until retry resolves the operation. Switching rooms permits separate messages and keeps the earlier unknown operation. No new credentials, grants, membership routes or Agent registration design are added.

Initial159 full frontend tests/build passed, followed by final79 focused tests/build after independent review fixes. Final12 HTTP tests passed; the first sandbox run could not bind three loopback servers and was rerun with scoped execution permission. Actual Matrix proved source outside recent50, canonical relation/body, no implicit mention and same-transaction retry. Isolated installed Chrome showed historical source, literal HTML, real Quote composer, preserved blockquote text and opened source. First browser selector matched both body and quoted preview; scoped it to direct message body, then passed without product changes. Evidence .local/quotes/{protocol.log,browser-proof.json,preview.png}. Complete Python and exact-head CI are recorded separately.


## Fixed Git source line references (2026-10-20)

Git source opens files in existing RepositoryReader grants. POST /api/repositories/read accepts only room/repository/path and uses the current Matrix identity. The room must be allowed, joined and unencrypted. The reader retains its fixed commit, file allowlist, sender/room grants and 8000-byte limit. No local path or client-selected revision is accepted.

Select one to50 lines and an excerpt of at most3500 characters. The message carries repository/path/commit/blob/start/end metadata and canonical text. The server reads the granted Git object again and rejects mismatched metadata/body, Agent mentions or document commands. Matrix still enforces message send permissions. A reference opens only if its exact commit/blob remains in the current grants. An unavailable earlier grant is shown as unavailable; arbitrary history access is not added. Unknown sends lock the original excerpt and transaction for retry. Source text remains literal and uses no HTML execution or OS clipboard.

Initial165 full frontend tests, final79 focused tests and build, plus16 backend/HTTP tests passed. Existing source-reader tests cover Git object and grant boundaries; added service tests cover live membership/encryption, revision/blob/line checks and excerpt limits. Real Git/Matrix protocol passed canonical source read/message, same-transaction retry, spoofed body400 and traversal/ungranted-room/revision override403. Isolated installed Chrome selected line2, injected a lost response after commit, retried one event and opened the same commit/blob at line2. Evidence .local/sources/{protocol.log,browser-proof.json,preview.png}. Independent static review found no initial blocker. Final full Python/CI are recorded separately. Directory browsing, repository association configuration and PR references remain pending.
