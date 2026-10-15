# 讨论 / 文档 / commit 双向引用

原设计确定闭环：讨论、文档、Commit关联。当前只有折叠SHA文本，无法从回执打开版本，或从版本回到讨论。

- 只将真实Agent identity + task metadata + thread关系的固定格式回执识别为版本引用，限定demo.md和40位Git SHA。synthetic session显式用browser snapshot ID，不冒充Git。
- 回执Open document version调用现有已授权history read，显示固定快照，保留未保存草稿，不写Git。
- 文档View version discussion只在加载timeline存在该版本回执时可用，回到原thread；缺失回执不伪造关联。
- task activity不再无限轮询failed任务。
- 回归：合法回执/人类伪装/缺task metadata/非法commit、打开历史保留草稿、版本返回对应thread。独立review+CI+实际loopback浏览器验收。

范围：单一授权demo.md。不是任意仓库链接，不实现#14直接文档API或生产grants。

独立评审发现历史读取失败后的Retry错误复用save路径，可能误保存draft。已区分readRetry，重试固定commit读取，回归断言api.send零调用。新入口还在busy/reading/composing时禁用；空仓库没有commit时不伪造讨论关联。
