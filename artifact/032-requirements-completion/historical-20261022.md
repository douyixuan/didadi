# 历史窄验收归档

仅历史候选与合成自验，不是16片产品完成证明。来源Git提交 `671fa52aad1c866d7a8dd9d9e233dbf739c7fd40` 的 `artifact/032-requirements-completion/validation.md`，从“产品流程接入与候选版本”原文恢复；未重新运行。历史状态只代表当时。

### 产品流程接入与候选版本

2026-10-22新增流程调整沿用今日已有计划，不重开功能台账。远端main核对为1f371893baa0cf504a7c63d8df39170680336e40（PR67，准确CI39755264542通过）；开放PR仅41，保留其贡献者范围。以下为本机已提交且未发布的成果，不是main或线上版本：

- 未读49c61babd067359934149e3f6a3d665b222973b7：房间类型/成员/命名草稿、Thread标记边界与身份隔离；离线Python67/67、前端155/155、构建通过；独立审查身份发现修复后专项5/5及联合3/3通过。
- 任务1f3c7b2b8fd0782e7db1f51b09906cbaa152a176：复用46d07799进度与固定demo.md产物、命名草稿保护和同adapter换用户下载隔离；Python114/114、前端169/169、构建通过，独立复审无阻断。
- 移动036eac8ced6f0988da94d7fbed7f2de55557bb49：复用11d9391并保留命名文件抢救导出与主线浮层；Python114/114、前端182/182、构建与独立复审通过；无实际手机视觉验收。
- 讨论06fd0206905333893b82179639f09b91d65d6ba4：修复搜索与Thread同房换身份缓存/迟到隔离；Python114/114、前端186/186、构建通过，独立专项8/8。

上述结果来自原任务已观察到的离线检查，非本次重新执行或真实用户验收；本次只发布流程文档与离线门禁，不夹带这些业务代码。真实Matrix、登录/凭据、服务、截图、实际安装/部署与多设备回执未在本次运行。当前安装与线上SHA未知；现有Vercel可访问不能证明任何上述候选已交付。根ROADMAP既有七个历史勾选保持原窄范围证据，不因新增门禁升级为整个产品验收。


今晚流程增量：复用根ROADMAP，新增roadmap功能细化与轻量模板，文档管理为主实例、未读为补充实例；README旧四条Phase0列表改为链接根树。通用流程明确设计/实际自验/发布后版本/回滚/缺陷重开，不把用户当首轮测试员。实际查看本机用户原IMG_1677.png后提供mobile-editor.svg布局设计，非候选运行截图；未运行新的GUI或截图。门禁对84叶子、两个实例结构/链接/元数据检查通过，11个隔离回归通过；严格要求document-management可勾选时按预期拒绝，原因是仍有明确未实现/未验收门槛。SVG仅XML有效，未声称渲染或实际视觉验收。CI增加的只有离线产品门禁与其测试，原Matrix单独许可机制与默认离线守卫不变。


门禁独立复审建议已修：模板补acceptance.kind；历史豁免与PR目标/push前基线已勾叶子比较，不能在同批提交先勾再纳入历史。12/12隔离回归、84叶子/2功能结构检查通过。2026-10-22只读GitHub部署列表确认：PR67 head a322b50对应Preview，main1f371893对应Production，e5b49d3及PR64 head同样有记录；因此本次按父端明确要求暂停所有push/PR/合入，未更改Vercel设置绕过。只能交付本地流程提交，远端CI未触发，不能称其已通过。


### 合成手机横屏布局修复（2026-10-22）

新合成QA许可后，独立临时浏览器profile、loopback静态页与无真实后端createDemo适配器执行06fd020完整编辑路径：竖屏工具一行、更多面板、输入中文文本、保存响应失败、原操作Retry、页面正常重载后内容保留。该检查不创建身份、不碰真实内容或剪贴板。实际查看8张截图发现844×390横屏退回桌面工具区，正文被挤压；这是新发现，不是把旧回归计作新增。

本修复将既有移动布局同时用于宽度≤960且高度≤500的短视口；桌面1440宽度不命中。待修复后准确代码版本合成截图复验，再回写结果。真实iOS键盘、物理IME/触控选区、Matrix/Git/身份链路仍未验收；原始用户图只作已授权设计参考，不冒充改版截图。

