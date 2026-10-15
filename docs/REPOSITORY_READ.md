# Explicit source repository read grants

The external deterministic document runtime can read exact Git files at an administrator-configured full commit. It does not run an LLM, execute source text or perform semantic code analysis. It can generate a Markdown file inventory through the existing controlled `demo.md` document write path. Git remains the only Markdown source.

Pass `--repository-grants /private/grants.json` to `scripts.document_worker`. Omit the option to deny every repository request. Keep grants and local repository locations outside the browser bundle. Example with synthetic values:

```json
{"repositories":{"fixture":{"path":"/absolute/synthetic/source","commit":"0123456789012345678901234567890123456789","files":["src/main.py"],"rooms":["!explicit-room:local"],"senders":["@explicit-user:local"]}}}
```

A structured Matrix mention includes `org.didadi.repository`:

```json
{"action":"read","repository":"fixture","path":"src/main.py"}
```

Use `action: "report"` plus the current document `base_blob` (or null for a new document) to save a deterministic inventory into `demo.md`. The report contains source commit/blob, bytes, lines and SHA-256; its Matrix receipt links the resulting document commit to the original thread. It does not include local repository locations. The same task ID reuses the existing Git operation. Stale document writes conflict. Messages cannot choose local paths, source revisions, permissions or output document paths. Combining repository and document commands is rejected.

Every read requires a matching alias, exact file, room and requester identity. The runtime reads Git objects, never the worktree. Symbolic links, submodules, non-UTF-8/NUL content and blobs over 8000 bytes are rejected. Missing objects are rejected without fetching. Git must support `--no-lazy-fetch`; unsupported versions fail closed. Transport protocols, replacement objects, inherited Git environment overrides, global/system Git configuration and filesystem monitoring are disabled for these reads. There is no checkout, filter execution, shell interpolation or write command on the source repository.

This configuration is trusted local development policy for one external runtime, not production grant enrollment or tenant isolation. A granted room can see the result. Code text is untrusted data; an external LLM runtime must implement its own prompt isolation, approval and data handling. Room membership/lease validation occurs before runtime IO and again before completion; these checks do not form an atomic transaction with Git. Changing the grant file requires restarting this example worker. No credentials or arbitrary real-user repositories are required for verification.

Run the real Matrix acceptance against your isolated development stack:

```sh
python3 -m scripts.repository_read_smoke --state-file .local/smoke-state.json --token-file .local/agent-token
```

The smoke creates a temporary synthetic source repository and separate document repository. It verifies an allowed report, a denied file, unchanged source refs/worktree and a document receipt in the original Matrix thread. Do not run a competing continuous worker during this test. It does not prove semantic analysis or production authorization.

## Local workspace controls

Pass the same `--repository-grants` file to the loopback client adapter to advertise allowed source choices. The document footer shows “Read-only source repository” only when choices match the active room and fixture user. The browser receives aliases, file paths and fixed commits; it never receives local repository locations or the Agent credential. This advertisement does not authorize a read: the external runtime independently checks its configuration.

“Read source in discussion” posts a structured mention. “Replace document with file report” explicitly replaces `demo.md` through the existing stale-blob-protected Git write flow. The control is disabled for unsaved drafts and historical versions. Previous Git versions remain available. Source reports contain deterministic file metadata, not LLM analysis. Requests appear in the existing Agent task activity and post their result to the original Matrix thread. Runtime rejection preserves the document; Retry repeats the same type of request.
