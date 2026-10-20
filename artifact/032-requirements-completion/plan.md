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


## Granted source directory browser (2026-10-20)

The source viewer groups the current room's existing repositoryReads entries by repository alias and path segments. Native details controls collapse or expand folders; leaf buttons retain the original file index and show the selected file. The same filename in different repositories or folders stays distinct. Files cannot switch while sending, after an unknown send, or when opening an exact reference. This is a view of granted files only: it does not scan Git trees, discover ungranted filenames or create credentials/grants.

172 full frontend tests and build passed;7 focused directory/viewer tests cover nested paths, duplicate names, correct file selection, locked selection and excluding another room. Independent static review found no blocker. Actual8850 Git/Matrix plus isolated installed Chrome passed collapse/expand of the existing synthetic-example grant, literal source read, selecting line2, response loss after commit/same transaction retry and reopening commit/blob/line2. Evidence .local/directories/{protocol.log,browser-proof.json,preview.png}. The real fixture grants only flat example.py; nested directory paths have unit evidence only. No new fixture grant was added. Exact commit CI remains required.


## Identity, membership and Agent gap audit

This is a source audit, not an authorization design change. client_server.py uses state.tokens[0] for the current human and exposes a fixed session. Its proxy only reads joined rooms/state/messages/events or sends m.room.message; create_room invites the fixed example Agent. There are no human login/logout, invite/join/leave/member-role client routes in that adapter. matrix_as.py defines one AGENT and agent_auth compares one configured token. Its GET routes are tasks/audit/status/health; POST routes are complete/fail/validate/cancel/document-scope/runtime. runtime_socket.py forwards a fixed subset and runtime observations report connected/session, not model progress. Generic Agent registration, capability discovery and runtime-authored progress remain missing in those handlers. This does not deny that Synapse itself supports identity and membership APIs.

PR41 head7067385f33cfec1367c5ed821c761165e548c7fa remains a Proposed Document Service ADR covering direct IO, repository writers, Matrix authorization and scoped/revocable Agent grants. Do not change or take over those proposals. Agent grant/registration design needs coordination with that owner. The current work adds no persistent credential, homeserver configuration, new human identity or expanded source grant. A concrete implementation that needs such configuration must report the exact need before configuring it. Issue12 remains paused.


## Read-only room people (2026-10-20)

People shows the current local session identity and the joined/invited members visible in the selected room's existing Matrix state response. It uses the existing allowed state route and server-held identity. Names and IDs render as text; avatar URLs are ignored. Refresh failure clears the previous list; retry and room changes ignore late requests. The dialog supports Escape, trapped focus and restoring focus to the entry button. If retry removes its focused button, focus returns inside the dialog. No login/logout, invite/kick, roles, Agent registration, credential or grant changes are added. This is not a claim that the full membership product is complete.

176 full frontend tests/build and final4 focused tests/build passed. Actual Matrix SDK read returned the current human and visible joined members, omitted avatar URLs and rejected an ungranted room403. Isolated installed Chrome showed the same members, injected a refresh failure and confirmed the list cleared, retried successfully and closed with Escape/focus restoration. First browser run found that removing the retry button left focus outside the dialog and Escape failed; preserved that log, added the focused retry regression and corrected focus restoration, then the real browser passed. Evidence .local/people/{protocol.log,browser-focus-retry.log,browser-proof.json,preview.png}. Independent static review found no initial blocker. Final exact-head CI remains required.


## Private room types candidate (2026-10-20)

A private conversation has the creator and one explicitly configured local human. Groups support selected local humans. Channels are named private discussion rooms, without public discovery or broadcast roles. All new rooms are invite-only, private in the directory, guest-forbidden, history-visible from invitation and non-federated. The example Agent is absent by default; groups and channels may explicitly opt in after showing that it can read the room. Direct conversations cannot add the Agent. Existing rooms keep their state.

