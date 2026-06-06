# Task 001：Read Along 后端服务骨架

## Task ID

`001-reader-service-skeleton`

## Task Title

建立 Read Along FastAPI 空服务和健康检查。

## Backlog Reference

`MVP-001`：本地 FastAPI 服务。

## Goal

为 Read Along 建立最小后端入口，使开发者可以通过：

```bash
uv run --no-editable read-along serve
```

启动只绑定本机的 FastAPI 服务，并通过健康检查确认服务可用。

## Scope

- 新增 `src/read_along/` 后端模块骨架。
- 新增 FastAPI app 工厂和 `GET /api/health`。
- 在现有 Typer CLI 中新增 `serve` 子命令。
- 服务默认绑定 `127.0.0.1:8765`。
- 启动前检查监听地址可用，失败时输出清晰错误。
- 新增与健康检查和 CLI 入口相关的自动测试。
- 为本轮代码任务补齐最小 `ruff` 和 `mypy` 配置。

## Non-goals

- 不实现 SQLite、本地数据目录或 repository。
- 不实现 PDF 导入。
- 不实现网页导入或 Chrome 会话桥接。
- 不实现正文清洗、句子切分、TTS、音频缓存或前端。
- 不实现其他历史功能。

## Implementation Notes

- Read Along app 使用 `read_along.api:create_app` 创建，模块级 `app` 供 Uvicorn 导入。
- CLI 使用顶层 `serve` 命令。
- `serve` 使用 Uvicorn 运行 `read_along.api:app`，默认 host 和 port 与技术方案一致。
- 地址占用、host 无法解析或缺少服务依赖时返回非零退出码，并给出明确错误。

## Acceptance Criteria

- 存在 `src/read_along/` 后端模块。
- `GET /api/health` 返回 200 和可判断服务正常的 JSON。
- `read-along serve` 命令存在。
- 默认监听参数为 `127.0.0.1:8765`。
- 端口或 host 不可用时，CLI 输出清晰错误并退出。
- 未实现当前任务非目标中的功能。

## Test Plan

- 使用 FastAPI `TestClient` 验证 `/api/health`。
- 使用 Typer `CliRunner` 验证根命令挂载了 `serve`。
- 使用 monkeypatch 验证 `serve` 的默认 host、port 和 Uvicorn app 路径。
- 使用 monkeypatch 验证启动前 bind 失败时的错误输出。
- 运行：

```bash
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
```

## Completion Notes

已完成。

- 新增 `read_along` 后端模块，提供 FastAPI app 工厂和模块级 `app`。
- 新增 `GET /api/health`，返回 `{"status": "ok", "service": "read-along"}`。
- 在根 Typer CLI 下挂载 `serve`，默认绑定 `127.0.0.1:8765`。
- 启动前会检查 host/port 可绑定；不可用或缺少 Uvicorn 时以非零退出码输出错误。
- 已新增 API 和 CLI 自动测试。
- 已补齐 `fastapi`、`uvicorn`、`ruff`、`mypy` 依赖与最小配置。

验证结果：

```bash
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
```

以上检查均已通过。`pytest` 有一个来自 FastAPI/Starlette `TestClient` 的上游弃用警告，不影响本任务验收。
