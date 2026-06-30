# Read Along

Read Along 是一个本地优先的个人 Web App。它把单篇网页或文本型 PDF 转成可边听边读的阅读材料，并提供句子级朗读、同步高亮和断点续读。

项目当前已完成 MVP 核心闭环：单篇导入、材料库、书架、阅读偏好、句子级朗读、高亮、断点续读和多种 TTS 后端已经可用。

## 产品边界

- 支持单篇网页和文本型 PDF。
- 默认使用本地 Sherpa ONNX Kokoro 多语种模型生成句子级音频。
- 正文、音频和阅读进度默认只保存在本机；配置在线 TTS 后端表示允许把句子原文发送给该后端。
- TTS 输入使用句子原文，不为朗读引擎清理标点或特殊字符。
- 导入来源适配器不是产品边界；当前优先支持单篇材料。
- 不保存账号密码、Cookie 或导出的浏览器凭据。
- 不绕过登录或付费权限，不做批量课程抓取。
- MVP 不做 OCR、笔记、LLM 总结或改写。

## 技术栈

- 后端：Python 3.12、FastAPI、Typer、SQLModel、SQLite、Alembic baseline、uv。
- 前端：React 19、Vite、TypeScript、React Router、lucide-react、npm。
- 质量工具：Ruff、Pyrefly、pytest、Biome、Node.js test runner、Playwright smoke tests。

## 开发环境

```bash
uv venv
make setup
make dev
```

`make dev` 会在同一终端启动后端和前端：

- API: `http://127.0.0.1:8765`
- Web: `http://127.0.0.1:5173`
- 健康检查：`GET /api/health`

也可以分别启动：

```bash
make dev-api
make dev-web
```

## 本地 TTS 模型

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

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `make setup` | 安装 Python、Web 依赖并安装 pre-commit hook |
| `make dev` | 同时启动 FastAPI 和 Vite 开发服务器 |
| `make check` | 运行本地快速完整门禁 |
| `make check-browser` | 启动真实后端和前端并运行浏览器烟测 |
| `make format` | 格式化 Python 和渐进式 Web 文件 |
| `make pre-commit` | 对全量文件运行 pre-commit |

`make check` 包含 Python lint/format/typecheck/test、前端 lint/format/test 和生产构建。浏览器烟测需要额外安装 Playwright Chromium，并由 `make check-browser` 和 CI 单独运行。

## 项目文档

- [架构说明](docs/architecture.md)
- [代码布局](docs/code-layout.md)
- [测试说明](docs/testing.md)
- [前端准则](docs/frontend-guidelines.md)
- [领域词汇](CONTEXT.md)
- [架构决策记录](docs/adr/)
- [Agent 工作规则](AGENTS.md)

Topic 计划和任务位于 `docs/<topic>/`。当前 MVP 目标、计划和历史任务见 `docs/read-along-mvp/`。

## 贡献

欢迎通过 issue 或 pull request 反馈问题和改进建议。开始前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，并确认变更符合 [SECURITY.md](SECURITY.md) 中的安全边界。

## 许可证

Read Along 使用 [MIT License](LICENSE)。
