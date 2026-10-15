# 本地验证

- `npm --prefix client test`：39 passed，6 test files，44.32s（2026-10-15）。包含真实 Milkdown DOM、文档页面保存重开、raw/表格/中文 composition、CRLF、撤销/卸载、五种列表 marker split/join、内部空段和普通/raw 未闭合围栏边界。
- 固定语料：33 份，24 份真实公开文档 + 9 份自有边界样例；所有文件挂载真实 editor view 并保存重开。31 份有非空富文本块；2 份为空/纯空白。
- 整页 textarea 回退：0/33（0%）。局部源码块：110/1598（6.88%），其余普通块保持富文本。这不把局部 raw 比例混为整页回退率。
- 无编辑保存源码变化：0；不稳定重开：0；首存改写行：0。
- 31 份可编辑文件中的 1586 个可定位源码文本块分别执行真实 PM 中部插入，再保存、精确对比预期字节、重开：非目标源码改写0。每次独立从初始文档编辑，不用第一处编辑代表整篇。
- `npm --prefix client run build`：通过（原有 bundle size / use-client directive 警告保留）。独立 synthetic 样例构建也通过。
- `git diff --cached --check`：通过；固定上游语料通过 `.gitattributes` 保留字节并豁免既有尾空白，避免清理 Markdown hard break/空白测试输入。

语料 SHA-256 在每次测试校验；测试离线。CI 通过正常 npm test 运行相同 corpus，并上传 `.local/markdown-roundtrip.json`。本地日志位于 `/tmp/didadi-editor-final-tests.log`；版本化验证要求以最终 PR/主线提交的 CI 为准，创建 PR 时尚待运行。

## 预览与未运行项目

本地 sample-only 静态预览：`http://127.0.0.1:8770`，HTTP200，服务只监听127.0.0.1，使用浏览器localStorage，不接真实Matrix/Git/LLM。预览构建和日志在本 worktree `.local/editor-preview/`、`.local/editor-preview.log`，PID文件 `.local/editor-preview.pid`；原8767真实数据预览未重启或改写。

内嵌浏览器不可用；遵守本次不争用共享Chrome要求，未做新的物理浏览器操作/截图。真实editor DOM交互不等于物理OS IME或跨浏览器验证。未操作Vercel，没有新增公网部署。本次没有在本机重跑Python/真实Synapse全套；最终CI仍会运行原有Python和真实Matrix集成检查。

范围与普遍性：该33份固定语料不是 #13 原始未固定的1010文件调查；不宣称任意Markdown、任意结构变换均字节保真。未知inline构造保守保留其整个顶层块为源码；必要结构标记/新行允许引入，未实现持久化block IDs或实时协作。
