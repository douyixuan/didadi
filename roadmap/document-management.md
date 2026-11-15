# 多文档管理闭环

## 需求与有效变更

原V0.2要求独立文档、人和Agent编辑、Git唯一Markdown权威；技术V0.1补充稳定ID、按基线原子保存、重命名/移动和历史。用户随后明确完整流程：创建→列表→打开→编辑保存→重命名/移动→历史回看；失败/重试/冲突不能丢草稿或串文档。来源见[原需求核对](../docs/MVP_ACCEPTANCE.md#已恢复的原始功能与代码审计)，执行沿用[原计划](../artifact/032-requirements-completion/plan.md)。稳定ID、Agent任意文档编辑和跨路径历史未因此被排除为非目标。

## 用户流程与验收

| 场景 | 完成定义 | 已有与缺口 |
| --- | --- | --- |
| 创建与打开 | 创建两个命名Markdown，列表可见、各自打开正确内容；重试不重复建文档 | PR52已合main；本轮未重跑实际链路 |
| 编辑与保存 | 不同文档有独立草稿；明确保存到Git，按原base冲突保护；未知结果原操作重试 | main已实现；当前版本实际用户验收待跑 |
| 关闭与恢复 | 编辑后关闭/重开，在正确身份与文档恢复选择和草稿；存储失败能明确导出 | 777986c新增前端选择恢复与失效回退，合成自验通过；命名Git持久化未验 |
| 重命名与移动 | 无覆盖移动、列表与当前路径同步，失败保留原路径/草稿，重复请求幂等 | PR53已合main；缺跨移动前路径的完整历史入口 |
| 历史与冲突 | 查看旧版本不覆盖草稿，按原版本保存冲突明确；重命名前后的历史连续可找 | 当前路径历史已有；完整跨路径历史/稳定ID仍未实现，不能统称待验收 |
| 权限与隔离 | 切房/身份、迟到读取/保存及撤权均不串正文/草稿；无后台凭据进浏览器 | 已有隔离回归；真实身份/撤权时序待验 |
| 手机编辑 | 正文优先、常用工具一行、更多按需；退出/保存位置稳定，IME/草稿安全 | 036eac8基础上c58d3a1修复横屏；合成视觉已自验，真机未验 |

## 今晚执行与结果回链

执行者Didadi原任务；独立复审沿用原审查者。PR41身份/授权设计及Issue12暂停工作不接管。今晚既有候选不重做：49c61bab→1f3c7b2→036eac8→06fd020是兼容叠加链；准确版本与结果在[同一验收记录](../artifact/032-requirements-completion/historical-20261022.md#产品流程接入与候选版本)。

| 顺序 | 今晚具体产物 | 实施/核对结果与下一步 |
| --- | --- | --- |
| 1 多文档完整送验定义 | 本功能入口，逐项区分已合main、候选、缺实现及未验收；移除README第二棵旧roadmap | 已落实；main不是完整用户验收，不勾叶子 |
| 2 手机编辑整合 | 保留命名文件名抢救导出、退出恢复、全部主线浮层；提供可查看布局设计 | 036eac8已本地完成；[布局设计](mobile-editor.svg)是设计稿，实际像素待验 |
| 3 讨论检索恢复 | 同房换身份隐藏旧搜索/Thread并拒绝迟到响应，保留新身份重试 | 06fd020已本地完成；候选发布与真实会话边界分开核对 |
| 4 当前功能下一步 | 跨移动历史必须以稳定ID/路径演进契约贯通，不仅改标题；其余现有能力按上表送验 | 不凭新字段临时自定Git权威ID；先核对原设计与PR41边界，再确定不重叠实现；真实服务/截图权限另核对 |

不是今晚只产流程文档：前两项业务兼容及讨论恢复已在同一任务实做并有离线证据；不能重复计为本轮新功能。本轮流程调整新增的是可重复门禁、产品设计与执行映射，未推这些业务候选。当前文档/离线门禁可独立发布；业务发布需先核实候选完整diff与部署触发，不把一次文档授权扩大为真实服务/身份/线上部署。

## 设计与发布门槛

已实际查看用户提供IMG_1677.png：格式工具占三行，正文空间被挤压；系统浏览器栏及键盘附件条不归网页。目标遵循用户明确的iOS方向：内容层级清楚、触控可点、主次操作稳定，不能只缩小字。设计稿保留现有Web产品形态，不冒充原生iOS App或Apple合规认证。

新增自验：在新明确合成QA许可内已看手机/桌面截图并发现、修复横屏回桌面布局缺陷。实现c58d3a1，[横屏前后与8项自验](../artifact/032-requirements-completion/historical-20261022.md#合成手机横屏布局修复2026-10-22)有准确截图；失败重试与页面重载保留内容通过。仅demo.md合成适配，不是完整多文档/真实Git或iOS真机验收。

设计→代码→视觉验收是正式三道门槛：[设计稿](mobile-editor.svg)供查阅；实现为036eac8；未获准的浏览器/设备检查不运行。实际验收必须覆盖窄屏、键盘显隐、更多面板、滚动、长文/代码、横竖屏、中文IME与桌面回归。源码/DOM/viewport合成事件不是视觉通过。

发布前需完整scope审核、准确SHA CI、识别实际安装/线上版本、回滚与草稿兼容。当前没有安装或线上候选版本证据；回退代码不能删Git提交、原消息或用户草稿。未完成门槛写在本页，实际执行证据仍回原验收记录；缺陷重新打开本页与根叶子，不另建平行清单。

今晚补充实际自验：[文档路径结果](../artifact/032-requirements-completion/historical-20261022.md#文档管理完整路径合成自验)。6项合成UI观察通过；内存fixture重载不能证明命名仓库持久化，移动前跨路径历史仍未实现，不勾叶子。手机导航拆到同目录mobile-navigation.md，避免重复拥有同一根叶子。

新增前端缺口已修：[选择恢复自验](../artifact/032-requirements-completion/historical-20261022.md#文档选择恢复前端修复)。列表确认后恢复身份/文档房间内选择；失效回退保留隔离草稿。跨路径历史和真实后端持久化仍未通过。

## 检查元数据

```product-feature
{
  "id": "document-management",
  "leaves": [
    "文档管理/多文档编辑/独立创建文档",
    "文档管理/多文档编辑/文档列表打开",
    "文档管理/多文档编辑/人工编辑保存",
    "文档管理/多文档编辑/文档重命名移动",
    "文档管理/多文档编辑/历史版本回看",
    "文档管理/多文档编辑/草稿冲突保护"
  ],
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
    "version": "777986c37d9d2e07618c9a0ad39e791144ff98eb",
    "evidence": "../artifact/032-requirements-completion/historical-20261022.md#文档选择恢复前端修复"
  },
  "acceptance": {
    "status": "blocked",
    "version": null,
    "evidence": null,
    "environment": null,
    "data": null,
    "actor": null,
    "date": null,
    "steps": null,
    "observed": null
  },
  "delivery": {
    "status": "not-released",
    "version": null,
    "evidence": null
  },
  "design": {
    "required": true,
    "reference": "../artifact/032-requirements-completion/navigation-qa/mobile-05-edit.png",
    "status": "partial",
    "version": "b7f8b28dd089de4b4cc2062c33fb9703f9afacc4",
    "visual_evidence": "../artifact/032-requirements-completion/historical-20261022.md#合成手机横屏布局修复2026-10-22"
  },
  "blockers": [
    "跨移动路径历史和稳定ID仍缺实现",
    "当前完整用户流程未实际验收",
    "手机键盘/选区/滚动与桌面视觉回归未验",
    "业务候选未发布，实际安装/线上版本未知"
  ],
  "reopened": false
}
```
