# Reconcile an ordinary local Git remote divergence

This is an **operator procedure for trusted, service-owned local bare repositories**. It is not a web action or an automatic merge. Network remotes, credentials, permissions, rewritten/deleted upstream history and unrelated histories are outside this procedure. Never force-push, reset or rebase the shared branch. Do not erase the local repository or its receipt refs.

## What users see

`remote_diverged` is HTTP503, with `recovery.local_commit`, `remote_commit` and `merge_base` Git SHAs only. Both histories and the local commit/outbox remain in Git. Latest reads, new saves and unpublished receipts stay blocked. Fixed version reads remain available under existing room authorization. Restart keeps the ordinary-divergence diagnostic available; it does not declare the local version published.

Keep/export the unsaved draft. A failed save keeps the exact operation ID, text and base; editing is paused while its result is uncertain. Ask the workspace operator to reconcile, then use **Retry after reconciliation**. This sends the same request. Do not invent another save operation to work around publication failure. Existing browser recovery drafts can still be exported when the first Git read fails; restore waits for a successful Git load.

## Operator steps

1. Identify the configured service repository and its trusted absolute local upstream. Stop only the writers you own for this repository. Export user drafts first and keep them separate. Preserve a full backup of the bare repository including all refs/outbox receipts. Do not run these steps on someone else's checkout or live unknown service.

```sh
umask 077
service_repo=/absolute/path/to/service-documents.git
upstream_repo=/absolute/path/to/trusted-upstream.git
backup_dir=$(mktemp -d)
review_dir=$(mktemp -d)
cp -R "$service_repo" "$backup_dir/repository.git"
local_tip=$(git -C "$service_repo" rev-parse refs/heads/main)
remote_tip=$(git -C "$upstream_repo" rev-parse refs/heads/main)
git clone --no-hardlinks "$service_repo" "$review_dir/review"
git -C "$review_dir/review" remote add upstream "$upstream_repo"
git -C "$review_dir/review" fetch upstream main
```

2. Compare both tips with the diagnostic and check that the common base is expected. Review the changed paths and text. Work only in the new review clone. Do not resolve a rewritten/deleted or unrelated remote by treating it as ordinary divergence.

```sh
git -C "$review_dir/review" merge-base "$local_tip" "$remote_tip"
git -C "$review_dir/review" log --graph --oneline --all
git -C "$review_dir/review" merge --no-ff --no-commit "$remote_tip"
```

If this reports conflicts, **stop before commit or push**. Review every conflict and resolve it explicitly in the review clone. Preserve all wanted edits, including files other than demo.md. Never publish conflict markers. Stage only the reviewed resolution. If the histories have no expected common base, retain the backup and investigate separately; do not enable unrelated-history merging to bypass the refusal.

3. Inspect the staged tree and commit the reviewed merge. Confirm its two parents are exactly the retained local tip and remote tip, in that order. Both original commits must remain ancestors.

```sh
git -C "$review_dir/review" diff --cached --check
git -C "$review_dir/review" diff --cached
git -C "$review_dir/review" commit -m 'Reconcile reviewed document histories'
git -C "$review_dir/review" show -s --format='%H %P' HEAD
```

4. Recheck both shared tips before publishing. If either has changed, stop and review the new state. Ordinary push to the service repository must fast-forward; never add a force option to make it succeed.

```sh
test "$(git -C "$service_repo" rev-parse refs/heads/main)" = "$local_tip" &&
test "$(git -C "$upstream_repo" rev-parse refs/heads/main)" = "$remote_tip" &&
git -C "$review_dir/review" push origin HEAD:refs/heads/main
```

5. Resume the known service. Its normal sync checks the remembered upstream history and uses an ordinary push to publish the reviewed merge to the local upstream. Do not manually bypass this history check. If the upstream races ahead, disappears or rewrites history, publication remains blocked and both retained histories remain intact. Repeat diagnosis rather than force an update.

6. Retry the original save. The original operation returns its original commit and stable metadata receipt, once. A subsequent latest read shows the reviewed merge containing both histories. Verify the upstream and local main tips agree, both original commits are ancestors, the intended contents are present and the notification outbox is reconciled. Keep the backup and user draft until verification is complete.

## Evidence and limits

`tests/test_remote_recovery.py` covers ordinary divergence/reopen/fixed reads, explicit two-parent operator merge, same-operation receipt recovery, overlapping merge refusal, a remote advance during review, and continued refusal of known rewrites. `scripts/remote_recovery_smoke.py` exercises real HTTP plus Synapse receipts using isolated temporary local bare fixtures and an operator clone. It checks503 metadata, no early receipt, restart, fixed reads, both parent histories, normal pushes, one original-save receipt and latest merged contents.

These checks do not prove network transport, credential rotation, arbitrary operator conflict resolutions, power loss, repository corruption, multi-tenant access or GUI behavior. No user-selected shell command, Git repository or resolution can be submitted through the web API. Browser-only drafts remain local recovery copies; Git remains the saved-content authority.
