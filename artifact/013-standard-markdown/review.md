# 独立评审

Reviewer `/root/review_didadi` 初次复现真实Crepe Undo无法恢复旧marker字节：尾部合成输入段令等价比较失败。已修复为仅旧marker文档比较时忽略无origin的合成尾部空段，新增真实view输入→undo回归。最终独立探针和针对性测试通过，无剩余阻塞。

最终本地前端50 tests PASS，33文件/1586块编辑逐字节语料PASS，production build PASS。导出当前草稿/历史完整原文不触发Git写入。native浏览器下载/真实Git保存另验，不由组件测试冒充。
