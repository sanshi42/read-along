# 朗读会话 Module Tasks

## Task 1: 朗读会话 Interface 与生命周期

Goal: 建立可订阅 snapshot、接收命令并可销毁的非 React 朗读会话 Module，集中初始恢复、时间线和音频预取生命周期。

Depends on: none

Verification: 前端测试覆盖初始 Reading Progress 恢复、首轮预取、snapshot 通知和销毁后丢弃异步结果。

Status: Done

## Task 2: 播放与 Reading Progress 协调

Goal: 将播放、暂停、选句、时间跳转、倍速和 Reading Progress 节流与失败重试移入朗读会话。

Depends on: Task 1

Verification: 前端测试覆盖播放与暂停、切换当前句、时间跳转、倍速同步、进度节流、失败阻塞和手动重试。

Status: Done

## Task 3: 句末续播与音频修复

Goal: 将自然句末续播、播放模式、跨阅读材料导航和当前材料音频修复移入朗读会话。

Depends on: Task 2

Verification: 前端测试覆盖下一句续播、朗读完成、三种播放模式、跨材料导航、音频修复和恢复播放。

Status: Done

## Task 4: ReaderPage 接入

Goal: 让 `ReaderPage` 通过朗读会话 Interface 驱动朗读，删除已被吸收的协调状态、refs 和回调，同时保留 DOM 与视觉行为。

Depends on: Task 3

Verification: 前端测试与构建通过；浏览器验证材料加载、播放与暂停、选句、时间跳转、倍速和跨材料续播。

Status: Done

## Task 5: Topic 级验证

Goal: 完成全量自动检查和文档一致性检查，确认重构没有改变朗读行为或未提交的 TTS 变更。

Depends on: Task 4

Verification: 运行 `make check`；检查 `CONTEXT.md`、Proposal、Plan 与 Tasks 内容一致。

Status: Done
