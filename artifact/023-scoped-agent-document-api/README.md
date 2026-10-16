# Scoped Agent Document API

Agent document operations now enter a Document API. The service obtains the task event from Gateway storage with the active task ID and lease. It checks current room membership and write power through the same permission helper used by human saves. It checks the lease again after network checks. A runtime cannot select a different event, requester, room, path, base blob, operation ID, or report body in the API request.

The service owns the fixed `demo.md` Git write, source-grant checks, deterministic repository report generation, and Git outbox reconciliation. The task ID remains the Git operation ID, so old operations and replacement leases retain replay semantics. A completed Gateway task permits receipt reconciliation only; it does not authorize another write. Human direct saves keep their existing API and share the same Git compare-and-swap semantics.

Run the loopback service with the existing development runtime token:

```sh
python -m src.agent_document_api --repo .local/documents.git --token-file .local/agent-token --gateway-url http://127.0.0.1:9000 --port 9050 --document-room '!your-workspace-room:server'
python -m scripts.websocket_worker --url ws://127.0.0.1:9020/runtime --token-file .local/agent-token --document-url http://127.0.0.1:9050
```

Configure optional `--repository-grants` on the Document API. The worker requires no Git repository path in this mode. Existing `--repo` callers cohost the same service for development compatibility. That mode provides an API boundary, not operating-system isolation. The current trusted single-runtime token and loopback deployment are development constraints, not production tenant credentials or network authorization.

Permission checks and a Git commit cross service boundaries. Cancellation or permission revocation after the last check can race with a commit. Cancellation does not roll back a committed version. Git remains the sole document content/version store; no CRDT, TypeScript service, or production deployment is implied.

Validation evidence is recorded after the final checks. Existing frontend tests use Vitest/jsdom; no real browser or Chinese IME verification is claimed. Draft PRs remain unmerged.
