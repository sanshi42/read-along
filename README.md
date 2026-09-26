# Read Along

Read Along 是一个本地优先的个人 Web App。它把单篇网页或文本型 PDF 转成可边听边读的阅读材料，并提供句子级朗读、同步高亮和断点续读。

项目当前已完成 MVP 核心闭环：单篇导入、材料库、书架、阅读偏好、句子级朗读、高亮和断点续读已经可用。

## 产品边界

- 支持单篇网页和文本型 PDF。
- 使用本地 Sherpa ONNX 朗读引擎生成句子级音频；`.env.example` 提供的默认模型 profile 是 `kokoro-multi-lang-v1_1-int8`。
- 正文、音频和阅读进度保存在本机；朗读不把句子原文发送给在线 TTS 服务。
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
```

首次启动前需要从 `.env.example` 创建项目根目录 `.env`；如果已有 `.env`，请手工合并，不要直接覆盖：

```bash
cp .env.example .env
```

以下六项都必须存在且不能为空，代码不提供备用默认值：

```dotenv
READ_ALONG_API_URL=http://127.0.0.1:8765
READ_ALONG_TTS_MODEL=kokoro-multi-lang-v1_1-int8
READ_ALONG_TTS_VOICE_ID=3
READ_ALONG_TTS_PROVIDER=cpu
READ_ALONG_TTS_NUM_THREADS=2
READ_ALONG_TTS_SPEED=1.0
```

`READ_ALONG_API_URL` 是 Vite 开发服务器转发 `/api` 请求的目标，可以改为另一个非空的 HTTP(S) 地址。当前唯一支持的模型 profile 是 `kokoro-multi-lang-v1_1-int8`；示例中的 `READ_ALONG_TTS_VOICE_ID=3` 对应中文女声 `zf_001`。`PROVIDER`、`NUM_THREADS` 和 `SPEED` 是 Sherpa ONNX 运行参数。缺失、空值或无效配置会让使用该配置的进程启动失败；同名进程环境变量可以临时覆盖 `.env`。

`READ_ALONG_HOME` 不属于 `.env` 配置；需要改变本地数据目录时，应把它作为进程环境变量传入，例如：

```bash
READ_ALONG_HOME=/path/to/read-along-data uv run read-along serve --reload
```

配置完成后运行：

```bash
make dev
```

`make dev` 会在同一终端启动后端和前端：

- API: `http://127.0.0.1:8765`
- Web: `http://127.0.0.1:5173`
- 健康检查：`GET /api/health`

两个服务都会保持在前台运行。在执行 `make dev` 的终端按 `Ctrl-C`，Make 会同时关闭前端和后端；找不到原终端时，可在仓库目录运行 `make dev-stop`。任一服务启动失败或意外退出时，另一服务也会被清理。

也可以分别启动：

```bash
make dev-api
make dev-web
```

或者从仓库根目录在两个终端中直接运行底层命令，不依赖 Make：

```bash
# 终端 1：FastAPI 后端
uv run read-along serve --reload

# 终端 2：Vite 前端
npm run dev --prefix web
```

后端监听地址可通过 `--host` 和 `--port` 修改；前端可在 npm 命令末尾追加 Vite 的 `--host` 和 `--port`，例如 `npm run dev --prefix web -- --port 5174`。修改后端端口时，也要把 `.env` 中的 `READ_ALONG_API_URL` 改为同一地址。

前端可以单独启动，但导入、材料读取和音频等完整功能仍需要 `READ_ALONG_API_URL` 指向的 API。单独运行 `make dev-api`、`make dev-web` 或上述命令时，同样使用 `Ctrl-C` 停止对应的前台进程。

在 PyCharm、VS Code 或其他 IDE 中可以使用相同的 IDE 无关配置：

| 服务 | 工作目录 | 可执行文件 | 参数 |
| --- | --- | --- | --- |
| 后端 | 仓库根目录 | `uv` | `run read-along serve --reload` |
| 前端 | 仓库根目录 | `npm` | `run dev --prefix web` |

`--reload` 是 `read-along serve` 的普通命令行参数，可以直接填写在 IDE 的参数栏中。若 IDE 提供原生 npm 运行配置，也可以选择 `web/package.json` 的 `dev` script。

## 本地 TTS 模型

后端启动时会检查 `.env` 选择的模型 profile。模型不存在时，后端会先在日志中提示，再同步下载、校验并安装模型；模型准备完成后 API 才开始监听。下载或配置失败会让启动失败，不会静默回退到其他模型。

如果希望在启动后端前完成下载，或手动重试失败的下载，可以运行：

```bash
uv run read-along tts download-model
```

命令读取 `.env` 中的 `READ_ALONG_TTS_MODEL`，与后端启动使用同一套下载和安装流程。当前只登记了 `kokoro-multi-lang-v1_1-int8`；未知 profile 会明确报错。模型文件位置由 profile 管理，不需要在 `.env` 中填写路径。

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `make setup` | 安装 Python、Web 依赖并安装 pre-commit hook |
| `make dev` | 同时启动 FastAPI 和 Vite 开发服务器 |
| `make dev-stop` | 停止当前仓库由 `make dev` 启动的服务 |
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