修复代码准确版本c58d3a157ea039403b28a550fb78ab4fa268c3c3：离线Python114/114、前端186/186、构建通过；不是新增186个功能测试。新许可范围内合成headless QA复验8项断言和8张截图通过，实际查看全部图，并独立审查横屏前后/竖屏/更多/失败恢复/桌面，无新的具体布局阻断。截图与实际测试入口保存在[原证据目录](mobile-qa/results.json)，包括[横屏修复前](mobile-qa/00-landscape-before.png)、[横屏修复后](mobile-qa/07-landscape.png)、[竖屏编辑](mobile-qa/02-mobile-edit.png)、[更多格式](mobile-qa/03-mobile-more.png)、[失败重试](mobile-qa/04-mobile-save-retry.png)和[桌面](mobile-qa/08-desktop-edit.png)。

准确构建来自git archive c58d3a1的client/src，唯一额外入口qa.jsx注入createDemo和一次确定性保存错误；fetch拒绝，CDP只允许loopback静态资源。临时profile在结束时删除，静态服务及浏览器已关闭；不使用账号、真实内容、剪贴板或部署。默认沙箱loopback EPERM后，依据新明确合成QA许可申请执行并获准；没有绕过审批拒绝。初次测试脚本DOM序列化和错误按钮定位问题已修，最终完整运行使用实际Retry按钮，保存恢复通过。页面重载是网页重载，不是操作系统App重启；390×430短视口不是实际键盘。该样本只有demo.md，不能替代完整多文档/真实Git/Matrix验收，ROADMAP不打勾。

流程接入追加本轮自验：截图门槛由新明确合成QA许可解决，推送/合入仍因Vercel自动部署许可待答而停止。原“视觉未验”历史状态不改写为真机通过；新增仅为准确c58d3a1的headless合成界面与页面重载证据。

### Library交付与合成功能自验（2026-10-22）

三张已查看的合成截图及模板已存原/05_开发/didadi，不修改原验收报告、不新建平行状态台账。Library返回四项succeeded，版本均0：横屏修复前06fd020、844×390为libfile_1c0c5c3ab5f881918720d27f68d0230f；修复后c58d3a1、844×390为libfile_e34096a0508081918914f17e0898b1dc；竖屏最终c58d3a1、390×844为libfile_77ea9a2b992881919402b40767d65c24；通用PRODUCT_FEATURE_TEMPLATE.md为libfile_147853e109448191b5e353946c7dba53。全为合成浏览器非真机，不包含用户原图或真实内容。prepared helper在能力探测阶段报告prepare_uploads不可用，尚未开始写入；按该不可用能力路径改用当前官方host-create，逐项成功并保存本地Library身份。未遇403，没有改变目录或绕过权限拒绝。

随后对准确c58d3a1来源、独立临时profile的合成适配器继续浏览器自验，新增6项观察通过：[实际结果与界限](functional-qa/results.json)。搜索首次失败后Retry、结果返回完整Thread；未读标记首次丢响应后重试同一$task边界、重新读数量1而非伪零；已知任务展示自报说明、转终态后隐藏当前进度；固定Markdown产物查看失败后原版本重试；浏览器原生下载临时demo.md与合成Blob的15字节完全相同；合成拒绝下载后清除已显示正文并给重试。实际查看5张截图。没有发现需要新增代码修复的缺陷，没有把旧单元测试重跑计作新功能。

此轮适配器使用workflowFixture+确定性错误/进度/拒绝注入，身份字符串是虚构元数据，不创建账号，不接Matrix/Git/runtime，不验证真实撤权时序。顶部始终明示Synthetic QA；应用内部“Local/Stored in Git”来自既有非synthetic产品文案，不可拿此截图证明真实后端。仅恢复已加载本人请求，不是全历史枚举；保存与持久化、真实多设备回执仍保留此前门槛。截图和自验入口仅在原证据目录，浏览器与loopback静态服务结束，未推送/PR/合入或Vercel部署。


### 手机完整导航层级设计与自验

原用户要求整个App有产品设计，不能将编辑器一处布局当整体完成。本轮对同一隔离合成适配器按阅读→讨论→检索→完整Thread→编辑→退出返回重走并看完整屏幕。基线c58d3a1实际测到讨论关闭25×25、计数标记/任务恢复19px高、搜索按钮19px高、发送29px高、退出宽41px、保存高29px；长计数说明挤占讨论空间。原搜索返回Thread及编辑前后上下文逻辑正确，保留不重写。不是照代码猜需求或人为造缺陷。

