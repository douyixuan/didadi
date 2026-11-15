# ROADMAP 细化入口

根 [ROADMAP](../ROADMAP.md) 是唯一功能总树。这里按完整用户功能细化，不另建完成状态表。

采用[通用产品流程](../docs/PRODUCT_WORKFLOW.md)与[功能模板](_template.md)。Didadi 主接入实例：[多文档管理闭环](document-management.md)；补充实例：[未读消息提醒](unread-notifications.md)。本轮另有[讨论检索](discussion-search.md)、[任务进度与产物](task-progress-artifacts.md)、[手机导航](mobile-navigation.md)细化，四目标结果回同一验收记录。其他功能继续使用已有需求、执行计划和[验收记录](../artifact/032-requirements-completion/validation.md)，进入实施时逐项迁入功能入口并引用原记录，不重开今天计划。

原V0.2功能分组与技术V0.1已恢复；V0.3完整正文及原优先级仍缺，见[原需求核对](../docs/MVP_ACCEPTANCE.md)。用户已明确根树全部目标持续推进，不能借未知分级缩为MVP。


## 阶段与 issue 对应

采用2026-10-29远端新规划，以下是实施顺序，不是另一份完成状态表。功能进度只看根树；验收证据仍回[既有记录](../artifact/032-requirements-completion/validation.md)。

