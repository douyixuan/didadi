# Technical Risk Validation — 2026-10-14

## R1 — Matrix Application Service / client
**Status: spec validated, runtime not tested.** Matrix AS registration defines identity namespaces and a push transaction endpoint; retries reuse txn IDs. The AS may observe and inject events but cannot block or rewrite existing events. Design: AS transaction handler must durably commit incoming txn/event IDs and enqueue tasks before 200 ACK; processing each event idempotently prevents duplicate dispatch. Restrict service scopes, avoid catch-all namespaces. Standard m.room.message fallback preserves reading in regular clients, with custom namespaced events for optional task metadata.

Sources: https://spec.matrix.org/latest/application-service-api/ ; https://github.com/matrix-org/matrix-js-sdk ; https://github.com/element-hq/element-web

**UI decision:** build a slim React + matrix-js-sdk client for MVP; Element Web is dual/open/commercial licensed as documented, but a fork adds significant upstream maintenance. Do not treat this as benchmarked effort comparison.

## R2 — Git single source of truth
**Status: local proof passed, production not proven.** 4 Python unittest cases passed: create/version read, stale-write rejected, competing threads only one wins, path traversal blocked. Current lock is process-local. A production writer must implement per-repository cross-process serialization, external update handling, ref lock/remote CAS, push retry, durable outbox, immutable revision reference, authentication and authorization, sandboxed Git operations and symlink race mitigations. Content-addressable blob SHA checks do not by themselves guarantee a stable document identity or safe concurrent Git index access.

## R3 — E2EE + agents
**Status: deliberately out of MVP.** Only explicitly authorized, unencrypted collaboration rooms can be used with Agent AS. Encrypted room events are not plaintext accessible by an application service; future agent E2EE integration requires dedicated crypto-capable client identities, explicit key disclosure and trust design. Never silently downgrade a room.

## Decision gate before Phase 1
- Deploy real Synapse + PostgreSQL + AS container.
- Send one Matrix message and confirm exactly one durable Task even after replaying transaction and restarting AS.
- Test agent response represented as `m.room.message` with safe fallback and namespaced metadata.
- Run Git tests with two worker processes and externally updated remote branch.
- Verify E2EE rooms are rejected for agent tasks with clear UI feedback.

**No claims of end-to-end Matrix validation or production readiness are made.**


## Issue #1 implementation — 2026-10-15 (Asia/Shanghai)

Implemented Compose initialization, PostgreSQL persistence, Synapse registration, a scoped synchronous AS echo fixture, and a real Matrix smoke-test job. Exact commands and permission boundaries: [MATRIX_QUICKSTART.md](MATRIX_QUICKSTART.md).

Local evidence: `python -m unittest discover -s tests -v` passed **10 tests** (4 existing Git tests, 6 Matrix/configuration tests). `git diff --check` passed. Tests cover token rejection, retryable failure ACK, stable reply transaction IDs, invitation handling, filtering and fail-closed encryption-state lookup. These are unit/HTTP fixture tests, not evidence of a real Synapse deployment.

