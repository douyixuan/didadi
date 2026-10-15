# Outbound WebSocket runtime

Add a loopback WebSocket bridge for the existing durable single-agent gateway. The external document runtime opens and maintains the connection. It requests work over the stream; the bridge waits for a task using the existing HTTP claim operation, while WebSocket ping/pong maintains liveness. Validation, completion, failure and recovery status use the same stream. The bridge owns no task state. SQLite leases/results and Git operations/outbox remain authoritative across disconnects.

Reuse the existing deterministic renderer, explicit source grants, stale document checks and task IDs. No LLM integration, production grants, public binding or TLS deployment. Keep old HTTP worker working. Validate auth/origin/protocol rejection, disconnect after Git commit, completion/outbox recovery and actual Matrix -> WebSocket -> Git -> thread through a bridge restart. Add CI acceptance before the competing persistent SDK smoke worker.
