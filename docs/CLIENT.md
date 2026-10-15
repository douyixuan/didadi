# Document-first React workspace

This local client milestone depends on the Git document/runtime spike (PR #6) and its gateway dependency (PR #5). It uses React, Vite and **matrix-js-sdk** for real room membership/state, timeline reads, message sends, thread relations and stable outbound transaction IDs. It is not a static screenshot or an LLM UI.

## Run with the existing document demo

First follow [GIT_DOCUMENTS.md](GIT_DOCUMENTS.md) to start the isolated Matrix stack on `8009/9001` and the document preview/runtime on `8766`. Keep that document runtime running: the React adapter does not start a competing worker.

Requires Node 22+ (CI uses 24), Python 3.11+, Git and the existing local test stack:

```sh
npm ci --prefix client
npm --prefix client run build
python3 -m src.client_server --state-file .local/smoke-state.json \
  --token-file .local/agent-token --repo .local/documents.git \
  --metadata .local/client.sqlite --port 8767
```

Open **http://127.0.0.1:8767**. When using another checkout, point the file arguments to the existing document demo's private state/token/bare-repository files. Do not copy credentials into the frontend. This task's preview reuses `../didadi-docs/.local/` and leaves the older `8765/8766` servers and their data running.

The default screen is a document, not a message dashboard. The left sidebar contains the one real granted document and real allowed rooms. Read renders Markdown safely; Edit opens a Milkdown Crepe block editor with direct body editing, slash insertion, task lists, code blocks, drag handles and undo/redo. Save sends a Matrix task and waits for the external example runtime to commit to Git. History opens fixed commit snapshots; a stale edit shows a conflict and preserves the draft until the user explicitly loads the latest version.

Discussion and Example Agent are optional right panels. The example is labeled deterministic echo/no LLM. Room messages, thread replies and task completion are real. Version receipts and task IDs are collapsed in details. No fake multi-document tree, unimplemented sharing buttons, rich collaboration cursors or intelligent edits are shown.

Rooms can be selected or created as private local test rooms using the existing non-admin fixture identity. The managed example Agent is invited through the same verified AS flow. Creation retries use a deterministic alias and a local operation record. Message/save retries reuse Matrix transaction IDs; repeated clicks are gated while pending. Switching rooms keeps unsent chat drafts in memory. All demo rooms intentionally share the single `demo.md` grant; this is labeled in the document context and is not a production room/resource permission model.

## Development adapter boundary

`src/client_server.py` binds only to `127.0.0.1`. It accepts only loopback backend URLs and uses the existing fixture user token server-side. The SDK's browser-side `local-development-session` string is a placeholder, not a credential. Matrix, AS and worker tokens never appear in the session response or browser assets.

The adapter exposes an allowlist of joined room state/messages/event/send routes, filters joined rooms to the explicitly seeded/created local rooms, disallows user/token overrides, checks CSRF and Host/Origin, and refuses sends in encrypted rooms. Document task paths/grants cannot be supplied by messages. The gateway independently checks encryption/membership before acceptance and completion. No credentials, account/security settings or public exposure are added. This is a trusted loopback development session, not production authentication or multi-tenant authorization.

Markdown has no raw HTML rendering. React escapes messages, and the adapter serves a same-origin CSP. Static paths cannot leave the build directory. Only the existing deterministic runtime can service document requests. Sending to an invited Agent that has not joined yields a visible retryable error.

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

Milkdown Crepe 7.22.3 uses the MIT license. Its ProseMirror/Remark editing state is transient; saves still send Markdown through the existing Matrix/Agent/Git pipeline. Supported blocks are paragraphs, headings, bullet/ordered/task lists, quotes, GFM tables, code fences and dividers, with ordinary inline Markdown. Block actions duplicate, delete and move top-level blocks; lists move together. Crepe provides native dragging and slash insertion. Reading mode renders GFM tasks without enabling editing.

The editor retains original source for each top-level Markdown block, including separators and CRLF. Unchanged blocks bypass reserialization. Text edits are patched into the original spelling and validated through the editor parser; structural edits also restore unchanged source lines when that result represents the requested editor tree. Tables are editable. HTML, images, references, footnotes and code metadata remain editable **local source blocks**, while ordinary neighboring blocks stay rich text. Inline unsupported syntax currently makes its containing top-level block source-editable; hybrid inline atoms and persistent block IDs are not implemented. Front matter appears in a collapsed Properties panel. HTML is inert text, and image upload stays disabled.

Markdown does not encode a user-created empty paragraph or separation between adjacent same-kind lists. Empty paragraphs are view state and are omitted from new Markdown saves. Legacy `<!-- didadi:empty-paragraph -->` markers still open and remain byte-exact until a real edit; editing removes them. Undo restores the original bytes. A legitimate `<!-- -->` separator can still keep adjacent same-kind lists distinct. An unclosed code fence is closed before an appended ordinary block so it cannot swallow that block. New/changed structural lines can use normalized Markdown syntax. The Git blob comparison, immutable history and retained recovery draft continue to protect concurrent saves.

`npm --prefix client run roundtrip` verifies a pinned, offline corpus of 24 unmodified public Markdown files plus authored edge cases. `client/test-corpus/manifest.json` records exact source commits, hashes and licenses. Each file is mounted in the real editor view, saved and reopened; each source-locatable block receives a real ProseMirror text insertion and its saved bytes are compared against the exact intended insertion. CI uploads `markdown-roundtrip.json`, including total/opened/fallback files, raw blocks, lossy/unstable saves and unexpected rewritten lines. This small fixed corpus does not reproduce the issue's unpinned 1,010-file survey or establish universal compatibility. Dedicated interaction tests cover rich/raw/table edits, Chinese composition, CRLF, list split and structural boundaries.

Tests use real Milkdown for semantic block round-trip, direct editor changes, block commands, undo/redo, composition events and destruction safety. App workflow tests isolate the editor behind its Markdown interface. Synthetic composition events and Chinese text/paste checks do not establish compatibility with every physical OS IME.

## Export standard Markdown

Use **Export Markdown** below the document to download `demo.md`. It includes the current editor contents, including unsaved changes, or the exact historical snapshot currently open. It retains headings, front matter, code and original source spelling; it does not export rendered HTML or trigger a Git save. Export is disabled during a pending save/read or composition. The hosted synthetic preview downloads only browser-local sample content.

## Follow document versions through discussion

A managed Agent's task reply can offer **Open document version**. It opens the fixed Git snapshot through the same local document grant. Unsaved text is kept in **Preserved draft**. A failed historical read retries that same read; it cannot turn into a save.

**View version discussion** returns to the original receipt thread for the open version. It is enabled only when that receipt is present in the currently loaded timeline. This bounded timeline is not a repository-wide discussion index. A missing receipt is not replaced by an invented link.

Real Git receipts require the managed sender identity, task metadata, thread relation and a fixed 40-character commit ID. The synthetic preview recognizes browser snapshot receipts separately. Ordinary messages cannot impersonate actionable Agent version receipts. These controls do not replace production grants, a multi-document identity model or cryptographic attestation.
