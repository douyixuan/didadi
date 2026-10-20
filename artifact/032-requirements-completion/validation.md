# 实现与验证

当前阶段：部分验证。当前切片为Issue16；不将全部平台需求标完成。

- 首次用系统Python运行时9模块缺少websockets，属未装声明依赖；随后新建本分支.venv、安装requirements-runtime.txt，完整132项Python通过（109.624秒）。整改审查发现后单独5项metadata测试通过（12.662秒）；最终完整133项由提交CI继续核验，不能把两次运行数字相加。
- 独立合成项目didadi-requirements，Matrix8048/Gateway9110，真实Matrix/AS/非管理员fixture通过。agent_body_api_smoke通过：独立WS外部runtime无Git路径，scopedHTTP写读，真实本地bare remote正常main push；作者=托管Agent、subject可读，远端log无合成room/task ID、无私有intent refs；元数据回执、同请求幂等、不同正文冲突与outbox reconcile通过。
- metadata测试覆盖新/旧JSON格式、旧无作者hash的原提交重试、远端导入main后完整请求匹配重建本地路由、不同请求拒绝、CAS前失败无幽灵通知、损坏/缺字段intent显式失败。
- 既有multiprocess退出73→重开恢复测试在完整Python中通过；不宣称掉电/磁盘损坏恢复。通知私有refs不是可删派生索引，完整bare备份要求已文档化；旧已发布JSON历史不重写。
- 未修改任何前端产品源码；正在构建并评估独立headless测试路线，实际结果另记。GUI/剪贴板禁用、物理IME/拖拽和生产发布未验。

私有运行日志：.local/requirements/logs/；不提交fixture、凭据或数据库。源码包v13保留为历史已验归档，本分支不冒称该旧包包含本轮代码。

恢复边界补验：7项metadata测试通过（12.150秒），新增CAS失败→另一store发布不同时间的同operation→导入，以及显式GC清理旧候选后同一路径；错误请求保留原intent，匹配请求返回已发布commit并恢复pending。首个head push/PR CI均通过，因自动审查新增恢复修复，必须等待新head CI，不沿用旧绿。

## 2026-10-20消息历史切片（候选）

- 新源依据来自父端恢复的原始产品对话，不再用Phase0四模块代替全部PRD；docs/MVP_ACCEPTANCE原位完整功能对照，并标明V0.3全文/优先级仍待证。
- 63项定向前端测试通过；早期完整125项通过后，针对review新增非单调timestamp/空前进页/并发刷新与历史gap回归，最终全量另验。初次新测试有括号语法错误，已修；thread scope文案改变导致旧label断言失败，改为独立span保留原label并明确loaded scope，未删回归。
- 实际Matrix/Synapse8048、Gateway9110、独立client8832：65历史消息跨页完整、相同游标重试一致、期间新增第66条保留且不重复，通过。review要求保留Matrix流顺序和空页前进游标，均整改后相同真实protocol复验通过。
- 实际无权限隔离headless Chrome点击Load earlier：初始只见最近50，加载后65条、无重复，视口anchor top1640/height7165/viewport500；刷新新增第66条后旧第0条仍保留。无OS IME、剪贴板或用户profile访问，不冒称物理GUI。
- 独立最终只读复核两项P2已修、无新增阻断；完整thread、搜索、多文档等仍为真实缺口，不因这个切片通过而宣称全部完成。最终headCI、合入后mainCI另验。

## 2026-10-20 Named document candidate

The isolated workspace-documents branch adds regular Markdown file listing, path creation, opening, human direct Git saves, fixed history and separate local drafts. API retries reuse the operation UUID; duplicate paths and portable-name collisions cannot overwrite existing text. Room checks remain bound to the original document room. Agent document actions remain limited to demo.md; move/rename and from-messages are still missing.

Before the final pagination integration, 143 Python tests and 135 frontend tests passed. The integrated candidate adds a delayed-create/storage-failure regression, with 63 App tests passing. The first full Python attempt was sandbox-denied for loopback binds (25 errors); the permitted rerun passed all 143. This was an execution limitation, not a passed first run.

Real loopback preview 8834 uses its own Git repository and metadata. documents-smoke.mjs passed create/retry/list/two-file save isolation/fixed history/duplicate rejection/invalid paths. Isolated headless installed Chrome passed A unsaved draft, B direct Git save, A restoration/save, independent Git contents and reopening after reload. Evidence stays under .local/multi-documents; no physical IME or drag acceptance is claimed. An independent reviewer found and rechecked a delayed-create navigation race; the added latest-state check keeps the current editor mounted when it becomes unsafe to leave.

## 2026-10-20 Atomic move/rename candidate

