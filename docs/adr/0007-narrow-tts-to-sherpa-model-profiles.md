---
status: accepted
---

# 将朗读引擎收窄为 Sherpa ONNX 与内置模型 profile

Read Along 只保留本地 Sherpa ONNX 作为朗读引擎，并以代码内置且经过验证的模型 profile 作为唯一模型扩展点；这项决策取代 [ADR 0005](0005-default-local-sherpa-tts.md) 中通过配置切换多个本地或在线 TTS 后端的决定。当前只登记 `kokoro-multi-lang-v1_1-int8`，以后支持新模型时必须新增包含下载、校验、文件布局和运行类型的已验证 profile。

这个收窄继续满足本地优先和不向在线 TTS 发送正文的边界，同时删除多后端依赖、适配器及每模型路径配置带来的使用和维护复杂度。代价是任意后端或未登记模型不能再仅靠环境变量接入；所选 profile 缺失时，应用会在启动阶段明确下载并准备它，失败则拒绝启动而不回退。
