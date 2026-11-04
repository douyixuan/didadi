# DDD — Daily Didadi Delivery Contract (2026-10-29)

## Mission

Advance [Didadi](https://github.com/douyixuan/didadi) toward the self-hosted **Agent-native Workspace** defined in [PRODUCT_POSITIONING.md](PRODUCT_POSITIONING.md) and [ROADMAP.md](../ROADMAP.md). Your responsibility is **working, verified product delivery**, not expanding the feature list, writing plans repeatedly or generating mock screens. Make progress autonomously without asking for routine approval; never claim tests, merges, deployments or links that you have not verified.

## Tracked delivery milestones and issue selection

Delivery is tracked in GitHub issue-based milestone checklists: [P0 #85](https://github.com/douyixuan/didadi/issues/85) → [P1 #86](https://github.com/douyixuan/didadi/issues/86) → [P2 #87](https://github.com/douyixuan/didadi/issues/87) → [P3 #88](https://github.com/douyixuan/didadi/issues/88). These are parent Issues, not GitHub native Milestone objects.

At the start of every run, read the earliest incomplete milestone tracker and its linked child issues. **Current first unaccepted work item: [#70 real-user room navigation and membership](https://github.com/douyixuan/didadi/issues/70)**. Child #69 was accepted in isolated loopback real Matrix/browser/Git E2E after [PR #90 merged](https://github.com/douyixuan/didadi/pull/90) to main `271f15a68fbc37356b3cb368943cb1871f9ce30c` with [matching main CI](https://github.com/douyixuan/didadi/actions/runs/41783890475); see [#69 proof](https://github.com/douyixuan/didadi/issues/69). P0 #70–#72 and milestone #85 remain open. Check related existing Issues/PRs and newly merged changes before starting. Choose the first unaccepted, unblocked issue; use realistic vertical slices to implement, test and merge. If already implemented but unverified, do the required real acceptance instead of writing duplicate code. Every completed issue must link exact PR/head/main SHA, relevant CI and **actual** E2E evidence before its parent checkbox is checked. No pass based solely on mocks, screenshots or a green offline CI. Keep #12 paused and do not take ownership of PR #41.

## P0 TDD / CI work contract (2026-11-04)

Read [P0_TDD_CI.md](P0_TDD_CI.md) before implementing #70–#72. Each vertical slice begins with a **reproducibly failing behavior/authorization test (Red)**, followed by the smallest code change (Green), regression and cleanup (Refactor), and exact PR/head/main offline + real E2E evidence. Do not lower assertions or count a leaf on test-plan-only, mock-only or pre-merge changes. The existing #69 proof remains valid; do not reimplement it. The P0 real-CI gate applies to trusted in-repository code PRs and relevant main pushes; skipped fork/docs CI is not acceptance. Main branch protection required-check enforcement is not yet verified.

## On every execution

1. **Ground truth first.** Read `main` README, ROADMAP, this contract, PRODUCT_POSITIONING, current open issues/PRs, latest commits and CI. Check exact GitHub status; avoid working from stale previous-run assumptions. Treat the Oct 22 feature statements as historical: real loopback login/logout (#69) was subsequently verified and merged Nov 4; broader room/document/clean-install acceptance (#70–#72) and full Beta remain unverified.
2. **Choose one highest-value vertical slice**, always in P0→P1→P2→P3 exit-criteria order. If current top item is blocked, document the exact blocker and choose an independent adjacent slice. Never confuse offline test coverage with real integration acceptance.
3. **Begin with today's target and evidence required.** Prefer improving the actual end-to-end experience over another isolated feature or UI mock. Reuse code, reduce duplicate abstractions and explain any necessary architecture changes.
4. **Implement and verify.** Work on a dedicated branch; make one reviewable PR per coherent unit, with changed files, screenshots or trace, exact SHA, realistic tests, negative/security cases and reproduction steps. Use CI; after merge verify `main` CI. Run actual Synapse + API + browser tests where possible. Do not mark a checkbox complete if its exit test is not observed.
5. **Manage PRs and ownership.** Inspect concurrent changes and existing PRs before editing; avoid duplicate implementation. New PRs may be merged autonomously only when scope is authorized, owner/reviewer constraints permit it, no unresolved blocking review/conflict exists, exact-head CI passes, and the change is safe. Never bypass branch protection, authentication, missing explicit approval or refusals. Do **not** rewrite/merge PR #41 or assume approval of its ADR; Issue #12 stays paused. Security boundary/ADR/E2EE/CRDT decisions need their own review.
6. **Update artifacts with proof.** Update ROADMAP checkboxes only with the specific acceptance evidence; add links to validated tests or Issues. Record blockers, ownership and next slice. Do not open new issues for an existing tracked issue.
7. **End-user report, leaf-only:** `🌿 今天 +N 片｜累计 X/Y 片｜当前 Pn`, optionally one `新叶：#Issue 功能名（真实证据链接）` line and a critical-blocker line only if needed. Count each #69–#84 child once only after implementation on main, complete real acceptance, parent checklist and evidence. Compare validated leaf sets with the previous daily report (use baseline if unknown). Keep PR/commit/SHA/CI/E2E/next slice details in GitHub issues and PRs. An unmerged PR is “candidate”, not delivered; a successful offline CI is not real product acceptance. No hourly report.

## Historical first-slice baseline (2026-10-29; #69 accepted 2026-11-04)

The authentication work below was the initial scope, **not** an instruction to implement it twice. Continue #70 next, testing genuine Matrix DM/group/channel room navigation, membership revocation and unread state; then #71 and #72. Keep #41/#18 separately owned and #12 paused.

**P0 Real sign-in/sign-out and identity scoping in the running Matrix-backed client**, not the fictional-only memory contract of PR #64. First inspect existing token/session plumbing and owner constraints. Acceptance: genuine login of two separate accounts, durable session on refresh, sign-out invalidation in the current device, no cross-user leakage, expired/invalid login rejection; E2E tests against real Synapse and browser. Build on existing workspace UI and document flow, do not replace Matrix or broaden to federation/E2EE.

If integration infrastructure is unavailable, still ship an independently testable, reviewable slice plus exact reproducible command and verified blocking environment constraint. Do not forge live acceptance.

## Safety and product guardrails

- Matrix identity/rooms/messages; Git Markdown contents/versions; direct Document API for human saves; Matrix only metadata receipts for new document actions. External Agent runtime remains independent.
- No secret, token, private data or real user account in public test fixtures; avoid destructive resets of other services/volumes. Do not expose development APIs/tokens on public deployment.
- Defer native mobile, multi-agent orchestrators, marketplace, federation, E2EE, CRDT/live-cursor, TypeScript rewrite until ordered phases or explicit architecture approval.
- Full function inventory in ROADMAP is retained; “not first beta” is not “removed”.
