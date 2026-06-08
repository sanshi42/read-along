# Read Along

Read Along 是一个 macOS 优先的个人本地 Web App。它把单篇网页或文本型 PDF 转成可边听边读的材料，并提供句子级朗读、同步高亮和断点续读。

项目当前处于 MVP 开发阶段。已经完成 FastAPI 服务骨架，并保留了用于读取用户已授权页面可见正文的 Chrome 会话桥接能力。

## 产品边界

- 支持单篇网页和文本型 PDF。
- 默认使用 macOS `say` 生成句子级音频。
- 正文、音频和阅读进度只保存在本机。
- 得到是首个来源适配器，不是产品边界。
- 不保存账号密码、Cookie 或导出的浏览器凭据。
- 不绕过登录或付费权限，不做批量课程抓取。
- MVP 不做 OCR、笔记、LLM 总结或改写。

## 开发

```bash
uv venv
make setup
make dev
```

服务默认监听 `http://127.0.0.1:8765`，健康检查位于 `GET /api/health`。

前端默认监听 `http://127.0.0.1:5173`，开发服务器会将 `/api` 请求代理到本地后端。`make dev` 会在同一终端启动后端和前端；后端源码变更后重启命令，前端由 Vite 热更新。

也可以分别启动：

```bash
uv run read-along serve
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

产品范围、技术方案和迭代计划见 `docs/`；当前开发进度见 `tasks/progress.md`。
