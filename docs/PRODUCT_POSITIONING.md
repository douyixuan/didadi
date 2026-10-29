# Didadi — Product Positioning (2026-10-29)

## One-liner

**Didadi is an open-source, self-hostable Agent-native workspace where people and external Agents turn conversations into traceable tasks and versioned Markdown/Git deliverables.**

Chinese: **面向开发者的开源 Agent-native 协作空间，让人和 Agent 在同一个工作区讨论、执行任务、审阅并沉淀 Git 文档。**

## Who / job to be done

- First customer: developer or small software/Agent-building team that needs discussion, knowledge, code references and long-running autonomous Agents in one place.
- Urgent job: give external Agents **identity, least privilege, persistent work, progress visibility, accountable outputs and review**. Retain links across conversation, task, document and commit.
- First “aha”: a user asks an Agent in a room to work on a scoped task, can see real status, reviews a document change, and navigates from the saved Git commit back to its discussion.

## Differentiator and scope boundary

Didadi is neither an open-source Telegram clone nor an unlimited Notion/Feishu clone. It is also not a model-hosting system or an Agent execution sandbox. The *workspace* owns durable coordination, identities, permissions and artifacts; **each Agent keeps its own runtime**. Reuse Matrix for communications; use Git as the only authoritative Markdown document/version source; provide a direct Document Service API for writing and reading; Matrix receives references and receipts, not new document body copies.

Core primitives: **Workspace, Member (human/Agent), Room/Thread, Document, Task, Artifact, Grant, Git Revision**. Every feature should connect to at least one of these and improve the primary end-to-end journey.

## Design tenets

1. **Real beats simulated:** a fictional adapter is a test fixture, never an acceptable login or public demo.
2. **Agent is a member, not a chat gimmick:** independently connected runtime, explicit scopes, durable task status and recorded outcomes.
3. **Conversation produces artifacts:** discussions link to tasks, documents, versions and source references.
4. **Git is canonical for Markdown:** no shadow document system in Matrix; no force push. Protect drafts on conflict and failure.
5. **Least privilege by construction:** server-derived Matrix authority and scoped resource grants; never trust UI-selected paths, agent-supplied authority or embedded repository credentials.
6. **Self-hostable first:** start with one coherent secure deployment; distributed scale can come later.
7. **Evidence beats checkbox:** verified on an exact commit with end-to-end behavior and a published limitations list.

## Product surface

- **Communication:** private/group/channel rooms, Markdown chat, historical threads, quotes, files, search, notifications.
- **Documents:** Notion/Feishu-quality *usable editing experience* with independent Markdown documents, hierarchy, full-text search, version history, source attribution, clean conflict/recovery UX. Full synchronous CRDT collaboration is later scope.
- **Agents/Tasks:** invite/register, discover capabilities, assign, approve scoped grants, observe real progress, interrupt/resume, review structured results and linked artifacts.
- **Developer workflow:** authorized GitHub/GitLab/self-hosted references, immutable lines/commits, document-to-source traceability, safe write/PR review.

## What is deliberately deferred

Native iOS/Android, federation, E2EE with Agent plaintext access, marketplace, generalized multi-Agent orchestration, CRDT live cursors and speculative language rewrites do not gate the first beta. Preserve these as explicit backlog, not as forgotten features.

## Release promise

Beta requires a **genuine two-user + one external-Agent + Git-backed document** journey on an independently deployed setup. Tests of mocked Matrix, in-memory sessions, local fixtures and a green CI alone are not release evidence. Respect the live ADR #41 ownership and pause on Issue #12.
