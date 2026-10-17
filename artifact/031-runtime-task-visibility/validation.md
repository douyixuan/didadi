# 任务可见性验证与 MVP 收敛

基线5ebdc2c/PR47，mainf0ab205；open PR无新重叠，ADR41独立7067385，本执行者不接管。独立didadi-task-visibility/feat/runtime-task-visibility，checkout无AGENTS/.agents/skills。父任务明确授权该slice，collaborative-workflow/truth记录，父任务负责小时汇报/下一轮。

保留pending/unverified/done/failed/cancelled控制语义；status新增派生phase/attempts/lease期限/retry时间/固定原因及聚合WS观测，不返回lease/session token或未完成正文。新授权确认claimed_at与预留/旧DB租约区分；旧livelease展示未确认，不冒称在权限检查。连接关闭不释放lease；registered heartbeat不续lease、不证明模型进度；HTTPpresence不声称覆盖。closed墓碑不被晚心跳复活，多连接不互相抹除；所有过期观测（含closed）45s后unknown。retry budget耗尽提示不会承诺再执行。缺新metadata的旧Gateway也不推断空闲。

本机完整128Python通过84.757s，122frontend/13files/固定33文件语料通过，生产build通过；最终文案调整后122frontend完整再跑通过34.41s及build。独立后端20/前端61专项通过、最终有限静态review无阻塞。Review修复close记录永久disconnected、旧租约误称检查、短4s退避跨进程时序脆弱。初次Doc阶段fakeTimer在effect定时器创建后才安装，回归失败；调整测试timer创建顺序后通过，未改弱产品断言。后续真实短退避检查改server deadline，严格到期前拒claim由fakeclock验证。

真实Synapse/HTTP/WS：新ownCompose didadi-taskstate Matrix8040/Gateway9080和合成身份，scripts.task_visibility_smoke独立子进程无Git mount。首次与reviewed版本完整通过。metadata-only任务→claim→API写Git后保持；10s心跳推进但原lease expiry不变；只terminate本脚本子进程，观察断开、未到期仍running且新probe不能claim；真实60s到期后phase retry_wait/lease_expired，重启重取同task；显式fail/退避，再重启complete，旧lease被拒，重复complete同reply，Git一次操作/一条Matrixmetadata回执、outbox清空。日志.local/tasks-preview/logs/task-protocol-reviewed.log。不停止他人或旧预览runtime，父进程清理只针对自建子进程。

Doc与Agent activity显示相同阶段、attempt与server重试时间，区分lease/连接/进度；状态轮询错误保留草稿/请求并显示unknown，恢复只清自身错误，无新send；无条件Agent绿点移除。App polling不重叠、取消/审计/结果逻辑保持。

新8818预览自有WS9081/Doc9082/Git与新合成状态；源码报告/拒绝、真实SDK保存/历史/冲突及HTTP资产匹配验收记录私有.local/tasks-preview。复用B开发依赖，无新冷安装claim，无浏览器/GUI/剪贴板/历史/搜索或截图。旧所有预览/数据保留。

原始README7861f295四模块、ADR0001、Issue1/2/3共17项在docs/MVP_ACCEPTANCE.md逐项映射候选自动化与限制；无独立原PRD，不将17项覆盖当完整通用平台生产验收。main与draft栈仍有差距；当前最终zip冷启动/隔离旧DB卷升级、真实安全GUI、旧content任务迁移策略仍需收敛，生产注册/grants/网络Git/CRDT不自动扩成当前MVP。下一最高价值是冻结当前zip的干净安装及旧DB保留卷升级验收，完成有限清单后交回负责人，避免无限功能增长。

最终head pushCI/PR/原Library版本在PR和验收说明更新；本地通过不冒充云端通过。保持draft，未merge/ready/公网部署、权限凭据变更、ModelBench/Issue12性能/ADR41修改，未建重复automation。
