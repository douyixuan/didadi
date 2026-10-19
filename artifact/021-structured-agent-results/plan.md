# 结构化Agent文档结果

状态：实施中。用户授权持续推进、端到端验收、独立review/CI。依据原ADR0001、Issues14/18；18的ADR仍Proposed、原owner docs-only要求不被当成已接受架构。本切片不改直接保存路径或权限。

今天核验：main f0ab205；31–36全draft，无新协作者PR；已有暂停脏worktrees不动，8782/83对应36759ec。未找到独立PRD，以README/ADR/Issues为依据。合入既有拒绝保持，不用新泛化推进指令绕过。

目标：外部runtime complete同时提交body和v1 outcome，gateway同一原子固定点持久化，lease/restart重试完整复用；Matrix附org.didadi.task.result，客户端task状态直接取持久化结果，不再根据英文body判定保存/冲突/拒绝。兼容老string-onlyagent，缺结构结果保留草稿，仅显式加载最新，不假定成功或自动重发。

验证：worker/schema/gateway迁移、结果固定重放/发送失败重租约、翻译后的body不影响状态、未知协议保稿；真实独立Matrix+WS外部worker+Git+client CSRF闭环，进程/网关重启验收。完整前后端/语料/build、独立review、精确head CI。新draft依赖36。无生产登录、凭据变更、公开部署或CRDT声称。
