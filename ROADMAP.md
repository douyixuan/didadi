# Didadi — Product Roadmap

> Planning baseline: 2026-10-29. Source: `main` at `1f371893baa0` (last repository commit 2026-10-22). This is a **delivery plan**, not evidence that unverified features work. See [positioning](docs/PRODUCT_POSITIONING.md), [daily delivery instructions](docs/DDD_DAILY.md), and [acceptance evidence](docs/MVP_ACCEPTANCE.md).

## North star

**Agent-native Workspace for developers and Agent builders.** A human and an external Agent are first-class members of a shared workspace. Discussion (Matrix) creates actionable work; the Agent executes with scoped authority; results become reviewable, versioned Markdown/Git artifacts. Do not attempt to win by duplicating every feature of Feishu, Notion, or Telegram.

**Primary end-to-end journey:** sign in as a real user → enter a workspace/room → discuss → create/edit a Markdown document → mention/assign an external Agent → observe progress and recover after interruption → review the structured result/artifact → retain a Git version and trace back to its source discussion.

**Architecture invariants:** Matrix owns identity/rooms/messages; Git remains the authority for Markdown content and published versions; human document saves call Document Service directly, while Matrix carries metadata receipts; Agents execute in independent runtimes and receive server-enforced scoped access. Existing Python implementations are development spikes, not production trust boundaries. No plaintext document bodies in new Matrix receipts. E2EE, federation, CRDT and language migrations require explicit ADR decisions, not ad-hoc changes. PR #41 / Issue #18 have an existing owner; do not silently supersede them.

## What is already present, and what is NOT verified

