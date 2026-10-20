# Git document loop (Issue #3)

This development milestone extends the durable gateway in PR #5. A Matrix document request becomes an external runtime task. The runtime reads or writes a dedicated Git repository and replies in the source thread with the immutable commit SHA. Git is the only authority for document content and versions; Matrix stores requests and notifications, not a second document database.

## Independent preview

To keep an existing gateway preview running, use a separate Compose project and ports:

```sh
export MATRIX_HTTP_PORT=8009 GATEWAY_HTTP_PORT=9001
docker compose -p didadi-docs up -d --wait --wait-timeout 240
docker compose -p didadi-docs --profile test run --rm smoke
mkdir -p .local
chmod 700 .local
docker compose -p didadi-docs cp appservice:/config/agent-token .local/agent-token
docker compose -p didadi-docs cp appservice:/config/smoke-state.json .local/smoke-state.json
chmod 600 .local/*
python3 -m scripts.gateway_preview --state-file .local/smoke-state.json \
  --token-file .local/agent-token --document-repo .local/documents.git \
  --port 8766 --matrix-url http://127.0.0.1:8009 --gateway-url http://127.0.0.1:9001
```

Open **http://127.0.0.1:8766**. Edit `demo.md` and select **Save directly to Git**. The authenticated Matrix user becomes the Git author. The HTTP response shows the saved revision; Matrix receives a metadata receipt. **Ask agent to read Git** sends a metadata request to the external runtime. Version links open immutable commit snapshots. A stale save returns an HTTP conflict and retains the draft and operation ID for recovery.

Only `demo.md` is granted to the deterministic runtime. A Matrix request cannot choose a repository, remote, filesystem path or model. This HTML preview is a local development harness; the React client is documented in LOCAL_WORKSPACE.md. Tokens remain server-side; messages and Markdown are HTML-escaped. The form checks CSRF and loopback Host headers and accepts up to 64 KiB of UTF-8 document content. Built-in human write entrypoints use the Document API; the client Matrix proxy rejects document writes and read requests carrying content. External legacy Matrix clients remain compatible and may send body-bearing tasks; their historical messages are not erased.

Run one document worker per demo queue, or multiple instances of that same runtime. Do not mix the legacy echo-only worker with document tasks: it does not interpret document requests. The isolated project prevents the existing 8765 preview from taking these tasks.

## Store and version contract

`GitDocs(root, remote=None)` creates or opens a **dedicated bare repository** on macOS/Linux with Git and Python 3.11+. It rejects the old working-tree layout instead of silently migrating it. Keep the repository service-owned; this is not a sandbox for attacker-controlled Git configuration, hooks, repository internals or remote directories.

- `snapshot(name, commit=None)` returns content, blob SHA and commit SHA from one locked revision. `read` and `blob_version` are convenience methods. Fixed reads require a full existing commit SHA; whitespace is preserved.
- `write(name, content, base_blob, operation=event_id, notification=context)` compares the current blob. Only one process can write against the same old blob. The operation ID binds to a request hash; retrying it returns the original commit, while changed input is rejected.
- `history(name)` returns recent immutable commit IDs. No Markdown file is opened in the filesystem. Private temporary indexes and Git object operations create the next tree. Strict logical names reject traversal; tracked symlink blobs/parents are rejected. Replacing a same-named disk path with a symlink cannot redirect a document write because there is no document checkout.
- `flock` coordinates independent processes and threads using this service on one host. `update-ref` compares the previous branch SHA, so an actor ignoring the lock cannot silently replace a concurrent branch update. NFS/distributed locks and multiple application hosts are not supported.

The root and Git internals must remain private and trusted. The symlink tests concern document paths, not a hostile actor who can replace the service's object database or configuration. This code is not a public repository API.

## Remote conflicts

The spike accepts only an existing absolute **local directory** as `remote`; it never loads user credentials or contacts network remotes. The remote must be trusted. Tests use independent bare repositories.

