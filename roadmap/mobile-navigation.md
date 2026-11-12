# 手机导航与编辑

## 需求与验收

用户原图与后续反馈要求整个手机App有清晰层级、iOS方向、触控/渐进披露；不改变Web产品形态，不称Apple认证。

沿原今晚计划复用11d9391/036eac8，c58d3a1修横屏，b7f8b28补完整手机导航层级、实际44px目标及菜单关闭焦点。完整阅读→讨论→More检索→Thread→编辑→退出返回已自验7项并有9张最终图，桌面/横屏单列。主次操作/密度/排版/错误恢复按截图核实，不能只测DOM。

## 今晚执行与证据

沿用原任务与[原计划](../artifact/032-requirements-completion/plan.md)，不重开每日台账。执行者为原任务，独立复审沿用review_progress_candidate；开始下一轮重新核对贡献者与工作树。准确版本、实际通过与未完成逐项见[同一验收记录](../artifact/032-requirements-completion/validation.md#今晚四目标实际对账)。来源、当前候选、main和真实验收分开，已有结果不算本轮新增。

## 下一步与交付门槛

- 实际iOS键盘/物理IME与触控选区未验
- 尚非全部App页面设计验收
- 真实后端与业务发布未验

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
    "evidence": "../artifact/032-requirements-completion/validation.md#今晚四目标实际对账"
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
    "reference": "../artifact/032-requirements-completion/navigation-qa/mobile-01-read.png",
    "status": "partial",
    "version": "b7f8b28dd089de4b4cc2062c33fb9703f9afacc4",
    "visual_evidence": "../artifact/032-requirements-completion/validation.md#今晚四目标实际对账"
  },
  "reopened": false,
  "id": "mobile-navigation",
  "leaves": [
    "部署生态/自托管使用/Web移动适配"
  ],
  "blockers": [
    "实际iOS键盘/物理IME与触控选区未验",
    "尚非全部App页面设计验收",
    "真实后端与业务发布未验"
  ]
}
```
