# 跨平台本地优先 TTS Plan

## Approach

- 建立统一 `TTSBackend` Interface，材料库只依赖“为原句文本生成一个本地音频文件”的领域能力，不依赖具体朗读引擎。
- 默认后端使用 Sherpa ONNX Kokoro 本地模型；其他后端使用 lazy import 和 optional extras，缺依赖时给出可恢复的配置错误。
- 从项目根目录 `.env` 加载配置，进程环境变量优先；所有新变量使用 `READ_ALONG_TTS_` 前缀。
- 缓存指纹从“归一化后的 TTS 输入”改为“原始句子文本 + 朗读引擎身份 + 模型/声音/格式关键配置”。
- 音频缓存保留后端原生格式，当前支持 `wav` 与 `mp3`；API 返回真实 media type，前端播放 URL 不变。

## Decisions

- 默认朗读引擎是 `sherpa_onnx_tts`，默认模型 profile 是 Kokoro Chinese+English `v1_1` int8。
- `sherpa-onnx`、`soundfile` 和 `mutagen` 作为基础依赖；项目根目录 `.env` 使用内置解析器读取，非默认后端依赖放入 optional extras。
- 句子文本原文直送朗读引擎，不做标点、emoji、括号或特殊字符清理。
- 在线后端遵循“配置即同意”：配置在线后端即表示允许把句子原文发送给该后端。
- `read-along tts download-model kokoro` 下载模型到 `READ_ALONG_HOME/models/tts`，默认只打印 `.env` 片段，不自动修改本地配置。
- 旧 macOS `say` 缓存不作为当前引擎缓存复用；切换到新指纹后按需重新生成。

## API

- 公开音频 URL 保持 `/api/materials/{material_id}/sentences/{sentence_id}/audio`。
- 音频响应的 `Content-Type` 根据缓存文件格式返回 `audio/wav` 或 `audio/mpeg`。
- `X-Read-Along-Audio-Duration-Seconds` 继续返回当前缓存音频时长。
- 阅读材料详情中的内部 `audio_path` 仍不对前端公开。

## Verification

- 后端测试覆盖配置加载、默认后端、lazy import 缺依赖、适配器参数映射、原文直送、缓存指纹、`wav/mp3` 时长读取、API media type 和模型下载命令。
- 前端测试确认音频 URL 与播放流程不需要感知缓存格式。
- 文档检查确认 README、`.env.example`、CONTEXT.md、ADR 与 Topic 边界不冲突。
- 运行 `make check`。