Before normal operations, fetch incorporates an external fast-forward. The blob comparison then rejects an outdated edit. Publication uses an ordinary non-force push. A competing remote update or known remote rewind is rejected. A local commit created before a failed push stays in the local branch with its outbox intent; no successful notification is sent for that unpublished operation. The runtime leaves publication failures retryable rather than acknowledging them as a stale-edit result.

A transient failure before push can recover on reopen if the local branch still fast-forwards the remote. Diverged or rewritten history requires explicit operator reconciliation; there is no automatic merge, reset, force-push or destructive recovery. Preserve the whole local repository for review. No SSH/HTTPS remote, network outage or credential-rotation behavior is validated.

## Durable notification outbox

New service commits have a readable subject and hashed operation/request trailers. Raw task IDs and notification routing stay in private `refs/didadi/intents/<operation-hash>` blobs, written **before** the single main branch-ref commit point. Pending delivery considers only operations reachable from main, so an intent left by a failed pre-commit CAS is not delivered. There is no post-commit metadata write needed for recovery. Old JSON commit messages remain readable; already published history is not rewritten. This intentionally uses a history scan in the small spike; it is not a performance claim for large repositories.

A local `refs/didadi/notified/<operation-hash>` receipt is written after completion. If the worker exits after Git commit and before Matrix notification, the existing gateway lease expires, and the runtime reclaims the task and finds the same operation commit. If the worker exits after Matrix ACK and before the receipt, authenticated `/agent/status?id=<task-id>` reconciles the completed task without resending. The gateway fixes the result and uses its stable Matrix send transaction ID as before.

Keep the entire bare repository, including private intent and receipt refs, with the gateway volumes. Only `main` is pushed to the optional remote. Receipts do not become another document authority. The normal restart and injected worker-crash tests do not prove power-loss, filesystem corruption, disk-loss or arbitrary-outage exactly-once behavior. External runtimes still must deduplicate their own side effects.

## Verification

```sh
python3 -m unittest discover -s tests -v
python3 -m scripts.document_smoke --state-file .local/smoke-state.json \
  --token-file .local/agent-token --repo .local/documents.git \
  --matrix-url http://127.0.0.1:8009 --gateway-url http://127.0.0.1:9001
```

Stop the preview worker before running the crash smoke against its queue. The smoke sends real Matrix requests, injects process `exit(73)` after commit, waits for the gateway's 60-second lease, then verifies the same commit and recovered thread notification. It also verifies immutable reads and rejection of a stale write. The GitHub integration job runs this after the existing Matrix/restart smoke.

Unit tests additionally cover two independent processes racing one blob, local-remote fast-forward/stale writes, a push race retaining unpublished work, remote rewind rejection, crash-before-push recovery, notification failure/retry, symlink replacement, and receipt reconciliation. Actual results and remaining limits are recorded in [VALIDATION.md](VALIDATION.md).

## Scoped Agent API

The [scoped API increment](../artifact/023-scoped-agent-document-api/README.md) moves Agent reads, writes, source reports and outbox reconciliation into the Document Service. Run the external worker with `--document-url` to avoid giving it a Git repository path. The service requires an explicit room or an existing workspace binding. Requests contain only task ID and lease; the service loads the authoritative event and checks permissions with Gateway. `--repo` remains a cohost development option. Human direct saves retain their separate same-origin API and Git conflict semantics.

Ordinary remote divergence now returns metadata-only `remote_diverged` diagnostics and permits service restart for diagnosis; latest IO and unpublished receipts remain blocked. See [the operator recovery procedure](GIT_REMOTE_RECOVERY.md) for preserving both histories in a reviewed two-parent merge and retrying the original save without force-push or shared-history rewrites. Known upstream rewrites/deletions still require separate investigation.

An ordinary remote clone receives only main, not private routing. Matching retries can reconstruct routing only after the original request hash matches. Back up the entire service bare repository with gateway state; losing private intent refs cannot be treated as lossless notification recovery. Human commits retain the authenticated Matrix author; Agent commits use the managed identity from the authoritative Gateway task. The service remains the committer. Historical JSON metadata can still exist in old commits; do not rewrite shared history to remove it.
