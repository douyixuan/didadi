# 验证记录

状态：部分验证。新修复尚未原生 GUI 验收；Mac 锁屏，未继续前台操作。

- 独立 reviewer review_runtime_transport 复核最终 diff，无新增阻塞；独立运行27项 App测试全过。建议的恢复按钮 busy/reading/composing 双守卫已采纳，并增加异步加载保护回归。
- 本地完整前端69项测试全部通过；33文件/1586次块编辑语料逐字节通过，无丢失/不稳定/首存重写；production build成功（现有use client打包提示保留）。
- 针对CRLF/Unicode/entities/escapes的PreservedDraft组件验证恢复回调UTF-8字节完全相同；App恢复/导出验证编辑器发出state不改。textarea自身将CRLF规范为LF，相关测试没有把它冒充原始CRLF证明。
- cancellation测试确认无通用失败alert/Retry、无自动send；明确再次Save才新transaction，重复点击只发一项。source read/report取消提示分别指向原入口。
- 核心启用文字的CSS声明配色按WCAG sRGB相对亮度计算5.12:1–9.06:1（contrast.json），普通文字门槛4.5:1；未测实际浏览器computed样式、透明叠加、全部页面或禁用控件，不宣称全站可访问性认证。
- 首次Python运行使用系统环境，3项回环socket绑定被sandbox拒绝，1个WebSocket模块缺锁定依赖；随后使用隔离venv及已授权的回环测试环境重跑。最终结果见PR/CI。
- 本次不改后端、不启动新公网服务、不合并；真实Matrix完整组合由同一提交CI执行。

- 首提交128814f的push前端CI成功、PR前端CI一项新测试失败：测试在子文档heading出现后立即断言父侧栏metadata，未等待onMeta effect传播。修正为等待可见标题更新，不放宽功能断言或性能预算。该失败并非序列化性能或字节语料问题。
- 最终本地隔离环境Python78项通过；源码模块未因测试等待修正而改变。
