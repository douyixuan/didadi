# ADR 0002: Document Service boundaries

Status: Proposed (2026-10-16)

- Retain the accepted MVP decisions in [ADR 0001](0001-matrix-git-agent.md): unmodified Synapse, a dedicated Application Service / Agent Gateway, Git authority, external agent runtimes and separately scoped agent authorization.
- Propose a first-class Document Service in place of the architecture's ambiguous Platform API. The four boundaries below specify the target requested in [#18](https://github.com/douyixuan/didadi/issues/18); this ADR does not certify implementation or change ADR 0001's accepted status.

## Context and implementation status

On the inspected main commit `f0ab205`, human saves carry full Markdown through Matrix, the Application Service, gateway tasks and an external worker. This couples saves to messaging and worker availability, duplicates content in room history, and makes clients interpret reply prose. See [#14](https://github.com/douyixuan/didadi/issues/14), [CLIENT.md](../CLIENT.md) and [GIT_DOCUMENTS.md](../GIT_DOCUMENTS.md) for the existing spike and its limits.

As checked on 2026-10-16, no ADR 0002 PR existed. The separate open draft stack #31–#40 includes structured outcomes (#37), direct human saves (#38) and scoped Agent Document API calls (#39). Those are implementation work in progress, not main behavior or evidence that this entire architecture is implemented. This docs-only change neither depends on nor integrates that stack.

## Proposed boundaries

### 1. Matrix owns communication, not document persistence

- Matrix remains authoritative for identities, rooms, membership, power levels, discussion and commit receipts. It is not the document RPC transport or a store for document bodies, CRDT updates or read-result bodies. User-authored quotations remain ordinary discussion, not an automatic document transport.
- Human reads, writes and history requests go directly to the Document API, bypassing AS task dispatch and external workers. Matrix mentions may initiate agent tasks; document IO within those tasks uses the Document API.
- After a committed save, publish a metadata-only `org.didadi.document.commit` receipt with path, commit and author (and blob where useful) to the bound room. Threads can reference receipts; block anchors require a stable block identity design.
- Separate durable save, remote publication and receipt-delivery states. An unavailable Matrix receipt channel must not undo or repeat a committed save. Persist notification intent and retry with a stable identity; do not announce remote publication before it succeeds. Authorization availability is a separate constraint: an untrusted or stale permission view must not allow a write.
- Return machine-readable outcomes such as saved, conflict and rejected with version identifiers and reasons. Human prose is display-only, never protocol control flow ([#14](https://github.com/douyixuan/didadi/issues/14)).

### 2. Document Service owns a single writer per repository

- Exactly one active service owner serializes mutations of each service-managed repository. Shard by repository rather than sharing `flock` across hosts or NFS. Local locking and Git ref compare-and-swap remain guards; failover needs ownership fencing before another writer starts.
- External GitLab/GitHub MRs and Web IDE edits remain legitimate remote writers. The single-writer rule concerns the service-managed repository, not exclusive authorship of the remote. Fetch and integrate ordinary divergence using a non-force three-way merge, creating a merge commit when needed. Preserve both histories; surface overlapping conflicts to users rather than routinely requiring operator reconciliation. Remote rewrites and corruption still need explicit recovery policy; never reset away unpublished work or force-push.
- A future durable CRDT hot layer holds live, uncommitted collaboration state. Git is the only authority for committed Markdown versions and their history. A durable draft acknowledgment is not a Git commit or publish acknowledgment. Commit on idle or explicit publish, with recoverable mapping from draft/checkpoint to Git version and idempotent operations.
- Remote changes must be merged against the correct base and reconciled into live state without dropping uncommitted edits. Durable CRDT recovery, conflict UX, checkpoint timing and writer failover require validation before rollout; Git alone cannot recover a draft that was never committed.
- Preserve unchanged Markdown source blocks ([#13](https://github.com/douyixuan/didadi/issues/13)); introduce non-overlapping three-way merge before CRDT ([#15](https://github.com/douyixuan/didadi/issues/15)). Source preservation does not itself supply persistent block IDs.
- Keep readable, attributed commits with service committer identity and privacy-safe idempotency metadata. Keep Matrix room/event routing context out of pushed commit history; retain recoverable receipt routing separately. Migrate existing metadata without breaking replay/recovery ([#16](https://github.com/douyixuan/didadi/issues/16)). The atomicity of that migration must be designed and tested, not assumed.

### 3. Authorization derives from Matrix

- Bind a configured Matrix room or space to a repository and canonical path prefix. Derive read/write authority from authenticated membership and power levels; `member` reads and `power >= 50` writes is an example, not a settled universal policy.
- The Document Service enforces access for reads, writes, history and live sessions. Matrix identity must be verified server-side; user-supplied identity, repository paths or task text cannot grant access. Resolve path boundaries safely, including traversal and symlink protections.
- Use live Matrix checks or a cached projection invalidated by AS membership/power events. No independent document ACL authority: bindings, cached projections and grants are metadata derived from Matrix authority. Define cache freshness, revocation and fail-closed behavior before production use, including revoking live sessions.
- Space membership is not an implicit grant to every child room. Binding inheritance, overlapping prefixes, exact power thresholds and historical-version access policy require explicit rules and tests.

### 4. Agents are scoped API clients

- The gateway owns durable dispatch, managed identities, task state and audit; external runtimes own execution and model state. Neither is a second Git writer.
- A permitted room actor can issue a server-validated grant bound to agent identity, repository, path prefix, allowed actions and expiry. Issuance cannot exceed the issuer's authority. Recheck grant scope and current authority at use time, supporting revocation; possession of a task ID or a message mentioning a path is insufficient.
- Agents use the same Document API as humans, with `operation = task id` for idempotent task effects and structured results. Bind the operation to the validated request; retries return the same outcome and changed input cannot reuse the operation. Humans also require stable operation IDs for uncertain-save retries.
- Document bodies and credentials stay out of task results sent to Matrix. Results carry status and authorized references; API reads enforce the grant separately. A fixed-version reference does not bypass authorization.

## Policy and technology decisions still to confirm

The #18 comments request these topics explicitly; the issue body describes recommendations, not verified capabilities. They remain proposed here pending acceptance.

| Topic | Existing decision or evidence | Proposed direction / confirmation needed |
| --- | --- | --- |
| Workspace E2EE | ADR 0001 excludes automatic E2EE agent access in MVP; current client rejects encrypted-room sends. | Recommend unencrypted workspace rooms by policy, with client/server enforcement. Confirm the product/privacy policy; plaintext Git storage does not establish consent. Encrypted DMs remain outside agent scope, not a delivered capability. |
| Federation | Development Synapse config uses `federation_domain_whitelist: []`. | Confirm whether local-only operation and deferred federation/standard-client compatibility are product constraints. A spike setting is not a permanent federation decision or compatibility validation. |
| Document Service language | Current GitDocs and client adapter are Python; editor schema is JavaScript. | Recommend TypeScript and a shared editor/Markdown schema package. Keep the Python gateway. Runtime, migration and packaging choices are unapproved. |
| CRDT and persistence | Main has Git blob conflict checks, no durable CRDT layer. | Yjs/Hocuspocus and SQLite/PostgreSQL are candidates, not selections. Validate schema/source preservation and recovery first. |
| Push over poll | The React client uses matrix-js-sdk but polls `/messages`; worker/task delivery also polls. | Prefer Matrix `/sync`, agent long-poll/SSE or another validated push transport, and live document updates. Draft #33 explores outbound WebSocket transport; this ADR does not select or certify it. |

## Migration order

1. Verify correctness prerequisites and history-scan performance against the integration baseline. As checked on 2026-10-16, #10 is closed; #11 and #12 remain open. Reuse the completed #10 work and verify remaining acceptance without treating this ADR as completion.
2. Review and accept ADR 0002's boundaries and settle the policy choices needed for implementation.
3. Deliver Document Service v0: direct human IO, durable metadata-only receipts and structured agent results (#14), with readable/private commit metadata (#16), retaining the safe-name work from already-closed #17. Reuse and review existing drafts #37–#39 instead of duplicating them. Route all service-managed Git writes through one owner before claiming the single-writer boundary.
4. Build on #13, already closed via #20/#21 with pinned-corpus source-preservation evidence. Persistent block IDs remain outstanding; do not redo completed preservation work or infer general Markdown compatibility. Add three-way non-overlapping merge and explicit overlap handling (#15 step 1), including remote divergence.
5. Add durable CRDT state and live cursors (#15 step 2) only after schema, authorization, recovery and Git reconciliation checks pass.

Consequences: human saves no longer depend on worker dispatch; Matrix is no longer an automatic second content history; Git versions stay portable and attributed. The service gains responsibility for authorization freshness, single-writer ownership, durable drafts, remote merges and receipt recovery. Logical separation need not require an immediate separate deployment. Accepting this ADR would approve a design, not prove any migration step complete. Existing spike docs remain descriptions of implemented behavior until their respective code changes land.