Separate worktree didadi-document-move, based on draft52/head80c0ff1. Same bound-room authorization, metadata-only Matrix receipt and private operation intent recovery. The source removal and destination insertion share one private index/main CAS; request hashes bind the source path. The source blob must still match and the destination must not exist. A repeated request resolves its original operation before checking the removed source. Existing write hashes and legacy compatibility remain unchanged.

147 full Python tests and 138 frontend tests/build passed before adding the recovery-draft navigation guard. Final targeted backend/HTTP tests23 passed, covering actual route retry, source removal, target bytes, cross-room denial, competing moves and publication failure recovery. Final App recovery guard regression/build results are recorded in the PR. The first targeted move test found bare Git force-remove requires a worktree; switched to index-info deletion, then12service tests passed. No disk checkout is used.

Real preview8836, separate bare Git and metadata: protocol smoke proved CRLF-exact content/blob, historical original-path reads, idempotent move, stale-source rejection. Installed isolated headless Chrome proved actual Move form, same content at destination, source disappearance and reload/reopen. Screenshot/proof under .local/move. Reviewer found no blocking static issue. Prior paths remain readable by fixed commit; current UI history does not follow renames. Pending recovery drafts block moving, avoiding hiding their recovery entry. Case-only name collisions remain explicitly rejected.

## 2026-10-20 Selected messages to document candidate

Independent didadi-messages-to-document worktree, initially based53/b723651. API accepts only room/name/events/operation, checks existing bound-room write access, fetches each canonical Matrix event and validates ID/room/type/text. It generates deterministic literal fenced text and source links, no LLM. One to20 distinct IDs, all sources available, final64KiB; invalid sets leave no partial document. Existing create operation/receipt rules prevent duplicate or overwrite.

150 full Python and141 full frontend/build passed; final HTTP/service assertions added for canonical source, route retry and spoofed-body rejection. Actual loopback8838 protocol passed real two-event Matrix→Git, source URLs, unchanged canonical text, safe long fences, same-UUID retry, client-body/cross-room rejection and no partial file after missing source. Existing isolated headless Chrome selected two actual checkboxes, created the document, showed two links and verified canonical Git bytes, without executing literal HTML. Screenshot/proof under.local/from-messages. UI retries fixed selection/name/UUID and keeps current dirty drafts mounted. Independent static review found no blockers; corrected unavailable-source wording to avoid denying a possible earlier committed attempt. Source redaction after an uncertain save may block re-reading; inspect the file list, do not imply no previous document exists. Plain text/bound-room scope only.

Move candidate headb723651 first pushCI39408902567 failed one frontend fixture (138/139 passed); backend and real Matrix jobs passed. The create/list-failure fixture clicked demo.md while the control was still intentionally disabled by document/draft loading. Added an explicit enabled-state wait before navigation; targeted66 App tests passed. This is a test synchronization fix, not a product navigation bypass. New exact-head CI remains required.

## 完整线程候选（2026-10-20）

SDK relations独立取root+50回复，现有白名单固定v1 GET，无身份覆盖或授权设计扩张。完整145前端/build、最终75定向/10HTTP通过；新增初始空线程后新页游标回归。151完整Python结果另见候选PR。真实Matrix root在recent50之外、66回复两页/同cursor重试/流序去重通过。隔离已安装Chrome验证67条root+replies、注入root/older失败后重试、原cursor、compose保留、scroll top2697/height11371/view398、切房间隐藏旧thread。浏览器首轮选择器错误导致超时，修正ownedDOM选择器后通过；未为此修改产品。Review静态无阻断，已按建议将Complete thread改为Thread history避免把未加载页说成已加载。证据.local/threads，未验物理IME/拖拽。

## 正文搜索候选（2026-10-20）

155完整Python/151完整前端/build通过，4搜索service及25定向后端通过。真实8842/Matrix查到24条已超recent50的正文命中、两页取回；Git21份文件名无查询词、正文第3行命中，20+1分页同snapshot，未授权房间拒绝。隔离已安装Chrome完成24消息分页并打开历史thread；文档第一页后将第21份当前内容改写，注入一次分页503后同query/cursor/commit重试保留20结果，最终21结果并打开旧匹配版本；当前Git仍是新内容。证据.local/search/protocol.log/browser-proof.json/results.png/preview.png。首次protocol请求早于server启动ECONNREFUSED已保留protocol-startup-race.log，确认监听后重跑成功。Reviewer静态无阻断。最后补房间类型400验证；精确提交CI仍需观察。


## Message attachments candidate (2026-10-20)

The message composer uploads a file of up to 5 MiB as m.file. The server uses the current Matrix identity and checks joined, unencrypted room access and message power levels. Downloads require a canonical file event in an allowed room and a CSRF token. Only local-homeserver media is accepted. Downloads use attachment disposition, application/octet-stream and nosniff. No remote redirects or inline HTML rendering are allowed.

