# Task ID

018-url-import-failures

# Task title

修复公开网页和得到 Chrome 导入失败

# Backlog reference

- MVP-013：网页导入
- MVP-014：得到单篇导入
- MVP-019：错误提示

# Goal

修复本地验证中两个 URL 导入失败的问题：

- `https://01mvp.com/docs/resources/skills` 公开网页导入失败。
- `https://www.dedao.cn/course/article?id=obyrmnqGdwxkXWMa0VelBz2D5ZO8aN` 使用已登录 Chrome 导入失败。

# Scope

- 建立可自动运行的失败复现信号。
- 修复公开网页正文抽取或结构化导致的失败。
- 修复得到单篇 Chrome 会话匹配、正文读取或清洗导致的失败。
- 补充覆盖这两类失败模式的回归测试。
- 保持现有 URL 导入 API 和前端调用方式不变。

# Non-goals

- 不实现批量课程抓取。
- 不自动登录或绕过付费权限。
- 不保存 Cookie、账号密码或浏览器凭据。
- 不实现重复导入体验优化。
- 不改动 TTS、播放器或阅读进度功能。

# Implementation notes

- 优先沿用 `src/read_along/importers.py`、`src/read_along/browser.py` 和 `src/read_along/sources/dedao.py` 的现有 seam。
- 若真实网络或真实 Chrome 会话不可稳定自动化，使用最小化 fixture 复现导入失败的代码路径。
- 测试说明文本使用中文，协议值和代码标识符保持英文。

# Acceptance criteria

- 公开网页 URL 的正文候选能被结构化为非空阅读材料。
- 得到文章 URL 的 Chrome 标签匹配能覆盖 `id=` 查询参数形式。
- 导入失败时仍返回可理解的错误信息。
- 新增回归测试失败后修复通过。

# Test plan

- 运行定向导入相关测试。
- 运行全量后端测试。
- 运行 Ruff 和 mypy。
- 如涉及前端显示，运行前端构建或浏览器验证。

# Completion notes

已完成。

- 在 `main` 上恢复并修复 `mode=chrome` URL 导入路径。
- 公开网页正文抽取优先选择 `.prose`、Markdown、正文内容容器，避免把 `Zen`、`Copy Markdown` 等文档站工具栏文本当作正文。
- Chrome 导入先按完整 `host/path?query` 匹配标签页；若得到文章登录后跳转或改写 query，再按 `host/path` 重试。
- Chrome DevTools 端口不可用时，回退读取用户当前前台 Chrome 标签页，并校验前台页 host/path 与请求 URL 一致。
- 保留得到 URL 直抓边界：`auto` 模式无正文时继续提示可能需要登录态或动态渲染。
- 新增回归测试覆盖文档正文容器选择、得到 `id=` URL 标签页重试、前台 Chrome fallback 和 Chrome 错误聚合。
- 已用真实公开 URL `https://01mvp.com/docs/resources/skills` 验证非 editable 包导入成功，首句为“欢迎来到 01MVP 的 Skills 系列教程。”。
- 真实已登录得到 Chrome 页面不可稳定自动化；当前通过可控 Chrome seam 回归测试覆盖，需用户在本机用目标页面手动复验。
