# 截止前产品交付

依据：最初 README roadmap、ADR 0001、docs/ARCHITECTURE.md、docs/CLIENT.md、Issues #10–#25。用户已授权实施、独立评审、测试及合入；公开站点仅合成数据。截止：2026-10-16 00:00 UTC。

## 首个切片：#25

- 独立 worktree，保留 #10/#11、#12 的未提交草稿，不并行重复该范围。
- 读模式按 Markdown AST 提取第一个顶层 H1，不把 code/list 内 H1 当标题；移除该标题时仅改变展示，不修改保存源。
- 复用 sourceBlocks 的 front matter 边界，在折叠 Properties 中安全展示，不渲染 YAML 为标题。
- memoize 展示解析；仅阅读需要生成阅读视图。
- 真实组件测试：front matter + H1、无 front matter、代码内伪标题、Setext H1、HTML inert、源不变。
- 独立 review 后运行现有测试/构建；draft PR，最终主线 CI 与部署分别验证。

## 后续

核验真实核心链路和可复现启动，处理安全/恢复依赖；不把 Phase 0 当生产完成。没有产品 PRD 或用户故事文件时明确说明证据来源，不编达成百分比。GUI 测试先申请协调窗口，避免 Stickies 同机争用。