| 阶段 | Tracker | 执行 issue | 功能范围 |
| --- | --- | --- | --- |
| P0 Real Workspace | [#85](https://github.com/douyixuan/didadi/issues/85) | #69→#70→#71→#72 | 真实会话、房间隔离、多人文档、完整流程自验 |
| P1 Agent teammate | [#86](https://github.com/douyixuan/didadi/issues/86) | #73–#76 | Agent身份、授权申请撤销、真实进度、恢复 |
| P2 Reviewable Git delivery | [#87](https://github.com/douyixuan/didadi/issues/87) | #77–#80 | 来源追溯、差异审阅、接受拒绝、仓库引用 |
| P3 Self-hosted Beta | [#88](https://github.com/douyixuan/didadi/issues/88) | #81–#84 | 安装升级备份、安全评估、跨端交互、版本交付 |

完整边界、依赖和真实验收条件以各tracker及关联issue为准；#12暂停，#41保持原贡献者分工。旧技术细项的历史证据不等于稳定产品叶验收。根树以16个完整产品功能为验收叶，细项与长期范围保留如下；不把验证日志、工时或提交号放入根树。


## 原需求逐项追踪

R001–R099 按原始清单顺序固定；原文中的“待接入/待验收”为历史措辞，不是当前进度。下表只回答 issue 是否承诺该需求，不表示实现或验收通过；唯一完成状态以根树为准（当前2/16）。“已映射”指范围有对应承诺；“部分覆盖”明确缺失承诺；“未映射”保留原目标、等待范围归属，不能默认并入宽泛阶段。证据为 2026-11-14 只读核对的 #69–#84 正文 Scope/Acceptance/Non-goals；摘句仅供定位，完整约束以链接正文为准。外链后续可变化，离线门禁只检查记录结构与本地链接，不验证远端真实性。

| 稳定标识 | 原始需求原文 | 范围映射 | 相关产品叶 | 范围证据 | 对应承诺或缺口 |
| --- | --- | --- | --- | --- | --- |
| R001 | 真实登录（待接入） | 已映射 | #69 | [#69](https://github.com/douyixuan/didadi/issues/69) | Login with a real non-admin Matrix user |
| R002 | 当前设备退出（待接入） | 已映射 | #69 | [#69](https://github.com/douyixuan/didadi/issues/69) | genuine current-device logout |
| R003 | 登录会话恢复 | 已映射 | #69 | [#69](https://github.com/douyixuan/didadi/issues/69) | session across reload/restart |
| R004 | 失效会话拒绝 | 已映射 | #69 | [#69](https://github.com/douyixuan/didadi/issues/69) | invalid/expired credentials |
| R005 | 房间列表浏览（待验收） | 已映射 | #70 | [#70](https://github.com/douyixuan/didadi/issues/70) | real current-user room list and memberships |
| R006 | 未读消息提醒 | 已映射 | #70 | [#70](https://github.com/douyixuan/didadi/issues/70) | Unread state and room navigation survive refresh |
| R007 | 私聊会话（待验收） | 已映射 | #70 | [#70](https://github.com/douyixuan/didadi/issues/70) | private chat, group and channel |
| R008 | 群组会话（待验收） | 已映射 | #70 | [#70](https://github.com/douyixuan/didadi/issues/70) | private chat, group and channel |
| R009 | 频道会话（待验收） | 已映射 | #70 | [#70](https://github.com/douyixuan/didadi/issues/70) | private chat, group and channel |
| R010 | Markdown消息（待验收） | 部分覆盖 | #70, #82 | [#70](https://github.com/douyixuan/didadi/issues/70)、[#82](https://github.com/douyixuan/didadi/issues/82) | text / Markdown paste：未明确 Markdown 消息渲染与发送全范围 |
| R011 | 附件收发（待验收） | 已映射 | #70, #82 | [#70](https://github.com/douyixuan/didadi/issues/70)、[#82](https://github.com/douyixuan/didadi/issues/82) | quotes/files/search/history / file attachment flow |
| R012 | 引用回复（待验收） | 已映射 | #70 | [#70](https://github.com/douyixuan/didadi/issues/70) | quotes/files/search/history |
| R013 | 话题完整回复（待验收） | 部分覆盖 | #70, #77 | [#70](https://github.com/douyixuan/didadi/issues/70)、[#77](https://github.com/douyixuan/didadi/issues/77) | history / room/thread/event：未细化话题完整分页验收 |
| R014 | 历史分页浏览 | 已映射 | #70 | [#70](https://github.com/douyixuan/didadi/issues/70) | quotes/files/search/history |
| R015 | 消息正文搜索（待验收） | 已映射 | #70, #82 | [#70](https://github.com/douyixuan/didadi/issues/70)、[#82](https://github.com/douyixuan/didadi/issues/82) | quotes/files/search/history / search |
| R016 | 搜索返回上下文（待验收） | 部分覆盖 | #70, #77 | [#70](https://github.com/douyixuan/didadi/issues/70)、[#77](https://github.com/douyixuan/didadi/issues/77) | search/history / back to source thread：未明确搜索命中跳回完整上下文行为 |
| R017 | Agent注册邀请（待接入） | 已映射 | #73 | [#73](https://github.com/douyixuan/didadi/issues/73) | Invite/register an Agent |
| R018 | 通用Agent身份绑定（待接入） | 已映射 | #73 | [#73](https://github.com/douyixuan/didadi/issues/73) | bind stable identity |
| R019 | 主动连接网关（待验收） | 已映射 | #73, #76 | [#73](https://github.com/douyixuan/didadi/issues/73)、[#76](https://github.com/douyixuan/didadi/issues/76) | actual connection state / websocket disconnect |
| R020 | 头像名字设置 | 部分覆盖 | #73 | [#73](https://github.com/douyixuan/didadi/issues/73) | Show name, capabilities：未明确头像设置 |
| R021 | 能力展示说明 | 已映射 | #73 | [#73](https://github.com/douyixuan/didadi/issues/73) | declared capabilities |
| R022 | 上下文范围控制 | 已映射 | #74 | [#74](https://github.com/douyixuan/didadi/issues/74) | room, repo/path-prefix, allowed actions, expiry |
| R023 | 授权申请撤销 | 已映射 | #74 | [#74](https://github.com/douyixuan/didadi/issues/74) | grant request/approval/revoke state |
| R024 | 提及唤起任务（待验收） | 已映射 | #75 | [#75](https://github.com/douyixuan/didadi/issues/75) | real room mention creates exactly one persistent task |
| R025 | Agent私聊交互 | 部分覆盖 | #73, #75 | [#73](https://github.com/douyixuan/didadi/issues/73)、[#75](https://github.com/douyixuan/didadi/issues/75) | permitted Matrix rooms / mentions/assignments：未明确 Agent 私聊独立交互 |
| R026 | 成员任务分配 | 已映射 | #75 | [#75](https://github.com/douyixuan/didadi/issues/75) | Link task creation to mentions/assignments |
| R027 | Git唯一文档源（待验收） | 已映射 | #71 | [#71](https://github.com/douyixuan/didadi/issues/71) | Save through direct Document Service API into Git |
| R028 | 独立创建文档（待验收） | 已映射 | #71 | [#71](https://github.com/douyixuan/didadi/issues/71) | create/list/open/edit/move/export |
| R029 | 文档列表打开（待验收） | 已映射 | #71 | [#71](https://github.com/douyixuan/didadi/issues/71) | create/list/open/edit/move/export |
| R030 | 人工编辑保存（待验收） | 已映射 | #71 | [#71](https://github.com/douyixuan/didadi/issues/71) | create/list/open/edit/move/export |
| R031 | 文档重命名移动（待验收） | 已映射 | #71 | [#71](https://github.com/douyixuan/didadi/issues/71) | create/list/open/edit/move/export |
| R032 | 历史版本回看（待验收） | 已映射 | #71 | [#71](https://github.com/douyixuan/didadi/issues/71) | version history ... usable |
| R033 | 文档稳定标识 | 已映射 | #77 | [#77](https://github.com/douyixuan/didadi/issues/77) | stable references ... Markdown document identity/path |
| R034 | 按基线原子保存（待验收） | 已映射 | #71, #78 | [#71](https://github.com/douyixuan/didadi/issues/71)、[#78](https://github.com/douyixuan/didadi/issues/78) | stale base, conflict / Git CAS |
| R035 | 草稿冲突保护（待验收） | 已映射 | #71, #78 | [#71](https://github.com/douyixuan/didadi/issues/71)、[#78](https://github.com/douyixuan/didadi/issues/78) | Preserve drafts / preserve competing drafts on conflict |
| R036 | Agent编辑文档 | 已映射 | #78 | [#78](https://github.com/douyixuan/didadi/issues/78) | Agent proposes a change ... human ... before publishing |
| R037 | 变更差异审阅 | 已映射 | #78 | [#78](https://github.com/douyixuan/didadi/issues/78) | proposed document changes/diff |
| R038 | 提案接受拒绝 | 已映射 | #78 | [#78](https://github.com/douyixuan/didadi/issues/78) | accept/reject/retry action |
| R039 | 选择消息生成（待验收） | 部分覆盖 | #71, #77 | [#71](https://github.com/douyixuan/didadi/issues/71)、[#77](https://github.com/douyixuan/didadi/issues/77) | message-to-document links / chain of references：未明确选择消息生成正文操作 |
| R040 | 保留来源引用（待验收） | 已映射 | #71, #77 | [#71](https://github.com/douyixuan/didadi/issues/71)、[#77](https://github.com/douyixuan/didadi/issues/77) | message-to-document links / origin identifiers |
| R041 | 返回来源讨论（待验收） | 已映射 | #77 | [#77](https://github.com/douyixuan/didadi/issues/77) | back to source thread |
| R042 | 失败重试去重（待验收） | 部分覆盖 | #71, #76 | [#71](https://github.com/douyixuan/didadi/issues/71)、[#76](https://github.com/douyixuan/didadi/issues/76) | failed network writes / duplicate Git writes：未明确消息转文档重试去重全路径 |
| R043 | 多人实时协作 | 未映射 | — | [#77](https://github.com/douyixuan/didadi/issues/77) | Not in scope: synchronous co-editing；保留实时协作完整目标，需独立范围 |
| R044 | Git提交后通知 | 已映射 | #71, #80 | [#71](https://github.com/douyixuan/didadi/issues/71)、[#80](https://github.com/douyixuan/didadi/issues/80) | version metadata only / Git records the new version; Matrix ... notification |
| R045 | 通知失败重试 | 部分覆盖 | #76, #80 | [#76](https://github.com/douyixuan/didadi/issues/76)、[#80](https://github.com/douyixuan/didadi/issues/80) | reconcile ... Matrix result/receipt / replay：未明确通知失败重试策略 |
| R046 | 文档正文搜索（待验收） | 部分覆盖 | #82 | [#82](https://github.com/douyixuan/didadi/issues/82) | search：未明确文档正文索引与搜索范围 |
| R047 | Markdown导出（待验收） | 已映射 | #71 | [#71](https://github.com/douyixuan/didadi/issues/71) | export multiple independent Markdown files |
| R048 | 关联GitHub仓库 | 已映射 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | GitHub/GitLab/self-hosted repository |
| R049 | 关联GitLab仓库 | 已映射 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | GitHub/GitLab/self-hosted repository |
| R050 | 关联自建Git | 已映射 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | GitHub/GitLab/self-hosted repository |
| R051 | 文件行引用（待验收） | 已映射 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | exact line-range source links |
| R052 | Commit引用 | 已映射 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | fixed-commit line citation |
| R053 | PR引用 | 部分覆盖 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | full issue/PR-management UI 非首片范围：仅固定引用，未明确 PR 引用解析 |
| R054 | 授权Git写入 | 部分覆盖 | #74, #79 | [#74](https://github.com/douyixuan/didadi/issues/74)、[#79](https://github.com/douyixuan/didadi/issues/79) | write/PR ... separate explicit elevated grant：边界有据，完整写入流程未承诺 |
| R055 | 创建PR | 部分覆盖 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | write/PR ... separate explicit elevated grant：未承诺创建 PR 操作闭环 |
| R056 | 默认只读访问（待验收） | 已映射 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | prioritize read/cite path first / read-only Agent |
| R057 | Agent授权读取（待验收） | 已映射 | #74, #79 | [#74](https://github.com/douyixuan/didadi/issues/74)、[#79](https://github.com/douyixuan/didadi/issues/79) | read-only grant / Agent source reads |
| R058 | 仓库版本路径授权（待验收） | 已映射 | #74, #79 | [#74](https://github.com/douyixuan/didadi/issues/74)、[#79](https://github.com/douyixuan/didadi/issues/79) | repo/path-prefix / fixed SHA |
| R059 | 浏览器无仓库凭据（待验收） | 已映射 | #79 | [#79](https://github.com/douyixuan/didadi/issues/79) | server-held credentials (not credentials in browser) |
| R060 | 任务独立运行（待验收） | 已映射 | #75, #76 | [#75](https://github.com/douyixuan/didadi/issues/75)、[#76](https://github.com/douyixuan/didadi/issues/76) | persistent task / process restart |
| R061 | 重启恢复任务（待验收） | 已映射 | #76 | [#76](https://github.com/douyixuan/didadi/issues/76) | Disconnect and restart ... one canonical task |
| R062 | 断线恢复执行（待验收） | 已映射 | #76 | [#76](https://github.com/douyixuan/didadi/issues/76) | websocket disconnect |
| R063 | 租约恢复保护（待验收） | 已映射 | #76 | [#76](https://github.com/douyixuan/didadi/issues/76) | lease expiry |
| R064 | 重复分发去重（待验收） | 已映射 | #75, #76 | [#75](https://github.com/douyixuan/didadi/issues/75)、[#76](https://github.com/douyixuan/didadi/issues/76) | Matrix replay / idempotent task delivery |
| R065 | 查看任务状态（待验收） | 已映射 | #75 | [#75](https://github.com/douyixuan/didadi/issues/75) | Show task history ... actual progress |
| R066 | 暂停继续任务 | 部分覆盖 | #75 | [#75](https://github.com/douyixuan/didadi/issues/75) | cancellation controls：未承诺暂停后继续的产品语义 |
| R067 | 取消任务执行（待验收） | 已映射 | #75, #76 | [#75](https://github.com/douyixuan/didadi/issues/75)、[#76](https://github.com/douyixuan/didadi/issues/76) | Cancellation ... accepted/racing/finished |
| R068 | Runtime主动进度（待接入） | 已映射 | #75 | [#75](https://github.com/douyixuan/didadi/issues/75) | authenticated runtime progress/status reporting |
| R069 | 产物查看下载 | 已映射 | #77 | [#77](https://github.com/douyixuan/didadi/issues/77) | visible artifact / downloads |
| R070 | 任务关联产物 | 已映射 | #77 | [#77](https://github.com/douyixuan/didadi/issues/77) | discussion ... task ... artifact ... Git SHA |
| R071 | 来源双向追溯 | 已映射 | #77 | [#77](https://github.com/douyixuan/didadi/issues/77) | and back ... source thread |
| R072 | 进度回原话题（待接入） | 部分覆盖 | #75, #77 | [#75](https://github.com/douyixuan/didadi/issues/75)、[#77](https://github.com/douyixuan/didadi/issues/77) | actual progress / source room/thread：未明确主动进度回帖传输 |
| R073 | 固定Agent结果回帖 | 部分覆盖 | #76 | [#76](https://github.com/douyixuan/didadi/issues/76) | Matrix result/receipt：未明确固定 Agent 结果回帖身份契约 |
| R074 | 任务产物回话题 | 部分覆盖 | #77 | [#77](https://github.com/douyixuan/didadi/issues/77) | back to source thread：未明确产物自动回帖行为 |
| R075 | 多Agent任务委派 | 未映射 | — | [#73](https://github.com/douyixuan/didadi/issues/73) | Non-goals: multi-Agent planning；保留多 Agent 委派目标 |
| R076 | 敏感操作审批 | 部分覆盖 | #74, #78, #83 | [#74](https://github.com/douyixuan/didadi/issues/74)、[#78](https://github.com/douyixuan/didadi/issues/78)、[#83](https://github.com/douyixuan/didadi/issues/83) | grant approval / deliberate acceptance / security audit：不等同全部敏感操作审批 |
| R077 | 房间最小授权（待验收） | 已映射 | #70, #74 | [#70](https://github.com/douyixuan/didadi/issues/70)、[#74](https://github.com/douyixuan/didadi/issues/74) | current memberships / explicitly approved resources |
| R078 | 指定房间Agent收件 | 部分覆盖 | #73, #74 | [#73](https://github.com/douyixuan/didadi/issues/73)、[#74](https://github.com/douyixuan/didadi/issues/74) | permitted Matrix rooms / room grant：未明确 AS 指定 Room 收件实现 |
| R079 | Workspace隔离 | 部分覆盖 | #69, #70, #83 | [#69](https://github.com/douyixuan/didadi/issues/69)、[#70](https://github.com/douyixuan/didadi/issues/70)、[#83](https://github.com/douyixuan/didadi/issues/83) | switching users ... no ... rooms / cross-room：账号房间隔离有据，未明确多 Workspace 独立隔离 |
| R080 | 端到端加密 | 未映射 | — | [#69](https://github.com/douyixuan/didadi/issues/69)、[#70](https://github.com/douyixuan/didadi/issues/70)、[#83](https://github.com/douyixuan/didadi/issues/83) | Not in scope E2EE / confirm restrictions：保留端到端加密目标 |
| R081 | 审批记录查询 | 部分覆盖 | #74, #83 | [#74](https://github.com/douyixuan/didadi/issues/74)、[#83](https://github.com/douyixuan/didadi/issues/83) | record decision for audit / Audit records：未明确审批记录查询 UI |
| R082 | 操作审计追踪 | 已映射 | #83 | [#83](https://github.com/douyixuan/didadi/issues/83) | Audit records who authorized ... task/commit |
| R083 | 安全风险评估 | 已映射 | #83 | [#83](https://github.com/douyixuan/didadi/issues/83) | Threat-model ... security statement |
| R084 | 单机Compose部署 | 已映射 | #72, #81 | [#72](https://github.com/douyixuan/didadi/issues/72)、[#81](https://github.com/douyixuan/didadi/issues/81) | Isolated Compose startup / supported installation path |
| R085 | 双用户消息互通 | 已映射 | #70, #71 | [#70](https://github.com/douyixuan/didadi/issues/70)、[#71](https://github.com/douyixuan/didadi/issues/71) | Two real users ... exchange ... messages |
| R086 | Web移动适配（待验收） | 已映射 | #82 | [#82](https://github.com/douyixuan/didadi/issues/82) | desktop and mobile Web |
| R087 | 独立安装引导 | 已映射 | #81, #84 | [#81](https://github.com/douyixuan/didadi/issues/81)、[#84](https://github.com/douyixuan/didadi/issues/84) | independent developer ... deploys / quickstart |
| R088 | 升级回滚恢复 | 已映射 | #81 | [#81](https://github.com/douyixuan/didadi/issues/81) | safe upgrades ... rollback boundaries |
| R089 | 备份一致恢复 | 已映射 | #81 | [#81](https://github.com/douyixuan/didadi/issues/81) | snapshot/restore ... identity/DB/Git |
| R090 | 完整流程自验 | 已映射 | #72, #80 | [#72](https://github.com/douyixuan/didadi/issues/72)、[#80](https://github.com/douyixuan/didadi/issues/80) | browser-driven smoke / canonical acceptance scenario |
| R091 | 原生移动端 | 未映射 | — | [#82](https://github.com/douyixuan/didadi/issues/82)、[#84](https://github.com/douyixuan/didadi/issues/84) | Not in scope: native mobile apps / native iOS/Android；保留原生移动目标 |
| R092 | Matrix联邦 | 未映射 | — | [#69](https://github.com/douyixuan/didadi/issues/69)、[#70](https://github.com/douyixuan/didadi/issues/70)、[#83](https://github.com/douyixuan/didadi/issues/83) | Not in scope federation / confirm restrictions；保留联邦目标 |
| R093 | Agent市场 | 未映射 | — | [#73](https://github.com/douyixuan/didadi/issues/73)、[#84](https://github.com/douyixuan/didadi/issues/84) | Non-goals marketplace / Not in scope marketplace；保留市场目标 |
| R094 | SDK接入 | 未映射 | — | [#73](https://github.com/douyixuan/didadi/issues/73)、[#84](https://github.com/douyixuan/didadi/issues/84) | 仅 external runtime / Agent connection，未承诺 SDK 交付；需范围确认 |
| R095 | MCP接入 | 未映射 | — | [#73](https://github.com/douyixuan/didadi/issues/73)、[#84](https://github.com/douyixuan/didadi/issues/84) | 仅 external runtime / Agent connection，未承诺 MCP 交付；需范围确认 |
| R096 | 开源许可明确 | 已映射 | #84 | [#84](https://github.com/douyixuan/didadi/issues/84) | approved open-source LICENSE |
| R097 | 版本发布说明 | 已映射 | #84 | [#84](https://github.com/douyixuan/didadi/issues/84) | tagged release with changelog |
| R098 | 示例上手引导 | 已映射 | #84 | [#84](https://github.com/douyixuan/didadi/issues/84) | example end-to-end scenario |
| R099 | 测试反馈入口 | 已映射 | #84 | [#84](https://github.com/douyixuan/didadi/issues/84) | small tester feedback template |

## 完整需求与长期范围

以下保留原功能细项，仅用于范围核对，不是另一份进度清单。其历史勾选已取消显示；唯一验收勾选在根树。原生移动、联邦、端到端加密、实时协作、市场、SDK/MCP与Git写入等仍属于完整目标。

### 普通通信

#### 会话管理

- 真实登录（待接入）
- 当前设备退出（待接入）
- 登录会话恢复
- 失效会话拒绝
- 房间列表浏览（待验收）
- 未读消息提醒
- 私聊会话（待验收）
- 群组会话（待验收）
- 频道会话（待验收）

#### 消息交流

- Markdown消息（待验收）
- 附件收发（待验收）
- 引用回复（待验收）

#### 讨论检索

- 话题完整回复（待验收）
- 历史分页浏览
- 消息正文搜索（待验收）
- 搜索返回上下文（待验收）

### Agent成员

#### 成员接入

- Agent注册邀请（待接入）
- 通用Agent身份绑定（待接入）
- 主动连接网关（待验收）
- 头像名字设置
- 能力展示说明

#### 成员交互

- 上下文范围控制
- 授权申请撤销
- 提及唤起任务（待验收）
- Agent私聊交互
- 成员任务分配

### 文档管理

#### 多文档编辑

- Git唯一文档源（待验收）
- 独立创建文档（待验收）
- 文档列表打开（待验收）
- 人工编辑保存（待验收）
- 文档重命名移动（待验收）
- 历史版本回看（待验收）
- 文档稳定标识
- 按基线原子保存（待验收）
- 草稿冲突保护（待验收）
- Agent编辑文档
- 变更差异审阅
- 提案接受拒绝

#### 消息转文档

- 选择消息生成（待验收）
- 保留来源引用（待验收）
- 返回来源讨论（待验收）
- 失败重试去重（待验收）

#### 实时协作

- 多人实时协作

#### 文档版本通知

- Git提交后通知
- 通知失败重试

#### 文档检索导出

- 文档正文搜索（待验收）
- Markdown导出（待验收）

### Git集成

#### 仓库关联

- 关联GitHub仓库
- 关联GitLab仓库
- 关联自建Git

#### 代码引用

- 文件行引用（待验收）
- Commit引用
- PR引用

#### Git写入协作

- 授权Git写入
- 创建PR

#### 授权读取

- 默认只读访问（待验收）
- Agent授权读取（待验收）
- 仓库版本路径授权（待验收）
- 浏览器无仓库凭据（待验收）

### 长任务管理

#### 任务生命周期

- 任务独立运行（待验收）
- 重启恢复任务（待验收）
- 断线恢复执行（待验收）
- 租约恢复保护（待验收）
- 重复分发去重（待验收）
- 查看任务状态（待验收）
- 暂停继续任务
- 取消任务执行（待验收）
- Runtime主动进度（待接入）

#### 任务产物

- 产物查看下载
- 任务关联产物
- 来源双向追溯
- 进度回原话题（待接入）
- 固定Agent结果回帖
- 任务产物回话题

#### 多Agent协作

- 多Agent任务委派
- 敏感操作审批

### 安全权限

#### 访问隔离

- 房间最小授权（待验收）
- 指定房间Agent收件
- Workspace隔离

#### 加密通信

- 端到端加密

#### 审批审计

- 审批记录查询
- 操作审计追踪
- 安全风险评估

### 部署生态

#### 自托管使用

- 单机Compose部署
- 双用户消息互通
- Web移动适配（待验收）
- 独立安装引导
- 升级回滚恢复
- 备份一致恢复
- 完整流程自验

#### 跨端使用

- 原生移动端

#### 联邦互通

- Matrix联邦

#### Agent生态

- Agent市场

#### 开发者接入

- SDK接入
- MCP接入

#### 版本交付

- 开源许可明确
- 版本发布说明
- 示例上手引导
- 测试反馈入口
