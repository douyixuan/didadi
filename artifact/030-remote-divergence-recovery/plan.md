# 普通远端分叉的安全恢复

实施中。授权来源：父任务明确继续上一轮建议的Git恢复切片，允许实现、测试、独立review、draft和原Library更新；禁止强推、共享历史重写、真实远端权限变更、GUI/剪贴板及合入绕过。本执行者负责；ADR41独立7067385不改，Issue12性能暂停。基线4a296ac/PR46，mainf0ab205；无更新重叠PR，独立worktree/branch。

按docs/GIT_DOCUMENTS.md已有约束：普通分叉保留localcommit/outbox，操作员显式协调，无自动merge/reset/forcepush。本轮不放宽这些约束。修复分叉导致重启无法启动及API泛化错误：新增metadata-only typed remote_diverged，保留服务可诊断，读latest/新写仍阻止；固定版本仍按Git读取，未发布回执仍不发。删除/重写远端继续保守拒绝，不当普通分叉处理。

客户端显示保留草稿/两边历史、操作员协调及原请求重试提示，显示有界SHA无路径/正文。503保留原operation/body/base并冻结编辑；不变成409自动Load latest，不清空或自动采用remote。失败初始化也可导出本地恢复草稿，restore需成功加载Git。恢复完成后重试同operation不产生第二提交或回执，读取合并后latest。

交付已验证操作员runbook：暂停自己负责的写入进程并备份整个仓库，在新副本merge明确remoteSHA，审查/人工解决冲突，普通非force push到本地service main（必须fastforward），服务再普通push到本地bare远端。测试只用临时bare夹具；双亲merge使双方提交可达，原outbox操作保留；竞争更新必须拒绝，绝不重写已知remote历史。不增加网页恢复写接口/凭据/权限，也不自动修改任何真实数据。

验收：先复现旧行为；Git层分叉/重启/固定读/无副作用/回执保留、真实HTTP+Matrix503结构/无提前回执/手工合并后同请求一次提交回执/重启、客户端保稿/导出/准确重试/失败初始化记录可用。独立review，完整Python/frontend/build，精确pushheadCI。新隔离本地预览8816（Matrix8038/Gateway9076/WS9077/Doc9078），旧服务与数据不变，GUI不验。额外8817仅展示独立合成bare分叉诊断，真实HTTP503和资产匹配核验，不接入用户文档或自动恢复。Library原身份版本8/9继续受guard更新；最终实现/自动化验收不代表main合入或生产部署。
