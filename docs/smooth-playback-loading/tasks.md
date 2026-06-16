# 朗读加载流畅性 Tasks

## T001: 建立音频预取窗口模型

- Goal: 用可测试的纯函数表达预取锚点和窗口选择规则。
- Depends on: 无。
- Verification: 前端单元测试覆盖无进度、未完成进度、已完成进度和窗口推进。
- Status: Done

## T002: 实现阅读页音频准备队列

- Goal: 阅读页打开、选句和播放推进时串行预取当前句与后 4 句，并复用同句 in-flight 请求。
- Depends on: T001。
- Verification: 前端单元测试覆盖后台失败自动重试一次、失败不立刻打断未来句、前台重试重新请求。
- Status: Done

## T003: 接入播放器前台准备与错误恢复

- Goal: 播放当前句前先确保音频已准备；准备失败时停在当前句并在播放器提供重试。
- Depends on: T002。
- Verification: 前端测试和浏览器验证覆盖连续朗读衔接、当前句失败提示和重试。
- Status: Done

## T004: 完成 Topic 验收

- Goal: 验证后端 API、前端构建和主要朗读体验没有回归。
- Depends on: T003。
- Verification: `make check` 通过，并完成浏览器主要朗读流程验证。
- Status: Done