The editing environment has no Docker executable/daemon; real runtime validation was performed on GitHub Actions Ubuntu instead. **PASS**: [run 38664316060](https://github.com/douyixuan/didadi/actions/runs/38664316060), implementation commit `c4555f0764f699b75f21e4e59639f60df48f6517`, 2026-10-15 (Asia/Shanghai). Both jobs passed: 10 unit tests and the real Matrix integration job.

Runtime evidence: Compose configuration and image pulls succeeded; Synapse, PostgreSQL and AS became healthy; unauthenticated AS traffic was rejected; out-of-namespace human impersonation was rejected; Alice/Bob exchanged messages in both directions via `/sync`; AS received the trigger and replied as the managed echo identity; replay yielded one reply. Containers were removed and recreated while retaining volumes; both original user tokens could read the original room message; a second complete smoke run passed.

Two failures found during real CI were fixed before this passing run: initialize Synapse data volume ownership as 991:991, and permit the smoke fixture to persist its restart-check credentials. No runtime validation is claimed for macOS/ARM, production deployment, or long-outage exactly-once behavior. The Phase 1 durable task and Git concurrency gates above remain outstanding and are deliberately outside this change.

## Issue #2 durable external runtime — 2026-10-15

Implementation commit `c9f3b7cdc14e423bd9268032a42699a502d0e6c8`: [CI run 38694070688](https://github.com/douyixuan/didadi/actions/runs/38694070688) **PASS**, both unit and real Matrix jobs. 18 tests passed locally on starlabs-112 (macOS, Python 3.11) and in CI (Ubuntu, Python 3.13). New tests cover durable transaction/event deduplication across reopened stores, concurrent claims, expired lease replacement, result recovery after failed outbound send, stable thread root, worker HTTP credential separation and fail-closed room encryption checks.

Real local OrbStack/ARM Compose stack also **PASS**: healthy Synapse/PostgreSQL/AS, bidirectional messages, mentioned durable task, independent outbound example worker, plain Matrix reply in the originating thread, rejection of the AS credential at the worker endpoint, and no pending task after repeated/different transaction replay. `docker compose -p didadi-gateway down` and recreation retaining volumes followed by `--check-persistence` **PASS**: original user tokens/message and accepted pending task survived; recovered task completed after restart. No local volumes were deleted.

Interactive preview at `http://127.0.0.1:8765` uses the same live test room and a separate polling example runtime. Browser submission of a new Chinese test message was observed in the real Matrix timeline. See [setup and contract](AGENT_GATEWAY.md).

Evidence boundaries: this is a single-node trusted development gateway with one credential bound to one managed identity. Runtime is deterministic, not an LLM. Encrypted-room rejection is unit-tested; no real E2EE client/crypto or UI rejection notice is implemented. External execution is at-least-once; runtimes must deduplicate side effects by task ID. Stable Matrix send transaction IDs do not prove exactly-once replies beyond homeserver retention. SQLite durability is tested across normal container recreation, not disk loss or abrupt power failure. Git multiprocess/remote/outbox gates remain Issue #3, and no Git-document writes or public deployment are claimed.

## Issue #3 Git document loop — 2026-10-15

Local **PASS** on starlabs-112 (macOS/ARM): **32 unittest cases**, including two independently spawned writers racing one base blob (one save, one conflict); trusted local-remote fast-forward and stale-version rejection; a remote push race preserving the unpublished local commit and outbox; known remote rewind rejection without repushing it; crash-before-push recovery; fixed commit/whitespace preservation; path traversal; document-path symlink replacement; tracked symlink parent rejection; and completion-receipt reconciliation after a simulated post-ACK crash. `git diff --check` passed.

Real independent OrbStack stack **PASS**, project `didadi-docs`, Matrix `127.0.0.1:8009`, gateway `127.0.0.1:9001`: existing bidirectional Matrix/agent smoke remained green. `scripts.document_smoke` passed real Matrix write → external runtime → Git → original thread. It started a separate worker process which committed and exited with code 73 before gateway completion, reopened the bare repository, observed one pending outbox item, waited for the existing 60-second task lease and recovered the notification using the exact same Git commit. Pending outbox became empty. A real Matrix request read the first immutable commit after the second write; a stale write returned an explicit conflict and preserved the second version.

Browser evidence: the editor at `http://127.0.0.1:8766` submitted Chinese Markdown through a real Matrix task. Refresh read the committed text from Git and showed a matching agent commit receipt. Original `http://127.0.0.1:8765` returned HTTP 200 during the milestone and runs from the untouched parent worktree. The new stack uses separate ports, identities, volumes and document repository. No user credentials, paid model, public listener or force-push was used.

The integration workflow now runs the real document/crash smoke after the existing Matrix recreation test. Final-commit CI status is reported on the dependent draft PR; local results above are not substituted for CI evidence.

Boundaries: dedicated service-owned bare repositories on one macOS/Linux host, trusted local directory remotes, normal restart and explicitly injected worker crashes only. No network remote or credential flow, distributed filesystem, hostile Git internals/configuration, disk corruption/power-loss recovery, production tenant/grant system, E2EE crypto client, user-facing E2EE rejection flow or exactly-once external execution is validated. The outbox derives intent from each committed tree's commit metadata using a single branch-ref commit point; local Git receipt refs and gateway status reconcile completed notifications. History scanning is a small-repository spike, not a throughput benchmark. Remote divergence is retained and blocks publication until explicit operator reconciliation; no automatic merge/reset is claimed.

## Document-first React client — 2026-10-15

Implemented on an independent branch depending on PR #6, preserving the original `8765/8766` previews and existing Git/Matrix data. The user requested a knowledge-base layout after seeing the earlier preview. Current Outline and Docmost official screenshots were opened and captured before redesign. The client now has a light document tree, a centered reading surface, working Markdown editing controls, immutable-history panel, and optional discussion/example-Agent side panel. Full receipts/task details are collapsed. No product screenshot is substituted for functioning code.

Local **PASS**: React component regression suite (10 cases), production Vite build, and Python backend suite (37 cases). Frontend cases cover normal/loading/failure, draft-preserving conflicts, idempotent retry transaction IDs, repeated submits, actual formatting, historical reads/inert HTML and per-room unsent drafts. Adapter tests cover room/method/identity restrictions, encryption refusal, room creation/recovery, CSRF/Origin/Host, static traversal and no credential disclosure.

Real-browser **PASS** against existing Synapse/Git/runtime: SDK sent a Chinese message and the external worker echoed it; the editor saved additional Chinese Markdown and read it back from Git; a new private local room “产品协作” was created and selected; a prior Git snapshot opened, a stale save returned an explicit conflict without overwriting the latest commit, and the draft remained until explicit latest-version loading. Normal, loading, failure and conflict states were rendered, captured and inspected. Loading/failure captures use a separate labeled QA adapter, not claimed as backend success. The first failure screenshot exposed a continuing skeleton, which was corrected. Design reference/QA details are in `artifact/004-workspace-client/design.md`.

CI now includes React tests/build and a real `matrix-js-sdk` regression through the adapter, in addition to the existing backend, Matrix restart and worker-crash/Git tests. Final commit CI is recorded on the dependent draft PR. No earlier commit's passing CI is substituted for it.

Limits: one real shared document, trusted loopback development session, deterministic example Agent (no LLM), no production authentication/tenant/resource grants or E2EE, no network credentials or public deployment. Main Matrix/AS/worker tokens stay server-side. Only explicitly seeded/created local rooms are proxied; the adapter still depends on the same fixture user rather than a production account flow. The SDK uses bounded HTTP timeline polling rather than a complete sync/offline client. Desktop visual checks and code semantics do not establish full accessibility or device coverage. Optional crypto bundle artifacts and bundle-size warnings do not mean crypto was initialized or E2EE supported.

## Independent pre-merge review follow-up (2026-10-15)

An independent review identified a cross-store remote operation retry defect and draft loss during conflict recovery. GitDocs now checks operation identity again after remote synchronization, with a regression for identical and mismatched retries. The client exposes the retained draft during conflict recovery, historical navigation, and Agent reads. Worker loops retry transient failures without logging private response details; interrupts still stop the process.

Local final checks: 39 Python tests passed, 12 frontend tests passed, and the normal real-backend Vite build succeeded. Vite reports the existing bundle-size warning. A separate synthetic static build was published using Vercel's anonymous temporary deployment. Browser verification confirmed the explicit no-backend banner, editing and browser snapshot save. No real workspace documents, messages or credentials were included in that upload. Temporary deployments expire after approximately one hour; they are not a persistent backend environment.

## Block editing milestone (2026-10-15)

Milkdown Crepe replaced the primary source textarea with direct block editing. Local checks passed: 39 Python tests and 17 frontend tests, including the actual editor's semantic round-trip for Chinese headings, paragraphs, lists/tasks, quotes, fenced code and inline marks. Editor transaction tests cover immediate updates, block actions/undo/redo, synthetic composition and cleanup. Workflow tests isolate the editor's Markdown boundary; they do not substitute for native editor checks.

Native Chrome checks used isolated synthetic data for Markdown paste, slash Heading 2 insertion, task/code rendering, drag-handle reordering, save/reopen, and mouse-only bold formatting followed immediately by save. The saved DOM retained a strong node. Against the real local backend, an appended Chinese block-editing section was saved through Matrix/Agent to Git commit `6a42b7a326bf03e47c2b60ebd2b9e6f1b45c302a`; existing content was retained. An old Git snapshot was used to exercise stale-save rejection and draft recovery.

Independent review identified cleanup overwrites and missing mouse-only changes in an early draft. The implementation now ignores destroyed-editor callbacks and tracks actual document-changing transactions synchronously. The final implementation received no blocking findings. Unsupported source opens without conversion. Source formatting may normalize after edits. Physical OS IME, all browser engines and arbitrary rich blocks remain outside verified claims.

## Gateway isolation and terminal task failures (#10/#11)

Local tests on starlabs-112: the complete Python suite passes 56 tests; frontend suite passes 45 tests, including 33 pinned Markdown corpus files and 1586 block edits. Production frontend build passes. Independent review found malformed-event isolation, network/lease races and client terminal-task recovery defects; all were fixed with regressions, then independently re-reviewed without blockers.

The isolated `didadi-lifecycle` Synapse/PostgreSQL/AS stack on loopback `8013/9013` passes the existing real Matrix smoke. `scripts.gateway_lifecycle_smoke` creates a real room, waits for the Agent to join, queues a mention, kicks the Agent, and confirms that its pending task becomes terminal while a healthy room completes. A mixed AS delivery uses real Synapse permission lookups and is ACKed. Final-commit CI is recorded on the PR and must be checked independently of local evidence.

Git abandonment receipts are durable objects rooted by refs. They retain the existing document commit and record a fixed reason while closing the outbox item. The document worker validates room access and its current lease immediately before Git operations; completion rechecks after network access verification. Matrix membership and Git are still separate systems, so this is not an atomic revocation guarantee or a production grants implementation.