- The Oct 22 merge series (#52–#64) brought multi-document create/move, message-to-document, historical threads, body search, attachments, quotes, source-line references, People, room types and fictional session-contract tests onto `main`.
- Latest `main` CI [Test #39755264542](https://github.com/douyixuan/didadi/actions/runs/39755264542) succeeded for commit `1f371893baa0`, but the archived merge evidence explicitly says this does not verify real login, production security, real Matrix on the final package, physical browser/IME behavior, public deployment, or real mobile interactions.
- README still labels Phase 0; `docs/LOCAL_WORKSPACE.md` describes a loopback synthetic-identity dev environment. **Real login/logout are not implemented**: PR #64 is fictional only.
- Only PR #41 is open, proposing ADR 0002. Issue #12 remains explicitly paused. Open Issues/unchecked boxes are not proof code is absent; reconcile code, exact SHA, tests and real acceptance before changing checkmarks.

## Delivery phases (targets, not guaranteed dates)

### P0 · Real usable workspace — first 1–2 weeks (NOW)

- [ ] **Real identity:** working Matrix sign-in, session persistence, current-device sign-out, rejected expired credentials; no fictional fallback in the actual product flow.
- [ ] **Workspace flow:** account/room listing, private/group/channel entry, permissions and isolation, unread/status indicators (as supported) and understandable empty/error states.
- [ ] **Human workflow:** a real user can send a message, create/edit a distinct Markdown document, reload and find the same Git-backed version; retry/conflict never silently loses drafts.
- [ ] **Verification:** from clean install, two independent test accounts pass real Synapse + API + browser E2E; saved content is in Git and only metadata receipts are in Matrix; reconnect and retained-volume recovery pass.
- [ ] **Evidence:** recorded exact main SHA, CI, reproducible commands/screenshots, test scope and known failures; if no public deployed product exists say “local preview only.”

**P0 exit:** two genuine users can sign in, communicate, edit a shared workspace document and return after reload/restart on an independently installed build. Offline mocks or fictional accounts cannot satisfy this.

### P1 · Agent as a first-class teammate — next 2 weeks

- [ ] Invite/register an externally hosted Agent; bind an actual Agent identity, display capabilities/presence and restrict room/project/document scopes.
- [ ] Mention/assign a task with stable task ID; show actual lifecycle, runtime-reported progress, cancellation and retry with durable task state.
- [ ] Recover lease/restart/disconnect without duplicate side effects; enforce revocation and denied-path checks in integration tests.
- [ ] Return structured outcomes and user-visible reasons for failure, not only natural-language chat replies.

**P1 exit:** human assignment → authorized external runtime → observed progress → completed/rejected result, including one interruption and permission-revocation test.

### P2 · Reviewable work products and Git collaboration — next 2 weeks

- [ ] Link task, source conversation, produced Markdown artifact, author, and immutable Git commit in both directions.
- [ ] Agent edits through the scoped Document API; human can inspect diffs, accept/reject or retry without overwriting a changed base.
- [ ] Link and browse repositories (GitHub/GitLab/self-hosted) with explicit grants; cite fixed commit/file lines; support authorized write/PR operations in a separate approved scope.
- [ ] Ensure multi-document moves/renames, source references, version history and recoverable conflicts work together on actual running services.

**P2 exit:** from a Matrix discussion, an Agent produces one reviewable document change, the human accepts it, Git records it, and the workspace links the result back to its task and discussion.

### P3 · Reproducible self-hosted beta — next 2 weeks

- [ ] One supported installation/upgrading path with a truthful minimum configuration, secret handling and backup/recovery procedure.
- [ ] Explicit authorization, multi-user isolation, audit traces, security threat-model pass and no production deployment of the prototype token/API.
- [ ] Cohesive responsive Web UI with tested desktop + mobile browser flows, basic accessibility and meaningful empty/error states.
- [ ] Public demo URL **only after actual deployment and verification**; reproducible independent-install onboarding, license decision, release notes and GitHub issue templates.

**P3 exit:** a new developer can deploy from the documented source, invite another person and an Agent, complete the P2 core journey, and restore from a backup.

## Later phases: preserve scope without blocking beta

- **P4:** real-time multi-person editing/CRDT, stronger merge UX, multi-Agent delegation, human approval/audit controls, plugin SDK and MCP integrations.
- **P5:** native mobile, Matrix federation/E2EE policy and implementation, Agent marketplace, advanced enterprise workspace and operational management.

## Daily execution rules

Read [docs/DDD_DAILY.md](docs/DDD_DAILY.md) at the start of every work session. Select the top unmet acceptance item; deliver a **vertical slice** with code, realistic tests and observable output. Keep each PR small, review against `main`, preserve untouched contributors' work (especially PR #41 and paused Issue #12), and do not mark completion based on offline CI alone.

---

## Original feature inventory (retained for completeness)

The checked items below reflect the original narrow checkmark criteria; new phase acceptance is independent. Do not remove feature scope or automatically mark an item complete solely because a PR was merged.

## 普通通信

### 会话管理

- [ ] 真实登录（待接入）
- [ ] 当前设备退出（待接入）
- [ ] 房间列表浏览（待验收）
- [ ] 未读消息提醒
- [ ] 私聊会话（待验收）
- [ ] 群组会话（待验收）
- [ ] 频道会话（待验收）

### 消息交流

- [ ] Markdown消息（待验收）
- [ ] 附件收发（待验收）
- [ ] 引用回复（待验收）

### 讨论检索

- [ ] 话题完整回复（待验收）
- [x] 历史分页浏览
- [ ] 消息正文搜索（待验收）
- [ ] 搜索返回上下文（待验收）

## Agent成员

### 成员接入

- [ ] Agent注册邀请（待接入）
- [ ] 通用Agent身份绑定（待接入）
- [ ] 主动连接网关（待验收）
- [ ] 头像名字设置
- [ ] 能力展示说明

### 成员交互

- [ ] 上下文范围控制
- [ ] 提及唤起任务（待验收）
- [ ] Agent私聊交互
- [ ] 成员任务分配

## 文档管理

### 多文档编辑

- [ ] Git唯一文档源（待验收）
- [ ] 独立创建文档（待验收）
- [ ] 文档列表打开（待验收）
- [ ] 人工编辑保存（待验收）
- [ ] 文档重命名移动（待验收）
- [ ] 历史版本回看（待验收）
- [ ] 文档稳定标识
- [ ] 按基线原子保存（待验收）
- [ ] 草稿冲突保护（待验收）
- [ ] Agent编辑文档

### 消息转文档

- [ ] 选择消息生成（待验收）
- [ ] 保留来源引用（待验收）
- [ ] 返回来源讨论（待验收）
- [ ] 失败重试去重（待验收）

### 实时协作

- [ ] 多人实时协作

### 文档版本通知

- [x] Git提交后通知
- [x] 通知失败重试

### 文档检索导出

- [ ] 文档正文搜索（待验收）
- [ ] Markdown导出（待验收）

## Git集成

### 仓库关联

- [ ] 关联GitHub仓库
- [ ] 关联GitLab仓库
- [ ] 关联自建Git

### 代码引用

- [ ] 文件行引用（待验收）
- [ ] Commit引用
- [ ] PR引用

### Git写入协作

- [ ] 授权Git写入
- [ ] 创建PR

### 授权读取

- [ ] 默认只读访问（待验收）
- [ ] Agent授权读取（待验收）
- [ ] 仓库版本路径授权（待验收）
- [ ] 浏览器无仓库凭据（待验收）

## 长任务管理

### 任务生命周期

- [ ] 任务独立运行（待验收）
- [ ] 重启恢复任务（待验收）
- [ ] 断线恢复执行（待验收）
- [ ] 租约恢复保护（待验收）
- [ ] 重复分发去重（待验收）
- [ ] 查看任务状态（待验收）
- [ ] 暂停继续任务
- [ ] 取消任务执行（待验收）
- [ ] Runtime主动进度（待接入）

### 任务产物

- [ ] 产物查看下载
- [ ] 任务关联产物
- [ ] 进度回原话题（待接入）
- [x] 固定Agent结果回帖
- [ ] 任务产物回话题

### 多Agent协作

- [ ] 多Agent任务委派
- [ ] 敏感操作审批

## 安全权限

### 访问隔离

- [ ] 房间最小授权（待验收）
- [x] 指定房间Agent收件
- [ ] Workspace隔离

### 加密通信

- [ ] 端到端加密

### 审批审计

- [ ] 审批记录查询
- [ ] 操作审计追踪

## 部署生态

### 自托管使用

- [x] 单机Compose部署
- [x] 双用户消息互通
- [ ] Web移动适配（待验收）

### 跨端使用

- [ ] 原生移动端

### 联邦互通

- [ ] Matrix联邦

### Agent生态

- [ ] Agent市场

### 开发者接入

- [ ] SDK接入
- [ ] MCP接入
