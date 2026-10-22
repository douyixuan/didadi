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

### PR57附件重试复核（2026-10-22）

独立审核发现并修复两项上下文问题：408超时保留原文件/线程/operation的不确定重试；文件下载在卸载、切房、换API或换事件后丢弃迟到结果与错误，旧请求不能释放新请求的锁，也不能触发离开界面后的下载。仅作用于既有附件流程，不增加存储、权限或任意URL能力。离线guard涵盖附件服务和纯注入组件测试：主执行Python30/30、前端104/104与构建通过。真实Matrix媒体上传、撤权时序和浏览器文件下载未运行，不视为真实验收。

### 既有PR依赖链合入复核（2026-10-22）

按照新的明确合入授权，先完成ROADMAP PR66，再依序审核PR52–64；使用独立review工作树，未推送或混入未读3080c8f、进度a4cc1a00、产物0847411、集成46d07799或移动UI11d9391候选。PR41与Issue12不在本轮范围。旧分支默认Matrix/HTTP smoke、npm lifecycle与分支名条件均未带回；`.github/workflows`保持安全main定义不变。所有实际合入均使用普通merge及预期head校验，不绕过保护。各PR准确head与合入main的CI链接保留在GitHub Actions，TLS查询失败仅重试只读查询，不重复写入或触发CI。

最终PR64合入前本地guard：Python62/62，前端144/144（16文件），构建通过。Python只运行临时Git、假Matrix/媒体适配、进程内代理、临时SQLite和纯内存SessionContract类；HTTP fixture类明确排除，传输及非临时Git子进程守卫保持启用。独立分组审核发现的附件408冻结重试及迟到下载问题已修并复审通过。纯虚构会话与真实身份认证分离；没有执行真实登录、注册、注销、媒体服务或真实数据迁移。历史PR说明中的真实验收不等于本轮重新验收，ROADMAP不据离线结果提前打钩。


### 已合入提交与CI归档（2026-10-22）

本表将本轮临时证据归入本验收记录，GitHub链接为持久来源。所列准确head与merge提交的Test离线工作流均已观察到成功；不证明真实Matrix、认证、部署或手机视觉验收。最终业务主线为 `e5b49d3f2e2479e92a49f027174455e0eaca5b31`。

