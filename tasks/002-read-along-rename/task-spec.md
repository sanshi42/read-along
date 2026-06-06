# Task 002：统一为 Read Along

## Task ID

`002-read-along-rename`

## Task Title

完成 Read Along 破坏性改名并删除旧学习笔记功能。

## Backlog Reference

支撑性工作；统一产品定位和工程命名，为后续 MVP 开发清除历史边界。

## Goal

让产品、代码、命令、文档和数据目录约定统一表达“边听边读、同步高亮”的 Read Along 应用。

## Scope

- 项目和 CLI 改为 `Read Along` / `read-along`。
- Python 包扁平化为 `src/read_along/`。
- 启动命令改为顶层 `read-along serve`。
- 前端目录约定改为 `web/`。
- 数据目录和环境变量约定改为 `~/.local/share/read-along/` 与 `READ_ALONG_HOME`。
- 删除旧学习笔记流水线、依赖、测试、样例和输出。
- 保留通用 Chrome 会话桥接。
- 将得到专用清洗规则迁入 `src/read_along/sources/dedao.py`。

## Non-goals

- 不提供旧名称、旧命令或旧包名兼容层。
- 不实现新的导入 API、存储、PDF、TTS 或前端功能。
- 不改变得到仍是首个重点来源的产品计划。

## Implementation Notes

- Read Along 定位为完整应用，不承诺公开 Python API。
- 通用浏览器读取与来源专用清洗规则分离。
- `serve` 是顶层命令，不保留重复的 `reader` 子命令。

## Acceptance Criteria

- `uv run --no-editable read-along serve` 指向 `read_along.api:app`。
- 健康检查返回服务标识 `read-along`。
- 代码和文档中不存在旧项目名、旧包名或旧数据目录约定。
- 旧学习笔记功能及其依赖、测试、样例和输出均已删除。
- 得到专用清洗规则由独立来源适配器覆盖测试。

## Test Plan

```bash
uv lock
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
```

另外全局搜索旧名称和旧笔记功能残留。

## Completion Notes

已完成。

- 产品、CLI、Python 包、服务标识、文档和目录约定已统一为 Read Along。
- Python 包已扁平化为 `src/read_along/`，顶层命令为 `read-along serve`。
- 旧学习笔记流水线、Ollama 依赖、相关测试、样例、输出和忽略规则已删除。
- Chrome 会话桥接保留在通用模块；得到识别与清洗规则迁入来源适配器。
- API 测试依赖改为显式声明 `httpx2`，不再依赖已删除依赖的传递安装。

验证结果：

```text
uv run --no-editable pytest              10 passed
uv run --no-editable ruff check .        passed
uv run --no-editable mypy src tests      passed
uv run --no-editable read-along --help   shows serve command
```
