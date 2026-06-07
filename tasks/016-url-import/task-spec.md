# Task 016：公开网页 URL 导入

## Task ID

`016-url-import`

## Task Title

输入公开网页 URL，使用 Scrapling 抽取正文并导入为阅读材料。

## Backlog Reference

`MVP-013`：网页导入。作为学习者，我可以输入一个公开网页 URL，将正文导入阅读器。

## Goal

在现有材料库和结构化正文基础上，新增公开网页 URL 导入闭环：用户提交一个 HTTP/HTTPS URL，后端抓取网页正文、结构化为段落和句子、保存为 URL 来源材料，并能在书架和阅读页中打开。

## Scope

- 新增后端 URL 导入入口，使用 Scrapling 抓取公开网页。
- 从抓取结果中选择正文候选，优先使用 `article`、`main`、`[role=main]` 等语义区域。
- 抽取标题，优先使用 `h1`，其次使用页面标题，最后回退为 URL。
- 复用现有 `structure_text` 管线清洗和切分正文。
- 复用 `MaterialLibrary.save()` 保存 URL 来源 Draft。
- 新增 `POST /api/import/url` API，接受 `url` 和可选 `mode` 字段。
- 当前任务仅支持 `mode=auto`；其他模式返回清晰错误。
- 书架页新增 URL 输入表单，导入成功后刷新书架。
- 补充单元测试和 API 测试，避免依赖真实外网。
- 新增 Scrapling Python 依赖并更新锁文件。

## Non-goals

- 不实现得到单篇 Chrome 会话桥接（`MVP-014`）。
- 不实现完整异步导入任务状态页或轮询 UI（`MVP-018`）。
- 不实现重复导入冲突提示的完整前端体验（`MVP-015`）。
- 不做批量 URL 导入、课程目录遍历、自动翻页或抓取队列。
- 不保存 Cookie、账号密码或导出的浏览器凭据。
- 不绕过登录、付费或访问权限。
- 不引入 LLM 改写、总结或正文修复。

## Implementation Notes

- `src/read_along/importers.py` 新增 `import_url()` 和内部网页抽取辅助函数。
- Scrapling 调用集中在一个小函数中，便于测试时 monkeypatch。
- 正文候选选择保持启发式：在候选节点中选择清洗后文本长度最长且达到最小长度的节点；没有候选时回退整页文本。
- URL 校验交给 Pydantic 和材料库的 URL 来源键规范化共同处理；API 层负责返回中文错误。
- `POST /api/import/url` 先同步完成导入并返回 `MaterialDetail`，异步 `import_jobs` 留给后续任务实现。
- 前端仅做最小入口：URL 输入、提交状态、错误提示、成功后刷新书架并清空输入。

## Acceptance Criteria

- 输入公开 HTTP/HTTPS URL 后，后端能创建 URL 来源阅读材料。
- 导入后的材料出现在书架，来源类型显示为网页。
- 打开阅读页时能看到结构化正文。
- 抽取正文不包含明显导航、按钮、评论区标题或版权页脚噪声。
- 无法抓取、非 HTTP/HTTPS URL、空正文或不支持的 `mode` 返回中文错误。
- 后端测试覆盖成功导入、无正文失败、API 成功和 API 失败路径。
- 不依赖真实外网完成自动化测试。
- 后端全量测试、Ruff、mypy 和前端生产构建通过。

## Test Plan

- 运行 `uv run --no-editable pytest`。
- 运行 `uv run --no-editable ruff check .`。
- 运行 `uv run --no-editable mypy src tests`。
- 运行 `npm run build --prefix web`。
- 通过单元测试 monkeypatch Scrapling 抓取结果，验证 URL 导入正文结构化和错误路径。
- 通过 API 测试 monkeypatch `import_url()`，验证 `/api/import/url` 请求和错误响应。

## Completion Notes

已完成。

- 新增 `scrapling` 依赖并更新 `uv.lock`。
- 新增 `import_url()`：校验 HTTP/HTTPS URL，使用 Scrapling `Fetcher.get()` 抓取公开网页，抽取标题和正文候选，并复用 `structure_text()` 生成段落和句子。
- 新增 `WebPageContent` 和 `UrlImportError`，网页导入失败统一返回中文错误。
- 新增 `POST /api/import/url`，支持 `mode=auto`，成功返回导入后的 `MaterialDetail`。
- 书架页新增公开网页 URL 导入表单，提交成功后刷新本地材料列表，失败时展示错误。
- 新增 URL 导入单元测试和 API 测试，测试通过 monkeypatch 避免真实外网。
- `uv run --no-editable pytest`：121 个测试通过。
- `uv run --no-editable ruff check .`：通过。
- `uv run --no-editable mypy src tests`：通过。
- `npm run build --prefix web`：通过。
- 浏览器验收通过：书架页导入区和 URL 输入存在，空输入提交显示“请输入网页 URL”。
