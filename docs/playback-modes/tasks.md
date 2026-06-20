# 播放模式与列表续播 Tasks

## Task 1: 后端导航扩展

Goal: 在材料详情导航中提供 first/last/previous/next。

Depends on: none

Verification: 后端测试覆盖单篇、第一篇、中间篇和最后篇导航。

Status: Done

## Task 2: 前端播放模式偏好

Goal: 增加播放模式类型、localStorage 读取保存和无效值回退。

Depends on: none

Verification: 前端单测覆盖默认值、保存和无效值回退。

Status: Done

## Task 3: 播放模式决策 Module

Goal: 集中计算自然篇末和手动上一篇/下一篇的目标。

Depends on: Task 1, Task 2

Verification: 前端单测覆盖三种播放模式、边界和单篇列表。

Status: Done

## Task 4: 阅读页接入和 UI

Goal: 阅读页播放器接入播放模式菜单和自动续播行为。

Depends on: Task 3

Verification: 前端测试和手动交互验证覆盖计划中的主要行为。

Status: Done

## Task 5: 领域术语和整体验证

Goal: 补充 CONTEXT.md 术语并完成 Topic 级验证。

Depends on: Task 4

Verification: 运行 `make check`。

Status: Done
