# 实现与验证

- client_server代理8项测试通过，write/read-with-content在/send前拒绝，普通metadata read仍可发送。
- 旧HTML真实loopback HTTP（Matrix stub、worker禁用）3项通过：超过旧6000字符限制的UTF8正文直接保存、同表单重试一个版本；冲突/撤权/超限保留转义正文和UUID，错误CSRF不写Git或Matrix。
- 独立真实Synapse项目8048/9110、旧HTML预览8828：9068 UTF8字节正文保存与同UUID重试通过，只有一个Git版本/一个metadata回执，时间线无唯一合成正文marker。
- 独立只读review发现textarea会吞首个换行；正常编辑页与错误页均增加HTML规范要求的保护换行。真实headless Chrome临时无权限上下文检查正常页与409错误页DOM值均保留前导两个换行及原UUID；不用只检查HTML源码代替解析。
- 另一个同轮headless验收针对真实React预览8826：实际下载未保存中文Markdown，下载前Git不变，关闭页面后恢复本地草稿，随后无worker保存的Git正文与下载字节一致，properties/H1单一标题与历史通过。无用户浏览器profile/扩展、GUI权限或剪贴板访问，物理IME/拖拽仍未验。
- 未移除外部旧Matrix任务兼容、未重写消息/提交历史，不宣称所有外部客户端都不能发送正文。最终完整CI、review整改复核及合入后main CI另验。

- 本地完整Python 139项通过（119.023秒）。旧head 67cf489的CI中Python与前端通过，真实Matrix在scoped API旧fixture被平台代理正确拒绝400。保留失败记录39372886100/39372915677；fixture先断言代理拒绝，再仅以独立旧外部客户端向Synapse发送兼容任务，未放宽产品代理。修复后的scoped API和structured-result真实Synapse smoke分别通过，只读复核无阻断项；新head CI另验。
