# 未读消息提醒

## 需求与有效变更

面向开发者与Agent构建者：用户在房间列表发现需要处理的讨论，进入房间阅读后显式标记已读；失败可恢复，不丢消息或草稿。原技术V0.1包含未读；后续明确要求数量、显式标记、失败重试、切房和迟到隔离，见[原始功能来源](../docs/MVP_ACCEPTANCE.md#已恢复的原始功能与代码审计)。全部根树目标仍有效，本次只选择该完整功能先推进，不更改产品范围。

数量采用Matrix原生notification_count，遵循通知规则，不声称所有未读消息条数。没有自行维护第二套权威计数；不做进入房间自动已读。标记当前身份实际加载的房间时间线边界，历史Thread需返回全部消息；后来新消息可能仍未读。

## 用户流程与验收

| 场景 | 执行与可观察结果 | 当前门槛 |
| --- | --- | --- |
| 发现与阅读 | 隔离身份向允许房间发消息；列表显示原生数量；进入讨论看到正确内容和数量语义 | 候选离线覆盖；实际Matrix未跑 |
| 明确标记 | 点击标记已加载消息；服务确认后重新读原生数量；不乐观伪造零 | 实际private read marker支持与计数规则待验 |
| 失败与重试 | 中断计数或标记请求；显示失败；重试原标记边界，后来消息不被意外吞掉 | fixture覆盖；真实传输待验 |
| 上下文隔离 | 请求中切房、换身份、同adapter换用户，再返回；旧回执不修改新界面，未载入新时间线时禁标 | 离线覆盖；真实会话切换待验 |
| 文档与成员兼容 | 命名Notes.md留草稿、讨论留未发送消息；查看成员、切房、标记后返回 | 候选联合回归通过；真实流程待验 |
| 多设备回执 | 同一隔离身份两台设备观察标记与新消息；记录设备及服务版本 | 未运行；不能用单设备fixture代替 |
| 权限变化 | 读取/标记期间撤销房间访问；拒绝访问、保留草稿且不回退公共回执 | 离线代理拒绝覆盖；真实撤权时序待验 |

## 执行与贡献者

沿用[原执行计划](../artifact/032-requirements-completion/plan.md)，不取消今天八点及后续有效计划。当前执行者为Didadi原任务，独立复审由review_progress_candidate完成；PR41身份设计与暂停Issue12不在本范围。开始下一轮必须刷新贡献者/PR/工作树，不能把此认领当永久锁。

今天既有结果：3080c8f为旧未读候选；49c61bab基于main 1f371893完成房间类型/成员/命名草稿整合；其上1f3c7b2任务、036eac8移动布局、06fd020讨论身份隔离均为未发布叠加候选。不是新提交都算新增功能。准确SHA、离线测试和未运行项见[原验收记录](../artifact/032-requirements-completion/validation.md#产品流程接入与候选版本)。

剩余顺序：先审查选定业务候选与当前main差异并取得对应发布/真实验收范围；再用隔离数据运行上表实际流程；修缺陷并复审；按允许目标发布并核对main/实际运行版本；最后回写证据并勾根叶子。任一部分获准不自动授权认证、截图或部署。后续已获准的合成前端自验见下方回链；真实服务限制保持。

## 验证与发布

main为1f371893，未读候选49c61bab；当前组合候选06fd020。设备安装版本未知，线上页面部署SHA未知，不能称候选已上线。默认CI仅离线Python守卫和注入前端测试；真实Matrix入口仍需单独明确开启，本轮不开。

此次功能仍是部分验证：既有离线与后续已批准合成前端自验有记录，准确版本见同一验收记录。既有Vercel演示不作为当前候选证据；真实Matrix/多设备回执和业务发布仍未通过。

后续发布前核对基线和数据兼容、准确head CI及main CI；仅发布审核差异，不能推整条旧候选分支夹带其他功能。回滚保留原候选和草稿；本功能不迁移服务数据，代码回退仍须核对客户端/代理接口及用户实际版本。不得删除真实消息/回执模拟回滚。发现漏读、串房、草稿损失或回执错误时，在原验收记录记复现并重开本功能，撤销根勾选后修复重验。

## 检查元数据

```product-feature
{
  "id": "unread-notifications",
  "leaves": ["普通通信/会话管理/未读消息提醒"],
  "owner": "Didadi原任务",
  "sources": ["../docs/MVP_ACCEPTANCE.md#已恢复的原始功能与代码审计"],
  "plan": "../artifact/032-requirements-completion/plan.md",
  "versions": {"main": "1f371893baa0cf504a7c63d8df39170680336e40", "candidate": "777986c37d9d2e07618c9a0ad39e791144ff98eb", "installed": null, "online": null},
  "target": "local",
  "review": {"status": "passed", "version": "49c61babd067359934149e3f6a3d665b222973b7", "evidence": "../artifact/032-requirements-completion/validation.md#产品流程接入与候选版本"},
  "acceptance": {"status": "blocked", "version": null, "evidence": null, "environment": null, "data": null, "actor": null, "date": null, "steps": null, "observed": null},
  "delivery": {"status": "not-released", "version": null, "evidence": null},
  "design": {"required": true, "reference": "mobile-editor.svg", "status": "partial", "version": "49c61babd067359934149e3f6a3d665b222973b7", "visual_evidence": null},
  "blockers": ["业务候选尚未发布", "真实Matrix与隔离身份流程未获本轮许可", "原生计数及private read marker实际支持未验", "多设备回执和撤权时序未验"],
  "reopened": false
}
```
