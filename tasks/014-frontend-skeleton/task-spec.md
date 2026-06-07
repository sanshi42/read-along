# Task 014：前端骨架

## Task ID

`014-frontend-skeleton`

## Task Title

建立 React + Vite 前端骨架、书架页和阅读页入口。

## Backlog Reference

`MVP-006`：前端骨架。使学习者可以打开本地 Web 页面，查看材料书架并进入阅读页。

## Goal

建立可持续开发的 React + Vite + TypeScript 前端基线，并通过真实后端只读 API 展示材料书架、清晰空状态和可进入的阅读页入口。

## Scope

- 在 `web/` 建立 React + Vite + TypeScript 前端项目。
- 新增 `GET /api/materials` 和 `GET /api/materials/{material_id}` 只读 API。
- 实现书架页，覆盖加载、空状态、错误状态和材料列表。
- 实现阅读页路由入口，展示材料标题、主来源和后续正文阅读功能的占位说明。
- 配置 Vite 开发代理，使前端通过同源 `/api` 路径访问本地后端。
- 补充前后端本地开发说明和必要的忽略规则。

## Non-goals

- 不实现 PDF 上传界面。
- 不实现完整正文段落和句子展示；该范围属于 `MVP-007`。
- 不实现播放器、句子高亮、阅读进度或阅读设置。
- 不实现网页导入。
- 不实现后端静态服务 `web/dist`。
- 不在本任务引入独立前端单元测试框架。

## Implementation Notes

- 前端使用 npm 管理依赖，使用 React Router 建立书架和阅读页路由。
- 书架页只依赖 `MaterialSummary` 所需字段；阅读页入口读取完整材料详情，但不渲染正文。
- Vite 开发服务器将 `/api` 代理到 `http://127.0.0.1:8765`，后端无需为本地开发新增 CORS。
- API 对不存在材料返回中文 `404` 详情。
- 前端骨架保持最小，后续 `MVP-007` 在现有阅读页路由上继续实现。

## Acceptance Criteria

- `web/` 中的 React + Vite + TypeScript 前端可安装依赖并启动。
- 访问根路径可看到书架页。
- 没有材料时显示清晰的中文空状态。
- 有材料时书架显示标题和主来源，并可进入对应阅读页。
- 阅读页入口展示材料标题和主来源；不存在材料时显示清晰错误。
- 后端材料列表和材料详情 API 返回材料库真实数据。
- 后端全量测试、Ruff、mypy 和前端生产构建通过。
- 主要前端交互通过浏览器验证。

## Test Plan

- 新增 API 测试，覆盖空书架、材料列表、材料详情和不存在材料。
- 运行 `uv run --no-editable pytest`。
- 运行 `uv run --no-editable ruff check .`。
- 运行 `uv run --no-editable mypy src tests`。
- 运行 `npm run build --prefix web`。
- 启动后端和 Vite 开发服务器，在浏览器中验证空书架、材料列表和阅读页入口。

## Completion Notes

已完成。

- 在 `web/` 建立 React + Vite + TypeScript 前端项目，并使用 React Router 提供书架页和阅读页路由。
- 新增真实材料列表和材料详情 API；不存在材料返回中文 `404` 详情。
- 书架页覆盖加载、空状态、错误状态和材料卡片，材料卡片可进入阅读页入口。
- 阅读页入口展示标题和主来源，正文阅读界面明确留给下一任务。
- Vite 开发服务器通过 `/api` 代理访问本地后端，无需新增 CORS。
- README 已补充前端开发和构建命令，忽略规则已覆盖前端依赖、构建产物和 TypeScript 构建缓存。
- 浏览器验收通过：空书架、真实材料卡片、阅读页入口和不存在材料错误状态均正常，控制台无错误。
- `uv run --no-editable pytest`：115 个测试通过。
- `uv run --no-editable ruff check .`：通过。
- `uv run --no-editable mypy src tests`：通过。
- `npm run build --prefix web`：通过。
