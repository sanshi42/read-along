# 朗读可靠性修复 Tasks

## Task 1: 修复成对标点导致的 TTS 正文跳过

Goal: TTS 生成前统一归一化正文包裹标点，避免 macOS `say` 跳过 `“…”`、`《…》` 等标点内正文。

Depends on: None

Verification: 运行覆盖 TTS 输入归一化的后端测试。

Status: Done

## Task 2: 减少连续朗读句间接缝

Goal: 阅读页在播放当前句时提前准备下一句浏览器音频对象，连续朗读时尽量复用已加载音频。

Depends on: Task 1

Verification: 运行前端音频衔接测试；浏览器中确认页面和音频预取链路正常，真实播放因 in-app Browser 拒绝媒体播放而需人工复核。

Status: Done
