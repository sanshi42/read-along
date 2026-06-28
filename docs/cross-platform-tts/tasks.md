# 跨平台本地优先 TTS Tasks

## T001: 领域文档和配置入口

- Goal: 建立 Topic 文档、术语、ADR、README 和 `.env.example`，并让应用能从项目根目录 `.env` 读取 TTS 配置。
- Depends on: 无。
- Verification: 配置单测覆盖环境变量优先级、默认 Sherpa Kokoro 和非法输出格式。
- Status: Done

## T002: TTS Interface 与默认 Sherpa 后端

- Goal: 用统一 Interface 替换 `MacOSSayTTS` 直连，并实现 Sherpa ONNX Kokoro 本地后端。
- Depends on: T001。
- Verification: TTS 单测覆盖原文直送、Kokoro 参数、缺模型文件错误和 WAV 落盘。
- Status: Done

## T003: 多后端适配器与依赖策略

- Goal: 迁入 Open-LLM-VTuber 同名 TTS 后端适配器，非默认依赖使用 optional extras 和 lazy import。
- Depends on: T002。
- Verification: 每个 adapter 至少覆盖 factory 创建、缺依赖提示和调用参数映射。
- Status: Done

## T004: 音频缓存与 API 格式

- Goal: 让音频缓存和 API 支持真实输出格式、配置指纹和旧缓存失效。
- Depends on: T002。
- Verification: 材料库和 API 测试覆盖 `wav/mp3`、指纹变化、旧缓存清理、duration header 和 media type。
- Status: Done

## T005: 模型下载 CLI

- Goal: 提供 `read-along tts download-model kokoro` 下载默认本地模型并输出 `.env` 片段。
- Depends on: T001。
- Verification: CLI 测试覆盖下载目录、重复下载、失败回滚和配置片段输出。
- Status: Done

## T006: Topic 验收

- Goal: 完成跨平台 TTS 主题的整体验证并更新任务状态。
- Depends on: T003, T004, T005。
- Verification: `make check` 通过。
- Status: Done
