# Start a fresh local workspace

This is a loopback development workspace with synthetic test identities and a deterministic Agent. No LLM, production account, production credential or public deployment is required. Git is the only document content/version store. A source archive needs no `.git` directory.

## Prerequisites and isolation

Use Python 3.11+, Node.js 22+ (CI uses 24), Git with `--no-lazy-fetch` support, and Docker with Compose v2 `--wait` support. Run these preflight checks in the terminal you will use:

```sh
python3 --version
node --version
git --version
docker compose version
docker info
```

Docker must be running. Its daemon connection and installed Compose plugin are platform prerequisites; an empty HOME may need those locations configured explicitly. Do not copy credentials or project state from another checkout. Dependencies/images come from public registries.

Extract the source or check out the candidate in a new directory, then `cd` to its `didadi` root. The commands use Compose project `didadi-bundle` and ports 8020 (Matrix), 9040 (Gateway), 9041 (WebSocket), 9042 (Document API), 8790 (client). Choose an unused project and ports if these already belong to another environment; update every matching command. Do not stop an unknown service or erase its volumes to free a port.

## Start Matrix and create isolated test data

Set both variables in the terminals that run Compose or the fixture helper:

```sh
export MATRIX_HTTP_PORT=8020
export GATEWAY_HTTP_PORT=9040
docker compose -p didadi-bundle config --quiet
docker compose -p didadi-bundle up -d --wait --wait-timeout 240
docker compose -p didadi-bundle --profile test run --rm smoke
mkdir -p .local/bundle
chmod 700 .local .local/bundle
docker compose -p didadi-bundle cp appservice:/config/agent-token .local/bundle/agent-token
docker compose -p didadi-bundle cp appservice:/config/smoke-state.json .local/bundle/smoke-state.json
chmod 600 .local/bundle/agent-token .local/bundle/smoke-state.json
```

The smoke creates non-admin synthetic users and a private unencrypted room only on this local test Synapse. Re-running it creates a new fixture; do not run it over an active workspace whose identities you want to retain. Keep the copied state private.

## Install and build

```sh
python3 -m venv .venv-delivery
.venv-delivery/bin/python -m pip install -r requirements-runtime.txt
npm ci --prefix client
npm --prefix client run build
.venv-delivery/bin/python -m scripts.create_synthetic_source --matrix-url http://127.0.0.1:8020
```

The helper creates only `.local/bundle/synthetic-source`, a pinned `example.py` commit and an exact room/sender/file read grant. It refuses an existing source, grant output or symlink. It checks the state and Matrix identity before creating files. If it stops, fix the stated prerequisite; do not delete unknown data to retry. The fixture is synthetic and contains no user repository.

## Start four processes

Keep each process in its own terminal, at the same extracted source root. Start the client first:

```sh
.venv-delivery/bin/python -m src.client_server --state-file .local/bundle/smoke-state.json --token-file .local/bundle/agent-token --repo .local/bundle/documents.git --metadata .local/bundle/client.sqlite --repository-grants .local/bundle/repository-grants.json --matrix-url http://127.0.0.1:8020 --gateway-url http://127.0.0.1:9040 --port 8790
```

Wait until http://127.0.0.1:8790/api/session responds. The configured workspace binds its document repository to the seeded room. Then start the Document API, which reuses this binding:

```sh
.venv-delivery/bin/python -m src.agent_document_api --repo .local/bundle/documents.git --token-file .local/bundle/agent-token --gateway-url http://127.0.0.1:9040 --port 9042 --repository-grants .local/bundle/repository-grants.json
```

Start the WebSocket bridge:

```sh
.venv-delivery/bin/python -m scripts.runtime_socket --url http://127.0.0.1:9040 --port 9041 --token-file .local/bundle/agent-token
```

Start the external runtime. It has no document repository path or source grants:

```sh
.venv-delivery/bin/python -m scripts.websocket_worker --url ws://127.0.0.1:9041/runtime --token-file .local/bundle/agent-token --document-url http://127.0.0.1:9042
```