An uncertain send keeps the original bytes, operation UUID and thread root. A retry reuses the cached media URI and Matrix message transaction. Losing an upload response before the URI is recorded can leave an orphan media object; exactly-once media storage is not claimed. Markdown embedding, inline images, encrypted files and remote media remain pending.

161 full Python tests and 155 frontend tests plus build passed. Final targeted76 frontend tests/build passed after the file-message selection guard. Actual Matrix protocol proved byte-exact download, one message on retry, conflicting bytes409 and ungranted room403. Isolated installed Chrome used the real file input, injected a lost response after server commit, retried the same operation/root, downloaded57 exact bytes and did not execute HTML. Evidence: .local/attachments/protocol.log, browser-proof.json and preview.png. CI runs attachment-smoke.mjs; final commit CI must be checked separately.


## Message quotes candidate (2026-10-20)

Quote is separate from Reply in thread. It sends m.in_reply_to metadata and the user's own text, without copying source text or adding implicit mentions. A quote of a threaded message retains its thread root. The existing server validates relation fields and reads each referenced event through the current allowed room. Canonical quoted text loads independently of the recent timeline, with retry and room/request isolation. The source is rendered as text and can open in the existing thread reader. Legacy reply fallback is removed only with its recognized sender header; ordinary user blockquotes and leading blank lines remain.

Unknown send results retain original room, content, quote, thread and transaction. Editing and cancelling are disabled until retry resolves the operation. Switching rooms permits separate messages and keeps the earlier unknown operation. No new credentials, grants, membership routes or Agent registration design are added.

Initial159 full frontend tests/build passed, followed by final79 focused tests/build after independent review fixes. Final12 HTTP tests passed; the first sandbox run could not bind three loopback servers and was rerun with scoped execution permission. Actual Matrix proved source outside recent50, canonical relation/body, no implicit mention and same-transaction retry. Isolated installed Chrome showed historical source, literal HTML, real Quote composer, preserved blockquote text and opened source. First browser selector matched both body and quoted preview; scoped it to direct message body, then passed without product changes. Evidence .local/quotes/{protocol.log,browser-proof.json,preview.png}. Final full Python: 162 passed in 122.961 seconds. Exact-head CI remains required.


## Fixed Git source line references (2026-10-20)

Git source opens files in existing RepositoryReader grants. POST /api/repositories/read accepts only room/repository/path and uses the current Matrix identity. The room must be allowed, joined and unencrypted. The reader retains its fixed commit, file allowlist, sender/room grants and 8000-byte limit. No local path or client-selected revision is accepted.

Select one to50 lines and an excerpt of at most3500 characters. The message carries repository/path/commit/blob/start/end metadata and canonical text. The server reads the granted Git object again and rejects mismatched metadata/body, Agent mentions or document commands. Matrix still enforces message send permissions. A reference opens only if its exact commit/blob remains in the current grants. An unavailable earlier grant is shown as unavailable; arbitrary history access is not added. Unknown sends lock the original excerpt and transaction for retry. Source text remains literal and uses no HTML execution or OS clipboard.

Initial165 full frontend tests, final79 focused tests and build, plus16 backend/HTTP tests passed. Existing source-reader tests cover Git object and grant boundaries; added service tests cover live membership/encryption, revision/blob/line checks and excerpt limits. Real Git/Matrix protocol passed canonical source read/message, same-transaction retry, spoofed body400 and traversal/ungranted-room/revision override403. Isolated installed Chrome selected line2, injected a lost response after commit, retried one event and opened the same commit/blob at line2. Evidence .local/sources/{protocol.log,browser-proof.json,preview.png}. Independent static review found no initial blocker. Final full Python: 166 passed in 116.656 seconds. Independent static re-review of the source-opening entry found no blocker. Final exact-head CI remains required. Directory browsing, repository association configuration and PR references remain pending.

PR59 head4b3a281 push39418286428 attempt1 failed search-smoke filler51 with429; frontend/backend passed. PR39418291225 passed all3 jobs; only failed push job was rerun, attempt2 succeeded. These are separate outcomes. Host transport disconnected after launching final browser; after recovery, browser-final-lines.log confirms success and clean worktree. The final line-number fix now omits a trailing terminator from displayed rows.

The observed429 led to a separate fix: preserve numeric retry_after_ms in the loopback error, and let five fixture transports honor the larger server body/header hint while keeping the same URL/options/transaction. At most8 attempts and60seconds waiting; an excessive hint returns429 without an early retry. Other errors and network failures are not retried.7 focused frontend and14 HTTP tests/build passed. Actual sequential thread/search/quote/attachment/source protocols all passed on8848; this does not claim the local run itself encountered429. Independent static review found no blocker. No rate limit was disabled. Final commit CI is required.


