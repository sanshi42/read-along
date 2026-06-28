# 默认使用本地 Sherpa ONNX TTS

Read Along 不再以 macOS `say` 作为默认朗读引擎，而是默认使用本地 Sherpa ONNX Kokoro 多语种模型，并通过 `.env` 或环境变量切换到其他 TTS 后端。

这个决定牺牲了 macOS 系统命令的零配置路径，换来跨平台运行、可替换模型、原文直送和更一致的缓存指纹。在线 TTS、Edge TTS、本地 WebUI 和云服务后端仍作为可选后端存在，但默认路径不要求账号、API key 或把阅读材料正文发送到外部服务。
