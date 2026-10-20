# Document-first React workspace

This local client milestone depends on the Git document/runtime spike (PR #6) and its gateway dependency (PR #5). It uses React, Vite and **matrix-js-sdk** for real room membership/state, timeline reads, message sends, thread relations and stable outbound transaction IDs. It is not a static screenshot or an LLM UI.

## Start from a fresh checkout or archive

Follow [LOCAL_WORKSPACE.md](LOCAL_WORKSPACE.md). The guide creates fresh local test users, a private room, a synthetic read-only source and a separate Git document repository. It installs the runtime dependency, builds the client and starts the scoped Document API with an external WebSocket worker. It does not require another checkout's credentials or processes.

The default screen is a document, not a message dashboard. The left sidebar lists regular Markdown files in the workspace Git repository and real allowed rooms. Create document accepts a relative Markdown path; each file has independent reads, saves, history and local drafts. Read renders Markdown safely; Edit opens a Milkdown Crepe block editor with direct body editing, slash insertion, task lists, code blocks, drag handles and undo/redo. Save writes directly through the same-origin Document Service to Git; Matrix receives metadata-only version receipts. Human saves do not require the Agent worker. Explicit source read/report tasks use the external worker and scoped Document API. History opens fixed commit snapshots; a stale edit shows a conflict and preserves the draft until the user explicitly loads the latest version.

Discussion and Example Agent are optional right panels. The example is labeled deterministic echo/no LLM. Room messages, thread replies and task completion are real. Version receipts and task IDs are collapsed in details. No fake multi-document tree, unimplemented sharing buttons, rich collaboration cursors or intelligent edits are shown.

Rooms can be selected or created as private local test rooms using the existing non-admin fixture identity. The managed example Agent is invited through the same verified AS flow. Creation retries use a deterministic alias and a local operation record. Message retries reuse Matrix transaction IDs; direct saves reuse their UUID and original payload; repeated clicks are gated while pending. Switching rooms keeps unsent chat drafts in memory. The document repository is bound to the seeded workspace room. Selecting another discussion room does not rebind or discard the document draft. Cross-room document access is rejected. This is a development workspace, not a production resource-permission model.

## Development adapter boundary

`src/client_server.py` binds only to `127.0.0.1`. It accepts only loopback backend URLs and uses the existing fixture user token server-side. The SDK's browser-side `local-development-session` string is a placeholder, not a credential. Matrix, AS and worker tokens never appear in the session response or browser assets.

The adapter exposes an allowlist of joined room state/messages/event/send routes, filters joined rooms to the explicitly seeded/created local rooms, disallows user/token overrides, checks CSRF and Host/Origin, and refuses sends in encrypted rooms. Document paths and grants cannot be selected by messages; the service derives task scope from Gateway storage. The gateway independently checks encryption/membership before acceptance and completion. No credentials, account/security settings or public exposure are added. This is a trusted loopback development session, not production authentication or multi-tenant authorization.

Markdown has no raw HTML rendering. React escapes messages, and the adapter serves a same-origin CSP. Static paths cannot leave the build directory. The direct service owns human saves; the scoped API owns Agent document requests. Sending to an invited Agent that has not joined yields a visible retryable error.

## Verification and visual states

```sh
npm --prefix client test
npm --prefix client run build
python3 -m unittest discover -s tests -v
```

Component tests cover the normal reading surface, editable Markdown formatting, loading/failure recovery, conflicts preserving edits, failed request transaction reuse, repeated sends/saves, historical snapshots with inert HTML, and per-room chat drafts. Backend tests cover room/route/identity boundaries, E2EE rejection, idempotent room recovery, CSRF, Host/Origin, static traversal and token non-disclosure.

CI also starts the adapter and an independent document worker against real Synapse/PostgreSQL, then runs `node client/scripts/smoke.mjs`. That SDK regression verifies room reads, duplicate transaction deduplication, external echo reply, Git save/history/conflict and idempotent private room creation. It uses isolated CI data and does not overwrite the user's local preview document.

`scripts.client_visual_qa` is a separate, explicitly labeled visual regression adapter for `loading` and `failure`. It delays/fails only document reads, does not change stored data, and is not enabled in the normal client. Actual normal/save/conflict states were exercised against the real backend. See the design audit in `artifact/004-workspace-client/design.md` and runtime evidence in [VALIDATION.md](VALIDATION.md).

## Remaining scope

Production login/tenant grants, real model runtimes, E2EE, multiple document creation/tree operations, per-room document ACLs, realtime collaborative rich editing, durable task views across browser sessions, full-text search, room administration, network Git remotes and public deployment remain outside this milestone. Search filters the small real local navigation list; it is not a full-text index. The SDK bundles its optional crypto artifacts but this demo does not initialize crypto or claim E2EE. Bundle size tuning and full accessibility certification are not claimed.

## Synthetic hosted UI preview

Build with `VITE_PREVIEW_MODE=synthetic npm --prefix client run build -- --outDir ../.local/vercel-preview`. Upload only that isolated static output. The explicit preview banner identifies browser-only sample data. It uses localStorage for document snapshots, rooms, messages and deterministic example replies; it makes no backend requests. It does not connect Matrix, Git, a remote runtime or an LLM. The normal build retains the real loopback backend.

An anonymous Vercel temporary deployment expires after approximately one hour. It requires no persistent login credentials. A durable hosted environment with a real backend remains separate work.

## Block editor scope

Milkdown Crepe 7.22.3 uses the MIT license. Its ProseMirror/Remark editing state is transient; human saves send Markdown to the direct Document Service, while explicit Agent writes use the scoped API. Supported blocks are paragraphs, headings, bullet/ordered/task lists, quotes, GFM tables, code fences and dividers, with ordinary inline Markdown. Block actions duplicate, delete and move top-level blocks; lists move together. Crepe provides native dragging and slash insertion. Reading mode renders GFM tasks without enabling editing.

The editor retains original source for each top-level Markdown block, including separators and CRLF. Unchanged blocks bypass reserialization. Text edits are patched into the original spelling and validated through the editor parser; structural edits also restore unchanged source lines when that result represents the requested editor tree. Tables are editable. HTML, images, references, footnotes and code metadata remain editable **local source blocks**, while ordinary neighboring blocks stay rich text. Inline unsupported syntax currently makes its containing top-level block source-editable; hybrid inline atoms and persistent block IDs are not implemented. Front matter appears in a collapsed Properties panel. HTML is inert text, and image upload stays disabled.

Markdown does not encode a user-created empty paragraph or separation between adjacent same-kind lists. Empty paragraphs are view state and are omitted from new Markdown saves. Legacy `<!-- didadi:empty-paragraph -->` markers still open and remain byte-exact until a real edit; editing removes them. Undo restores the original bytes. A legitimate `<!-- -->` separator can still keep adjacent same-kind lists distinct. An unclosed code fence is closed before an appended ordinary block so it cannot swallow that block. New/changed structural lines can use normalized Markdown syntax. The Git blob comparison, immutable history and retained recovery draft continue to protect concurrent saves.

`npm --prefix client run roundtrip` verifies a pinned, offline corpus of 24 unmodified public Markdown files plus authored edge cases. `client/test-corpus/manifest.json` records exact source commits, hashes and licenses. Each file is mounted in the real editor view, saved and reopened; each source-locatable block receives a real ProseMirror text insertion and its saved bytes are compared against the exact intended insertion. CI uploads `markdown-roundtrip.json`, including total/opened/fallback files, raw blocks, lossy/unstable saves and unexpected rewritten lines. This small fixed corpus does not reproduce the issue's unpinned 1,010-file survey or establish universal compatibility. Dedicated interaction tests cover rich/raw/table edits, Chinese composition, CRLF, list split and structural boundaries.

Tests use real Milkdown for semantic block round-trip, direct editor changes, block commands, undo/redo, composition events and destruction safety. App workflow tests isolate the editor behind its Markdown interface. Synthetic composition events and Chinese text/paste checks do not establish compatibility with every physical OS IME.

## Export standard Markdown

Use **Export Markdown** below the document to download `demo.md`. It includes the current editor contents, including unsaved changes, or the exact historical snapshot currently open. It retains headings, front matter, code and original source spelling; it does not export rendered HTML or trigger a Git save. Export is disabled during a pending save/read or composition. The hosted synthetic preview downloads only browser-local sample content.

## Follow document versions through discussion

A managed Agent's task reply can offer **Open document version**. It opens the fixed Git snapshot through the same local document grant. Unsaved text is kept in **Preserved draft**. A failed historical read retries that same read; it cannot turn into a save.

**View version discussion** returns to the original receipt thread for the open version. It is enabled only when that receipt is present in the currently loaded timeline. This bounded timeline is not a repository-wide discussion index. A missing receipt is not replaced by an invented link.

Real Git receipts require the managed sender identity, task metadata, thread relation and a fixed 40-character commit ID. The synthetic preview recognizes browser snapshot receipts separately. Ordinary messages cannot impersonate actionable Agent version receipts. Each actionable receipt must match the active document path. These controls do not replace production grants or cryptographic attestation.

## Control accepted Agent tasks

Open **Agent activity** in the discussion panel. Accepted pending tasks offer **Cancel task**. A cancelled document save keeps the draft and lets you save again as a new task. **View execution history** shows recorded transitions across gateway restarts. These controls are omitted from the browser-only synthetic preview, which has no persistent gateway.

Only the original requester can cancel through this trusted local session. Cancellation stops further cooperative processing; it does not remove existing Git commits or undo external work already under way. The current client is still a local fixture identity, not a production login system.

## Direct human saves

Human edits now use the [Document Service](DIRECT_DOCUMENT_SERVICE.md). They do not require an external worker. Failed requests keep the original payload and UUID; unknown completion pauses editing until the same request can be retried. Core discussion and Agent operations still use Matrix.

## Local unsaved draft recovery

Git remains authoritative for saved `demo.md`. Unsaved edits are stored in localStorage on this browser origin, scoped by Matrix user ID, room ID, fixed document path and synthetic/real mode. A different port/origin has separate storage. Copies are plaintext, not synced, and browser clearing/private mode/device changes can make them unavailable. No draft is sent to a service until the existing explicit Save action.

Reopening loads Git first. Review, Export local draft, Restore local draft or Discard local draft explicitly. Restoration cannot replace current unsaved edits; first save or discard them. Restored old base versions keep their CAS base and may conflict; only confirm `I reviewed and merged latest Git text` after merging current Git text. Loading another version checkpoints the old draft before switching, and stops if that cannot be done safely. Successful confirmed saves clear this editor's unchanged copies, preserving other tabs' newer drafts.

Each editor has its own record. Web Locks serialize all application storage writes/deletes across tabs. Browsers without Web Locks fall back to page editing/export with a warning. Limits are64KiB UTF-8 per draft,16 records and1MiB across this app's origin storage; no old draft is automatically evicted. Storage failure/limit/corruption warns visibly. Keep the page open until recovery writes finish, or export. Recovery is best effort, not a guarantee against OS/browser data loss.

## Message history pagination

The discussion view can load earlier Matrix pages beyond the latest 50 events. The adapter preserves Matrix stream order and opaque cursors, including advancing empty pages. Repeated page boundaries are deduplicated by event ID. Loading an earlier page retains the viewport anchor; failures retain the cursor, current messages and composer draft for retry. Room changes discard late responses. A refresh keeps loaded history when pages overlap; if recent traffic creates a gap, the UI resets to the recent page and explicitly offers earlier loading again. Thread history now uses independent SDK relations pages, including a root outside the recent timeline. This does not provide full-text search.

`node client/scripts/history-smoke.mjs http://127.0.0.1:8832` uses synthetic data to verify 65 historical messages, stable cursor replay and a new 66th message through the same SDK page function used by the UI. Use only an isolated preview because it creates a test room and messages.

## Named documents

`GET /api/documents?room=…` lists regular Markdown files. `POST /api/documents` creates a new path with `{room,name,content,operation}`. Creation retries reuse the UUID; an existing path returns 409 without overwriting it. `PUT /api/documents/<encoded-path>` saves with `{room,content,base_blob,operation}`. Reads and history accept `path`; omitted paths retain `demo.md` compatibility. Invalid paths return 400; case or Unicode name collisions return 409.

The browser keeps recovery drafts separately for each file. Navigation waits for local draft writes and is blocked while a save result is uncertain or dirty text could not be stored. A confirmed create remains selectable even if refreshing the list fails. Human edits support named files; the current deterministic Agent document actions remain limited to `demo.md` and are disabled for other paths. Move and rename are supported for clean current documents; selected-message conversion is implemented in the next stacked candidate.

## Move or rename a document

Enter a new relative Markdown path in **Move document to path**. Save current edits and resolve local recovery drafts first. The move uses one Git commit: it checks the source blob, rejects an existing destination, removes the source and adds the destination with the same blob. Paths must follow the same portable naming rules; case-only path collisions are rejected. An uncertain response locks editing/navigation until the same move is retried. Explicit 4xx failures release the lock.

`POST /api/documents/move` accepts `{room,source,name,base_blob,operation}`. Retry with the same UUID and request. The original source remains readable at its historical commit through its original path. The current destination history starts at the move; the UI does not yet follow old paths automatically. Agent actions remain limited to demo.md. Use `node client/scripts/move-smoke.mjs <loopback-url>` only on an isolated test workspace.

## Create a document from selected messages

Open Discussion in the bound workspace room. Select up to 20 messages, enter a new Markdown path and choose **Create document from messages**. The browser sends event IDs only. The service fetches canonical Matrix events and creates a deterministic document with source links, sender, timestamp and literal message text. It does not summarize or call an LLM. Text from unsupported or redacted events is rejected; the entire source set must be available before a new write. Existing names cannot be overwritten.

`POST /api/documents/from-messages` accepts `{room,name,events,operation}`. An unknown response keeps the original UUID and selection for retry. A later redaction can prevent retrying source reads even if an earlier attempt committed; inspect/refresh the document list in that case. No new document is partially written when a source read fails. Human edits remain in the current editor if it is unsafe to navigate after creation. This slice supports plain-text messages from the existing bound room; attachments and other rooms require later work.

## Thread history

View thread fetches its root directly and reads m.thread replies independently of the recent room page. Load earlier thread replies paginates backward in pages of50. The UI preserves Matrix order, deduplicates boundaries and keeps the viewport anchor. Root and page failures have separate retries; a failed earlier page retains its cursor and the composer. Room/root changes hide old snapshots and discard late responses. Refreshes merge overlapping pages; if recent replies create a gap, a notice asks the user to reconnect history through earlier loading.

The local v1 proxy permits only GET for the fixed m.thread/m.room.message relations path in the existing allowed rooms. It forces backward direction/50 and rejects identity overrides. Synthetic adapters without relations keep the explicit loaded-only fallback. The real Matrix smoke creates a root outside the latest50 messages and66 replies across two pages.

## Search message and document bodies

Choose Search in the header. Messages searches content.body through Matrix in the current allowed room, using recent order and20-result pages. It can find historical messages outside the loaded timeline; opening a result fetches that message as a thread root. Pagination errors retain results and retry the same opaque token.

Documents searches regular Markdown bodies in the granted Git document repository. Results include line, excerpt, blob and a fixed reachable commit. Each page scans up to50 files and returns up to20 matching files; an empty page can still have more files. Later pages keep the same Git snapshot even if documents change. Open matched version reads that historical content and preserves draft navigation guards. A file larger than64KiB or with unsupported text encoding is skipped with a visible count. Query text is literal and case-insensitive. The existing sidebar field remains a navigation filter.

The endpoints POST /api/search/messages and POST /api/search/documents retain the current Matrix identity, room allowlist and document-room authorization. They do not search ungranted repositories, attachments or private runtime data. Search responses are rendered as text. No persistent index, production authorization change or paused performance work is introduced.


## Message attachments candidate (2026-10-20)

The message composer uploads a file of up to 5 MiB as m.file. The server uses the current Matrix identity and checks joined, unencrypted room access and message power levels. Downloads require a canonical file event in an allowed room and a CSRF token. Only local-homeserver media is accepted. Downloads use attachment disposition, application/octet-stream and nosniff. No remote redirects or inline HTML rendering are allowed.

An uncertain send keeps the original bytes, operation UUID and thread root. A retry reuses the cached media URI and Matrix message transaction. Losing an upload response before the URI is recorded can leave an orphan media object; exactly-once media storage is not claimed. Markdown embedding, inline images, encrypted files and remote media remain pending.

161 full Python tests and 155 frontend tests plus build passed. Final targeted76 frontend tests/build passed after the file-message selection guard. Actual Matrix protocol proved byte-exact download, one message on retry, conflicting bytes409 and ungranted room403. Isolated installed Chrome used the real file input, injected a lost response after server commit, retried the same operation/root, downloaded57 exact bytes and did not execute HTML. Evidence: .local/attachments/protocol.log, browser-proof.json and preview.png. CI runs attachment-smoke.mjs; final commit CI must be checked separately.
