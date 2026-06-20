# 时间式朗读进度与跨材料导航 Tasks

## Task 1: 后端时长、进度和窄迁移

Goal: 增加真实音频时长、句内进度、上一版 schema 窄迁移和对应 API 输出。

Depends on: None

Verification: 后端相关 pytest 覆盖 schema 创建、窄迁移、异常旧库拒绝、音频时长、响应头、offset 校验、材料导航和书架时间进度。

Status: Done

## Task 2: 前端时间轴和进度保存

Goal: 阅读页支持混合时间轴、拖动 seek、快退 15 秒、快进 30 秒、节流保存句内位置。

Depends on: Task 1

Verification: web 单元测试覆盖时间轴估算/真实修正、seek 映射和 API 时长回传；浏览器验证主要交互。

Status: Done

## Task 3: 跨材料导航和篇末继续

Goal: 阅读页播放器左右按钮切换相邻材料，篇末在播放器内提示继续下一篇，并继承播放意图。

Depends on: Task 1, Task 2

Verification: web 单元测试覆盖相邻材料按钮状态和完成提示；浏览器验证跨材料切换。

Status: Done

## Task 4: 完整验证

Goal: 确认后端、前端和文档一致，Topic 达到完成状态。

Depends on: Task 1, Task 2, Task 3

Verification: `make check` 通过；浏览器验证完成时间轴拖动、快退/快进、跨材料切换、篇末继续提示、书架时间进度和移动端播放器布局。应用内浏览器无法实际播放音频，播放触发路径已验证到应用的重试状态。

Status: Done
