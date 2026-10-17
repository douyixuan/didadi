# Direct document saves

The React workspace saves human edits through `PUT /api/documents/demo.md`.
It does not send the document body to Matrix or wait for an external worker.
Git is the only store for document contents, versions and receipt intent.
This is a single-host development service, not a production authorization system.

```json
{
  "room": "<bound workspace room>",
  "operation": "<client UUID>",
  "content": "<Markdown text>",
  "base_blob": "<previous Git blob or null>"
}
```

The service supports only `demo.md` and the configured workspace room.
The server session supplies the author identity.
Every save checks current Matrix membership, room encryption and power levels.
A joined user with power level 50 or higher can write.
Joined readers can read but cannot save.
Failed authority checks cannot write Git.
Matrix must be reachable for live authorization; an external Agent is not required.

The limit is 64 KiB of UTF-8, including an empty document.
CRLF and Unicode remain unchanged in the Git blob and read API.
The commit author is the Matrix user ID.
Its email is an opaque identifier under `matrix.invalid`, not an inferred personal address.
The service remains the committer.

A successful response has `status: saved`, `commit`, `blob`, `author`, `receipt` and `receipt_pending`.
A stale base or a changed payload under the same operation returns HTTP 409 with `status: conflict`.
Publication uncertainty returns HTTP 503 with `status: publication_pending`.
A retry must use the original operation, content and base.
The client keeps the entire pending request and pauses editing until Retry resolves it.
It does not create another operation for an uncertain save.
A known conflict keeps the draft for an explicit merge.

## Durable receipts

The commit contains metadata-only notification intent in the existing Git outbox.
The reply carries `org.didadi.document.commit` with path, commit, blob and author.
It contains no document text and makes no Agent task.
The Matrix transaction is derived from the fixed Git operation.
The service acknowledges the outbox only after Matrix acknowledges the receipt.
A failed notification returns saved with `receipt_pending: true`.
A later read or save can recover pending receipts after a restart.
A repeated request resends the same Matrix transaction, including after an ACK is lost.
The direct service never sends or acknowledges old Agent outbox items.
The Agent reconciler skips direct receipt items.

The document repository records its bound room in local Git configuration.
Existing Agent document reads and mutations cannot use another room with that repository.
Gateway validation checks current requester membership for document/source tasks and power level 50 for mutations.
These checks also prevent raw low-power Matrix commands from bypassing the direct API policy.
They cannot make a Matrix permission change and a Git write one distributed atomic transaction.

## Migration boundaries

Human workspace saves now use the direct API.
Discussion and document selection are separate; changing the discussion room does not discard the workspace draft.
The existing Agent protocol remains for compatibility and explicit source reports.
It is not a second public document API.
Migrating all Agent effects to scoped Document Service grants, remote merge handling and CRDT editing remains future work.
No TypeScript service, tenant login or CRDT hot state is claimed here.
The proposed ADR from issue #18 is still a separate architecture decision.

Run the real workerless acceptance after Matrix setup:

```sh
python3 -m scripts.direct_document_smoke --state-file .local/smoke-state.json --token-file .local/agent-token
```

It covers raw UTF-8/CRLF, author identity, idempotent retries, concurrent conflicts, reader denial, room binding and CSRF.
It also checks receipt failure, service recreation, lost notification ACK and raw Matrix privilege bypass denial.
No external document worker is started for these saves.
Native editor layout and IME input require separate browser acceptance.

## Non-overlapping concurrent human edits

Human direct saves now attempt a line-based three-way merge when the submitted base is stale. The base must be a regular blob from this document's reachable history. Different paragraphs can merge; overlapping changes return409 with bounded `conflict_markdown` and `conflict_truncated` details and leave Git unchanged. Unknown/deleted bases, binary or invalid UTF-8, and inputs/results above64KiB fail conservatively. This is not a remote divergent-branch merge or CRDT.

Successful responses include `merged` and exact committed `content` over the authorized HTTP API. The client adopts that text before refreshing history, so a failed refresh cannot pair unmerged text with a merged blob. Original operation IDs replay the original commit and merged flag, even after restart; receipts remain metadata-only. Review-only conflict details never replace the draft or enter Matrix.

`GitDocs.write(..., merge_non_overlapping=True)` is opt-in; default CAS and external Agent writes remain strict. The existing author, room/power checks and outbox behavior are unchanged. `python -m scripts.concurrent_merge_smoke --state-file ... --token-file ...` verifies two independent HTTP sessions with real Matrix authority, restart/idempotency, overlap protection and no body in Matrix. Both sessions use the same already-authorized synthetic identity; this does not certify distinct-user production permissions.
