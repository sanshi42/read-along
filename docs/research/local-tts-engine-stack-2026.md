# 本地中文朗读引擎技术栈调研（2026-08）

> 调研日期：2026-08-30  
> 目标：解释“当前最佳实践的朗读引擎”到底由哪些层组成，并为 Apple Silicon M4、16 GB、句子级中文朗读的 Read Along 选择合理技术栈。  
> 证据：官方文档、官方仓库、论文与模型卡；具体音质候选另见 [开源中文 TTS 本地替代方案调研](open-source-chinese-tts-2026.md)。

## 结论先行

“最佳实践的朗读引擎”不是一个与 PyTorch、TensorFlow 并列的单一产品名，而是一条分层流水线：

```text
原始文章
  → 文本规范化（TN）
  → 分词 / G2P / 发音覆盖
  → TTS 模型家族
  → 模型表示与权重
  → 本地推理运行时
  → 进程内或 localhost sidecar
  → WAV 验证与句子级内容寻址缓存
  → 浏览器播放
```

它和常见软件栈的类比更接近：

| TTS 层 | 类比 | 例子 | 回答的问题 |
| --- | --- | --- | --- |
| 训练框架 | 编程语言/编译器工具链 | PyTorch、JAX、TensorFlow | 模型作者怎样训练与导出？ |
| 模型图/权重格式 | 可执行图与数据文件 | ONNX、SafeTensors、GGUF、Core ML package | 模型怎样被保存和交给运行时？ |
| 推理运行时 | JVM/浏览器引擎/本机 runtime | 原生 PyTorch、ONNX Runtime、sherpa-onnx、MLX、Core ML、llama.cpp | 哪段软件在本机真正算张量？ |
| TTS 模型家族 | 算法/程序本身 | VITS/Kokoro、flow matching、codec-LM | 声音质量、速度、稳定性和功能由什么架构决定？ |
| 服务形态 | 进程与 RPC 边界 | 进程内对象、localhost sidecar、OpenAI-compatible API | 依赖、内存和失败如何隔离？ |
| 语言前端 | 编译器前端 | TN、G2P、多音字、词典 | `2026/8/30`、`银行`、英文缩写应该怎样读？ |
| 音频缓存 | 构建缓存/CDN | 文本+模型配置指纹 → WAV | 如何避免重复生成并保证切模型后不串音？ |

对当前项目的明确推荐是：

1. **默认轻量栈**：预训练模型 → 官方 ONNX/int8 发布物 → **sherpa-onnx/ONNX Runtime CPU** → FastAPI 进程内单例 → PCM WAV → 现有句子级指纹缓存。
2. **语言前端**：在模型自己的 G2P 之前加一层可测试、可版本化的中文 TN；多音字和专名用版本化覆盖词典，而不是散落在业务代码中的字符串替换。
3. **高质量重型栈**：只有轻量模型盲测不合格时，才使用 **MLX 或原生 PyTorch sidecar**；绑定 `127.0.0.1`，主应用通过小而稳定的 HTTP 协议调用。
4. **Core ML**：作为实测优化选项，不作为默认信仰。ONNX Runtime 的 CoreML Execution Provider 有算子和动态 shape 限制，必须比较完整模型的 RTF、RSS、首句延迟和输出正确性。
5. **不建议**：为了“更主流”把项目改成 TensorFlow/JAX；把 SafeTensors 当推理引擎；把 GGUF/llama.cpp 当通用 TTS runtime；把重型 PyTorch 模型直接塞进 FastAPI 主进程；为了模型宣传的 streaming 重写现有句子缓存播放链路。

## 一、训练框架：PyTorch、JAX、TensorFlow

### 它们是什么，不是什么

训练框架负责张量运算、自动微分、优化器、分布式训练和模型开发。应用消费一个已导出的 ONNX 模型时，并不需要安装训练它的框架。类似“程序由 Clang 编译，不代表用户运行程序时要嵌入 Clang”。

### PyTorch：当前开放 TTS 模型的事实标准开发栈

