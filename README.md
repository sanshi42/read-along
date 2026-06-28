# Read Along

Read Along 是一个跨平台、本地优先的个人 Web App。它把单篇网页或文本型 PDF 转成可边听边读的材料，并提供句子级朗读、同步高亮和断点续读。

项目当前已完成 MVP 核心闭环。单篇导入、材料库、书架、阅读偏好、句子级朗读、高亮和断点续读已经可用。

## 产品边界

- 支持单篇网页和文本型 PDF。
- 默认使用本地 Sherpa ONNX Kokoro 多语种模型生成句子级音频。
- 正文、音频和阅读进度默认只保存在本机；配置在线 TTS 后端表示允许把句子原文发送给该后端。
- TTS 输入使用句子原文，不为朗读引擎清理标点或特殊字符。
- 导入来源适配器不是产品边界；当前优先支持单篇材料。
- 不保存账号密码、Cookie 或导出的浏览器凭据。
- 不绕过登录或付费权限，不做批量课程抓取。
- MVP 不做 OCR、笔记、LLM 总结或改写。

## 开发

```bash
uv venv
make setup
make dev
```

首次使用默认本地 TTS 前，下载 Sherpa ONNX Kokoro 模型并按命令输出填写项目根目录 `.env`：

```bash
uv run read-along tts download-model kokoro
```

交互终端会显示下载进度；命令重复执行时会安全续传局部归档，并对临时网络错误自动重试 3 次。如需丢弃局部归档并从头下载，使用：

```bash
uv run read-along tts download-model kokoro --restart
```

也可以参考 `.env.example` 切换到其他 TTS 后端。进程环境变量优先于 `.env`。

可选 TTS 后端按需安装 extra：

| 后端 | 安装命令 |
| --- | --- |
| Edge TTS | `uv sync --extra tts-edge` |
| OpenAI 兼容 API | `uv sync --extra tts-openai` |
| Azure Speech | `uv sync --extra tts-azure` |
| GPT-SoVITS / X-TTS / SiliconFlow / MiniMax HTTP API | `uv sync --extra tts-http` |
| Piper | `uv sync --extra tts-piper` |
| pyttsx3 | `uv sync --extra tts-pyttsx3` |
| CosyVoice / CosyVoice2 / Spark Gradio | `uv sync --extra tts-gradio` |
| Fish Audio | `uv sync --extra tts-fish` |
| ElevenLabs | `uv sync --extra tts-elevenlabs` |
| Cartesia | `uv sync --extra tts-cartesia` |
| Bark | `uv sync --extra tts-bark` |
| Coqui TTS | `uv sync --extra tts-coqui` |

MeloTTS 的 PyPI 包当前不能稳定锁定；需要时按 MeloTTS 官方安装方式安装，后端仍使用 `melo.api.TTS`。

服务默认监听 `http://127.0.0.1:8765`，健康检查位于 `GET /api/health`。

前端默认监听 `http://127.0.0.1:5173`，开发服务器会将 `/api` 请求代理到本地后端。`make dev` 会在同一终端启动后端和前端；后端启用 Uvicorn reload，前端由 Vite 热更新。

也可以分别启动：

```bash
uv run read-along serve --reload
npm run dev --prefix web
```

uv 本地开发默认使用 editable mode，部署或打包场景才需要考虑 `--no-editable`。

## 质量检查

```bash
make format
make check
```

`make check` 会运行 Ruff、Pyrefly、pytest 和前端生产构建。首次初始化时 `make setup` 会安装 pre-commit hook；之后 `git commit` 会自动执行 Ruff 修复、格式化和 Pyrefly 检查。也可以单独运行：

```bash
uv run pre-commit install
npm run build --prefix web
```

MVP 目标、计划和当前任务见 `docs/read-along-mvp/`。
