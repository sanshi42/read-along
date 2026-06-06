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
uv sync --no-editable
uv run --no-editable read-along serve
```

服务默认监听 `http://127.0.0.1:8765`，健康检查位于 `GET /api/health`。

## 质量检查

```bash
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
```

产品范围、技术方案和迭代计划见 `docs/`；当前开发进度见 `tasks/progress.md`。
