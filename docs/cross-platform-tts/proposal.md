---
status: done
priority: P0
created: 2026-06-23
---

# 跨平台本地优先 TTS Proposal

## Goal

把 Read Along 的朗读音频生成从 macOS `say` 迁移到跨平台、多后端的朗读引擎体系。

目标完成后，默认朗读引擎使用本地 Sherpa ONNX Kokoro 多语种模型；用户可以通过项目根目录 `.env` 或环境变量选择其他 Open-LLM-VTuber 同名 TTS 后端；句子文本原文进入朗读引擎，不再为适配 macOS `say` 清理标点或特殊字符。

## Boundary

### In

- 默认本地 Sherpa ONNX Kokoro 朗读模型和模型下载 CLI。
- 通过 `.env` 与 `READ_ALONG_TTS_*` 环境变量配置朗读引擎、模型、声音、输出格式和后端参数。
- Open-LLM-VTuber 当前 TTS 后端的同名适配器与按需依赖策略。
- 原文直送 TTS 输入、朗读引擎配置指纹、真实音频格式缓存和 API media type。
- 移除 macOS `say` 默认路径和 fallback。
- README、`.env.example`、CONTEXT.md 和 ADR。

### Out

- Web 设置页、账号密钥管理 UI 或在线后端二次确认弹窗。
- 数据库 schema 迁移。
- OCR、导入解析、正文切句和阅读进度语义变更。
- 自动提交、推送或发布。
