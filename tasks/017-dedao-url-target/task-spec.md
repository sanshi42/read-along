# Task 017：得到单篇 URL 抽取目标验证

## Task ID

`017-dedao-url-target`

## Task Title

以指定得到单篇链接为目标，完善 URL 抽取链路的依赖和得到页面处理。

## Backlog Reference

关联 `MVP-013` 网页导入和 `MVP-014` 得到单篇导入。本任务按用户要求只走 URL 抽取链路，不使用 Chrome 会话桥接。

目标 URL：

```text
https://www.dedao.cn/course/article?id=obyrmnqGdwxkXWMa0VelBz2D5ZO8aN
```

## Goal

确保现有 `/api/import/url` 和 `import_url()` 对指定得到单篇 URL 有明确、可验证的行为：Scrapling 运行依赖完整，得到域名走专用清洗规则，抽取成功时保存为阅读材料；若 URL 直抓无法访问完整正文，则返回清晰错误且不绕过权限。

## Scope

- 修复 Scrapling `Fetcher` 运行所需依赖缺失问题。
- 将得到域名识别和清洗接入 URL 导入结构化流程。
- 为得到 URL 抽取补充单元测试，覆盖得到噪声过滤和 URL 来源保存。
- 使用目标 URL 做一次手动验证，记录 URL 抽取结果。
- 保持现有公开网页导入能力不回退。

## Non-goals

- 不读取本地浏览器 Cookie。
- 不保存账号密码、Cookie 或导出的浏览器凭据。
- 不绕过得到登录、付费或访问权限。
- 不实现 Chrome 会话桥接。
- 不做课程目录批量导入、自动翻页或目录遍历。
- 不实现异步导入任务状态 UI。

## Implementation Notes

- `pyproject.toml` 使用 `scrapling[fetchers]`，显式安装 Scrapling `Fetcher` 运行需要的 extra 依赖。
- `import_url()` 在结构化前根据 URL 判断是否使用 `read_along.sources.dedao.clean_text()`。
- 普通网页继续使用通用 `structure_text()` 管线。
- 得到 URL 的结构化逻辑仍复用现有段落/句子模型和 `MaterialLibrary.save()`。
- 自动测试不依赖真实得到网络访问；目标 URL 仅用于手动验证。

## Acceptance Criteria

- `fetch_webpage()` 不再因为缺少 Scrapling fetcher 运行依赖直接失败。
- 得到 URL 抽取前会应用得到专用噪声清洗。
- 得到噪声行如“课程目录”“下一讲”“写留言”等不会进入结构化正文。
- 指定目标 URL 的 URL 抽取结果被手动验证并记录。
- 如果目标 URL 直抓无法取得完整正文，错误信息说明 URL 直抓不可访问或正文为空，不扩大到 Chrome 会话。
- 后端测试、Ruff、mypy 和前端构建通过。

## Test Plan

- 运行 `uv run --no-editable pytest`。
- 运行 `uv run --no-editable ruff check .`。
- 运行 `uv run --no-editable mypy src tests`。
- 运行 `npm run build --prefix web`。
- 直接调用当前代码抓取目标 URL，检查标题、正文长度和前若干字符。

## Completion Notes

已完成。

- 将网页抓取依赖改为 `scrapling[fetchers]>=0.4.1`，补齐 Scrapling `Fetcher` 运行所需依赖，并更新 `uv.lock`。
- `import_url()` 在结构化前识别得到域名，并应用 `read_along.sources.dedao.clean_text()` 去除得到专用噪声。
- 得到 URL 直抓无正文时返回明确错误：“得到页面 URL 直抓未返回正文，可能需要登录态或动态渲染。”
- 新增测试覆盖得到 URL 专用清洗和得到空正文错误。
- 目标 URL 手动验证结果：Scrapling `Fetcher` 返回 HTTP 200，但原始 HTML 只有 SPA 容器 `<div id="app"></div>`，`window.__INITIAL_STATE__` 为 `isLogin:false`，没有文章正文；因此在不使用本地登录态、不执行 Chrome 会话桥接的 URL 直抓模式下无法导入完整正文。
- `uv run --no-editable pytest`：123 个测试通过。
- `uv run --no-editable ruff check .`：通过。
- `uv run --no-editable mypy src tests`：通过。
- `npm run build --prefix web`：通过。
