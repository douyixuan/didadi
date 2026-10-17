# 普通分叉恢复验证

基线4a296ac/PR46，mainf0ab205；没有新重叠PR，ADR41独立7067385不改，Issue12性能暂停。checkout无AGENTS.md/.agents/skills。本执行者独立worktree负责此切片，parent负责小时汇报/下一轮，无新automation。

旧代码回归：远端分叉仅publication_pending，新增actionable测试失败（/tmp/didadi-remote-before.log）。现分叉类型含local/remote/base SHA，不含路径/正文；constructor只容忍该类以保留诊断/固定版本读。latest读写和未发布回执仍阻止。已知重写/删除继续原拒绝，无自动merge或权限变化。

最终本地完整122Python通过84.527秒，115frontend/corpus通过，build通过；新恢复5、App54通过。独立恢复5/App54通过，最终runbook/脚本静态复核无阻塞。覆盖普通分叉/重启/固定读、原提交/outbox、操作员双亲merge后同save只一个原commit/receipt、重叠merge失败sharedrefs不变、review期间remoteadvance再次blocked、已知rewind仍拒绝。客户端503保留UUID/body/base、冻结编辑但可导出；恢复后准确重试同请求；初始化失败仍可导出原browser草稿，restore不放开。

真实协议：独立didadi-remote Compose Matrix8038/Gateway9076及新合成身份。scripts.remote_recovery_smoke使用临时bare远端/服务repo和operatorclone，真实HTTP503metadata/latestblocked/fixedread/reopen、无提前Matrixreceipt；普通merge两亲核对，nonforcepush到service，服务normalpublish，原save两次返回同原commit，latest双方内容正确、两历史可达、outbox清空、唯一metadata回执且正文marker不在timeline。该脚本已接入CI。并非任意冲突解决/网络远端/凭据/掉电/损坏证明。

新8816预览使用独立WS9077/Doc9078/Git；真实源码报告/拒绝及matrix-js-sdk保存/历史/冲突、HTTP资产匹配通过。额外8817仅独立合成分叉fixture，latest预期503带同样typedmetadata、页面资产匹配；留作诊断演示，非故障生产数据。没有浏览器/GUI/剪贴板/历史/搜索；nativeGUI不验。依赖复用既有B开发环境，不声称重新冷安装；df4冷安装/保留卷基线独立。

操作员runbook只在新clone审查并合并，暂停自己负责writer、备份全bare含receiptrefs、导出草稿、核对两tip和两parent、普通pushservice，恢复由原服务检查remoteseen和普通发布完成。冲突/无共同base/竞争新tip均暂停复核，不给网页提交shell/仓库/merge权限。测试只触碰隔离本地bare夹具；真实远端授权、权限、强推和共享历史重写均未执行。

PR/最终head push CI/原Library交付状态在PR和验收说明更新，不将本地通过当云端已通过。未合入、未ready或公网部署，所有旧预览/用户数据保留。下一候选需沿原规划再界定，生产Agent grants/远端网络Git及安全GUI仍独立未验。