Creation binds the actor, name, type, participants and Agent option to a durable operation. A deterministic Matrix alias recovers an unknown result. Before admitting the room, the server verifies its original creator/marker, exact active roster and privacy state. Concurrent retries serialize locally. Changed options or changed recovery membership are rejected. A partially successful native Matrix room/invitation can remain if later verification fails; exactly-once underlying room resources are not claimed. Matrix is_direct marks the invitation; m.direct account-data synchronization is deferred.

Contacts come from explicit ID configuration only. The smoke helper verifies the existing isolated Alice/Bob identities and writes Bob's ID, with no credential copy or new identity. It rejects other identities and replacement configurations. No general invitations, real third-party contact discovery, login/logout, role editing, production grants or Agent registration are added.

Validation: 21 focused backend/HTTP tests and 180 full frontend tests plus build passed. Actual Synapse showed private/non-federated rooms, two-way synthetic Alice/Bob messages, one room for a repeated operation, changed options409, external contacts403 and unsupported public visibility400. Agent mention in a no-Agent room was rejected before send; only the opt-in channel included the Agent. Isolated installed Chrome verified default Agent off, direct selection, invited/joined People consistency and identical-operation retry after losing the committed response. Evidence: .local/rooms/protocol.log, browser-proof.json and preview.png. Independent review found extra recovered group/channel members were accepted; exact-roster verification and a regression now reject them.

Earlier local validation failures are preserved: system Python lacked websockets before launch; the first protocol call raced server startup; one browser selector matched both current identity and roster. The corrected venv/ready server/scoped locator passed. An unprivileged full Python run could not bind temporary test servers and was interrupted; the allowed loopback run is recorded separately. Final full Python passed: 176 tests in 184.822 seconds, including the fixture-helper regressions. Independent static re-review confirmed the roster fix and found no remaining material blocker; it did not execute tests. Exact-head CI remains required. Physical IME, external contact accounts, cross-client m.direct interoperability and production login are not verified.


The first committed head8356766 passed all three jobs in push39426107868 and PR39426155877. A later repeated local protocol got503 (unconfirmed creation); its upstream cause was not captured and is not asserted to be429. A stale launcher record pointed to dead72521 while the actual owned listener65042 remained; the exact listener command was verified, then only that process was stopped and final source restarted, retaining Git/SQLite. Failed restart/protocol logs remain separate.

The follow-up preserves Matrix429 and the existing sanitized retry_after_ms HTTP response instead of converting it to generic503. The intent remains bound, and the UI already freezes429 for the same-operation retry. The protocol fixture waits only on429, at most8 attempts/60seconds, respecting its body hint with the identical request. No rate setting changes,503 retry or attribution of the earlier503 to throttling is made.24 targeted backend/HTTP/helper tests passed. This follow-up requires its own exact-head CI; the earlier green runs are historical evidence for8356766.

## 当前用户的私聊偏好与登录审计（2026-10-20）

本切片在候选62上添加标准 Matrix m.direct 账户数据同步，不修改 PR41 Proposed Document Service ADR/通用Agent授权归属。账户数据是当前人的偏好，不是房间访问权；任何远端映射均不能把未获准房间纳入本地 allowed 集。创建私聊后独立持久化 actor/room/peer 的待同步项，失败保留已建房间，专用端点只重试既有绑定，不接受任意人/账户数据对象。每次先读最新整图再加自己的room，验证并有界再读；成功后尊重其他客户端删除，不自动复活旧偏好。远端标签通过刷新/10秒轮询读取，浏览器只得 allowed且joined房间的标签，原始account_data不开放代理。标准整事件PUT无CAS，无法保证未观察到的任意并发写入无损；不以有界回读冒称原子合并。

