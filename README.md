# Didadi

Open-source, self-hosted Matrix-based communications for humans and external agents. Markdown documents use Git as the only source of truth.

> **Status:** Phase 0. A local Synapse + PostgreSQL + Application Service communication spike is implemented, with automated Matrix smoke tests and a single-node durable external-agent gateway spike. This is not a full messenger or production agent gateway. See [runtime evidence](docs/VALIDATION.md).

## Decisions
- Matrix (Synapse) provides identity, rooms, messages and synchronization.
- Agents use independent runtimes and connect through an Agent Gateway (planned).
- Git is the only authority for Markdown document contents and versions.
- First users: developers and agent builders; no Matrix homeserver fork.

## Run the Matrix spike

```sh
docker compose up -d --wait --wait-timeout 240
docker compose --profile test run --rm smoke
```

See [Agent gateway and interactive local preview](docs/AGENT_GATEWAY.md) for structured mentions, durable tasks and an outbound example runtime.

See [Matrix quickstart](docs/MATRIX_QUICKSTART.md) for prerequisites, registration, permissions, persistence and troubleshooting.

## React workspace client
See [the document-first React client](docs/CLIENT.md) for a real Matrix/Git workspace with optional discussion and an explicitly labeled example Agent panel. Local preview uses port `8767`; the older demos remain available.

## Git document loop
See [Git documents and local editor](docs/GIT_DOCUMENTS.md) for the Matrix → external runtime → Git → thread demo. `src/gitdocs.py` uses a dedicated bare repository, cross-process locks, blob/branch comparisons and a Git-backed notification outbox. Agent operations now use a [scoped Document API](artifact/023-scoped-agent-document-api/README.md) that derives writes from authoritative Gateway tasks and owns Git recovery. It remains a single-host development spike, not a production API.

Requirements: Python 3.11+ and Git on PATH.

```sh
python -m unittest discover -s tests -v
```

## Roadmap
1. Deploy Synapse + PostgreSQL and Matrix Application Service; verify message delivery and transaction replay.
2. External agent connection, authentication, persistent task creation and idempotent dispatch.
3. Git document service with multi-process locks, remote refs and recovery tests.
4. React + matrix-js-sdk client, docs and agent task views.

See `docs/ARCHITECTURE.md`, `docs/adr/` and `docs/VALIDATION.md`.

## Security notes
Do not deploy this prototype as an exposed Git document API. Repository operations, multi-tenant authorization, audit logging and E2EE agent behavior are not implemented. Do not expose agent credentials to web clients.

## Contributing
Open an issue describing expected behavior and tests. Keep changes small and attach evidence for concurrency and security-sensitive changes.

## License
Not yet selected. Do not assume this repository is licensed for reuse until a LICENSE file is added.
