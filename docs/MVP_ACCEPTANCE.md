# 产品需求对照与 Phase0 验收证据

原始产品范围来自用户对话[《open飞书产品需求》](https://chatgpt.com/c/6ace0693-5648-83e8-a751-43a5b4f829c2)。父端已从原对话恢复V0.2场景、V0.3开头和技术方案V0.1；V0.3完整正文、用户故事与优先级表仍不可见，以下不编造MVP/V1/远期分级。此前将仓库README四模块、ADR0001与Issue1/2/3当作全部原始功能范围是不充分的：它们只是Phase0通信/耐久任务/Git风险验证，不能证明完整产品功能已完成。许可证及物理GUI验收待答不阻止独立功能开发。

## 已恢复的原始功能与代码审计

下表基线main为786562f；来源为父端从上述原对话恢复的具体条目，并非本轮新增需求。历史实现与本轮候选分别注明，不以文档计划替代代码/运行结果。

| 原功能 | 现有代码/证据 | 状态与独立缺口 |
|---|---|---|
| 私聊、群组、频道与成员 | client_server固定state.tokens[0]，create_room只创建本地测试私有room；SDK消息真实运行 | 部分实现；无真实登录/注销及成员/私聊/频道产品入口 |
| 消息历史、引用与话题 | api.js只取最近50条，App线程只筛选已加载数组；SDK发送/replay/线程回复已验 | 部分实现；本轮候选补游标分页，完整thread查询尚缺 |
| 附件 | BlockEditor上传器禁用，消息Composer纯文本；无媒体上传/下载产品链路 | 未实现；不能再因Phase0未列而排除原需求 |
| 搜索 | App仅过滤房间名/单文档标题，无正文索引/消息搜索接口 | 部分实现；非全文搜索 |
| 多文档创建、打开、move/重命名 | 本轮候选增加真实列表、创建、独立保存/历史/草稿；Agent动作仍限demo.md | 创建/打开PR52本地与精确CI已通过；move/重命名另一个候选已本地实测，精确CI待完成，跨路径历史UI尚缺 |
| 选消息转新文档及来源引用 | 候选from-messages API/UI已实现选ID、服务端取原文、来源链接和确定性Markdown | 已本地真实Matrix/Git/浏览器验证；精确CI待完成；当前限绑定房间的文本消息，无LLM |
| Agent注册、能力、资源授权 | Gateway固定AGENT/单开发token，静态本地source白名单 | 部分实现；注册/授权可能涉及PR41原owner，需协调，不抢做 |
| Agent真实进度API | 已有耐久状态/租约/退避/取消/执行审计；连接观测不冒充进度 | 部分实现；没有runtime主动上报进度的API |
| Git关联、目录与代码行/Commit/PR引用 | repository_read仅静态本地固定SHA文件白名单/8000字节；固定源码读取与报告有真实证据 | 部分实现；无原规划的关联/目录/代码引用产品入口 |
| Git为Markdown唯一数据源、编辑/历史/冲突 | GitDocs/DocumentService/编辑器；139 Python/122前端及真实Matrix/Git/浏览器证据 | 已实现声明的固定文档范围；不推广成全部文档产品完成 |
| 未恢复的V0.3条目和优先级 | 正文尚不可见，父端继续恢复 | 待证；不以推测替代，不宣布全部功能完成 |

Issue12仍明确暂停。ADR41和其他贡献者独占设计保留；本轮选择不改授权/CRDT的消息历史分页切片。生产语言重写、多租户等不自动追加为本轮必做，也不能用这些泛化边界掩盖上面的已确认原功能缺口。

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
5. **完整产品功能。** 上方已恢复原功能中的多文档、登录/成员、附件、全文搜索、消息转文档、Agent注册/进度、Git关联/引用仍有缺口。按原文继续实现，V0.3未恢复的优先级保持待证；不能以Phase0未列为理由排除这些功能，也不能据此擅自追加未确认生产承诺。
