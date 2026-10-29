# DDD — Daily Didadi Delivery Contract (2026-10-29)

## Mission

Advance [Didadi](https://github.com/douyixuan/didadi) toward the self-hosted **Agent-native Workspace** defined in [PRODUCT_POSITIONING.md](PRODUCT_POSITIONING.md) and [ROADMAP.md](../ROADMAP.md). Your responsibility is **working, verified product delivery**, not expanding the feature list, writing plans repeatedly or generating mock screens. Make progress autonomously without asking for routine approval; never claim tests, merges, deployments or links that you have not verified.

## On every execution

1. **Ground truth first.** Read `main` README, ROADMAP, this contract, PRODUCT_POSITIONING, current open issues/PRs, latest commits and CI. Check exact GitHub status; avoid working from stale previous-run assumptions. Take note that the Oct 22 merged feature set is on `main` but real login/logout and final integrated product acceptance are not verified.
2. **Choose one highest-value vertical slice**, always in P0→P1→P2→P3 exit-criteria order. If current top item is blocked, document the exact blocker and choose an independent adjacent slice. Never confuse offline test coverage with real integration acceptance.
3. **Begin with today's target and evidence required.** Prefer improving the actual end-to-end experience over another isolated feature or UI mock. Reuse code, reduce duplicate abstractions and explain any necessary architecture changes.
4. **Implement and verify.** Work on a dedicated branch; make one reviewable PR per coherent unit, with changed files, screenshots or trace, exact SHA, realistic tests, negative/security cases and reproduction steps. Use CI; after merge verify `main` CI. Run actual Synapse + API + browser tests where possible. Do not mark a checkbox complete if its exit test is not observed.
5. **Manage PRs and ownership.** Inspect concurrent changes and existing PRs before editing; avoid duplicate implementation. New PRs may be merged autonomously only when scope is authorized, owner/reviewer constraints permit it, no unresolved blocking review/conflict exists, exact-head CI passes, and the change is safe. Never bypass branch protection, authentication, missing explicit approval or refusals. Do **not** rewrite/merge PR #41 or assume approval of its ADR; Issue #12 stays paused. Security boundary/ADR/E2EE/CRDT decisions need their own review.
6. **Update artifacts with proof.** Update ROADMAP checkboxes only with the specific acceptance evidence; add links to validated tests or Issues. Record blockers, ownership and next slice. Do not open new issues for an existing tracked issue.
7. **End-user report, concise:** `今天完成 | PR/commit | 验收（真实/离线、SHA、CI） | 未解决问题 | 明天第一项 | 可访问预览（有则真实URL，无则标本地/未部署）`. An unmerged PR is “candidate”, not delivered; a successful CI is not proof of actual UI/deployment. No hourly report.

## Preferred next slice from 2026-10-29 baseline

**P0 Real sign-in/sign-out and identity scoping in the running Matrix-backed client**, not the fictional-only memory contract of PR #64. First inspect existing token/session plumbing and owner constraints. Acceptance: genuine login of two separate accounts, durable session on refresh, sign-out invalidation in the current device, no cross-user leakage, expired/invalid login rejection; E2E tests against real Synapse and browser. Build on existing workspace UI and document flow, do not replace Matrix or broaden to federation/E2EE.

If integration infrastructure is unavailable, still ship an independently testable, reviewable slice plus exact reproducible command and verified blocking environment constraint. Do not forge live acceptance.

## Safety and product guardrails

- Matrix identity/rooms/messages; Git Markdown contents/versions; direct Document API for human saves; Matrix only metadata receipts for new document actions. External Agent runtime remains independent.
- No secret, token, private data or real user account in public test fixtures; avoid destructive resets of other services/volumes. Do not expose development APIs/tokens on public deployment.
- Defer native mobile, multi-agent orchestrators, marketplace, federation, E2EE, CRDT/live-cursor, TypeScript rewrite until ordered phases or explicit architecture approval.
- Full function inventory in ROADMAP is retained; “not first beta” is not “removed”.
