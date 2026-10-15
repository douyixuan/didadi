# Outbound WebSocket runtime (development)

The external example runtime can open one persistent WebSocket connection to a loopback gateway bridge. It carries task claims, lease validation, completion, failure and status. The bridge waits up to 20 seconds for an available task, using the existing HTTP gateway internally. This is a transport adapter; it does not add a second queue or persistent state. The original HTTP runtime remains available.

Install the pinned optional runtime dependency into your virtual environment:

```sh
python -m pip install -r requirements-runtime.txt
python -m scripts.runtime_socket --token-file .local/agent-token
python -m scripts.websocket_worker --token-file .local/agent-token --repo .local/documents.git
```

Run the bridge and worker in separate terminals. Stop competing HTTP workers for predictable development behavior. The worker accepts `--repository-grants` with the same [explicit fixed-revision read grants](REPOSITORY_READ.md). The deterministic renderer does not call an LLM or execute message/source text.

The worker initiates `ws://127.0.0.1:9020/runtime`, sends its fixed Agent bearer credential in the upgrade header and never requires an inbound runtime port. Browser Origin requests and wrong credentials/paths are rejected before task access. Both the bridge backend and client endpoint must be loopback. Tokens are not URL parameters. The protocol permits only tasks/status/validate/complete/fail routes. Runtime requests are limited to 65536 bytes. Client task responses allow 4 MiB to cover the AS 1 MiB transaction boundary plus JSON escaping and task metadata. Receive queues hold at most four frames per connection; compression is disabled. Each connection permits one outstanding request. An idle disconnected stream stops requesting new tasks; a disconnect racing an existing HTTP claim can still retain that lease until expiry. Automatic ping/pong detects dead connections. Connections retry with bounded exponential delays and small jitter; message bodies and credentials are not logged by this code.

Disconnecting does not release an executing lease. After durable expiry, a reconnected runtime can reclaim the task and reuse its persisted completion result or task-ID Git operation. A crash after Git commit retains the same commit; a completed Matrix reply with an unacknowledged Git outbox is reconciled from gateway status. Completion still rechecks membership and lease. Exactly-once external side effects and messages beyond Matrix transaction retention are not guaranteed. Cancellation remains cooperative and cannot undo an earlier write.

The bridge does not implement production TLS, identity enrollment, scoped Agent credential rotation, per-tenant quotas or production authorization. Its synchronous server does not impose a global connection/thread quota; per-connection limits do not provide a total process resource bound. Do not expose these development ports publicly. Its in-process connections are transient; retain the existing gateway and Git volumes for recovery. Restarting the bridge only drops connections; restarting the gateway retains the existing SQLite recovery rules.

Run actual Matrix acceptance on an isolated development stack:

```sh
python -m scripts.websocket_smoke --state-file .local/smoke-state.json --token-file .local/agent-token
```

This creates a temporary document repository, verifies two real Matrix/Git thread receipts around a same-port bridge restart, automatic runtime reconnect and exactly two document versions. Protocol regression tests separately cover lease recovery after a committed Git operation and recovery after a completed reply before outbox acknowledgement. These are distinct checks; a bridge restart is not a full infrastructure disaster recovery test.

Transport API references: [websockets synchronous client](https://websockets.readthedocs.io/en/stable/reference/sync/client.html), [synchronous server](https://websockets.readthedocs.io/en/stable/reference/sync/server.html).