设计改动45dff0c：阅读页保留编辑与讨论主操作，搜索/历史/Agent等收到可发现More菜单（成员/源码按已有能力显示）；计数语义保留但改About counts按需展开；搜索改为输入/消息文档分段/结果的层级；明确移动按钮触控边界，不只改文字。独立审查指出More关闭缺口后，b7f8b28补Escape关闭聚焦summary、点外关闭、切房/身份/模式/面板关闭及退出后不重现。原权限、身份、服务和功能范围不改。前端187/187（新增1个菜单恢复回归）、Python114/114、构建通过；原186个测试不计新增功能。

最终准确代码版本b7f8b28dd089de4b4cc2062c33fb9703f9afacc4重新构建并自验：

| 步骤 | 屏幕与结果 | 验收边界 |
| --- | --- | --- |
| 1 阅读 | [最终阅读](navigation-qa/mobile-01-read.png)：编辑/讨论主操作稳定，更多承载次级功能 | 合成390×844，非真实数据 |
| 2 讨论 | [改前](navigation-qa/before/mobile-02-discussion.png)→[改后](navigation-qa/mobile-02-discussion.png)：短计数与按需说明，消息与输入区域主次清楚 | 真实Matrix计数未验 |
| 3 更多 | [操作菜单](navigation-qa/mobile-02b-actions.png)：搜索/历史/Agent可发现；实际Escape/点外关闭通过 | 非真机触控体验 |
| 4 检索 | [改前](navigation-qa/before/mobile-03-search.png)→[改后](navigation-qa/mobile-03-search.png)：输入和两类结果层级，失败Retry后可选结果 | 注入错误，不接真实搜索服务 |
| 5 回上下文 | [完整话题](navigation-qa/mobile-04-thread.png)：结果打开原Thread及回复，不误标历史回复为房间已读 | fixture只有声明的历史样本 |
| 6 编辑 | [编辑态](navigation-qa/mobile-05-edit.png)：收起周边，退出与保存实际44px高 | 未实际iOS键盘 |
| 7 退出恢复 | [返回原话题](navigation-qa/mobile-06-return.png)：讨论确实可见；重新编辑仍有Navigation draft中文草稿 | 页内恢复，非设备重启 |
| 8 横屏/桌面 | [844×390](navigation-qa/mobile-07-landscape.png)保持聚焦编辑；[1440×960](navigation-qa/mobile-08-desktop.png)保留桌面导航 | 不声称所有尺寸或桌面平台已验 |

[准确版本与测量](navigation-qa/mobile-navigation.json)含7项通过断言。read/discussion/actions/search/edit实际所测可见button边界全部≥44×44；不是仅CSS声明，也不推广为全部控件/全App无障碍合规。全部9张最终图已逐张实际查看；前后对比使用相同synthetic=true fixture，消除外部QA文字与fixed header叠加的测试入口伪影。用户原IMG_1677仅作原设计参考。QA入口与driver保留同目录，临时profile/loopback服务结束；禁外网、真实身份后端、真实内容及剪贴板。没有部署/推送，根ROADMAP未改勾。

最终独立复核：App专项80/80通过，最终b7f8b28的7项QA及实际讨论/搜索/退出返回/横屏/桌面图均已复核，无具体阻断。整体产品设计仍未宣称完成。关键390×844图已保存原Library目录，均succeeded/version0：讨论前c58d3a1 libfile_8fa6d4da7f348191b2c4c4e90b67c599；讨论后b7f8b28 libfile_6ca47444480081918080b0dc196bb4cb；搜索b7f8b28 libfile_e5952ee6668881919de8746135909f2d；阅读b7f8b28 libfile_9d9fa85d9b748191986ff2ffcb06adec。没有改原Library层级、报告或发布设置。


### 文档管理完整路径合成自验

按今晚原计划继续，代码来源准确b7f8b28dd089de4b4cc2062c33fb9703f9afacc4，无新增产品代码。现有workflowFixture注入实际App/Crepe，在1440×960独立临时profile浏览器操作；只将fixture已有history.entries投影为客户端history.commits形状，并注入一次写前保存错误，不模拟真实Git原子性。界面顶部明示内存适配器，不创建账号/后端，不触真实数据。

