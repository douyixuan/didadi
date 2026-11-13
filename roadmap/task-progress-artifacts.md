# 已知任务进度与产物

## 需求与验收

原技术V0.1要求runtime自报进度、结果产物回Thread与持久任务；不能把收件回执/heartbeat当执行进度。

复用a4cc1a00/0847411→46d07799→1f3c7b2，不新造运行环境。今晚实际自验已知请求→自报说明→终态→固定版本产物查看失败Retry→原生下载→合成拒绝反馈。合成任务浏览器证据准确来源为c58d3a1，不能自动冒称最终b7f8b28的真实流程通过；最终组合的任务送验仍待。完成定义包括未知进度明确显示、旧lease/乱序重复与终态保护、跨任务拒绝、草稿不替换；真实runtime、真实Git绑定及全历史不能被fake覆盖。

## 今晚执行与证据

沿用原任务与[原计划](../artifact/032-requirements-completion/plan.md)，不重开每日台账。执行者为原任务，独立复审沿用review_progress_candidate；开始下一轮重新核对贡献者与工作树。准确版本、实际通过与未完成逐项见[同一验收记录](../artifact/032-requirements-completion/historical-20261022.md#今晚四目标实际对账)。来源、当前候选、main和真实验收分开，已有结果不算本轮新增。

## 下一步与交付门槛

- 真实外部runtime与授权撤权时序未验
- 仅固定demo.md Git Markdown，不代表通用产物
- 全历史枚举仍需授权分页契约
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
    "status": "pending",
    "version": null,
    "evidence": null
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
    "reference": "../artifact/032-requirements-completion/functional-qa/04-task-artifact.png",
    "status": "partial",
    "version": "b7f8b28dd089de4b4cc2062c33fb9703f9afacc4",
    "visual_evidence": "../artifact/032-requirements-completion/historical-20261022.md#今晚四目标实际对账"
  },
  "reopened": false,
  "id": "task-progress-artifacts",
  "leaves": [
    "长任务管理/任务生命周期/查看任务状态",
    "长任务管理/任务生命周期/Runtime主动进度",
    "长任务管理/任务产物/产物查看下载",
    "长任务管理/任务产物/任务关联产物"
  ],
  "blockers": [
    "真实外部runtime与授权撤权时序未验",
    "仅固定demo.md Git Markdown，不代表通用产物",
    "全历史枚举仍需授权分页契约",
    "业务候选未发布"
  ]
}
```
