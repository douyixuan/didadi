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


## 多文档恢复局部真实回归

2026-11-15，[PR102](https://github.com/douyixuan/didadi/pull/102)已合入，记录对象为测试head `051ef170240ff1ee87acbde1919b6edb0590a909`、main `003e97d2f78b1ad6f06b8e1534bf5beabad85239`。两者src/client/workflow差异为空；main另含独立交付的文档门禁。head的[Fast](https://github.com/douyixuan/didadi/actions/runs/43691052647)、[真实Matrix](https://github.com/douyixuan/didadi/actions/runs/43691052633)，main的[Fast](https://github.com/douyixuan/didadi/actions/runs/43691976382)、[真实Matrix及p0 gate](https://github.com/douyixuan/didadi/actions/runs/43691976363)均成功；[精确head独立审查](https://github.com/douyixuan/didadi/pull/102#issuecomment-6890906644)完成无发现，不是代用户approval。

| 用户路径 | 实际观察 |
| --- | --- |
| 两人两文档 | Alice和Bob分别通过UI创建并保存A/B；修改A不改变B；刷新恢复经当前授权列表确认的选择 |
| 冲突与网络失败 | 同一Git基线的重叠修改返回409，赢家正文/历史不变，败方草稿可刷新恢复；浏览器在传输前中止写请求不改变Git，刷新恢复后显式重试成功 |
| 移动与导出 | 成功移动B后刷新重开目标路径，导出字节与Git正文一致，A不变；长目录中的A.md/B.md可区分，完整路径保留 |
| 历史回看 | A的固定旧版本可读，正常点击历史面板内“返回最新”可恢复当前正文；未使用强制点击 |
| 后端重启 | 重启隔离Workspace/Document API与Synapse后，新浏览器身份分别读取A/B，正文/blob与固定Git提交一致；Git作者及元数据回执对应真实写入者 |

这是现有临时双用户、loopback真实Synapse/API/Git/Chromium流程。沿用现有owner设备，测试中暂授另一个既有成员现有50级写权限，finally恢复原power levels并核对；未创建额外账号、改产品权限模型或访问生产内容。Matrix回执不含新文档正文；原生引用/路径/写权限负向由同一真实入口执行。

[17c52d7真实失败](https://github.com/douyixuan/didadi/actions/runs/43689235650)定位历史面板遮挡返回按钮；修复后真实流程通过。命名文档重载和长路径文件名均有确定性Red→Green；该版本标准前端191项、构建通过。截图为051ef17的1280×720桌面Chromium合成数据，均已实际查看；失败图来自17c52d7。不是物理iOS验收。

- [历史遮挡修复前](../artifact/032-requirements-completion/p071-real-browser/history-before.png)
- [历史返回修复后](../artifact/032-requirements-completion/p071-real-browser/history-after.png)
- [文件名与移动重开](../artifact/032-requirements-completion/p071-real-browser/filenames-after.png)
- [重启后固定内容](../artifact/032-requirements-completion/p071-real-browser/restart-after.png)

**不关闭#71，不新增产品叶。** 003e版本的当前路径历史可回看，但`GitDocs.history(name)`仍按当前路径查询，未贯通移动前旧路径；独立#41/#18的身份、授权及操作幂等设计不在本轮修改；其未合并不等于路径历史必需等待ADR，当前路径历史仍是需要修复的实现缺口。该版本的消息来源已核对可移植Matrix permalink及真实事件，尚不是应用内返回讨论的交互验收；后续改动需单独验证。本节为003e版本记录，不代表后续候选状态。#72独立安装恢复尚未完成，P0保持2/4、全局2/16；未启动P1。Vercel仅为合成预览，不代表公开真实后端交付。


## 多人文档协作真实验收

| 验收字段 | 准确记录 |
| --- | --- |
| version | `b9d13cd5067b022bd5ce179620b1e5d82e2d5e83` |
| main | `8f9923b6810e63c0561c266bb6141fdecdf26ae5` |
| record | `https://github.com/douyixuan/didadi/issues/71#issuecomment-6894570132` |
| real_ci | `https://github.com/douyixuan/didadi/actions/runs/43713648426` |
| main_ci | `https://github.com/douyixuan/didadi/actions/runs/43714823601` |

2026-11-15，执行者在准确主线真实验收成功后接受 #71。当前完整产品叶为 #69、#70、#71，共 3/16，P0 为 3/4。#72 独立安装与备份恢复仍未完成，P1 尚未开始。多个 PR 只计同一个完整产品叶。

- [PR104](https://github.com/douyixuan/didadi/pull/104) head 与 main 的 Git tree 均为 `3d9ee98fc9f15f02efc84f094a438fdf2706593c`。head [Fast](https://github.com/douyixuan/didadi/actions/runs/43713648437) 和上表真实 CI 成功。main [Fast](https://github.com/douyixuan/didadi/actions/runs/43714823607) 和上表真实 CI 成功，包含 `p0-real-e2e-gate`。
- [准确 head 的 Codex 审查](https://github.com/douyixuan/didadi/pull/104#issuecomment-6894296220)完成，无发现。CodeRabbit/Codex 的同步顺序和固定搜索入口问题有确定性 Red→Green 及真实回归。没有代用户执行 GitHub approval。
- 环境是 CI 临时 loopback Synapse/PostgreSQL、Workspace/Document API、实际 Git 与 Chromium。两个账号和所有正文均为合成数据。标准离线 Python 112/112、React 221/221 与构建成功，但不代替真实流程。

| 完整路径 | 实际观察与断言 |
| --- | --- |
| 两用户与两文档 | 真实登录、同房间通信后，Alice/Bob 通过 UI 创建 A/B，列表、打开、编辑、切换和保存走真实 API。修改 A 不改变 B 的正文/blob/历史。实际 Git 作者及可读提交标题对应写入者。 |
| 失败与并发恢复 | 同基线重叠修改返回 409，赢家不变，败方草稿经刷新恢复。不同段落的真实并发写入保留双方内容。实际中止网络写入后 Git 不变，草稿保留并显式重试。 |
| 移动与完整历史 | 移动 B 后刷新重开并逐字节导出。超过八条历史可分页，实际中止页请求后用原位置重试，可读移动前的原路径。搜索固定版本入口也能加载历史。 |
| 来源与重试 | 选择根消息/回复创建 Git 文档。创建回执丢失后重试不多写提交。点击来源在应用内回到准确消息/Thread，保留房间草稿。 |
| 授权与元数据 | 回执递归解码后不含正文。跨房间读取、无授权写入和路径穿越失败，HEAD/路径/正文不变。临时测试写权限在 finally 恢复。 |
| 重启后真实回读 | 重启隔离后端及 Synapse。新浏览器中的两个用户分别打开 A/B，正文/blob 与不可变 Git 对象一致。 |
| 手机自验 | 390px Chromium 从紧凑导航进入历史，打开更多工具、滚动旧版本、正常点击返回并下载。固定头部和 44px 操作可达。不是物理 iPhone/键盘/IME 验收。 |

执行入口：`client/scripts/real_login_browser.mjs`、`document_recovery_acceptance.mjs`、`cross_user_receipt_browser.mjs` 和 `scripts/real_login_smoke.py`。复现环境与真实执行步骤保留在现有 `.github/workflows/real-matrix.yml`。head 的 credential-free artifact 为 `14161881863`，14 天后可能过期。下列 PNG 已下载并实际查看，内容仅合成，无密码、Cookie、token 或用户数据库。

- [改前手机历史](../artifact/032-requirements-completion/p071-real-browser/history-mobile-before-815.png)：旧 head `81540738`，历史控制曾随内容滚出屏幕，不能作为最终通过图。
- [改后手机历史](../artifact/032-requirements-completion/p071-real-browser/history-mobile-b9.png)、[手机阅读与导出](../artifact/032-requirements-completion/p071-real-browser/read-mobile-b9.png)、[更多工具](../artifact/032-requirements-completion/p071-real-browser/more-mobile-b9.png)：最终 head `b9d13cd5`。
- [搜索固定版本历史](../artifact/032-requirements-completion/p071-real-browser/search-history-b9.png)、[冲突草稿](../artifact/032-requirements-completion/p071-real-browser/conflict-draft-b9.png)、[真实非重叠合并](../artifact/032-requirements-completion/p071-real-browser/merge-b9.png)、[重启回读](../artifact/032-requirements-completion/p071-real-browser/restart-b9.png)：最终 head。合并图只显示可见区域，双方内容完整性由实际 Git 断言证明。
- [main 手机阅读](../artifact/032-requirements-completion/p071-real-browser/read-mobile-main8f.png)、[main 重启回读](../artifact/032-requirements-completion/p071-real-browser/restart-main8f.png)：合并后 `8f9923b6` 的真实 CI，均实际查看。

保留失败边界：固定搜索版本没有历史、迟到授权响应恢复旧内容及同步顺序问题由回归复现后修复。真实 UI 截图暴露了历史返回不可达和长路径挤压导航，修复后重新实际操作。旧 Real `43712156484` 在文档流程前因测试过早读 URL 而查询旧私聊，属于 harness 竞态，不是产品越权 Red。修正通过实际创建回执 ID/type 关联 URL/选中项，保留 Matrix 原生类型断言。最终 head 和 main 均重新通过。

关联 #3/#14/#15/#16 已核对。当前流程验证人类直接保存、元数据回执、作者、冲突和非重叠合并，但没有自动关闭它们的全部多进程/远端/旧格式崩溃/幂等条款。实时协作未交付，稳定文档身份属于 #77。本次历史只跟随应用产生的字节一致移动，不承诺任意外部编辑加重命名识别。99 项原需求与长期范围保持原文，映射不等于通过。

[现有 Vercel 预览](https://didadi.vercel.app/)是合成静态界面，不是上述真实后端或公开 Beta。GitHub 已确认 `8f9923b6` 的 Production 部署成功。既有私有 SQLite token 明文限制仍保留至安全工作，不能据此发布真实多租户后端。#41/#18 归属和 #12 暂停不变。


## #72 独立安装恢复真实交付（未整叶验收）

产品计数仍为3/16、P0 3/4。单命令、独立恢复与诊断已经执行，分支保护尚未启用，不能据此关闭#72或进入P1。

- 测试head：`44b3c67981527610223759f4445f7aff137e2143`，PR106。
- 准确head Fast：[43722451148](https://github.com/douyixuan/didadi/actions/runs/43722451148)。真实CI：[43722451156](https://github.com/douyixuan/didadi/actions/runs/43722451156)，结果成功。
- 合入main：`a0dd0b3ebd84a848f2866a998b657a6d2bcbfe46`，与head同tree `b2bfc245cbc6451a5f5e48f3ea93e64e1ccfe4b4`，main Fast：[43723745120](https://github.com/douyixuan/didadi/actions/runs/43723745120)，真实/恢复CI：[43723745091](https://github.com/douyixuan/didadi/actions/runs/43723745091)，结果成功。
- 标准隔离Python122/122、React221/221及构建。[准确head Codex审查](https://github.com/douyixuan/didadi/pull/106#issuecomment-6895661781)完成无发现；CodeRabbit未知Cookie测试缺口经源码核实修正，不能把旧无Cookie负例冒充未知句柄负例。

实际环境是新的GitHub runner与干净checkout，无既有.local/node_modules/dist。随机命名的Synapse/PostgreSQL/config/gateway四卷初始不存在，端口仅loopback。执行现有LOCAL_WORKSPACE的一条命令，复用真正#70/#71流程，不使用Vercel或注入假身份。

| 验证阶段 | 实际边界 |
| --- | --- |
| 干净启动与真实用户 | 明确前置条件和拒绝已有状态，安装锁定依赖，创建临时非管理员账号，通过服务健康检查 |
| 保留卷重启 | 重建自有容器并保留卷，原用户、消息及任务证据存在 |
| 双用户/双文档 | 真HTTP/Chromium登录、消息、拒绝授权、元数据回执、文档保存、冲突草稿及重启回读 |
| 独立备份恢复 | 停止源服务，备份四卷和主机状态。恢复至不同卷与文件副本，逐文件核对归档字节。源卷保持停止，不用原卷启动恢复服务 |
| 原设备与隔离 | 不重新登录，使用原始设备Cookie恢复两个用户，校验原消息及不可变A/B Git正文、私有房间403和CSRF隔离。分别验证缺少Cookie和合法随机未知Cookie的401 |
| 实际失败诊断 | 再次对本次自有状态执行入口，子命令必须失败并返回指定preflight原因，Git引用/私有设备证明指纹不变。公开只保留阶段、源码位置、固定错误类别和退出码，完整私有日志不上传 |
| 清理 | 只清理本次独有命名空间；没有删除未知卷、生产内容或其他用户工作区 |

报告passed描述本runner，accepted固定false，物理iOS/IME和生产备份均未验收。原始Cookie、数据库、日志和归档不进入artifact allowlist。允许交付的PNG均为合成数据，并由执行者实际查看。

此处保留代码恢复证据；纯文档豁免另外验证，不把其绿色状态称为真实E2E。main规则只读结果为protected=false/enforcement=off。拟要求p0-offline-gate与p0-real-e2e-gate（实际App ID15368），strict=true、管理员也受约束，禁止强推/删除。没有应用设置；需适用确认、写权限和应用前完整只读复核。不新增审批人数、推送成员、凭据或费用。

准确head公开报告（artifact `14165665583`，不是整叶接受记录）：

| 实际阶段 | 退出码 | 秒 |
| --- | --- | --- |
| preflight | 0 | 0.71 |
| clean-start-and-real-users | 0 | 73.37 |
| retained-volume-restart | 0 | 22.84 |
| real-http-and-two-browser-documents | 0 | 390.44 |
| independent-four-volume-and-host-restore | 0 | 84.83 |
| reject-state-reuse-without-side-effects | 0 | 0.07 |
| owned-resource-cleanup | 0 | 11.35 |

重复执行负例的子进程实际退出1，state_unchanged=true。原始报告仅含白名单字段，未复制私有日志、Cookie、数据库或备份归档。

已实际查看：[Alice恢复](../artifact/032-requirements-completion/p072-clean-room/restored-alice-44.png)、[Bob恢复且保持只读](../artifact/032-requirements-completion/p072-clean-room/restored-bob-44.png)。截图来自上述head的1280×720 Chromium，只有合成数据，不是物理设备验收。

[现有Vercel预览](https://didadi.vercel.app/)仍是synthetic静态界面，和上述真实隔离后端分开。原始99需求不变，#41/#18和暂停事项不动。


### 输入隔离补强与文档豁免实测

证据分支首个纯Markdown/PNG head `c64cda7af20fdbf532141f7263432b0e17769836` 已实际验证：[Fast 43723991536](https://github.com/douyixuan/didadi/actions/runs/43723991536)成功，[豁免工作流43723991384](https://github.com/douyixuan/didadi/actions/runs/43723991384)中matrix-smoke与clean-room-release均skipped，聚合输出EXEMPT documentation only，不是实际E2E。后续本PR加入输入隔离代码，因此必须重新执行两条真实作业，不能沿用这个豁免。

静态复核与纯虚构环境负例证明初版命令继承COMPOSE_FILE/COMPOSE_PROFILES，且没有固定Compose文件。补强固定仓库compose.yaml、--env-file /dev/null、明确本地context及子进程环境白名单。没有在任何真实服务/生产数据上复现或运行。新clean-room作业故意设置指向虚构不存在路径的COMPOSE_FILE和额外profile，要求入口忽略外部覆盖仍完成整个流程。该代码补强的准确CI另行记录，不能拿旧干净环境的成功代替。