Human saves require only the client and Matrix. Explicit Agent source tasks require all four processes. Agent IO and Git recovery belong to the Document API. It derives room, document path and base version from Gateway storage and checks the current task lease and live Matrix authority. Read/source bodies return only in the HTTP response resource field. New writes use the metadata-only Matrix task and scoped HTTP body API described below. The existing single-runtime token and loopback services are development boundaries. Legacy `--repo` cohosting provides no OS isolation. Cancellation can race after the last authorization check; it does not undo an existing Git commit.

## Verify and use

With the four processes running, execute:

```sh
.venv-delivery/bin/python -m scripts.workspace_acceptance --url http://127.0.0.1:8790
node client/scripts/smoke.mjs http://127.0.0.1:8790
```

These commands modify only this synthetic workspace. The first verifies advertised source choice, source read, service-generated report and denied-path isolation. The SDK test then verifies real discussion/replay, human direct save/history/stale conflict and synthetic private room creation. This is HTTP/SDK automation, not browser or Chinese IME acceptance.

Open http://127.0.0.1:8790/. Below the document, open **Read-only source repository**, select `example.py`, and choose **Read source in discussion** or **Replace document with file report**. The report replaces the current document, so use it on this synthetic fixture. **Edit** and **Save changes** save human changes directly to Git. **History** opens immutable versions; **Discussion** contains version receipts. **Export Markdown** downloads the current editor text, including unsaved edits. Export and physical IME behavior require separate browser verification; passing the commands above does not certify them.

## Stop and recover

Press Control-C in the four process terminals. Stop only this Compose project, retaining its data:

```sh
docker compose -p didadi-bundle down
```

Restart with the same directory, project, ports and volumes. Reuse the existing state/grants; do not rerun fixture creation. The configuration, database and Synapse volumes form one identity set. Preserve them together. `.local` contains test credentials, grants and document data; `.venv-delivery`, `node_modules` and `client/dist` are local build outputs. None belongs in a public source archive.

If startup fails, inspect `docker compose -p didadi-bundle ps -a` and service logs. Do not reset volumes as a generic repair. A PostgreSQL initialization race is prevented by TCP readiness; an unrelated port, missing tool or insufficient Docker resource issue still needs its own diagnosis.


## Agent body IO without Matrix document bodies

Recommended write task content: `org.didadi.document: {"action":"write","base_blob":null}` (or the current Git blob). Do not include document text in that Matrix event. After claiming the task over the outbound runtime connection, call `DocumentClient(document_url, token).write({"id":task["id"],"lease":task["lease"],"content":new_text})`. Only the Document API owns the Git repository. Path, room and base cannot be overridden by this request. The write remains strict CAS; retrying the same task/body is idempotent and changing an already fixed saved body returns HTTP409.

For document/source reads, `.execute({"id":...,"lease":...})` returns body text under `resource.content` over HTTP only. Use it inside the runtime; send only the returned `result` and `outcome` to Gateway completion. Gateway also canonicalizes resource-task results before sending, so an old/custom runtime echoing a body cannot put that result into the Matrix receipt. Source outcomes include only the granted repository alias, path, commit and blob. Document reads are bounded to64KiB.

Legacy inbound Matrix writes containing `content` still work for compatibility but are deprecated; they already place their input in Matrix. Existing historical messages cannot be retracted by this migration. Ordinary chat is unchanged. This is a development API and shared runtime-token boundary, not a production grant model.

Protocol acceptance: `python3 -m scripts.agent_body_api_smoke --state-file .local/bundle/smoke-state.json --token-file .local/bundle/agent-token --matrix-url http://127.0.0.1:8020 --gateway-url http://127.0.0.1:9040`. The subprocess has no Git path/grant, writes and reads through HTTP, deliberately sends raw synthetic resource text as completion, and verifies Matrix retained metadata only. Older document smoke scripts retain body-bearing inputs specifically as legacy compatibility fixtures.

## Local remote publication recovery

When a configured trusted local Git upstream diverges, retain/export the draft and use the [operator recovery procedure](GIT_REMOTE_RECOVERY.md). The client keeps the original save ID/body/base, displays retained version metadata, and retries only that request after reconciliation. Restart supports diagnosis, not automatic merging. Existing browser recovery drafts can be exported even if the first Git read is blocked. No force-push, shared-history rewrite, remote credential change or web recovery command is provided.
