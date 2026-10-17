# 原始 MVP 验收边界与剩余差距

本清单用于收敛现有交付，不增加产品范围。原始来源是 [README@7861f295](https://github.com/douyixuan/didadi/blob/7861f295aa55c9c1d65e850386230aebe760b4c6/README.md) 的四模块路线、ADR0001和Issue1/2/3；仓库没有另一个可核对的独立原始PRD。它们定义的是Phase0通信/耐久任务/Git风险验证，不等同于完整通用Agent平台生产验收。Git/PR为权威；当前main仍f0ab205，候选叠加PR31–47及本切片，独立ADR41不包含在候选。

## 原始检查项（17项，按来源逐项映射）

下列“候选自动化覆盖”只对隔离合成Matrix身份、单固定Agent/开发凭据、可信本地bare远端和声明的测试语料成立。没有据此关闭Issue或宣称已经合入main；最终候选精确CI/交付版本在PR和验收说明中记录。

| 来源与检查项 | 候选自动化覆盖与证据 | 必须保留的限制 |
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

第四模块React+matrix-js-sdk文档/讨论/Agent任务视图已有真实SDK/API自动化、声明语料编辑器回归、源码/报告、取消、草稿、并发保存及本轮状态提示。真实浏览器操作仍不是已验结果。Issue11/14/15/16/22等后续缺陷有候选修复证据，但open状态与main合入不能靠本清单自动改变；Issue12性能工作仍独立暂停，ADR41设计归另一执行者。

## 本轮仅补任务生命周期可见性

原pending/unverified/terminal控制状态不变；展示Gateway观测的waiting/verifying/running/retry_wait、attempts/期限和原因。WS观测只证明连接：关闭不提前释放lease、过期变unknown、旧schema租约明确未确认，HTTP runtime不冒充被观测。原task重取/显式退避/重复完成仍依赖已有幂等，不自动新建任务。真实协议停的是本脚本自己的runtime，Git提交后停机→租约有效期拒重复claim→到期重取→显式retry→恢复完成，一条Git操作/一条Matrix回执。

## 收敛到 MVP 验收还差什么

1. **候选与main仍有发布差距。** 当前成果在draft栈。未合入/未ready；不能把绿色候选称作主线交付。合入限制保持，由负责人处理，不能绕过。
2. **当前最终源码包复验。** 最近真实本机冷安装/保留卷证据基线是df4；新候选本机复用开发依赖，CI从checkout安装。应冻结一份候选zip，在全新目录冷启动，并用隔离旧候选DB/卷升级验证新元数据迁移；不修改任何现有用户卷。优先做这项有限验收，而不是追加可选功能。
3. **GUI验收尚缺。** 中文IME、鼠标拖拽、光标/滚动、实际磁盘导出字节、新草稿关闭/跨标签等真实GUI未验。安全工具链停止期间保持未验，不用jsdom或截图代替。
4. **跟进要求的严格边界尚未全面兑现。** 新推荐读写已把正文放在API/Git、Matrix仅metadata，但弃用的旧Matrix content任务仍兼容，历史消息无法撤回；若将Issue14的“任何平台写入口均不投递正文”作为MVP硬门槛，需明确迁移/拒绝旧入口策略并单独验收。
5. **生产平台不是当前Phase0。** 多Agent注册/生产grant/多租户认证、网络Git传输、CRDT/live cursors、生产运维、E2EE和许可证均未因此完成。先由产品/架构owner界定是否进入下一阶段，不能以此无限扩展现有MVP或接管ADR41。

下一最高价值动作建议是第2项：冻结当前候选源码包，做干净安装与隔离旧DB/保留卷升级验收，输出通过/失败及阻塞，然后交回原始清单负责人。不要默认再开一轮功能开发。
