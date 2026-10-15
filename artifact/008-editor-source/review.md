# 独立评审与修复

评审者：独立 review_didadi Agent；只读仓库，使用 /tmp 中真实 Crepe/ProseMirror 探针。需求来源为 #13 与本次用户委派，不涉及 #10/#11/#12/#18 的文件归属。

## 已发现并修复

- P2：复制同类有序列表后 Markdown 把两段列表合并，编号改变。新增必要的 `<!-- -->` 边界，parser 将其识别为不可见边界节点；回归比较重开后两个列表与起始编号，而非只比较 textContent。
- P2：无来源的内部空 paragraph 被当成末尾输入段省略。仅省略末尾输入段；内部空段用 `<!-- didadi:empty-paragraph -->` 持久化，重开恢复为空 paragraph。清空已有内部段也保留。
- P2：未闭合围栏后追加段落会被吞进代码块，带 metadata 的 raw code 也有同样问题。普通/raw code 均在新边界前补关闭围栏，重开验证段落独立。
- 空白文件输入后清空/撤销丢失原始空白。事务保留原始空白元数据，回归逐字节比较。
- P2：Enter 拆分列表第一项时，整个列表 canonical 回退会改写未编辑兄弟行的 marker、尾部双空格。结构修改先恢复未变源码行并重解析验证；额外覆盖五种 marker、嵌套 split/join、重复文本与无末尾换行。数字 marker 的匹配忽略派生序号，保存保留未编辑行原数字和 delimiter/zero-padding。语义验证仅忽略 Milkdown list_item 派生 label，仍检查 order、spread、内容、marks。
- 原生 DOM 编辑会把 raw CRLF 变成 LF。raw 编辑状态使用规范 LF，输出按原文 offset 映射修改，保留原 CRLF；真实编辑器交互回归验证 raw HTML/metadata code。

普通文字修改优先原文本节点/字符补丁；结构变化优先行补丁，避免结构重排改写兄弟行，也避免普通文字编辑牵连同一行的 escape spelling。所有补丁均经实际 editor parser 验证，不使用原文位置猜测后直接落盘。

## 边界

这不是任意 Markdown 的普遍兼容性证明。未知 inline 结构的整个顶层块作为源码块编辑，未实现混合 inline atoms 或持久化 block IDs。结构变更必要的边界标记/新增行不计作未编辑内容改写；源码语义无法安全映射时仍可能局部规范化修改块，固定语料与结构回归的零噪音结论只覆盖实际执行的用例。

内嵌浏览器当前不可用；为避免争用共享 Chrome，本次不进行新的物理浏览器点击或截图。真实编辑器 DOM/组件保存重开、构建及 CI 与物理浏览器验证明确区分。本地预览为独立 loopback 样例构建，不连接真实 Matrix/Git，也没有 Vercel 部署。