本次候选的官方实现——Kokoro 导出流程、MeloTTS、F5-TTS、CosyVoice、ZipVoice、Spark-TTS、IndexTTS、Fish Speech——都以 PyTorch 为主要开发/导出路径。这一结论是对本次候选官方仓库的观察，不是对所有机器学习领域的全球份额统计。PyTorch 官方在 macOS 提供 `mps` device，把计算图和算子映射到 Metal Performance Shaders。[PyTorch MPS 官方文档](https://docs.pytorch.org/docs/stable/notes/mps.html)

优势：

- 最新 TTS 论文通常首先发布 PyTorch 代码和 checkpoint；模型功能最完整。
- 动态控制流、研究代码和自定义算子容易表达。
- MPS 让已有模型有机会在 Apple GPU 上运行。

劣势：

- 安装体积、冷启动和常驻内存明显大于 ONNX 专用 runtime。
- “可以 `.to("mps")`”不等于整条 TTS 管线支持 MPS；tokenizer、音频 codec、自定义 CUDA/Triton 算子可能回退 CPU 或直接失败。
- 依赖版本容易与主应用冲突，重模型升级成本高。

适用：模型评测、最新 flow/codec-LM、训练/微调、尚无可靠导出的模型。对 Read Along 应放在隔离 sidecar，而不是默认进程内路径。

### JAX：优秀的研究/大规模数值计算框架，但不是本项目部署选择

JAX 以 `grad`、`jit`、`vmap` 等可组合程序变换和 XLA/PJRT 为核心。官方文档说明 Apple Metal 后端是由 Apple 团队推进的 PJRT 插件，而非 JAX 核心内建的成熟默认路径。[JAX 官方介绍](https://docs.jax.dev/en/latest/about.html)

优势是函数式变换、XLA 编译和 TPU/大规模研究；劣势是本次中文 TTS 候选没有以 JAX checkpoint/runtime 为主，Apple Metal 路径也不能替代现成 sherpa-onnx。除非将来胜出模型只提供 JAX 实现，否则迁移没有用户价值。

### TensorFlow：完整通用框架，但与当前候选生态错位

TensorFlow 的 SavedModel 包含完整程序、参数和具名 signature，可交给 TensorFlow Serving、TFLite 等运行。[TensorFlow SavedModel 官方文档](https://www.tensorflow.org/guide/saved_model) Apple 也提供 `tensorflow-metal` 插件。[Apple TensorFlow Metal 页面](https://developer.apple.com/metal/tensorflow-plugin/)

它的能力没有问题，但本次高质量中文候选的官方实现不以 TensorFlow 为主。为了 Read Along 把 PyTorch/ONNX 模型重写或转换到 TensorFlow，会引入新转换链而不改善音色。只有胜出模型已有官方 TensorFlow/TFLite 发布物时才值得考虑。

### 本层选择

- **消费模型**：不选训练框架；选官方导出物和运行时。
- **需要评测最新模型**：沿用上游 PyTorch，放 sidecar。
- **需要自己训练/微调**：跟随胜出模型官方训练栈，当前通常是 PyTorch。
- **不做**：只因 TensorFlow/JAX 是知名框架就迁移。

## 二、模型表示：ONNX、SafeTensors、GGUF、Core ML

### ONNX：计算图交换格式，适合固定推理图

ONNX 规范定义可扩展计算图、标准数据类型和内建算子；它不是训练框架，也不自己执行模型。[ONNX IR 官方规范](https://onnx.ai/onnx/repo-docs/IR.html) 执行工作由 ONNX Runtime 等 runtime 完成。

优势：

- 把运行时与 PyTorch 训练代码解耦；可做 fp16/int8 导出。
- 同一图可在 macOS、Windows、Linux、移动端使用。
- 非可信 Python pickle 风险较少，部署依赖小。

劣势：

- 动态循环、自定义算子、新模型组件不一定能完整导出。
- “导出成功”不代表数值一致、性能更快；要做逐句回归和 RTF 对比。
- TTS 常常还有模型图外的 TN、G2P、词典、tokenizer、vocoder，不能只拷一个 `.onnx` 就称为完整模型。

对于 Kokoro、Melo/VITS、Matcha、ZipVoice 的 sherpa 官方发布物，ONNX 是当前 Read Along 最合理的部署表示。

### SafeTensors：安全权重容器，不是图也不是 runtime

SafeTensors 官方定义是“安全（相对 pickle）且快速、支持 zero-copy 的简单张量存储格式”。[SafeTensors 官方文档](https://huggingface.co/docs/safetensors/main/index) 它只保存 tensor；模型结构仍来自 Python/config，真正执行仍需 PyTorch、MLX 或其他实现。

因此看到 `model.safetensors` 只能说明权重封装较安全，不能据此判断 Mac 性能、模型大小是否完整，或应用无需 PyTorch。

### GGUF：GGML 运行时生态的单文件模型格式，不是通用 TTS 标准

GGUF 官方说明它是供 GGML 及其 executor 推理使用的二进制格式，强调单文件、可扩展、`mmap` 和量化元数据；模型通常从 PyTorch 转换。[GGUF 官方说明](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)

它很适合 llama.cpp 已实现的 Transformer/LLM 架构，但完整 TTS 还可能包含 G2P、声学模型、flow decoder、codec、vocoder。除非某个 TTS 的所有必要组件都已被一个受维护的 GGML runtime 实现，单纯“转 GGUF”不会让它可朗读。Read Along 不应自建 llama.cpp TTS 后端来追逐文件格式。

### Core ML package：Apple 原生部署目标

Core ML Tools 可把 PyTorch/TensorFlow 模型转换为 Core ML package；Core ML 会利用 CPU、GPU 和 Neural Engine，并针对设备功耗与内存优化。[Core ML Tools 官方概览](https://apple.github.io/coremltools/docs-guides/source/overview-coremltools.html)

它适合 Mac/iOS 原生产品、固定模型和长期维护的转换测试。对当前 Python+Web、跨平台项目，直接维护 Core ML 转换会形成 Apple 专用分叉。更低成本的试验是先让 ONNX Runtime 使用 CoreML EP；只有实测明显获益且输出等价，再考虑原生 Core ML package。

## 三、本地推理运行时

### sherpa-onnx + ONNX Runtime：轻量默认路径

sherpa-onnx 不是新训练框架，而是围绕 ONNX Runtime 封装语音前后处理、模型配置和多语言 API 的本地语音 runtime。官方支持 TTS，并覆盖 macOS arm64、Linux、Windows、iOS、Android、WebAssembly 等平台；Python wheel 无需本地 C++ 编译。[sherpa-onnx 官方 README](https://github.com/k2-fsa/sherpa-onnx)；[TTS 安装 FAQ](https://k2-fsa.github.io/sherpa/onnx/tts/faq.html)

优势：

- 当前项目已经集成、测试和缓存指纹化，迁移成本最低。
- 运行时小、冷启动可控、CPU 行为稳定；有 C/C++/Python/Swift 等 API。
- 同一 runtime 已支持 VITS/Melo、Matcha、Kokoro、ZipVoice 等不同 TTS 模型家族。

劣势：

- 只能运行已实现配置且成功导出的模型；最新 PyTorch 功能会滞后。
- 量化可能改变音质或暴露平台特定数值问题。
- CoreML provider 不是自动加速保证。

推荐在 M4 上先用 CPU provider 建立正确性基线，再单独实测 CoreML provider。

### ONNX Runtime CoreML Execution Provider：优化选项

ONNX Runtime 通过 Execution Provider 把受支持节点/子图分配给硬件后端，未覆盖部分可由其他 provider 执行。[ONNX Runtime EP 架构](https://onnxruntime.ai/docs/execution-providers/) macOS 官方 Python wheel包含 CoreML EP，但官方文档也列出算子限制；动态 shape 可能影响性能，启用 ANE 也不保证整图只在 ANE 上执行。[CoreML EP 官方文档](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html)

最佳实践是测量而非猜测：同一模型、同一十句、CPU 与 CoreML 分别记录首次编译/冷启动、预热 RTF、P95、RSS、波形有效性和 CER。若 CoreML 首次编译慢、频繁分图或没有稳定收益，保留 CPU。

### 原生 PyTorch：功能完整的兼容路径

优先用于尚未导出或无法导出的重型模型。MPS 可利用 Apple GPU，但应把 `mps`、CPU fallback、dtype 和上游补丁记进模型 revision/运行清单。依赖和模型放 sidecar，确保主 API 在模型崩溃或 OOM 时仍能读取材料与已有缓存。

### MLX：Apple Silicon 专用的重模型候选 runtime

MLX 是面向 Apple Silicon 的数组框架，利用统一内存让 CPU/GPU 直接访问同一内存池；无需在 CPU/GPU 间显式搬数组。[MLX unified memory 官方文档](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html) 官方包要求 Apple Silicon、原生 Python 和较新的 macOS。[MLX 安装文档](https://ml-explore.github.io/mlx/build/html/install.html)

第三方 `mlx-audio` 已提供 Apple Silicon TTS 模型、量化、streaming 和本地 server，说明生态具备实际可用性；但它不是多数上游 TTS 模型的官方 runtime，转换 checkpoint 与实现可能晚于或偏离原模型。[MLX Audio 项目](https://github.com/Blaizzy/mlx-audio)

适用条件：

- 目标明确只支持 Apple Silicon；
- 胜出重模型有活跃、可复现的 MLX 实现；
- 与官方 PyTorch 同 revision 的输出质量、发音、稳定性通过 A/B；
- 作为 sidecar 可独立升级和回滚。

不适合作为当前轻量默认层，因为它会牺牲跨平台性，而且现有 50–200 MB ONNX 模型未必会因改写 MLX 获益。

### Core ML 原生 runtime

若未来产品变成 Swift/macOS+iOS 原生应用，Core ML 是最自然的长期部署目标。当前 Python Web 应用则需要额外桥接、转换和回归矩阵；在没有实测优势之前，其工程成本高于 sherpa-onnx。

### llama.cpp / GGML / 纯 C runtime

llama.cpp 对已支持的 codec-LM 文本/语音 token 模块可能很高效，但不是通用 TTS 运行时。sherpa-onnx 本身已经提供 C/C++ 内核与多语言绑定，不需要为了“纯 C”重造完整中文前端、声学模型和 vocoder。只有某个胜出模型发布官方或成熟的完整 C/Metal 实现时才考虑单独适配。

## 四、TTS 模型家族

运行时决定“在哪里算”，模型家族更直接决定“算什么、声音如何”。

### VITS 与小型固定声线模型：成熟、快、稳定

VITS 把条件 VAE、normalizing flows、对抗训练和随机时长预测组合成端到端并行 TTS；原论文在单说话人 LJ Speech 上取得接近真实音频的 MOS。[VITS 论文](https://proceedings.mlr.press/v139/kim21f.html)

Piper、MeloTTS 的 sherpa 导出属于这一轻量路线。其优势是模型小、CPU 友好、确定性和句级稳定性较好；劣势是固定音色和韵律上限、中文多音字高度依赖前端。

Kokoro 并非 VITS 本身，但在产品位置上同属“小型固定/预置声线、一次前馈生成”的轻量层：82M 参数、多声线、可导出 ONNX。对阅读器，它和 VITS 的共同价值是无需维护参考声音、不会引入自回归采样漂移。

### Flow matching / diffusion 类：自然度和克隆能力更强，采样成本更高

F5-TTS 是基于 DiT flow matching 的全非自回归 TTS；ZipVoice 用 Zipformer flow decoder 和蒸馏减少采样步数，论文报告在 100k 小时多语数据上，相对 DiT flow 基线小 3 倍、最快 30 倍。[F5-TTS 论文](https://aclanthology.org/2025.acl-long.313/)；[ZipVoice 论文](https://arxiv.org/abs/2506.13053)

优势是零样本音色、自然韵律和并行生成；劣势是需要参考音频、vocoder、多步采样和更复杂稳定性验证。ZipVoice-Distill 的 sherpa ONNX 发布物是此类模型中最符合当前项目“小而本地”的升级路线。

### Codec-LM / speech-token LLM：功能最丰富，也最重

CosyVoice 将语音表示为监督语义 token，用 LLM 做 text-to-token，再以 conditional flow matching 做 token-to-speech；CosyVoice2 又加入 chunk-aware causal flow 支持流式/非流式。[CosyVoice 论文](https://arxiv.org/abs/2407.05407)；[CosyVoice2 论文](https://arxiv.org/abs/2412.10117)

ChatTTS、Spark、Fish、IndexTTS 等也属于广义的语音 token/自回归或混合 LLM 路线。它们的优势是声音克隆、情绪、方言、上下文韵律和控制能力；劣势是 GB 级权重、采样稳定性、冷启动、内存和复杂 codec 依赖。对于个人阅读器，只有轻模型音质无法接受时才值得承担这些成本。

### 本层选择

- 固定中文朗读：先选修正音色后的 Kokoro 或 Melo/VITS/Matcha。
- 需要更自然且接受参考音频：ZipVoice-Distill。
- 需要情绪、方言、复杂克隆且接受数 GB：CosyVoice3/Qwen3-TTS 等 sidecar。
- 不以“参数越多”作为朗读质量代理；按真实材料盲测。

## 五、服务与集成形态

### 进程内：只给轻量、稳定、依赖可控的 ONNX

当前 `SherpaOnnxTTSBackend` 在 FastAPI 进程内构建单个 `OfflineTts`，每次按一句生成 WAV。这个边界适合小型 ONNX：没有 RPC、延迟低，已有锁和缓存能避免同一句并发重复生成。

风险是推理崩溃会影响 API。因此只有经过 20+ 句连续稳定性验证、RSS 可控的轻模型进入进程内路径。

### localhost sidecar：重型模型的默认边界

PyTorch/MLX/codec-LM 使用独立进程，只监听 `127.0.0.1`。主应用负责材料、权限、缓存和超时，sidecar 只负责模型加载、健康检查和音频生成。好处是：

- 隔离 Python/torch/transformers/系统库版本；
- OOM 或模型崩溃不会让书架和已有音频不可用；
- 可单独预热、重启、切换 CPU/MPS/MLX；
- 重模型不进入主应用基础依赖。

已有 [本地私有声音克隆 TTS 方案](../local-private-voice-clone-tts/proposal.md) 采用的就是这条边界。

### OpenAI-compatible API：可选协议适配，不是推理技术

OpenAI-compatible 只描述 HTTP 请求/响应形状，背后可以是 Kokoro、MLX、PyTorch 或远程服务。它的优点是替换服务方便，项目已有 `OpenAITTSConfig`；缺点是很多本地 server 对 `voice`、streaming、错误、音频格式和模型 revision 的语义并不完全一致。

最佳做法是在 Read Along 内部保留窄的 `TTSBackend` 接口：

- 轻 ONNX 直接实现接口；
- sidecar 适配器可采用 OpenAI-compatible `/v1/audio/speech`，但健康检查、模型 revision、参考声音摘要和超时需要本项目扩展；
- 不让外部 API 的所有参数渗入材料库领域模型。

## 六、中文文本规范化与 G2P

这是中文朗读质量最容易被低估的一层。换更大的声学模型，也不会自动修复所有数字、日期、单位、URL、英文缩写和多音字。

### TN 与 G2P 必须分开

- **Text Normalization（TN）**：把 `12.5%`、`2026-08-30`、`3.2GB` 转成适合朗读的语言形式。
- **G2P**：把规范化文本转成音素/拼音，并结合上下文消歧 `行`、`重`、`长` 等多音字。
- **模型 tokenizer**：再把音素或文字编码成模型 token。

WeTextProcessing 官方提供中英文 TN/ITN、FST 缓存、可追踪输入输出 span 的映射和 C++ runtime，适合做可测试的中文 TN 基线。[WeTextProcessing 官方仓库](https://github.com/wenet-e2e/WeTextProcessing) `pypinyin` 支持多音模式和变调，但开启 heteronym 只返回候选，不负责在上下文中自动选对。[pypinyin 官方用法](https://github.com/mozillazg/python-pinyin/blob/master/docs/usage.rst) g2pW 则专门以 BERT 做普通话多音字消歧，也提供 ONNX checkpoint。[g2pW 官方仓库](https://github.com/GitYCC/g2pW)

推荐设计：

1. 数据库和 UI 永远保存/展示原文；只在生成音频时派生 `normalized_text`。
2. TN 先处理数字、日期、单位、百分比；G2P 仍由模型官方前端负责，避免通用拼音与模型 token 集不一致。
3. 对课程专名、作者名、英文缩写和已知多音字提供版本化词典/发音覆盖；覆盖优先级高于通用 G2P。
4. 记录 `normalizer_id + version + pronunciation_dict_hash` 到缓存指纹。
5. 为真实材料建立 golden corpus，断言规范化文本和关键实体的预期读法。

## 七、音频缓存才是阅读体验的关键“运行时”

Read Along 当前按句生成并在本地文件系统缓存 WAV/MP3；缓存指纹由原文和 `tts.fingerprint_parts()` 组成。这个设计比追求 token streaming 更符合断点续读：已生成句子零推理延迟、可离线复用，播放失败也容易定位到一句。

胜出模型接入时，指纹至少应包含：

- 原文与规范化文本；
- TN/G2P/覆盖词典版本；
- engine、模型 ID、固定 revision 和量化；
- SID 或参考音频 SHA-256 + 准确逐字稿；
- speed、seed/采样参数、输出 sample rate/format；
- 影响输出的 runtime 实现版本（仅当不同 runtime 输出不可视为等价）。

生成流程应保持：临时文件 → 验证可解码、非空、时长合理 → 原子移动到缓存 → 写指纹。切换模型或声音时不能复用旧指纹，也不要在同一材料播放途中静默降级到另一声音。

### Streaming 不是当前的硬需求

模型的 audio-out streaming 主要降低首音延迟；项目按句预取并缓存，后续播放已经绕开大部分实时生成。只有测得“第一句等待”仍是主要体验瓶颈，且目标模型真正支持稳定的 text-in/audio-out streaming，才值得增加流式协议。不要把异步 API、生成回调和真流式混为一谈。

## 八、面向 M4/16 GB 的推荐栈

### 推荐：跨平台、轻量、可维护

```text
原文（数据库）
  → WeTextProcessing 风格的可版本化中文 TN
  → 模型官方 G2P + 项目发音覆盖词典
  → Kokoro 中文 SID / MeloTTS int8 / Matcha（盲测胜者）
  → 官方 sherpa-onnx ONNX 模型包
  → sherpa-onnx + ONNX Runtime CPU（进程内单例，2–4 threads 实测）
  → PCM_16 WAV
  → 句子级内容指纹缓存
```

理由：当前代码、依赖和缓存均已围绕这条路径；官方支持 macOS arm64；模型可在约 50–300 MB 范围；CPU 输出是可靠基线；跨平台性保留。第一步仍是修正当前 Kokoro `SID=0` 的英语音色误配，而不是换 runtime。

### 次选：同一 ONNX 栈的质量升级

使用 ZipVoice-Distill int8 + Vocos，通过 sherpa-onnx 新增模型类型。仍可进程内，但必须先验证参考音频契约、20 句稳定性、RSS 和白噪声/重复防护。若常驻内存或崩溃影响主 API，再移动到 sherpa sidecar。

### 重型次选：MLX sidecar，其次原生 PyTorch sidecar

当 CosyVoice/Qwen3-TTS/Index 等重型模型在匿名盲测中显著胜出：

1. 先验证模型官方 PyTorch CPU/MPS 输出作为正确性基线；
2. 若有活跃 MLX 实现，比较相同 revision/量化下的 CER、听感、RTF、RSS 和连续稳定性；
3. MLX 确实胜出才作为 M4 专用 sidecar；否则使用原生 PyTorch sidecar；
4. 主应用协议和缓存不随 runtime 改变。

### Core ML 何时升级为推荐

只有同时满足以下条件：胜出模型能完整转换；核心算子不大量回退；M4 上比 CPU/MLX 有稳定收益；十句音频数值/听感与发音回归通过；项目愿意维护 Apple 专用构建。此前只作为实验 provider。

## 九、反推荐清单

- **不把 PyTorch 与 Kokoro 比谁更好**：一个是开发/runtime 框架，一个是模型。
- **不把 ONNX 与 SafeTensors 比谁音质高**：格式不决定训练数据和模型能力。
- **不因 M4 有 Neural Engine 就默认 Core ML 更快**：算子覆盖、分图、动态 shape 和首次编译都会改变结果。
- **不为轻量模型改用 MLX**：没有实测收益时只增加 Apple 专用维护面。
- **不把 GGUF 当万能部署格式**：没有完整 TTS executor，就只有一包 tensor。
- **不在主 FastAPI 进程加载数 GB PyTorch 模型**：OOM、崩溃和依赖冲突会扩大故障域。
- **不把模型自带 TN 当永久黑盒**：数字、多音字和专名必须有回归语料与版本化覆盖。
- **不自动降级到不同声音**：缓存身份和听感会漂移。
- **不先做 streaming 重构**：先测现有句子预取+缓存是否真的有首音问题。
- **不以 CUDA/H200/L20 benchmark 预测 M4**：所有最终选择以目标机同语料实测收口。

## 十、决策与验证顺序

1. 修正 Kokoro 中文 SID，建立当前音质/RTF/RSS 基线。
2. 给测试语料增加规范化输出、关键实体和发音覆盖预期。
3. 在同一 sherpa CPU runtime 下盲测 Kokoro、Melo int8、Matcha；此时只比较模型和前端，不混入 runtime 变化。
4. 对胜者再比较 CPU 与 CoreML provider；把 runtime 优化和模型选择拆成两个实验。
5. 轻量栈仍不合格，再测 ZipVoice-Distill。
6. 仍不合格，进入 MLX/PyTorch sidecar 的重型模型评测。
7. 只有目标机数据证明瓶颈在首音延迟，才评估真 streaming。

这套顺序的核心是一次只改变一层：先语言音色，再模型，再 runtime，最后服务形态。否则听感、发音、速度或稳定性变化无法归因，也无法形成可维护的“最佳实践”。