## Granted source directory browser (2026-10-20)

The source viewer groups the current room's existing repositoryReads entries by repository alias and path segments. Native details controls collapse or expand folders; leaf buttons retain the original file index and show the selected file. The same filename in different repositories or folders stays distinct. Files cannot switch while sending, after an unknown send, or when opening an exact reference. This is a view of granted files only: it does not scan Git trees, discover ungranted filenames or create credentials/grants.

172 full frontend tests and build passed;7 focused directory/viewer tests cover nested paths, duplicate names, correct file selection, locked selection and excluding another room. Independent static review found no blocker. Actual8850 Git/Matrix plus isolated installed Chrome passed collapse/expand of the existing synthetic-example grant, literal source read, selecting line2, response loss after commit/same transaction retry and reopening commit/blob/line2. Evidence .local/directories/{protocol.log,browser-proof.json,preview.png}. The real fixture grants only flat example.py; nested directory paths have unit evidence only. No new fixture grant was added. Exact commit CI remains required.


## Read-only room people (2026-10-20)

People shows the current local session identity and the joined/invited members visible in the selected room's existing Matrix state response. It uses the existing allowed state route and server-held identity. Names and IDs render as text; avatar URLs are ignored. Refresh failure clears the previous list; retry and room changes ignore late requests. The dialog supports Escape, trapped focus and restoring focus to the entry button. If retry removes its focused button, focus returns inside the dialog. No login/logout, invite/kick, roles, Agent registration, credential or grant changes are added. This is not a claim that the full membership product is complete.

176 full frontend tests/build and final4 focused tests/build passed. Actual Matrix SDK read returned the current human and visible joined members, omitted avatar URLs and rejected an ungranted room403. Isolated installed Chrome showed the same members, injected a refresh failure and confirmed the list cleared, retried successfully and closed with Escape/focus restoration. First browser run found that removing the retry button left focus outside the dialog and Escape failed; preserved that log, added the focused retry regression and corrected focus restoration, then the real browser passed. Evidence .local/people/{protocol.log,browser-focus-retry.log,browser-proof.json,preview.png}. Independent static review found no initial blocker. Final exact-head CI remains required.


## Private room types candidate (2026-10-20)

A private conversation has the creator and one explicitly configured local human. Groups support selected local humans. Channels are named private discussion rooms, without public discovery or broadcast roles. All new rooms are invite-only, private in the directory, guest-forbidden, history-visible from invitation and non-federated. The example Agent is absent by default; groups and channels may explicitly opt in after showing that it can read the room. Direct conversations cannot add the Agent. Existing rooms keep their state.

Creation binds the actor, name, type, participants and Agent option to a durable operation. A deterministic Matrix alias recovers an unknown result. Before admitting the room, the server verifies its original creator/marker, exact active roster and privacy state. Concurrent retries serialize locally. Changed options or changed recovery membership are rejected. A partially successful native Matrix room/invitation can remain if later verification fails; exactly-once underlying room resources are not claimed. Matrix is_direct marks the invitation; m.direct account-data synchronization is deferred.

Contacts come from explicit ID configuration only. The smoke helper verifies the existing isolated Alice/Bob identities and writes Bob's ID, with no credential copy or new identity. It rejects other identities and replacement configurations. No general invitations, real third-party contact discovery, login/logout, role editing, production grants or Agent registration are added.

Validation: 21 focused backend/HTTP tests and 180 full frontend tests plus build passed. Actual Synapse showed private/non-federated rooms, two-way synthetic Alice/Bob messages, one room for a repeated operation, changed options409, external contacts403 and unsupported public visibility400. Agent mention in a no-Agent room was rejected before send; only the opt-in channel included the Agent. Isolated installed Chrome verified default Agent off, direct selection, invited/joined People consistency and identical-operation retry after losing the committed response. Evidence: .local/rooms/protocol.log, browser-proof.json and preview.png. Independent review found extra recovered group/channel members were accepted; exact-roster verification and a regression now reject them.

Earlier local validation failures are preserved: system Python lacked websockets before launch; the first protocol call raced server startup; one browser selector matched both current identity and roster. The corrected venv/ready server/scoped locator passed. An unprivileged full Python run could not bind temporary test servers and was interrupted; the allowed loopback run is recorded separately. Final full Python passed: 176 tests in 184.822 seconds, including the fixture-helper regressions. Independent static re-review confirmed the roster fix and found no remaining material blocker; it did not execute tests. Exact-head CI remains required. Physical IME, external contact accounts, cross-client m.direct interoperability and production login are not verified.