| PR | 审核head | head CI | 合入main | main CI |
| --- | --- | --- | --- | --- |
| [#66](https://github.com/douyixuan/didadi/pull/66) | `45f342f62b546c1e85b935ffcbaa032527c48e26` | [通过](https://github.com/douyixuan/didadi/actions/runs/39578980705) | `de0d24b172d197cad9795701bc245ed5dcaf4fa8` | [通过](https://github.com/douyixuan/didadi/actions/runs/39748440359) |
| [#52](https://github.com/douyixuan/didadi/pull/52) | `6ba88b5263060fd4d636b0bc7cc5036f418dd565` | [通过](https://github.com/douyixuan/didadi/actions/runs/39749081642) | `d8f4035e8b83f4912d70c8bbfffde04012b7710c` | [通过](https://github.com/douyixuan/didadi/actions/runs/39749241374) |
| [#53](https://github.com/douyixuan/didadi/pull/53) | `4ee3ffe75b6291f9703756b9faac13bc1bd44127` | [通过](https://github.com/douyixuan/didadi/actions/runs/39749505881) | `6aa03cd73edb630438c25507cc634ba2d629583a` | [通过](https://github.com/douyixuan/didadi/actions/runs/39749616706) |
| [#54](https://github.com/douyixuan/didadi/pull/54) | `2e76a129a00c663df013b519626ef045161387c6` | [通过](https://github.com/douyixuan/didadi/actions/runs/39749823781) | `3a6722ad9f7fa36e7d0331de98d848347acac51f` | [通过](https://github.com/douyixuan/didadi/actions/runs/39749930923) |
| [#55](https://github.com/douyixuan/didadi/pull/55) | `5325232d1d828b485fcd0b47739654539efd77a2` | [通过](https://github.com/douyixuan/didadi/actions/runs/39750131313) | `4c5f231337a99c3ccc6ef1e100d3f4f13898ec0c` | [通过](https://github.com/douyixuan/didadi/actions/runs/39750236981) |
| [#56](https://github.com/douyixuan/didadi/pull/56) | `b3f96694847ebba735b3bb109ce75b89307676c7` | [通过](https://github.com/douyixuan/didadi/actions/runs/39750387764) | `1564fb8746651fe8a26d63a0e445e5f3a08f277a` | [通过](https://github.com/douyixuan/didadi/actions/runs/39750496799) |
| [#57](https://github.com/douyixuan/didadi/pull/57) | `da38ff325f2ff3312febc3b27cafd0afe96adae7` | [通过](https://github.com/douyixuan/didadi/actions/runs/39750892411) | `3c9bf2c3ef7c211c3cd324ba2589994035639680` | [通过](https://github.com/douyixuan/didadi/actions/runs/39751009732) |
| [#58](https://github.com/douyixuan/didadi/pull/58) | `a0641ce5c99da79c6fbaa32db9ce6b278bc5c2a3` | [通过](https://github.com/douyixuan/didadi/actions/runs/39751269715) | `2a7086352a2a511418333f39df807bbbd4a9296f` | [通过](https://github.com/douyixuan/didadi/actions/runs/39751397554) |
| [#59](https://github.com/douyixuan/didadi/pull/59) | `2f305769e8fb4178c5dd4bd0f2362773bc9214f6` | [通过](https://github.com/douyixuan/didadi/actions/runs/39751659079) | `51c3dd4be6d0869114b4451d121ff346c6a326f7` | [通过](https://github.com/douyixuan/didadi/actions/runs/39751782644) |
| [#60](https://github.com/douyixuan/didadi/pull/60) | `1b757995c08772d8f9e22b929fb882fc4a565080` | [通过](https://github.com/douyixuan/didadi/actions/runs/39752010705) | `a9ef603a6639821d170ca95ca1e4bef19628da75` | [通过](https://github.com/douyixuan/didadi/actions/runs/39752152362) |
| [#61](https://github.com/douyixuan/didadi/pull/61) | `eadc8338701a3030842e09265505371401b2d05f` | [通过](https://github.com/douyixuan/didadi/actions/runs/39752306389) | `74fc924ad0332ff419a9306055906087ac50fd67` | [通过](https://github.com/douyixuan/didadi/actions/runs/39752420366) |
| [#62](https://github.com/douyixuan/didadi/pull/62) | `478b161a585f3ce6fec33462519b08a9a3192591` | [通过](https://github.com/douyixuan/didadi/actions/runs/39752606643) | `b9f82976deffda109aec81aa7994874e67e4d212` | [通过](https://github.com/douyixuan/didadi/actions/runs/39752746802) |
| [#63](https://github.com/douyixuan/didadi/pull/63) | `bfa21d0974af3ddf6e0b794f9e4cc77a1f1b0e22` | [通过](https://github.com/douyixuan/didadi/actions/runs/39753103323) | `16dffa40490c012d19cdbff3bfece00a547c6ed2` | [通过](https://github.com/douyixuan/didadi/actions/runs/39753440253) |
| [#64](https://github.com/douyixuan/didadi/pull/64) | `f1e724273cd54748b5faf97bef70ff8d7484d269` | [通过](https://github.com/douyixuan/didadi/actions/runs/39753785838) | `e5b49d3f2e2479e92a49f027174455e0eaca5b31` | [通过](https://github.com/douyixuan/didadi/actions/runs/39753912477) |

ROADMAP边界复核：本轮没有新增勾选。原有七个已勾叶子保留其既有范围证据；新增多文档、引用、搜索、附件、房间及纯虚构会话的代码合入不扩大既有真实验收。真实登录与退出仍待接入，未读/Runtime主动进度/任务产物/移动改版候选尚未合入。完整历史任务恢复仍缺本人授权分页枚举契约，不能把已加载消息的最近八项当作全部任务。
