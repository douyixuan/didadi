# P0 TDD 与 CI 验收契约（#85）

> 2026-11-04 核验基线：`main` `53ec637ae39134b04df613571be9bc116a255a5a`；P0 [#85](https://github.com/douyixuan/didadi/issues/85) 当前 **1/4**（[#69](https://github.com/douyixuan/didadi/issues/69) 已验收、[#70](https://github.com/douyixuan/didadi/issues/70)–[#72](https://github.com/douyixuan/didadi/issues/72) 未验收）。以下定义的是测试与交付规则，不是对尚未实现的功能作成功声明。

## 现有能力与缺口

- [`test.yml`](../.github/workflows/test.yml)：自动在 push/PR 执行隔离的 Python 临时 Git/注入 Matrix 测试、真实登录 HTTP mock、React/Vitest 选定测试，以及浏览器 runner **语法**检查；过去缺少前端 production build 和全源码语法门禁。本规划 PR 补上两者，仍不把离线 mock 说成 E2E。
- [`real-matrix.yml`](../.github/workflows/real-matrix.yml)：已经有 Docker Compose 下真实 Synapse/PostgreSQL、Gateway、Document API、Git 和 Playwright/Chromium 测试，且 [#69 对应真实 CI](https://github.com/douyixuan/didadi/actions/runs/41587178841) 通过。但之前自动触发**只支持历史 PR #90**；本规划 PR 将真实 `matrix-smoke` 运行推广到可信同仓库的相关代码 PR，以及 `main` 上相关代码 push。手动触发仍要求明确审批引用，fork PR 不自动启动真实集成环境。
- 已有脚本：`scripts/real_login_smoke.py`、`client/scripts/real_login_browser.mjs`、`scripts/room_types_smoke.py`、`client/scripts/documents-smoke.mjs`、`client/scripts/move-smoke.mjs`、`scripts/concurrent_merge_smoke.py`；**这些脚本已有不等于 #70–#72 的全部验收覆盖**。不要继续为 #69 重复建登录系统。
- GitHub branch protection API 对当前连接返回 403，**无法证明所需检查已被设置为合并阻断规则**。CI 运行与 GitHub 强制拒绝合并是两个不同事实。规则生效前，执行者须人工/自动核实精确 PR head 和合并后 `main` 全部实际检查通过。

## 每个子 Issue 的 Red → Green → Refactor → Evidence

1. **Red（先写失败的行为契约）**：在真实功能改动前，为本 Issue 至少增加一个新的、可复现、指向真实需求的失败测试；附上失败的具体断言、命令和 commit/日志。失败应来自**缺少产品行为**，不是 Docker 没启动、凭据错误或环境超时。先复用已有测试/脚本，避免同名重复。
2. **Green**：以最小生产代码让新测试及既有回归测试通过。不得用 skip、放松断言、mock 掉被验收的路径或把真账号替换成假状态来伪造通过。
3. **Refactor**：不扩大信任边界、不放宽 Matrix 授权或 Git CAS、不重构无关架构。补足负例（越权、重复、断线、版本冲突）、幂等和恢复，并保持测试绿。
4. **Evidence（合入门槛）**：PR 附 Red→Green 证据、测试命令、精确 head SHA、快速 CI 与真实集成 CI URL；合入后另附 `main` SHA、main CI 与真实集成证据。**只有在 main 已交付并逐条通过本 Issue 的现实验收标准时，才能在父 Issue #85 勾选 1 片树叶。**

## P0 测试矩阵（未打勾的测试均视为待实现）

| Issue / 测试 ID | 首先写的 Red 行为测试 | Green 和实际验收必须证明 | 推荐层级 / 位置 |
| --- | --- | --- | --- |
| **#69 已验收，回归** | 不重新开启已完成 Slice | 真实 Alice/Bob 登录、cookie/CSRF、会话重启、退出、私有房间隔离和固定 Git 提交仍通过 | `test_real_matrix_client_server.py`, `real_login_smoke.py`, `real_login_browser.mjs` |
| **#70 ROOM-01** | 新登录用户不应从另一人账号恢复房间列表/未读状态 | Alice/Bob 独立 session、DM/群组/频道 UI 列表/新建/进入与刷新后上下文正确 | Python room/session 单元 + React 注入测试 + Playwright 真实两浏览器 |
| **#70 ROOM-02** | 从房间被踢出或主动离开后旧页面不应继续读消息/搜索/附件 | 后端 live membership 拒绝 403、前端清除失效房间数据并提示，重新加入后可重试 | Matrix 真实成员撤权 + HTTP 负例 + browser stale-state |
| **#70 ROOM-03** | 发出消息后未读数、房间切换、会话重载不应错记另一房间 | 真实 Matrix 未读/通知计数来自服务器/SDK 已观测状态，刷新后状态一致；不以 UI 假数字当验收 | UI 状态单测 + 真 Synapse/Chromium |
| **#70 ROOM-04** | 非成员/另一账号不能访问私有 group/direct/channel | 真实邀请/加入/撤权/无权限访问的正负例；引用、附件、历史消息无跨房间泄漏 | `room_types_smoke.py` 扩展 + Playwright |
| **#71 DOC-01** | 连续创建两个独立 Markdown 后历史/路径不能混淆 | 各自内容、blob、历史和 Git immutable revision 一致，创建重试幂等、重命名/移动不丢文件 | `test_document_service.py`, `documents-smoke.mjs`, `move-smoke.mjs` + browser |
| **#71 DOC-02** | 两用户同基线编辑/离线草稿不能无提示覆盖 | 非重叠变更安全合并、重叠冲突提示并保留两份草稿，重启后仍可恢复/导出 | concurrency/Git unit + 故障注入 + 真实双浏览器 |
| **#71 DOC-03** | 新文档正文不应出现在 Matrix 事件中 | 浏览器直接 API 保存，Git 有提交；Matrix 仅含路径、blob/commit、作者等元数据回执，正文不存在 | `real_login_smoke.py` + Git/MX 事件审计 |
| **#71 DOC-04** | 未授权者不能写另一房间文档，重试不能重复提交 | 403/409/路径穿越拒绝，固定操作 ID 不产生重复 Git effect；浏览器下载导出内容字节一致 | API 负例 + client download + real E2E |
| **#72 RELEASE-01** | 全新 checkout 不允许依赖开发者原有 `.local`、私有 token 或已启动服务 | 按 `LOCAL_WORKSPACE.md` 在干净 CI 工作区 Compose 启动、2 位非管理员账号、真实浏览器执行 #70/#71，失败则诊断 | 独立 clean-install/Compose/Playwright |
| **#72 RELEASE-02** | 后端/Synapse/存储重启后会话和文档不能丢失 | 保留卷重启，对照 Matrix 身份、权限、任务/Git 版本与浏览器刷新；恢复从独立备份需另有真实记录 | 真实 Docker lifecycle + backup/restore 检查 |
| **#72 RELEASE-03** | E2E 失败不能只留下绿色离线 CI，不能上传明文凭据 | PR head / main 两侧真实集成状态、失败截图、日志、独立 Git SHA、无密码 token 的可下载证据 | GitHub Actions status + allowlisted artifacts |

### CI 三道门（本规划 PR 生效后）

1. **Fast / 每次 PR、push**：`Test / git-docs-spike`（隔离 Python tests、注入 HTTP、compileall）；`Test / react-client`（受网络守卫的 Vitest、脚本语法、实际 Vite production build）。任何失败阻止本次验收；**这些不是现实 E2E**。
2. **Real / 可信同仓库代码 PR + 相关 main push**：`Real Matrix integration / matrix-smoke`，使用 GitHub ephemeral Docker Compose + 真 Synapse/PG + 浏览器 + Git。针对 fork PR 不自动跑敏感的实集成工作流；需经信任/授权后在维护者分支执行。触发路径为 client/src/scripts/tests/deploy/compose/运行依赖与 workflow 变更；非功能文档变动不触发。**#70/#71 的真实测试新增后必须加入此 job 并实际运行**；目前只覆盖已有 #69 端到端和旧兼容 smoke。
3. **Release / P0 关闭前**：由 #72 提供一次独立干净安装、服务/卷恢复、双浏览器 #70/#71 全场景的真实验收，并在准确 `main` SHA 上记录 CI、截图、Git commit 和缺口。用户侧真实设备/物理 IME 仍需标注未覆盖，不得把 Playwright 等同物理设备。

### 门禁与运行安全

- GitHub required status checks 推荐设置为稳定 `Test / git-docs-spike` 和 `Test / react-client`。**Real Matrix 的 job 目前按路径触发，不能未经调整就把它全局设为 required check，否则纯文档 PR 可能因为未生成该检查而被卡住**。先验证 branch protection 配置；如果需要全局强制，在 #72 中添加在每个 PR 上都会产生状态的独立 gate/聚合 job（代码 PR 必须等真实 E2E，文档 PR 明确注明豁免原因），然后再设置 required check。当前连接无法读取/写入保护策略，不能宣称已强制。
- 真实 E2E 仅可使用临时非管理员 Matrix 测试账号、GitHub ephemeral Compose、loopback；测试工具不能持有生产凭据。记录的截图、Git proof 不含 cookie/密码/令牌；失败时仅按 allowlist 上传测试截图和提交证据，绝不上传 `.local` 数据库、授权文件或测试密码。
- 敏感代码变化需复核审查线程和拒绝路径；不得绕过 PR review、使用模拟结果冒充真实验收；PR #41 / Issue #18 为另一所有者，Issue #12 继续暂停。不要为了过 CI 降低测试标准。
- 不用 `% code coverage` 替代行为验收；覆盖率工具可后续增加，但此 Milestone 的唯一完成证据是每个 Issue 的真实行为与权限/恢复负例，以及准确代码版本的 CI。

### ddd 每日执行

每日从 #85 第一个未通过的子任务（目前 **#70**）读取需求；先添加一条失败测试并记录 Red，做最小修改到 Green，再核验 offline + real + main。#71 和 #72 同理。将测试 ID 对应到 PR 与子 Issue；更新 #85 的勾选与叶子数只在完整验收后进行。不为测试计划本身增加叶子。
