# 实现与验证

当前阶段：部分验证。当前切片为Issue16；不将全部平台需求标完成。

- 首次用系统Python运行时9模块缺少websockets，属未装声明依赖；随后新建本分支.venv、安装requirements-runtime.txt，完整132项Python通过（109.624秒）。整改审查发现后单独5项metadata测试通过（12.662秒）；最终完整133项由提交CI继续核验，不能把两次运行数字相加。
- 独立合成项目didadi-requirements，Matrix8048/Gateway9110，真实Matrix/AS/非管理员fixture通过。agent_body_api_smoke通过：独立WS外部runtime无Git路径，scopedHTTP写读，真实本地bare remote正常main push；作者=托管Agent、subject可读，远端log无合成room/task ID、无私有intent refs；元数据回执、同请求幂等、不同正文冲突与outbox reconcile通过。
- metadata测试覆盖新/旧JSON格式、旧无作者hash的原提交重试、远端导入main后完整请求匹配重建本地路由、不同请求拒绝、CAS前失败无幽灵通知、损坏/缺字段intent显式失败。
- 既有multiprocess退出73→重开恢复测试在完整Python中通过；不宣称掉电/磁盘损坏恢复。通知私有refs不是可删派生索引，完整bare备份要求已文档化；旧已发布JSON历史不重写。
- 未修改任何前端产品源码；正在构建并评估独立headless测试路线，实际结果另记。GUI/剪贴板禁用、物理IME/拖拽和生产发布未验。

私有运行日志：.local/requirements/logs/；不提交fixture、凭据或数据库。源码包v13保留为历史已验归档，本分支不冒称该旧包包含本轮代码。

恢复边界补验：7项metadata测试通过（12.150秒），新增CAS失败→另一store发布不同时间的同operation→导入，以及显式GC清理旧候选后同一路径；错误请求保留原intent，匹配请求返回已发布commit并恢复pending。首个head push/PR CI均通过，因自动审查新增恢复修复，必须等待新head CI，不沿用旧绿。

## 2026-10-20消息历史切片（候选）

- 新源依据来自父端恢复的原始产品对话，不再用Phase0四模块代替全部PRD；docs/MVP_ACCEPTANCE原位完整功能对照，并标明V0.3全文/优先级仍待证。
- 63项定向前端测试通过；早期完整125项通过后，针对review新增非单调timestamp/空前进页/并发刷新与历史gap回归，最终全量另验。初次新测试有括号语法错误，已修；thread scope文案改变导致旧label断言失败，改为独立span保留原label并明确loaded scope，未删回归。
- 实际Matrix/Synapse8048、Gateway9110、独立client8832：65历史消息跨页完整、相同游标重试一致、期间新增第66条保留且不重复，通过。review要求保留Matrix流顺序和空页前进游标，均整改后相同真实protocol复验通过。
- 实际无权限隔离headless Chrome点击Load earlier：初始只见最近50，加载后65条、无重复，视口anchor top1640/height7165/viewport500；刷新新增第66条后旧第0条仍保留。无OS IME、剪贴板或用户profile访问，不冒称物理GUI。
- 独立最终只读复核两项P2已修、无新增阻断；完整thread、搜索、多文档等仍为真实缺口，不因这个切片通过而宣称全部完成。最终headCI、合入后mainCI另验。

## 2026-10-20 Named document candidate

The isolated workspace-documents branch adds regular Markdown file listing, path creation, opening, human direct Git saves, fixed history and separate local drafts. API retries reuse the operation UUID; duplicate paths and portable-name collisions cannot overwrite existing text. Room checks remain bound to the original document room. Agent document actions remain limited to demo.md; move/rename and from-messages are still missing.

Before the final pagination integration, 143 Python tests and 135 frontend tests passed. The integrated candidate adds a delayed-create/storage-failure regression, with 63 App tests passing. The first full Python attempt was sandbox-denied for loopback binds (25 errors); the permitted rerun passed all 143. This was an execution limitation, not a passed first run.

Real loopback preview 8834 uses its own Git repository and metadata. documents-smoke.mjs passed create/retry/list/two-file save isolation/fixed history/duplicate rejection/invalid paths. Isolated headless installed Chrome passed A unsaved draft, B direct Git save, A restoration/save, independent Git contents and reopening after reload. Evidence stays under .local/multi-documents; no physical IME or drag acceptance is claimed. An independent reviewer found and rechecked a delayed-create navigation race; the added latest-state check keeps the current editor mounted when it becomes unsafe to leave.


### PR52安全合入复核（2026-10-22）



本次仅整理已发布PR的依赖与安全CI，未夹带本地未读、Runtime进度、任务产物或移动UI候选。保留main默认离线工作流及单独显式真实验收入口；命名文档增量经独立静态复审未见新阻断。离线guard增加DocumentService纯临时Git/假Matrix测试和文档引用、草稿、结果投影界面测试。WebSocket可选依赖延迟至实际bridge启动时导入，参数及权限规则不变；非普通Git模式测试直接重开合成Git索引，避免把远端传输混入文件模式检查。主执行离线Python14/14、前端82/82及构建通过。真实Matrix、认证、外部runtime、浏览器及远端Git验收未运行，不因此打勾。