[执行记录](document-qa/results.json)：6项功能观察通过＋1项环境限制诊断，不宣称7个功能通过。创建Notes.md并保存中文内容，demo.md未改；切换回demo再打开Notes内容正确；移动Archive/Notes.md后当前选择/路径同步、无源路径重复；再保存后的历史读取可回到移动后的旧版本，不串demo；保存失败保留当前草稿和选择，Retry的room/content/base/operation/name逐项完全相同；重载后恢复demo.md浏览器草稿，不混入命名文档内容。6张截图已逐张实际查看：[创建切换](document-qa/01-created-switched.png)、[移动](document-qa/02-moved.png)、[当前路径历史](document-qa/03-path-history.png)、[失败](document-qa/04-save-failed.png)、[重试后](document-qa/05-save-retried.png)、[重载草稿](document-qa/06-reload-draft.png)。

边界：fixture内存仓库重载重置，Archive/Notes.md不再存在；这是测试环境限制，未验命名文档仓库持久化，也不据此判真实Git丢文档。应用重载默认选择demo，本次仅确认其草稿不串；未证明重新打开原命名选择。移动前旧路径的全部历史不能由fixture读取，产品稳定ID/跨路径历史仍是已有明确缺口，未改41或临时发明ID契约。首次脚本把独立Workspace标题误作markdown-body正文导致等待失败，已按实际标题定位修正；不是产品缺陷。没有把模拟Saved to Git文案当真实Git证据。本轮无新产品缺陷，未为制造进展修改正确行为。

### 今晚四目标实际对账

| 原功能目标 | 本任务实际完成/复用 | 未完成门槛与细化入口 |
| --- | --- | --- |
| 文档管理完整恢复路径 | 创建/保存/切换/移动/移动后历史/失败原请求重试/浏览器草稿重载已作合成UI自验；不重复计旧实现 | 命名仓库重载持久化、移动前跨路径历史/稳定ID与真实Git流程未通过；重开选择的前端缺口后续已修，见下节，见roadmap/document-management.md |
| 检索与未读 | 复用49c61bab及06fd020；同身份作用域隔离已修；搜索Retry到完整Thread、未读原边界Retry和新计数已合成自验 | 真实Matrix检索/通知规则、多设备回执、撤权时序与发布未验，见roadmap/discussion-search.md及unread-notifications.md |
| 已知任务进度与固定Markdown产物 | 复用1f3c7b2；自报说明/终态、固定版本查看Retry、原生15字节下载和合成拒绝反馈已自验 | 外部runtime、真实授权撤权与Git产物绑定未真实重验；全历史枚举/通用产物仍有契约依赖，见roadmap/task-progress-artifacts.md |
| 手机导航与编辑设计 | b7f8b28新增实际设计修复；完整阅读/讨论/检索/编辑/返回＋触控测量、横屏/桌面自验7项，独立复核与9图 | 真机键盘/物理IME/触控、全部App页面及真实后端未验，见roadmap/mobile-navigation.md |

以上是我们先验后的今晚结果，不是给用户首轮测试作业。全部业务候选仍本地，main仍1f371893；Vercel自动发布确认待答，无push/PR/合入/CI触发，不改部署设置。四目标均保留完整产品门槛，不美化为全部完成；根ROADMAP不新增勾选。

文档自验独立复核确认6功能观察＋1限制诊断，重试比较完整原请求，UI源文件与b7f8b28逐字节一致；未发现新产品代码缺陷。ROADMAP细化现5个功能入口，84叶子结构/链接/元数据与12/12门禁回归通过；任务浏览器记录仍明确是c58d3a1，最终组合送验不自动继承。


### 文档选择恢复前端修复

新增代码候选 `777986c37d9d2e07618c9a0ad39e791144ff98eb`，独立工作树 `didadi-document-selection`，基于4bdd92e；未push/合入/部署。选择偏好按synthetic/matrix、用户、实际文档房间隔离，当前列表确认后才恢复；不存在路径回退到已列出文档，不删除原草稿。网络列表失败保留偏好；401/403不盲开默认文档。移动成功确认后更新偏好，失败维持旧路径。无稳定ID或跨路径历史新增。

