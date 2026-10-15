# Durable external agent spike (Issue #2)

This single-node development milestone builds on the Phase 0 Matrix stack. An explicitly invited managed identity receives structured mentions, the gateway commits transaction IDs and task event IDs to SQLite before ACK, and an independent runtime polls outbound with a separate credential. The runtime does not receive a homeserver or Application Service token.

## Run

```sh
docker compose -p didadi-gateway up -d --wait --wait-timeout 240
docker compose -p didadi-gateway --profile test run --rm smoke
```

The smoke creates a private, unencrypted room, invites the managed identity, sends a structured `m.mentions.user_ids` mention, runs the external example worker, verifies its Matrix thread reply and replays the original event under repeated and different transaction IDs. A pending real event is left for the restart test:

```sh
docker compose -p didadi-gateway down
docker compose -p didadi-gateway up -d --wait --wait-timeout 240
docker compose -p didadi-gateway --profile test run --rm smoke python -u -m scripts.matrix_smoke --check-persistence
```

## Local interactive preview

After the smoke and persistence check, copy development state without printing credentials. These ignored files contain local test credentials; keep them private.

```sh
mkdir -p .local
chmod 700 .local
docker compose -p didadi-gateway cp appservice:/config/agent-token .local/agent-token
docker compose -p didadi-gateway cp appservice:/config/smoke-state.json .local/smoke-state.json
chmod 600 .local/*
python3 -m scripts.gateway_preview --state-file .local/smoke-state.json --token-file .local/agent-token
```

Open **http://127.0.0.1:8765**. Send text, wait a second and refresh the timeline. This is a small development harness, not the planned React client. It uses the real Matrix room and runs the deterministic external example runtime in a background thread of the preview process, independently from the gateway. It does not run an LLM or modify Git documents. Test user access tokens stay server-side. The form uses a per-process CSRF token and the server rejects non-loopback Host headers.

Alternatively run your own runtime (Python 3.11+):

```sh
python3 -m scripts.agent_worker --token-file .local/agent-token
```

Do not run this alongside the preview if you want one predictable worker. The example echoes received text and never executes message instructions as code.

## Runtime contract

- `GET /agent/tasks`, with `Authorization: Bearer <agent-token>`, leases one task for 60 seconds or returns `{"task": null}`. A task includes `id`, original Matrix `event`, fixed `agent`, `lease`, and any persisted `result` from a failed completion.
- `POST /agent/complete`, with the same credential, accepts `id`, `lease`, `result` (1–16000 characters). It persists the first result, checks current room access/encryption and sends as `@_didadi_agent_echo:didadi.localhost`. Callers cannot choose a sender, destination room or thread. Retry failed requests with the same lease/result. If the lease expired, reclaim the task and use the persisted result.
- A reply preserves the original `m.thread` root, or starts a thread on the mentioned event. It contains a plain `m.room.message` fallback and `org.didadi.task` metadata.
- Each event ID creates at most one task. SQLite transactions serialize claims across processes. Expired leases allow redelivery; external runtimes must use the task ID for their own side-effect deduplication.
- A stable outbound Matrix transaction ID handles send retries. This does **not** guarantee exactly one message beyond the homeserver's transaction retention, or exactly-once external execution. No task cancellation, fairness, quotas, credential rotation UI, tenant isolation or production readiness is claimed.

## Authorization and persistence

The independent worker token is generated once in `config/agent-token` (existing configuration volumes migrate without changing other credentials). It grants only this one identity's queue. Do not share the broader config volume with external runtimes; copy only this token. Possession of the token permits reading task context. This is trusted local development authorization, not a multi-tenant enrollment system.

Rooms must explicitly invite the managed agent and it must be joined. Any local user can invite it, as in Phase 0. Only plaintext text messages with structured mentions create tasks. Encryption-state lookup fails closed; joined membership and no encryption are checked again before sending. Encrypted events are ignored; no keys are requested or room settings changed. There is no production room-grant UI or E2EE rejection notice yet.

The new `gateway` volume contains the SQLite transaction/task/result ledger and must be retained with the existing config, Synapse and PostgreSQL volumes. `down` keeps all volumes; `down -v` destroys all development data. AS port 9000 is now exposed only on host loopback for outbound local runtimes. Do not expose it or the preview publicly. SQLite is single-node metadata, not document storage: Git remains the only authority for Markdown content, with the subsequent [Issue #3 document spike](GIT_DOCUMENTS.md) providing a separate Git editor, runtime and recovery tests.

## Per-event eligibility and terminal failures

AS transactions persist each valid mention independently. A forbidden room is skipped; a transient room lookup creates an `unverified` task. Other rooms continue. The legacy echo path is best effort and cannot reject the transaction because of one room.

Tasks have `attempts`, `last_error`, and terminal `failed` status. Existing databases migrate in place. `GATEWAY_MAX_ATTEMPTS` defaults to 8; leases and explicit transient failure retries use bounded exponential delays. A terminated task is never leased again. `/agent/status` reports its terminal reason; the client keeps the draft and unlocks on failure.

Authenticated worker endpoints:
- `POST /agent/validate {id, lease}` checks room eligibility and revalidates the lease after the network lookup. The document worker calls this before reading/writing Git.
- `POST /agent/fail {id, lease, reason, retryable?}` reports runtime failure. Only fixed non-sensitive reason codes are accepted. `retryable` defaults to false.
- `/agent/complete` returns `{error: "room_forbidden", retryable: false}` for revoked access and `{error: "invalid_lease", retryable: true}` for a stale lease. Results remain fixed across transient delivery failures.

Failed document operations receive a durable Git abandonment receipt, including the reason. This removes the notification from `pending()` and retains the committed document version. It does not undo an existing commit or silently publish into a forbidden room.

Boundary: Matrix membership checks and Git writes do not share a transaction. Claim, pre-write validation and completion checks reduce the revocation window; they cannot guarantee that membership will remain unchanged between a successful validation and a Git operation. Production authorization/grants and active runtime interruption remain separate work.

## Cancel tasks and inspect execution history

`POST /agent/cancel {id}` uses the existing fixed Agent credential. It moves pending/unverified tasks to terminal `cancelled`, invalidates the lease and records the transition atomically. Repeated cancellation is idempotent; a completed task remains completed. Validate/complete reject cancelled tasks with `task_cancelled`, `retryable: false`.

`GET /agent/audit?id=...` returns persistent transition metadata: sequence, action, time, attempt and a fixed reason. It does not contain message text, results, credentials or leases. Existing databases migrate in place; older tasks can have partial or no recorded history. This is development execution history, not immutable or compliance-grade audit.

The local client exposes cancellation only for the current fixture user's original request in an explicitly allowed room, behind the existing CSRF/Origin/Host checks. Room-visible execution history requires visibility of the source Matrix event. Cancelled document saves keep the draft and unlock the editor. Git operations already committed are retained; cancelled notification outbox items receive abandonment receipts.

Cancellation is cooperative. It cannot undo a completed Git write or retract external IO already in progress. Runtimes must still check their lease before side effects and deduplicate by task ID. Production user/grant authorization and active runtime interruption require separate design.
