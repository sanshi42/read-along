---
status: active
priority: P1
created: 2026-07-02
---

# 本地私有声音克隆 TTS Proposal

## Goal

在 M4、16GB MacBook Pro 上对 CosyVoice3 与 Qwen3-TTS 进行同机声音克隆评测，并只在存在合格胜者时，为 Read Along 提供稳定、私有、可缓存的本地声音克隆朗读能力。

目标完成后，用户可以显式选择 `local_clone_tts` 朗读引擎，通过仅监听 localhost 的独立 sidecar 使用一个全局参考声音；Read Along 在 sidecar 不可用时仍能复用匹配缓存，但不会在朗读途中自动切换声音。

## Boundary

### In

- 在独立临时环境中评测 `Fun-CosyVoice3-0.5B-2512` 与 `Qwen3-TTS-12Hz-0.6B` Base。
- 使用同一参考声音、准确逐字稿、测试语料和输出格式比较自然度、音色相似度、错读率、速度、启动时间、稳定性和峰值内存。
- 用 SenseVoice 回转录、自动性能测量和匿名人工 A/B 盲测形成胜出结论。
- 若存在合格胜者，为该模型实现仅绑定 `127.0.0.1` 的声音克隆 sidecar。
- 新增显式 `local_clone_tts` 后端、全局单声音档案、配置指纹、缓存复用和可恢复错误处理。
- 保留 Kokoro 作为显式轻量后端；切换后端只影响后续请求，不在材料朗读途中自动降级。
- 记录模型实测结论、运行方式、隐私边界和整体验证证据。

### Out

- TTS 设置 UI、多声音档案、声音管理或在线同步。
- 把 Edge TTS 或其他云服务作为默认路径或自动降级路径。
- 同时常驻或自动调度多个重型 TTS 模型。
- 将模型权重、参考音频、课程音频、生成样本或一次性评测产物提交到 Git。
- 将 CosyVoice3、Qwen3-TTS 或一次性评测工具的依赖加入 Read Along 主应用依赖。
- 在两种候选模型均不合格时强行集成其中之一。
