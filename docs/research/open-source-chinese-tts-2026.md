# 开源中文 TTS 本地替代方案调研（2026-08）

> 调研日期：2026-08-30  
> 目标机器：Apple Silicon Mac（项目计划中为 M4、16 GB）  
> 使用场景：本地优先的句子级长文朗读；优先中文自然度、稳定性、体积与离线运行，而不是声音克隆或情绪表演  
> 证据范围：官方仓库、官方模型卡/文件树、官方论文或项目自带评测。没有把社区主观排行榜当成事实。

## 结论先行

现在最应该做的不是立刻换模型，而是先修正当前 Kokoro 的说话人选择。

项目当前使用 `kokoro-int8-multi-lang-v1_1`、CPU、2 threads，本机配置的 `READ_ALONG_TTS_SHERPA_SID=0`。但 sherpa-onnx 官方映射中，`sid=0` 是 **`af_maple`（美式英语女声）**；中文女声是 `sid=3..57`，中文男声是 `sid=58..102`。也就是说，目前“中文效果不好”很可能至少部分是把中文送进了英语音色，而不是 Kokoro 中文音色本身的上限。官方页面还为全部 103 个 SID 提供了同一中英混合文本的试听，可直接比较。[Kokoro v1.1-zh 官方 SID 映射与试听](https://k2-fsa.github.io/sherpa/onnx/tts/all/Chinese-English/kokoro-multi-lang-v1_1.html)

因此建议按以下顺序决策：

1. **零下载修正**：先对一组中文 SID 做盲听，把最好的中文 SID 与当前 `sid=0`、macOS 系统中文音色放进同一组 A/B。只有这一步仍不合格，才下载替代模型。
2. **最小改造候选**：优先试 sherpa-onnx 已支持的 **MeloTTS Chinese int8 ONNX**，其次试 **Matcha zh-baker**。它们继续复用当前 sherpa-onnx 运行时，权重约 53.5 MB（Melo int8）或约 124 MB（Matcha acoustic + Vocos），集成和维护风险最低。
3. **质量升级候选**：如果允许提供 10–30 秒参考音频并增加新模型类型，试 **ZipVoice-Distill int8 ONNX**。它是中英双语、123M 参数的非自回归 flow-matching 声音克隆模型，官方已有 sherpa-onnx CPU 部署路径，但完整必要权重约 180 MB 量级，并且必须管理参考音频与准确逐字稿。
4. **重型 sidecar 候选**：如果“小”可以放宽到数 GB，再评测 **Fun-CosyVoice3-0.5B**。它的中文一致性与音色相似度有当前候选中较完整的官方公开指标，但官方模型快照约 7.45 GB，明显不符合“模型不大”的首选约束。
5. **不进入首轮**：Piper 中文音色适合极低资源基线，但没有证据证明胜过当前中文 Kokoro 或 macOS；ChatTTS、F5-TTS、Spark-TTS、Fish Speech、IndexTTS 当前版本要么重、要么许可证限制明显、要么官方运行路径以 NVIDIA GPU 为前提，不适合这个阅读器的轻量默认后端。

这里不能诚实地承诺任何候选“一定胜过 macOS 自带声音”。公开资料没有覆盖相同中文长文语料、同一台 Mac、相同音量与盲听条件的统一基准。下文的推荐是**缩小实测范围**，最终结论必须由目标机器上的盲听和稳定性测试产生。

## 当前实现的关键诊断

### 1. 当前 SID 选错了语言音色

官方 `kokoro-multi-lang-v1_1` 说明：模型支持中英双语、103 个说话人、24 kHz；`af` 前缀为美式女声（SID 0–1），`bf` 为英式女声（SID 2），`zf` 为中文女声（SID 3–57），`zm` 为中文男声（SID 58–102）。映射第一项明确是 `0 -> af_maple`。[官方模型说明、映射与逐音色试听](https://k2-fsa.github.io/sherpa/onnx/tts/all/Chinese-English/kokoro-multi-lang-v1_1.html)

首轮无需枚举 100 个中文声音。建议先按区间均匀抽样：

- 女声：SID `3, 12, 28, 44, 57`
- 男声：SID `58, 72, 88, 102`
- 对照：当前 SID `0` 与选定的 macOS 中文音色

用 3–5 句相同中文材料匿名化后盲听；从每个性别选出 1–2 个，再用完整评测语料复赛。这不是宣称这些抽样 SID 更好，只是用较低成本覆盖整个声线区间。

### 2. Kokoro 本身仍有中文上限

即使换成中文 SID，也不应假定问题全部消失。Kokoro 官方音色说明明确警告：非英语语言可能因为较弱的 G2P 或训练数据不足而支持较薄，主观听感也会因人而异。[Kokoro-82M 官方 VOICES 说明](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)

当前 sherpa-onnx 模型是 Kokoro v1.1-zh 的 ONNX 导出，项目下载的是 int8 变体。官方 sherpa-onnx 文档对 fp32 版列出的核心权重为 311 MB，并在 Raspberry Pi 4 上报告 4 threads 的 RTF 约 3.19；这些树莓派数字不能直接推断 M4 性能，只能说明 Kokoro 并非 sherpa 列表里最快的 CPU 模型。[Kokoro 官方部署文档](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/kokoro.html)；[sherpa-onnx 官方 RTF 表](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/rtf.html)

## 候选总览

“体积”优先采用官方模型仓库文件树中的实际文件大小；“参数量”不能等同于下载体积。PyTorch、tokenizer、文本规范化器、音频库等运行时依赖另计。Apple Silicon 一栏只把官方明确提供的 CPU/ONNX/MPS 路径视为已证实；CUDA benchmark 不外推到 Mac。

| 候选 | 必要权重/仓库体积（约） | 中文与质量证据 | Apple Silicon 路径 | 流式/分句 | 许可证 | 本项目判断 |
| --- | ---: | --- | --- | --- | --- | --- |
| Kokoro v1.1-zh int8 | 82M 参数；fp32 ONNX 311 MB，int8 更小，另有 voices/词典 | 中英、100 个中文音色；官方承认非英语 G2P/数据可能较弱 | 已在本项目以 sherpa-onnx CPU 使用 | sherpa OfflineTts 可回调生成；项目本身按句缓存 | Apache-2.0 | **先修 SID，保留基线** |
| Piper `zh_CN` | huayan x_low 20.6 MB；chaowen/xiao_ya medium 各 63.2 MB | 只有官方样例和 `quality` 档位，无统一中文自然度指标 | ONNX/CPU；Python Piper 1.4+ 的新中文音色依赖 g2pW | 可逐块输出；适合句子级 | 代码/声音分别授权；xiao_ya 数据明确非商用 | **低资源基线，不预设更好** |
| MeloTTS Chinese / sherpa VITS int8 | int8 ONNX 53.5 MB + 6.8 MB 词典；同仓库也放了 170 MB fp32 | 官方称中文支持中英混读、CPU 实时；无与 Kokoro/macOS 的同语料公开盲测 | **现成 sherpa-onnx VITS CPU** | 离线按句；符合现有缓存架构 | MIT（上游与导出元数据） | **首个下载试验** |
| Matcha zh-baker | 约 73 MB acoustic + 51 MB Vocos ≈ 124 MB | 中文单女声；官方有试听和 Raspberry Pi RTF | **现成 sherpa-onnx CPU** | 非自回归；按句适合 | Apache-2.0 代码；需随包复核模型/数据许可 | **第二个轻量试验** |
| ZipVoice-Distill int8 | text encoder 5.57 MB + decoder 125 MB + Vocos 约 50 MB，约 180 MB 量级 | 官方称 123M、中英、零样本克隆，在相似度/可懂度/自然度上有论文与 demo；仍需本机验证 | **现成 sherpa-onnx CPU C/Python 配置** | 非自回归；官方 async API，但不是文本输入真流式 | Apache-2.0（仓库）；训练数据为 Emilia，发布物许可仍应在集成时逐文件复核 | **轻量质量升级候选** |
| CosyVoice2/3 0.5B | CosyVoice3 官方 HF 快照约 7.45 GB（包含 2.02 GB LLM、1.33 GB flow、969 MB tokenizer 等） | 官方同表：CV3 test-zh CER 1.21%、相似度 78.0%；RL 版 CER 0.81%、相似度 77.4% | 官方安装/性能主路径偏 Linux/CUDA；Mac 只能视为待实测 PyTorch CPU/MPS | **双流式**，官方称最低 150 ms | Apache-2.0 | **质量优先 sidecar，不算小** |
| F5-TTS v1 Base | 主 checkpoint 1.35 GB，另需 Vocos/运行时；0.3B | 中英，官方共享卡列 Emilia 95k h；CosyVoice 官方表列中文 CER 1.52%、相似度 74.1% | 官方 PyTorch；未提供一等 Mac 保证，需 CPU/MPS 实测 | 离线 flow matching；可分句 | 代码 MIT，预训练权重 CC BY-NC 4.0 | **重且非商用，排除默认后端** |
| Spark-TTS 0.5B | 仅 LLM 权重 2.03 GB，完整快照更大 | 中英克隆；CosyVoice 官方表列中文 CER 1.20%、相似度 66.0% | 官方主要给 Linux/CUDA 与 Triton；无 Mac 一等支持 | 官方推理以完整请求为主 | 权重 CC BY-NC-SA 4.0 | **重且非商用** |
| ChatTTS | 官方 HF 仓库 2.37 GB（历史快照约 1.09 GB） | 中英对话韵律；官方 FAQ 承认自回归稳定性、多人声/音质问题，并有意加入高频噪声、用 MP3 压缩发布音频 | PyTorch CPU 可尝试；官方性能以 4 GB VRAM/4090 为例 | 官方 roadmap 仍把 streaming 列为待办 | 代码 AGPL-3.0；模型 CC BY-NC 4.0 | **不适合稳定长文默认后端** |
| IndexTTS 2.5（当前） | GPT 约 0.8B；还会首次下载多个仓库外辅助模型，完整体积显著超过主权重 | 中、英、日、西、阿；克隆、情绪、拼音和语速控制 | 官方模型卡要求 NVIDIA GPU、约 6 GB VRAM；仓库设备检查虽认识 MPS，但不等于官方可用保证 | 自回归，CLI 有 batch；不是轻量句级模型 | Bilibili Model Use License，有规模门槛及额外义务 | **不符合 Mac 轻量首选** |
| Fish Speech S2-Pro（当前） | 4B slow AR + 400M fast AR；远大于本表轻量模型 | 官方称中文 Tier 1、80+ 语言、10M+ 小时；质量声明来自项目方 | 官方要求 Linux/WSL、24 GB GPU 显存 | SGLang 流式；H200 RTF 0.195/TTFA 约 100 ms | Fish Audio Research License | **明确排除** |

### 关于体积口径

- MeloTTS 官方 PyTorch Chinese 模型还依赖中文 BERT。Qualcomm 的官方派生模型卡把浮点组件列为 BERT 581 MB、decoder 55.5 MB、encoder 31.9 MB、flow 76.9 MB；所以“上游 MeloTTS”并不天然小。这里推荐的是 **sherpa-onnx 已导出的单文件 VITS 版本**，其 int8 权重 53.5 MB，避免把 PyTorch+BERT 全栈带进主应用。[Qualcomm MeloTTS-ZH 模型卡](https://huggingface.co/qualcomm/MeloTTS-ZH)；[sherpa-onnx Melo 文件树](https://huggingface.co/csukuangfj/vits-melo-tts-zh_en/tree/main)
- CosyVoice3 的“0.5B”描述的是主干规模，不是完整下载体积。官方文件树列出约 7.45 GB 快照，其中还同时包含普通和 RL LLM 权重；实际部署可裁掉不用的变体，但仍是数 GB 级。[CosyVoice3 官方文件树](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512/tree/main)
- IndexTTS 2.5 模型卡明确说 CAMPPlus、BigVGAN、w2v-bert、MaskGCT codec 等辅助模型在首次运行时另行下载，因此只报 GPT 参数量会严重低估磁盘与冷启动成本。[IndexTTS 2.5 官方模型卡](https://huggingface.co/IndexTeam/IndexTTS-2.5)

## 逐项判断

### Piper 中文声音

Piper 的优势是体积和 CPU 部署简单。官方 `voices.json` 记录了 `huayan-x_low` 为 20,628,813 bytes；`chaowen-medium`、`xiao_ya-medium` 为 63,221,984 bytes。官方声音库现有中文音色至少包括 huayan、chaowen、xiao_ya。[官方 voices.json](https://huggingface.co/rhasspy/piper-voices/blob/main/voices.json)

限制更重要：

- `xiao_ya` 的官方模型卡说明它仅能在 Piper Python 1.4+ 运行，因为依赖 g2pW；训练数据 BZNSYP 标注为 non-commercial。[xiao_ya 官方模型卡提交](https://huggingface.co/rhasspy/piper-voices/commit/1f265c6bbb3612a8581fc384c91b23fe0b5a0297)
- 官方的 `medium`/`x_low` 是模型配置档位，不是对中文自然度的独立评价。
- 没有一手资料证明这些声音胜过 Kokoro 中文 SID 或 macOS。Piper 应只作为极低资源对照，不应直接替换默认模型。

### MeloTTS Chinese（推荐先测其 sherpa 导出）

MeloTTS 官方仓库称中文声音支持中英混读，并能在 CPU 上实时推理。[MeloTTS 官方仓库](https://github.com/myshell-ai/MeloTTS)

sherpa-onnx 已把 `myshell-ai/MeloTTS-Chinese` 转成 VITS：单女声、中英双语，官方文档给出 163 MB fp32 ONNX、6.5 MB 词典，并提供 Raspberry Pi RTF；当前 HF 文件树还提供 53.5 MB 的 int8 ONNX。项目现有适配器已经支持 sherpa VITS 配置，因此这是最接近“换权重而不是换技术栈”的候选。[sherpa-onnx Melo 部署与试听](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/vits.html#vits-melo-tts-zh-en-chinese-english-1-speaker)；[ONNX 文件树](https://huggingface.co/csukuangfj/vits-melo-tts-zh_en/tree/main)

风险是英文只会读词典中已有词，且公开材料没有给出它相对 Kokoro v1.1-zh 的同语料盲测。因此“首测”表示成本最低，不代表预先判定音质胜出。

### Matcha zh-baker

sherpa-onnx 官方支持中文单女声 `matcha-icefall-zh-baker`，并在 Raspberry Pi 4 上报告 4 threads RTF 0.391，核心 acoustic 约 73 MB，另需约 51 MB Vocos。与同页 Kokoro/Melo 的树莓派数字相比，它明显更快，但不同架构的音质仍只能听测。[Matcha 官方部署、大小与试听](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/matcha.html)；[官方 RTF 表](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/rtf.html)

它比 Melo 多一个 vocoder 文件，仍能留在 sherpa-onnx 内。若 Melo 音色不合口味，Matcha 是合理的第二个轻量试验。

### ZipVoice-Distill int8

ZipVoice 官方仓库称基础模型只有 123M 参数，支持中英双语、零样本声音克隆；Distill 版以较小质量损失换取更快推理，并明确把 sherpa-onnx 列为 CPU 部署方案。[ZipVoice 官方仓库](https://github.com/k2-fsa/ZipVoice)

sherpa-onnx 已提供 `encoder.int8.onnx`、`decoder.int8.onnx`、Vocos、词典和参考音频/逐字稿参数的完整 CPU API 示例。[sherpa-onnx ZipVoice C API 文档](https://github.com/k2-fsa/sherpa-onnx/blob/master/sherpa-onnx/c-api/docs/tts.dox)；[官方运行示例](https://github.com/k2-fsa/sherpa-onnx/blob/master/sherpa-onnx/csrc/sherpa-onnx-offline-tts-play.cc)

它的优势是保留 sherpa-onnx 运行时，同时跨入现代参考音频克隆模型；代价是：

- 模型并非固定内置声线，必须维护合法的参考音频及准确逐字稿；
- 项目适配器当前只支持 Kokoro/VITS，需要新增 ZipVoice 模型配置；
- “async” API 是异步调用，不等于 text-in streaming；阅读器本来按句缓存，首轮没有必要为了流式重构播放器；
- 官方 issue 中存在个别参考音频/句子生成白噪声的报告，应纳入 20 句连续稳定性门禁，而不能只听一条 demo。[相关 sherpa-onnx issue](https://github.com/k2-fsa/sherpa-onnx/issues/2701)

### CosyVoice 2/3

Fun-CosyVoice3 的官方说明覆盖普通话、9 种常用语言和 18+ 中文方言/口音，支持拼音修复、文本规范化、情绪/速度/音量指令以及 text-in/audio-out 双流式，宣称最低 150 ms 延迟。[CosyVoice 官方仓库](https://github.com/FunAudioLLM/CosyVoice)

官方同一张评测表给出的中文结果包括：F5-TTS CER 1.52%/相似度 74.1%，Spark-TTS 1.20%/66.0%，CosyVoice2 1.45%/75.7%，Index-TTS2 1.03%/76.5%，Fun-CosyVoice3 1.21%/78.0%，Fun-CosyVoice3-RL 0.81%/77.4%。这是一手、可追溯的候选缩小证据，但它由 CosyVoice 团队发布，并不包含 Kokoro、Melo、Piper 或 macOS，不能当成最终排名。[CosyVoice 官方模型卡评测表](https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B)

项目已经有专门的 [本地私有声音克隆 TTS 方案](../local-private-voice-clone-tts/proposal.md)，计划在同一台 M4/16 GB Mac 上比较 CosyVoice3 和 Qwen3-TTS。因此这次不应把 CosyVoice 塞进主 Python 依赖；若轻量方案失败，应延续现有 sidecar + 同机 A/B 方案。

### ChatTTS

ChatTTS 面向对话，支持中文和英文。官方说明其开放模型用 40,000 小时数据，代码 AGPLv3+、模型 CC BY-NC 4.0。更关键的是，官方 FAQ 承认自回归模型会发生多人声或音质不稳定；官方还说明为了限制滥用，在训练中加入少量高频噪声并用 MP3 尽量压缩开放音频。Streaming audio generation 仍在 roadmap 中。[ChatTTS 官方仓库与 FAQ](https://github.com/2noise/ChatTTS)；[官方模型文件树](https://huggingface.co/2Noise/ChatTTS/tree/main)

对“稳定、长时间、逐句阅读”而言，这些都是比偶发高表现 demo 更重要的反证，因此不进入首轮。

### F5-TTS

F5-TTS 是中英 flow-matching 零样本克隆模型；官方共享卡列出 v1 Base 使用 Emilia 95K 小时、主模型配置和 CC BY-NC 4.0。[F5-TTS 官方共享模型卡](https://github.com/SWivid/F5-TTS/blob/main/src/f5_tts/infer/SHARED.md)

官方 HF 主 checkpoint 为 1.35 GB；代码 MIT、预训练权重因 Emilia 数据为 CC BY-NC。[官方 checkpoint 文件](https://huggingface.co/SWivid/F5-TTS/blob/main/F5TTS_v1_Base/model_1250000.safetensors)；[F5-TTS 官方仓库](https://github.com/SWivid/F5-TTS)

它可能提供比传统 VITS 更自然的参考声音克隆，但体积、PyTorch 依赖和非商用权重使其不适合轻量默认路径。CosyVoice 官方表还显示它在同一测试中的中文指标并未全面胜过 0.5B 级候选，所以没有充分理由优先于已经计划评测的 CosyVoice3。

### Spark-TTS

Spark-TTS 是 0.5B 中英双语克隆/可控生成模型。官方仓库提供的性能是 NVIDIA L20 + Triton/TensorRT-LLM，不能外推到 M4；官方模型卡后来把权重许可证从 Apache-2.0 改为 CC BY-NC-SA 4.0。[Spark-TTS 官方仓库](https://github.com/SparkAudio/Spark-TTS)；[官方模型卡与许可证更新](https://huggingface.co/SparkAudio/Spark-TTS-0.5B)

单个 LLM safetensors 已有 2.03 GB，尚未计入 tokenizer、音频 tokenizer 和运行时。[官方 LLM 文件](https://huggingface.co/SparkAudio/Spark-TTS-0.5B/blob/main/LLM/model.safetensors) 因此不符合“小”的约束。

### IndexTTS（当前为 2.5）

截至本调研，官方最新模型卡是 IndexTTS 2.5：约 0.8B GPT，支持中英日西阿、拼音/CMU/假名发音控制和语速控制。官方要求 Python 3.10–3.11、NVIDIA GPU 和约 6 GB VRAM，并明确额外辅助模型不包含在主仓库中。[IndexTTS 2.5 官方模型卡](https://huggingface.co/IndexTeam/IndexTTS-2.5)

仓库的新 CLI 确实会检测 `mps` 和 `cpu`，但“能检测设备”不是官方承诺整条推理链在 MPS 正确、实时。模型使用 Bilibili 自定义许可；达到 1 亿 MAU 或年收入 10 亿元人民币等条件需另行授权，并有下游分发等额外义务。[官方 CLI v2 文档](https://github.com/index-tts/index-tts/blob/main/docs/cli_v2_usage.md)；[官方许可](https://github.com/index-tts/index-tts/blob/main/LICENSE)

它适合 GPU 质量/控制力评测，不适合这次的轻量 Mac 默认后端。

### Fish Speech（当前为 S2-Pro）

当前官方主线已经从 Fish Speech 1.5 演进到 S2-Pro：4B slow AR + 400M fast AR，中文列为 Tier 1。官方安装要求 Linux/WSL、24 GB GPU 显存，性能数字来自单张 H200。[Fish Speech 官方中文说明](https://github.com/fishaudio/fish-speech/blob/main/docs/README.zh.md)；[官方安装要求](https://github.com/fishaudio/fish-speech/blob/main/docs/zh/install.md)

代码与权重现使用 Fish Audio Research License，而不是宽松的通用开源许可证。[官方许可证](https://github.com/fishaudio/fish-speech/blob/main/LICENSE) 无论质量如何，它都与“小、Apple Silicon、本地阅读器默认后端”相冲突。

### 旧版本候选为何不应“复活”

- Fish Speech 1.5 的模型卡是 13 语言、CC BY-NC-SA 4.0、百万小时数据，但官方主线已替换为 S2；为追求较小而固定旧主线会承担安全、兼容与维护成本。[Fish Speech 1.5 官方模型卡](https://huggingface.co/fishaudio/fish-speech-1.5)
- IndexTTS 2 相比 2.5 更旧，官方仓库已经把 2.5 作为当前版本；除非 2.5 无法在目标平台运行且 2 有可复现优势，否则不应从旧版本开始新集成。[IndexTTS 官方仓库](https://github.com/index-tts/index-tts)
- CosyVoice2 仍可用于论文复现，但 CosyVoice3 官方宣称在内容一致性、音色相似度、韵律自然度上超过 2，并提供更完整的生产控制。如果决定承担重型 sidecar 成本，应先测 3，而不是新接 2。[CosyVoice 官方仓库](https://github.com/FunAudioLLM/CosyVoice)

## 未纳入候选

- **Supertonic 3**：sherpa-onnx 虽已支持，但官方语言列表没有中文，不能把“多语种”误解成支持普通话。
- **PocketTTS**：当前 sherpa-onnx 示例和模型包明确是 English TTS，未找到可信的一手中文模型，因此不纳入。
- **只由第三方提供的 MLX/量化移植**：它们可能显著改善 Apple Silicon 体验，但同时改变实现、量化与维护者。第一轮先比较官方或 sherpa-onnx 官方发布物；若官方 PyTorch 模型落选，再为 MLX 移植开独立评测。

## 推荐的验证方案

### 阶段 A：零下载 Kokoro SID 诊断

1. 从真实材料取 5 句，覆盖普通叙述、数字/日期、百分比、多音字、专有名词、中英混读。
2. 对 `0, 3, 12, 28, 44, 57, 58, 72, 88, 102` 生成相同 WAV，统一响度，不显示模型/SID 文件名。
3. 加入 macOS 当前中文声音作为对照。
4. 人工记录：自然度、发音准确、长句停顿、听觉疲劳；不要用“像真人”一个总分替代错误记录。
5. 如果任一中文 SID 达到接受门槛，先只改配置并连续听 20 句；这条路径没有新模型下载、依赖或适配器代码。

### 阶段 B：轻量模型三方盲测

只有阶段 A 不合格时，比较：

- 当前 Kokoro 中最佳中文 SID（基线）
- MeloTTS Chinese int8 ONNX
- Matcha zh-baker
- 可选的 Piper `chaowen-medium`（只作低资源对照，使用前复核声音许可）

建议沿用项目现有 [本地私有声音克隆 TTS 计划](../local-private-voice-clone-tts/plan.md) 的十句语料、SenseVoice 回转录、匿名 A/B、20 句稳定性和 RTF/RSS 记录方式。轻量固定声线模型无需参考音频，但其余协议应保持一致。

淘汰门槛：

- M4/16 GB 上预热后中位 RTF 必须 `< 1`，并记录 P95；
- 20 句连续生成不能有空输出、截断、异常重复、崩溃或持续内存增长；
- 人工复核后的总 CER 建议 `<= 5%`，数字、日期、百分比、英文词和专有名词单独计错；
- 人工盲听在“自然度、准确度、长听不疲劳”三项中必须明确优于当前最佳中文 Kokoro，才值得换默认值；
- 与 macOS 的比较只作为本机用户偏好对照，不写成普适结论。

### 阶段 C：ZipVoice 质量升级

如果固定声线轻量模型仍不合格，再测试 ZipVoice-Distill int8：

- 使用 10–30 秒、24 kHz、单声道、已授权的参考声音和准确逐字稿；
- 固定模型 revision、参考 WAV SHA-256、逐字稿、num_steps、seed（若可控）；
- 和阶段 B 使用同一十句，不允许换更容易的 demo 文本；
- 增加至少 20 句稳定性测试，特别捕捉白噪声、重复、音色漂移与长句截断；
- 测量完整进程 RSS、冷启动、首句时间和预热 RTF；
- 只有显著胜出，才给现有 sherpa adapter 增加 `zipvoice` 模型类型。

### 阶段 D：重型 sidecar

只有 ZipVoice 仍不合格、且用户愿意接受数 GB 下载与独立进程时，执行已有 CosyVoice3 vs Qwen3-TTS 计划。重型模型不要加入主应用基础依赖；使用 localhost sidecar、单模型常驻、显式健康检查、严格超时和可复用缓存。

## 集成最佳实践

不论哪个模型胜出，都应保持以下约束：

1. **模型 profile 是显式配置**：缓存指纹包含引擎、模型 ID、固定 revision、量化、SID/参考声音、speed、文本规范化版本和音频格式。
2. **下载与运行解耦**：继续使用显式下载命令、断点续传、校验和、原子安装；不要在第一次播放时静默下载数百 MB/数 GB。
3. **不要自动跨声音降级**：一个材料播放途中不从克隆声切到 Kokoro/Piper；已有匹配缓存可离线复用，新音频生成失败则明确报错并允许重试。
4. **前端文本规范化可测试**：数字、日期、单位、百分比、URL、英文缩写和多音字应有固定回归语料。Melo 的英文词典限制和 ZipVoice 的参考逐字稿都是配置契约的一部分。
5. **句子级是当前正确粒度**：Read Along 已按句生成和缓存。除非实测首句延迟成为主要问题，不要仅因为模型宣传“streaming”就重构播放器。
6. **固定来源与许可证**：记录代码许可、权重许可、训练数据限制、模型 revision；代码 Apache/MIT 不代表权重或声音数据同样允许商用。
7. **重模型隔离**：PyTorch/LLM TTS 放在 localhost sidecar，避免污染主应用依赖、启动时间和内存；ONNX 轻模型才适合直接复用 sherpa backend。
8. **以目标机证据收口**：CUDA/H200/L20/树莓派 RTF 只能帮助筛选，不能代替 M4 上的 RTF、RSS、冷启动、20 句稳定性和盲听。

## 最终建议清单

- **立即做**：把 `READ_ALONG_TTS_SHERPA_SID=0` 当作配置错误候选，先盲听中文 SID；短期不要改默认模型代码。
- **轻量首选试验**：MeloTTS Chinese `model.int8.onnx`（约 53.5 MB），因为现有 sherpa VITS adapter 可复用。
- **轻量备选试验**：Matcha zh-baker（约 124 MB 必要模型），作为不同架构/音色对照。
- **质量升级试验**：ZipVoice-Distill int8（约 180 MB 量级 + 参考声音），前提是接受声音档案和新增 adapter 模型类型。
- **重型质量路线**：CosyVoice3 sidecar，沿用仓库已有正式评测计划；不作为“小模型”推荐。
- **不建议首轮投入**：Piper（只作低资源对照）、ChatTTS、F5-TTS、Spark-TTS、IndexTTS 2.5、Fish Speech S2-Pro。

最终默认值的切换条件不是“新模型更新、参数更多或 demo 更好听”，而是：在同一台目标 Mac、同一真实中文语料、匿名听测下，候选明确胜过**修正 SID 后的 Kokoro**，同时满足 RTF、稳定性、内存、体积和许可证要求。
