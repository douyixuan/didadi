# Architecture (V0.1)

## Logical components

```
Web client ── direct save/read ── Document Service ── Git document repository
    │                                  │
    │                         metadata commit receipts
    │                                  ▼
    └── discussion ── Synapse ── PostgreSQL
                         │
                Matrix Application Service / Agent Gateway
                         │
                External Agent Runtime(s)
                         │
                scoped legacy document/source adapter
```


## Ownership
- Matrix is authoritative for rooms, messaging and membership.
- Git is authoritative for Markdown content and version history. Human saves use the direct Document Service API; Matrix receives version metadata only.
- The current Document Service is a loopback Python development component. Agent effects still use the compatible scoped adapter. It is not the proposed TypeScript/CRDT service. See `DIRECT_DOCUMENT_SERVICE.md`.
- Platform metadata DB stores tasks, agent registration, grants, audit and task retry records.
- The local Git document spike stores hashed operation metadata in new commits and private notification intent/receipts in local Git refs. See `GIT_DOCUMENTS.md`.
- Runtime owns model state and execution environment.

## Protocol guardrails
- App Service is an integration adapter, not a server-side event interception mechanism.
- Reject encrypted rooms for MVP agent context, pending E2EE permissions design.
- Task state survives gateway restart; inbound Matrix transaction IDs and event IDs must be deduplicated.
- Resource grants are server-validated references, never self-asserted permission.
- Git writes must compare versions, coordinate across processes and never force-push.

## Next spikes
1. Confirm Synapse + App Service event delivery, retry and identity namespaces.
2. Multi-process/remote-ref conflict, crash recovery and path / symlink hardening.
3. Custom Matrix event compatibility with a standard Matrix client.
