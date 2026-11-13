# 讨论检索闭环

## 需求与验收

原V0.2正文搜索、技术V0.1历史/Thread及用户后续要求查结果回原讨论；不是导航标题过滤。

先在原计划复用main55/56与06fd020身份隔离，再走搜索→失败Retry→结果→完整话题→返回；合成6项流程自验已有证据，不重做旧功能。完整验收含空结果、分页去重、原游标重试、切房/换人迟到隔离、返回上下文和草稿保护。未读计数与标记独立见unread-notifications.md。

## 今晚执行与证据

沿用原任务与[原计划](../artifact/032-requirements-completion/plan.md)，不重开每日台账。执行者为原任务，独立复审沿用review_progress_candidate；开始下一轮重新核对贡献者与工作树。准确版本、实际通过与未完成逐项见[同一验收记录](../artifact/032-requirements-completion/historical-20261022.md#今晚四目标实际对账)。来源、当前候选、main和真实验收分开，已有结果不算本轮新增。

## 下一步与交付门槛

- 真实Matrix搜索与历史分页上下文未在当前候选验收
- 真实会话切换/撤权时序未验
- 业务候选未发布

发布/真实服务许可未解决前，继续独立合成检查；不得以假环境凑真实通过。获准后审核完整diff、准确head/main CI、识别实际运行版本并自验后再交用户最终核验。回滚保留既有消息/Git/草稿，不把撤回代码当数据回滚。缺陷回原功能与记录，撤销根勾选后修复复验，PR41/Issue12保持边界。

## 检查元数据

```product-feature
{
  "owner": "Didadi原任务",
  "sources": [
    "../docs/MVP_ACCEPTANCE.md#已恢复的原始功能与代码审计"
  ],
  "plan": "../artifact/032-requirements-completion/plan.md",
  "versions": {
    "main": "1f371893baa0cf504a7c63d8df39170680336e40",
    "candidate": "777986c37d9d2e07618c9a0ad39e791144ff98eb",
    "installed": null,
    "online": null
  },
  "target": "local",
  "review": {
    "status": "passed",
    "version": "b7f8b28dd089de4b4cc2062c33fb9703f9afacc4",
    "evidence": "../artifact/032-requirements-completion/historical-20261022.md#今晚四目标实际对账"
  },
  "acceptance": {
    "status": "blocked",
    "version": null,
    "evidence": null
  },
  "delivery": {
    "status": "not-released",
    "version": null,
    "evidence": null
  },
  "design": {
    "required": true,
    "reference": "../artifact/032-requirements-completion/navigation-qa/mobile-03-search.png",
    "status": "partial",
    "version": "b7f8b28dd089de4b4cc2062c33fb9703f9afacc4",
    "visual_evidence": "../artifact/032-requirements-completion/historical-20261022.md#今晚四目标实际对账"
  },
  "reopened": false,
  "id": "discussion-search",
  "leaves": [
    "普通通信/讨论检索/话题完整回复",
    "普通通信/讨论检索/消息正文搜索",
    "普通通信/讨论检索/搜索返回上下文"
  ],
  "blockers": [
    "真实Matrix搜索与历史分页上下文未在当前候选验收",
    "真实会话切换/撤权时序未验",
    "业务候选未发布"
  ]
}
```
