# 完整用户功能名称

复制为 `roadmap/<feature-id>.md`，替换所有占位并删除本提示。根ROADMAP保留短叶子；本文件不再加功能完成复选框。

## 需求与有效变更

目标用户、场景、问题与完整结果。链接原文/设计；注明有效变更、被替代条目与未恢复原文。不能从代码推需求。

## 用户流程与验收

按“入口→操作→可见结果→退出/恢复”写主流程。逐项写错误/重试、草稿与数据保护、重复/迟到/乱序、权限变化及适用设备；每条给可执行步骤与预期。不适用项给理由。

## 产品设计

对于有界面的功能：实际查看被允许的截图或当前界面，记录信息层级、主次操作、导航、布局密度、排版间距、反馈状态。链接可查看设计产物，沿用平台交互习惯，不机械套外壳。设计→实现→真实视觉验收分别记录；无截图权限不能假称已验。

## 执行与贡献者

沿用已有计划链接；指定执行者/独立审查者、认领边界、准确基线和复用候选。当日先完成哪个完整结果、剩余步骤、对应检查和依赖；不把旧成果当新增，不虚构工时。

## 验证与发布

链接既有证据位置，分底层验证、实际用户流程、审查、准确SHA的CI、交付后检查。记录未运行项、具体权限/产品依赖、允许的下一步和完成定义。写发布范围、版本识别、数据兼容与回滚。缺陷回到本文件及原计划，撤销根叶子勾选。

## 检查元数据

以下JSON和正文同属一份功能定义，不是第二张台账。`evidence` 指向已有记录；通过项必须有准确版本。实际用户流程通过时kind填actual-user-flow。真实流程通过项还需环境、数据、执行者、时间、步骤和观察。发布与实际验收不同，未发布保持not-released。历史CI不得冒充候选CI。

```product-feature
{
  "id": "feature-id",
  "leaves": ["模块/完整功能/叶子"],
  "owner": "执行者",
  "sources": ["../docs/原需求.md"],
  "plan": "../artifact/现有计划/plan.md",
  "versions": {"main": null, "candidate": null, "installed": null, "online": null},
  "target": "local",
  "review": {"status": "pending", "version": null, "evidence": null},
  "acceptance": {"status": "blocked", "kind": null, "version": null, "evidence": null, "environment": null, "data": null, "actor": null, "date": null, "steps": null, "observed": null},
  "delivery": {"status": "not-released", "version": null, "evidence": null},
  "design": {"required": true, "reference": null, "status": "pending", "version": null, "visual_evidence": null},
  "blockers": ["具体未完成条件"],
  "reopened": false
}
```
