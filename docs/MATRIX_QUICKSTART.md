# Phase 0 Matrix communication spike

This is a local development stack for Issue #1, not a production messenger or a durable agent scheduler. Requires Docker Engine/Desktop and Compose v2 with `--wait` support; internet access is needed to pull images. No Python packages or local Python installation are required for the stack.

For the full document workspace and a fresh synthetic source fixture, use [LOCAL_WORKSPACE.md](LOCAL_WORKSPACE.md). The steps below exercise only Matrix communication.

## Start and test

```sh
git clone https://github.com/douyixuan/didadi.git
cd didadi
docker compose config --quiet
docker compose up -d --wait --wait-timeout 240
docker compose --profile test run --rm smoke
```

The init container generates Synapse configuration and the AS registration automatically. Synapse loads `/config/appservice.yaml` via `app_service_config_files`; there is no manual registration API call. Configuration is JSON (valid YAML) to avoid a bootstrap dependency. Server identity is fixed as `didadi.localhost`; the client endpoint is `http://localhost:8008`. Only this endpoint is published, bound to host loopback. AS port 9000 is also bound only to host loopback for the external runtime; PostgreSQL port 5432 remains internal. Federation is disabled for this spike. PostgreSQL readiness uses TCP, so Synapse cannot start against the temporary Unix-socket-only initialization server.

The smoke test uses Synapse's shared-secret admin registration endpoint to create two **non-admin** users with random names/passwords, then explicitly registers `@_didadi_agent_echo:didadi.localhost` through the AS registration flow. Anonymous registration is disabled. Tokens/passwords are never printed. Re-running the smoke test creates a fresh room and two users, so tests work with retained volumes.

The test asserts:

1. Unauthenticated AS transaction receives HTTP 403.
2. AS cannot impersonate the ordinary Alice identity outside its namespace.
3. Alice creates a private, unencrypted room; Bob joins; the invited echo agent joins through the AS callback.
4. Alice -> Bob and Bob -> Alice messages are received through `/sync` with matching event IDs and senders.
5. Alice sends `!echo <nonce>`; Synapse pushes it to AS; AS sends `Echo: <nonce>` using the managed identity; Bob receives it via `/sync` with a reply reference to the original event.
6. Immediate replay of the genuine trigger event twice produces one reply through a deterministic Matrix outbound transaction ID.

The Phase 0 echo fixture itself has no LLM or E2EE implementation. The subsequent [durable gateway spike](AGENT_GATEWAY.md) adds a separate mentioned-task queue, outbound runtime and local development preview. The echo responder is the smallest AS integration fixture; external agent execution remains separate future work.

## Persistence and restart check

Named volumes retain:

| Volume | Contents |
| --- | --- |
| `config` | Generated AS/HS tokens, database password, shared registration secret, Synapse config, AS registration, last smoke-test credentials |
| `postgres` | Matrix users, room state, messages, access tokens and Synapse database state |
| `synapse` | Signing key and media store |

After a successful smoke run:

```sh
docker compose down
docker compose up -d --wait --wait-timeout 240
docker compose --profile test run --rm smoke python -u -m scripts.matrix_smoke --check-persistence
docker compose --profile test run --rm smoke
```

The persistence check reads the previous message using both original user tokens. The second smoke run confirms AS still works after recreation. `down` preserves volumes. **`docker compose --profile test down -v` deletes all local data and credentials**; use only for an intentional clean reset. Do not remove only `config` while retaining the database: regenerated passwords would no longer match. Back up all three volumes together when stopped.

## AS permissions and limits

The exclusive user namespace is exactly `^@_didadi_agent_[a-z0-9_]+:didadi\.localhost$`. Room and alias namespaces are empty; there is no global room subscription. The separate AS sender is `@_didadi_service:didadi.localhost`. Matrix delivers events involving managed users and rooms they join. Inviting the echo agent authorizes its participation in this demo; it auto-accepts invitations. Any local user may invite it; there is no tenant/inviter allowlist yet.

`hs_token` authenticates Synapse -> AS through a Bearer header; distinct `as_token` authenticates AS -> Synapse and permits managed identity assertion. Ordinary users remain outside that scope. The handler responds only to `!echo ` text in rooms where the agent is joined; it ignores its own events and checks that room encryption state is absent. An unavailable encryption-state lookup fails closed. This is no claim of E2EE support.

Processing is synchronous, returning 503 if upstream handling fails so Synapse can retry. Outbound transaction IDs derive from source event IDs; immediate retries are covered, but there is **no durable inbound transaction/event ledger, no durable task dispatch, and no exactly-once guarantee across arbitrary outages or homeserver deduplication expiry**. The structured-mention path now has a durable ledger in the [Issue #2 spike](AGENT_GATEWAY.md); the legacy `!echo` path remains synchronous.

This is a trusted local development environment: the services share a configuration volume containing secrets, and Python fixtures run as container root. Do not expose it publicly or use real confidential conversations. Production secret isolation, TLS, image/security updates, resource limits, backups and authorization are not claimed. Images are pinned by release tag (not immutable digest); Synapse v1.139.0 is a reproducibility baseline, not a claim of latest supported release.

## Diagnostics and CI

```sh
docker compose ps -a
docker compose logs --tail=150 synapse postgres appservice
python -m unittest discover -s tests -v  # local Python 3.11+ and Git
```

AS logs source event IDs on replies, not message bodies or credentials. Avoid sharing generated configuration. The `matrix-smoke` job in `.github/workflows/test.yml` executes the real stack, smoke tests, container recreation and persistence check; failures print service diagnostics, then remove CI volumes. See `VALIDATION.md` for actual evidence and remaining gaps.

References:
- https://spec.matrix.org/v1.15/application-service-api/
- https://element-hq.github.io/synapse/latest/usage/configuration/config_documentation.html
- https://element-hq.github.io/synapse/latest/admin_api/register_api.html
