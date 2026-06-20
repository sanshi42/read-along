# 阅读进度与朗读位置 Module Tasks

## Task 1: 后端朗读位置 Module

Goal: 从材料库中抽出时间式朗读位置计算，形成可直接测试的 Module Interface。

Depends on: none

Verification: 后端测试覆盖无进度、完成进度、真实时长与估算时长。

Status: Done

## Task 2: 前端恢复锚点集中化

Goal: 让阅读页加载和音频预载共用同一套完成状态恢复语义。

Depends on: none

Verification: 前端测试覆盖已完成进度从第一句恢复、缺失句子回退第一句。

Status: Done

## Task 3: 接入与整体验证

Goal: 材料库和阅读页接入新 Module，保持现有行为不变。

Depends on: Task 1, Task 2

Verification: 运行 `make check`。

Status: Done
