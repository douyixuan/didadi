# 产品需求对照与 Phase0 验收证据

原始产品范围来自用户对话[《open飞书产品需求》](https://chatgpt.com/c/6ace0693-5648-83e8-a751-43a5b4f829c2)。父端已从原对话恢复V0.2场景、V0.3开头和技术方案V0.1；V0.3完整正文、用户故事与优先级表仍不可见，以下不编造MVP/V1/远期分级。此前将仓库README四模块、ADR0001与Issue1/2/3当作全部原始功能范围是不充分的：它们只是Phase0通信/耐久任务/Git风险验证，不能证明完整产品功能已完成。许可证及物理GUI验收待答不阻止独立功能开发。

## 已恢复的原始功能与代码审计

初始审计基线为786562f，当前main为70b0c88；下表区分main与叠加draft52–56，候选不冒充已合入。来源为父端从上述原对话恢复的具体条目，并非本轮新增需求。历史实现与本轮候选分别注明，不以文档计划替代代码/运行结果。

| 原功能 | 现有代码/证据 | 状态与独立缺口 |
|---|---|---|
| 私聊、群组、频道与成员 | client_server固定state.tokens[0]，create_room只创建本地测试私有room；SDK消息真实运行 | 部分实现；当前People候选只读成员/当前身份，真实登录/注销、成员写操作、私聊/频道产品入口仍待做 |
| 消息历史、引用与话题 | main PR51已含主时间线游标分页；draft55独立relations读取历史root及50回复分页，不依赖已加载数组 | 主时间线已验；draft55真实Matrix/浏览器及精确head CI39411748523/39411776277通过；引用/其他话题入口仍逐项验收 |
| 附件 | 候选消息Composer上传m.file并认证下载，5MiB上限，同事务重试 | 本地真实Matrix/浏览器字节一致和响应丢失重试通过；Markdown嵌入、内联图像、远端媒体及加密附件待做 |
| 引用消息 | 候选独立Quote及m.in_reply_to，canonical原文按房间读取、原文打开、未知结果固定事务 | 真实Matrix/隔离浏览器通过；原文不可读时显示失败/重试，消息编辑/撤回另待做 |
| 搜索 | 候选Matrix content.body搜索及Git Markdown正文/行/固定版本搜索，独立于导航标题过滤 | 已本地真实Matrix/Git/浏览器验证；搜索精确CI39413261124/39413266691通过；限已授权房间/文档、跳过>64KiB或非UTF8文件，附件/其他资源待做 |
| 多文档创建、打开、move/重命名 | 本轮候选增加真实列表、创建、独立保存/历史/草稿；Agent动作仍限demo.md | draft52/53本地与各自精确head CI均通过；跨路径历史UI尚缺 |
| 选消息转新文档及来源引用 | 候选from-messages API/UI已实现选ID、服务端取原文、来源链接和确定性Markdown | draft54本地真实Matrix/Git/浏览器及精确head CI39409982536/39410003123通过；当前限绑定房间文本，无LLM |
| Agent注册、能力、资源授权 | Gateway固定AGENT/单开发token，静态本地source白名单 | 部分实现；注册/授权可能涉及PR41原owner，需协调，不抢做 |
| Agent真实进度API | 已有耐久状态/租约/退避/取消/执行审计；连接观测不冒充进度 | 部分实现；没有runtime主动上报进度的API |
| Git关联、目录与代码行/Commit/PR引用 | 候选Git source直接查看既有grant固定SHA文件，选行引用消息及按commit/blob打开；仍8000字节上限 | 真实Git/Matrix/浏览器通过；当前目录候选只浏览已有grant路径；仓库关联配置、任意Commit/PR引用待做 |
| Git为Markdown唯一数据源、编辑/历史/冲突 | GitDocs/DocumentService/编辑器；历史初验139 Python/122前端，后续候选测试与真实运行结果见各PR | 已实现声明的固定文档范围；不推广成全部文档产品完成 |
| 未恢复的V0.3条目和优先级 | 正文尚不可见，父端继续恢复 | 待证；不以推测替代，不宣布全部功能完成 |

Issue12仍明确暂停。ADR41和其他贡献者独占设计保留；本轮继续不改授权/CRDT的完整线程与正文搜索切片。生产语言重写、多租户等不自动追加为本轮必做，也不能用这些泛化边界掩盖上面的已确认原功能缺口。

## Phase0检查项（17项，仅证明技术基础）

下列自动化覆盖只对隔离合成Matrix身份、单固定Agent/开发凭据、可信本地bare远端和声明的测试语料成立。不据此自动关闭Issue；每个源码包的精确SHA、CI和独立启动结果单独记录，旧版本验收不自动继承。

| 来源与检查项 | 自动化覆盖与证据 | 必须保留的限制 |
| --- | --- | --- |
| #1.1 Compose与持久卷 | workflow/test.yml启动、保留卷重建、persistence smoke | 原主机/当前源码包的干净安装需另复验；非灾备 |
| #1.2 两用户Room消息 | scripts/matrix_smoke.py真实Synapse双用户 | 合成测试身份 |
| #1.3 AS收事件及托管Agent回复 | 同smoke，Synapse→AS→managed identity→sync | 无homeserver fork；固定命名空间 |
| #1.4 启动/注册/测试命令 | LOCAL_WORKSPACE/MATRIX_QUICKSTART/AGENT_GATEWAY | 开发环境、loopback |
| #1.5 CI真实集成 | matrix-smoke完整job | 不以配置文件或unit替代真实运行 |
| #2.1 ACK前耐久transaction/event | gateway tests及AS事务路径 | SQLite单节点 |
| #2.2 replay仅一task | gateway/runtime/protocol重复事务与claim | runtime需用task ID去重外部副作用 |
| #2.3 Gateway重启保留任务 | gateway tests、容器保留卷及lifecycle smoke | 旧候选真实DB升级应单独复验 |
| #2.4 凭据绑定授权Agent身份 | gateway HTTP认证、固定AGENT发送、task cancel tests | 单Agent开发token；非注册/多租户grant |
| #2.5 仅授权未加密Room | room/access/lifecycle tests与真实revocation smoke | E2EE自动授权未实现且拒绝 |
| #2.6 outbound与原Thread回复 | websocket_smoke/task_visibility_smoke及稳定reply事务 | 连接观测不证明模型进度；HTTPpresence未跟踪 |
| #3.1 独立进程不静默覆盖 | gitdocs_hardening/concurrent_merge tests | 单host锁；非分布式single writer |
| #3.2 外部branch更新无force | localbare fast-forward/race/divergence/operator recovery | SSH/HTTPS/凭据轮换未验证 |
| #3.3 Git提交→通知崩溃恢复 | document_smoke、scopedAPI/task_visibility重启/重放/outbox | 非掉电/磁盘损坏exactly-once |
| #3.4 traversal/symlink竞态 | GitDocs/source-reader硬化tests | trusted service-owned bare配置 |
| #3.5 固定commit不可变 | Git/source读取tests、fixed API恢复 | 范围受现有room/grant限制 |
| #3.6 测试与证据记录 | docs/VALIDATION、各artifact、精确headCI | 分清当前与历史候选证据 |

Phase0第四模块React+matrix-js-sdk文档/讨论/Agent任务视图已有真实SDK/API自动化、声明语料编辑器回归、源码/报告、取消、草稿、并发保存及本轮状态提示。隔离无权限headless Chrome已验证实际下载字节、本地草稿关闭恢复和随后直接保存；物理IME、指针拖拽和桌面GUI仍未验。Issue11/14/15/16/22等后续缺陷有实现与测试证据，但open状态与main合入不能靠本清单自动改变；Issue12性能工作仍独立暂停，ADR41设计归另一执行者。

## 原始需求复核与本轮修复

逐项映射见 [需求复核](../artifact/032-requirements-completion/plan.md)，入口修复见 [实现与验证](../artifact/033-human-document-entrypoints/validation.md)。PR49将新提交的原始Matrix路由移入私有intent refs，保留可读提交及真实作者；PR50使内置人工入口直接保存Git文档，代理拒绝正文任务，错误页保留草稿和重试标识。外部旧Matrix任务兼容不等于平台人工入口继续发送正文。

## 仍需独立验收或外部决定

1. **每个最终提交与源码包。** 合入后main CI、冻结ZIP校验、该包独立安装和保留卷重建均需明确记录。旧源码包v13的字节核对不证明后续版本。
2. **物理交互。** headless实际下载与恢复已通过；中文IME、鼠标拖拽、光标/滚动及原生桌面GUI未验。使用隔离合成身份，不访问用户浏览器profile或剪贴板。
3. **既有消息与历史。** 内置人工入口正文走API/Git；外部旧Matrix客户端仍可发送正文任务，历史消息和旧JSON提交没有重写。
4. **独立暂停及设计。** Issue12历史性能工作保持原工作区暂停。ADR41由原owner处理，仍为Proposed；CRDT/live cursors、TypeScript迁移与生产授权等不被本轮代为接受。
5. **完整产品功能。** 上方候选已补多文档、线程、正文搜索和消息转文档切片；登录/成员、附件、Agent注册/进度、Git关联/引用，以及各切片明确的跨路径/跨资源边界仍有缺口。按原文继续实现，V0.3未恢复的优先级保持待证；不能以Phase0未列为理由排除这些功能，也不能据此擅自追加未确认生产承诺。

## 2026-11-04 增量验收 — P0 #69 真实 Matrix 身份（已在 main 交付）

本节替代本文件历史审计中“真实登录/注销待接入”的过时状态；不自动关闭其余产品功能。验收对象是**仅绑定 loopback 的隔离自托管开发工作区**，不是公网 Beta 或正式多租户安全边界。

- **源码与合并**：[PR #90](https://github.com/douyixuan/didadi/pull/90) 精确 head `4c6caf4f0f8eb62bb71c979b135da87b11f6b32c`，已合并到 main `271f15a68fbc37356b3cb368943cb1871f9ce30c`。两次提交的 Git **tree SHA 均为 `1122c4489b0dfe2951c689d04bb099b66853a0d3`**；已验证代码树相同。
- **真实 E2E，不是 mock**：[Real Matrix integration #41587178841](https://github.com/douyixuan/didadi/actions/runs/41587178841) 成功。隔离 Synapse/PostgreSQL 与真实非管理员测试身份、Workspace API、Playwright Chromium、独立 Git 提交；验证 Alice/Bob 登录、刷新和服务端进程重启会话保留、401 密码拒绝、CSRF、房间隔离、两个 Markdown 独立保存、仅元数据回执、跨用户只读与退出。浏览器结果 `PASS REAL BROWSER`；原始 Markdown [固定 Git 证明](https://github.com/douyixuan/didadi/actions/runs/41587178841/artifacts/13208217850) 对应文档提交 `12af32a5aebc343910c8b7a65964f4ef92cb2a98`。附件仅含无凭据测试证据。
- **额外验收**：[PR 精确头 Test #41587178746](https://github.com/douyixuan/didadi/actions/runs/41587178746) 与 [合并后 main Test #41783890475](https://github.com/douyixuan/didadi/actions/runs/41783890475) 均成功。针对原 Codex 线程已核对掉线登出、登录成功后初始化失败重试；旧审查线程全部解决，新增精确头 Codex review 无重大结论。
- **复现**：按 [LOCAL_WORKSPACE](LOCAL_WORKSPACE.md) 启动隔离 Compose、`src.client_server --auth-mode matrix --port 8791`，运行 `python -m scripts.real_login_smoke --credentials-file .local/bundle/smoke-passwords.json` 及 `node client/scripts/real_login_browser.mjs --credentials-file .local/bundle/smoke-passwords.json`；工作流还验证后端重启、固定提交的 `git show` 和保留卷恢复，详见 [真实集成 workflow](../.github/workflows/real-matrix.yml)。测试帐号密码只存私有、不加入仓库和截图。
- **未通过/不包含**：#70 的真实 DM/群组/频道、成员变更及未读语义；#71 草稿并发冲突、多文档 move/export 完整浏览器路径；#72 独立全新安装及恢复全链验收。物理中文 IME、公共 Demo/生产安全未验证；本地 SQLite 文件包含服务端明文 bearer token（mode 0600），只能用于隔离开发。P0 父项 #85 继续打开；#12 继续暂停，#18/PR #41 由原 owner 处理。

**验收决议**：仅关闭子交付 [#69](https://github.com/douyixuan/didadi/issues/69) 并在 [#85](https://github.com/douyixuan/didadi/issues/85) 勾选其子项；其余 15 项维持未验收，不把源码、离线 CI 或本地体验误当公网发布。


## 稳定产品叶验收口径（2026-11-12）

历史快照，当前状态以根树及下方“房间通信隔离真实验收”为准。

根ROADMAP只记录P0–P3的#69–#84共16个完整产品功能；仅#69已完整接受，当前为1/16。旧7项技术验收勾选保留在历史证据中，不迁移为新的完整产品通过。细项和长期范围保留于[原细化入口](../roadmap/README.md#完整需求与长期范围)，不因进度重组删除。

本轮文档依据父任务提供的最新事实：main ce24dd9a，#95/#98已合并；#99 a86806c真实集成通过但未合并，不能当main交付。#70仍缺kick、跨房间及快速切账号负向完整验收；#71/#72未完成。未在本轮重新执行这些真实检查，也未据此新增勾选。[#69验收状态](https://github.com/douyixuan/didadi/issues/69)、[#70剩余范围](https://github.com/douyixuan/didadi/issues/70)及各关联issue保留原证据入口。

本地细化文档中旧候选/历史leaf路径是历史口径，不可用来判定新的16叶验收；后续本地门禁迁移已将旧5份元数据与7项豁免按内容摘要归档保护，新门禁独立核对16个稳定issue、99项需求保留及#69真实记录，不继承旧豁免。#41/#18所有权与#12暂停不变；未启动服务或发布。


## 真实登录既有验收证据

| 验收字段 | 准确记录 |
| --- | --- |
| version | `4c6caf4f0f8eb62bb71c979b135da87b11f6b32c` |
| main | `271f15a68fbc37356b3cb368943cb1871f9ce30c` |
| record | `https://github.com/douyixuan/didadi/issues/69#issuecomment-6624096272` |
| real_ci | `https://github.com/douyixuan/didadi/actions/runs/41587178841` |
| main_ci | `https://github.com/douyixuan/didadi/actions/runs/41783890475` |


#69引用[2026-11-04已合并验收记录](https://github.com/douyixuan/didadi/issues/69#issuecomment-6624096272)：测试head `4c6caf4f0f8eb62bb71c979b135da87b11f6b32c`，main `271f15a68fbc37356b3cb368943cb1871f9ce30c`，相同Git tree `1122c4489b0dfe2951c689d04bb099b66853a0d3`。[真实CI](https://github.com/douyixuan/didadi/actions/runs/41587178841)验证隔离Synapse/PostgreSQL、双非管理员登录、Chromium、401、会话/CSRF、隔离、刷新、后端重启及退出；[main CI](https://github.com/douyixuan/didadi/actions/runs/41783890475)成功。该评论当时要求等待验收台账合入再计叶；本轮父任务已明确当前稳定验收为仅#69。仅loopback原型范围，SQLite私有文件中的token明文限制保留，公开Beta未批准。本轮只核对已有记录，没有重新运行真实流程。

门禁迁移本地验证：完整检查通过16叶/1项既有验收记录；13项离线回归通过，包含重复/缺失叶、误勾#70、缺失原需求、缺验收记录、错误准确版本和mock冒充真实验收的拒绝。HTTPS链接仅离线格式核对；#69记录已通过授权只读GitHub接口读取，真实CI未在本轮重跑。归档证据如需修改必须显式复核迁移，不能静默改变旧窄范围通过含义。


## 房间通信隔离真实验收

| 验收字段 | 准确记录 |
| --- | --- |
| version | `b69a8d63070333b7122998e21b0f950f550c5a7f` |
| main | `2c119c42652df4f2cf0aaf4d7904cc64424df365` |
| record | `https://github.com/douyixuan/didadi/issues/70#issuecomment-6890670784` |
| real_ci | `https://github.com/douyixuan/didadi/actions/runs/43685215402` |
| main_ci | `https://github.com/douyixuan/didadi/actions/runs/43686279507` |


2026-11-15执行并核验真实隔离流程后，接受#70。当前完整产品叶为#69、#70，共2/16；P0为2/4，#71多人文档冲突/草稿/恢复与#72独立安装恢复仍未完成，P1尚未启动。范围追踪的“已映射”不表示实现或验收。

- 测试head `b69a8d63070333b7122998e21b0f950f550c5a7f`，合并main `2c119c42652df4f2cf0aaf4d7904cc64424df365`，相同tree `d83cf0f7419b01988726d9df6652015af53155d7`。[正式验收记录](https://github.com/douyixuan/didadi/issues/70#issuecomment-6890670784)。
- 精确head：[Fast](https://github.com/douyixuan/didadi/actions/runs/43685215437)、[真实CI](https://github.com/douyixuan/didadi/actions/runs/43685215402)成功；合并后main：[Fast](https://github.com/douyixuan/didadi/actions/runs/43686279441)、[真实CI与p0 gate](https://github.com/douyixuan/didadi/actions/runs/43686279507)成功。[Codex精确head审查](https://github.com/douyixuan/didadi/pull/100#issuecomment-6890347716)无发现，不是代用户approval。
- 环境为CI临时loopback Synapse/PostgreSQL、Workspace/Document API、真实Git及1280×720 Chromium；两个隔离合成身份，无生产数据。执行入口为real_login_browser.mjs及其room_isolation_acceptance.mjs。不是mock返回、物理iOS或公网Beta。SQLite私有token文件的既有开发限制仍保留至#83。

| 完整验收条件 | 实际操作与断言 |
| --- | --- |
| 双用户私聊、群组、频道与成员行为 | 真邀请/join、双向消息、leave、拒绝房间、People双身份、引用、字节一致附件、超过50项唯一历史及可见原生搜索 |
| 撤权无旧内容泄漏 | 原生creator kick；持有真实成功history/Thread/search响应，踢出后释放，不回填旧内容；后续读取/引用/文件/搜索拒绝 |
| 未读与导航刷新保持 | Synapse原生计数与read marker、同身份刷新，不以本地总消息数伪造未读 |
| 房间与会话隔离 | 跨房间迟到分页/Thread；同一browser profile Bob→Alice→Bob及旧成功搜索迟到；旧引用/文件/历史不可访问 |

main的五张PNG均已下载并实际查看，内容仅合成，无cookie/密码/token；最后一张是账号切换加载瞬间，证明清除旧内容，不冒充稳定加载完成。后续完成断言见真实日志。

- [授权房间与附件](../artifact/032-requirements-completion/p070-real-browser/p070-authorized-room.png)
- [真实搜索结果](../artifact/032-requirements-completion/p070-real-browser/p070-authorized-search.png)
- [跨房间迟到响应](../artifact/032-requirements-completion/p070-real-browser/p070-cross-room-late-responses.png)
- [真实踢出后界面](../artifact/032-requirements-completion/p070-real-browser/p070-real-kick-eviction.png)
- [切账号瞬间隔离](../artifact/032-requirements-completion/p070-real-browser/p070-same-browser-account-isolation.png)

保留失败事实：Real 43683690935的新隔离断言通过，但旧错误密码测试截短服务端cooldown导致整轮失败。修复遵守完整retry_after_ms及7分钟上限，再要求真实401；未降低Synapse限流，不是产品Red→Green。PR正文否定句误含关闭关键词，GitHub在06:37提前关闭#70；该事件不是验收。实际接受在06:47后main gate成功并核对范围后记录，未倒签。

公开Vercel仍是合成演示，不是本次真实后端验收环境。#41/#18分工和#12暂停不变；本次只增加一个完整叶，不因合并多个PR增加计数。