验证规划：合并保留既有私聊/失败GET零PUT/PUT已提交丢响应/持久receipt重建/远端更新和删除/身份和房间边界；真实隔离Synapse通过现有Alice身份的独立原生HTTP客户端与本地受限适配器，核对m.direct、标准sync账户事件及重试。独立原生HTTP客户端复用既有合成token，不声称新设备token/另一个真实账户。保持实际429重跑未通过记录，不关限流。前端覆盖独立pending反馈、失败重试、不重复创建、刷新/迟到隔离。

登录/注销最小安全切片审计：当前Workspace使用state.tokens[0]与全局csrf、Git/SQLite和固定documentRoom，浏览器只有占位token，未实现用户认证会话。直接POST logout会撤销所有共用该测试token的旧预览，禁止把它接到现有界面。首个可真实验收切片应是一个独立临时device/session的登录与仅当前设备注销，采用服务端token保存、随机HttpOnly/SameSite会话cookie、每会话CSRF/TTL/注销失效、身份隔离的Workspace和仓库/房间映射；不得沿用Alice的文件/receipt/授权给Bob。生产需要HTTPS/安全cookie与明确SSO/OAuth或密码流程；不把任意homeserver URL作为可请求目标，不将密码/token放URL、日志、浏览器存储或Git。权限仍由现有Matrix/资源服务核验，不借认证流程接管PR41的Agent grants。

真实登录验收所需的具体追加步骤供父端审批：只在独立隔离Synapse的已有合成账户，为本次验收创建一个临时设备会话（可能产生短时测试token），只保存在测试进程内存，使用独立cookie jar和repo/metadata；核对whoami/切人隔离/CSRF/过期；仅注销这个新device token并证明旧共享fixture token仍有效，最后销毁内存会话。不得读取真实用户密码，不生成/配置生产凭据、不扩大持久权限。本轮没有执行新设备登录或撤销任何现有token；无此追加步骤时只交付审计，不伪称真实登录/注销已实现或验证。

## 虚构登录/注销服务契约（2026-10-20）

父端明确授权不依赖真实会话的UI/接口/内存隔离实现；既有33报告仍正确描述真实Matrix登录未做。独立候选新增完全独立的contract入口和loopback server，不接入Workspace固定token、不导入Matrix认证、不创建真实凭据。身份只有Alice/Bob、设备A/B固定虚构值，无密码框。fake session/CSRF相关标识明确非凭据（仅固定虚构身份/设备输入，内部generation防旧标识碰撞）、只在内存中用于契约测试，重启清空；不使用localStorage/cookie保存。此预览没有真实认证保证，界面始终标注虚构数据、未登录Matrix。

接口：login仅接受fixture_identity/device；workspace与文档只能由当前fake session推导身份，不能传user覆盖；文档按身份隔离，房间ID/文档名故意相同以验证不会误用room/path作唯一键。save以每会话operation绑定内容/base_version，未知响应原操作重试；logout仅接受current_device，不存在all_devices动作，另一个设备保持有效。服务对象是可注入契约实现，实际实现只有FakeIdentityService；不写真实登录适配器或接收用户密码。

失败规则：登录失败仅保留选择，不显示旧数据；登录成功/加载失败只保留当前session供重试，401清空身份/房间/文档/草稿。保存失败保留当前草稿，未知结果冻结原请求，换人/注销立即清所有工作区状态并以epoch忽略旧响应。注销发起即隐藏全部数据，只在内存隔离区保留原设备的注销请求；网络/5xx未知则禁止下一登录、仅重试原设备，401视为旧会话已失效。不能把本地隐藏说成服务端注销成功。每次登录新epoch，服务只替换同身份同设备的旧fake session，另一设备不受影响。

验证包括pure fake服务与真实loopback HTTP契约、未知保存/注销响应、过期/401清空、当前设备语义、身份相同room/path碰撞、迟到请求和浏览器内存/网络边界。现有Matrix运行路径保持原样，CI仍运行其完整回归；新增预览单独构建和验收。真实Matrix登录、密码/SSO、安全cookie和真实token撤销仍未完成，需要先前记录的独立临时设备授权，不以fake通过替代。
