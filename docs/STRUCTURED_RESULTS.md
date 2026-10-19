# Structured external runtime results

The runtime can send an optional `outcome` with `/agent/complete` over HTTP or the WebSocket transport.
The reply `result` remains display text.
The client does not use this text to decide whether a document was saved.

```json
{
  "id": "<task id>",
  "lease": "<current lease>",
  "result": "Human-readable reply in any language",
  "outcome": {
    "version": 1,
    "status": "saved",
    "path": "demo.md",
    "commit": "<40 lowercase hex characters>",
    "blob": "<40 lowercase hex characters>"
  }
}
```

The current development grant supports only `demo.md`.
The gateway validates metadata before it stores a result or sends a reply.
Unknown keys and document body fields are rejected.

- `saved` requires `path`, `commit` and `blob`.
- `read` can omit the document reference, or include all three reference fields.
- `conflict` and `rejected` can include a `reason`.
- Reasons are `stale_version`, `invalid_request` or `source_not_granted`.
- `version` must be the integer `1`.

The first accepted completion fixes the reply text and outcome in one database transaction.
A retry must use the same pair, even after a failed Matrix send or a new lease.
Claim responses include the fixed pair.
Do not render another result when a claimed task already has one.
The reply event includes `org.didadi.task.result` with the same metadata.
Completed task status reads this outcome from the gateway database.
It does not infer success from Matrix reply text.

Old string-only runtimes can still complete tasks.
Existing database rows keep a null outcome.
There is no inference or automatic metadata backfill.
For an unknown document outcome, the client keeps its draft and blocks further commands until a latest-version read succeeds.
This read does not resubmit the task.
Old version receipts remain readable for history navigation.
New structured receipts do not fall back to text when their version is unsupported.

An outcome is a statement from the authenticated runtime.
Schema validation does not independently prove a Git write.
It does not grant access to another repository or file.
This change does not implement the direct Document Service API from issues #14 and #18.
Document content still follows the existing Matrix task path.
No production login, tenant authorization or LLM is included.

## Acceptance

Run the normal Matrix smoke setup, then use its generated state and token:

```sh
python3 -m scripts.structured_result_smoke --state-file .local/smoke-state.json --token-file .local/agent-token
```

This test starts a separate client adapter and outbound runtime process on loopback ports.
It uses a temporary document repository.
It tests a translated reply, duplicate transactions, saved/read/conflict/rejected outcomes and the original thread receipt.
The test stops its processes and removes its temporary documents.
It does not test native editor layout or IME input.