本轮前端198/198通过、构建通过、diff检查通过。新增hook隔离/列表确认/失效回退/存储失败/旧响应/legacy拒绝恢复，App重挂载恢复、历史404保留当前路径、403显式重试及既有移动测试的偏好断言。一次全套出现未修改BlockEditor初始化时序失败；如实保留失败事实，后续同套完整通过，不将首次运行写为全绿。独立静态审查指出历史404误回退、旧卸载回调、legacy拒绝与重试问题，均修复并补回归，最终未发现剩余must-fix；审查者未独立跑测试。

准确777986c已重新构建合成QA，Chromium桌面1440×960：命名文档选择重载恢复、同文档中文草稿恢复、失效路径回退且隔离草稿记录保留，3/3通过。[结果](selection-qa/results.json)、[重载选择](selection-qa/01-named-restored.png)、[草稿恢复](selection-qa/02-named-draft.png)、[失效回退](selection-qa/03-missing-fallback.png)已逐张查看。夹具每次注入固定命名文档，不能证明创建/移动后的Git持久化；不是真机或真实身份权限验收。测试脚本曾在重载空body和误判随机草稿键处失败，已修正确等待与记录内容断言，不算产品修复。

未启动Document Service、Git后端、Matrix或身份夹具，未执行被拒后端测试。命名仓库重启/回读与跨路径历史仍未验，PR41/Issue12未触碰；根ROADMAP保持未勾。Vercel仍是既有合成站点，不能当本候选。


### 今晚累计候选最终前端自查

准确代码仍为777986c，本轮未发现需要新增产品代码的缺陷，也未把重跑旧测试计作新功能。先核对既有IntegratedWorkflow、UnreadMainIntegration、WorkspaceSearch、TaskArtifacts及选择恢复测试：身份/房间迟到响应、未读边界、草稿和产物隔离已有覆盖；同版本198项前端/构建结果沿用上节，不重复执行。

只补之前缺失的同一路径组合：390×844编辑未保存中文草稿→退出→搜索失败重试→完整Thread→未读失败重试→已知任务自报说明→固定Markdown产物失败重试→844×390返回原草稿；再检查窄屏空搜索。5项检查通过，被测按钮44px下限、可滚动入视口及中心命中未遮挡。查看了[搜索错误态](final-interaction-qa/01-narrow-search-error.png)、[横屏产物错误态](final-interaction-qa/02-landscape-artifact-error.png)、[返回草稿](final-interaction-qa/03-landscape-return-draft.png)、[搜索空态](final-interaction-qa/04-narrow-search-empty.png)，主操作可辨且无新阻断；独立查看四图与驱动后未发现新缺陷，复审要求补的未读两次相同room/event边界、产物两次相同room/task/id/commit/blob参数断言已补并重新5/5通过；横屏产物图是在滚动至重试后的状态，不宣称全部控件同时可见。[结果与限制](final-interaction-qa/results.json)及夹具/脚本同目录。脚本前两次因退出ARIA名称及summary菜单定位错误失败，修正脚本后通过；不是产品缺陷。

| 今晚既定目标 | 实现 | 合成自验 | 真实验收 | 交付 |
| --- | --- | --- | --- | --- |
| 文档管理完整恢复 | 选择恢复777986c新增；创建保存移动为既有；跨路径历史缺实现 | 既有6项UI＋选择/草稿重载3项；组合草稿保护通过 | Git命名仓库重启、真实权限和完整历史未通过 | 代码/截图/记录本地；未发布 |
| 讨论检索与未读 | main既有＋49c61bab/06fd020整合保留在777986c | 既有失败重试/完整Thread/未读边界；本轮窄屏错空态与组合通过 | 真实Matrix搜索、通知、多设备回执未验 | 本地候选；未发布 |
| 已知任务进度与固定Markdown产物 | 1f3c7b2复用在777986c；无全历史枚举/通用二进制扩展 | 已有固定版本下载；本轮进度→产物重试→返回草稿通过 | 外部runtime/撤权时序/Git产物绑定未验 | 本地候选；未发布 |
| 手机导航与编辑设计 | b7f8b28设计实现复用在777986c | 既有7项/9图＋本轮4状态截图，未发现新阻断 | 非实际iOS；真机键盘/物理IME/全部页面未验 | 本地截图可查看；线上仍旧版 |

以上不是完整产品已验收。没有后端、身份夹具、真实账号/数据或网络服务测试，无push/PR/合入/部署；PR41/Issue12未触碰。既有https://didadi.vercel.app/仍是旧合成展示，不能标为777986c，真实运行SHA未重新核实。根ROADMAP不新增勾选。
