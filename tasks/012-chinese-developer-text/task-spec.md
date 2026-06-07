# Task 012：统一代码与测试说明文本为中文

## Task ID

`012-chinese-developer-text`

## Task Title

统一代码与测试说明文本为中文

## Backlog Reference

支撑性质量任务；落实 `~/.codex/AGENTS.md` 的语言规范，不对应独立产品 Backlog。

## Goal

将 `src/` 与 `tests/` 中面向开发者或最终用户的英文说明文本统一为中文，同时保持代码标识符、协议契约和英文文本处理覆盖不变。

## Scope

- 翻译 Python 注释与 docstring。
- 翻译内部错误信息、CLI 帮助与 CLI 输出。
- 翻译 API 面向最终用户的错误 `detail`，保持字段名和状态码不变。
- 浏览器桥接异常使用中文上下文，并保留第三方原始错误。
- 将 PDF 来源标签从 `Page N, Block M` 改为 `第 N 页，第 M 段`。
- 翻译测试注释、测试 docstring 和与已翻译错误对应的断言。

## Non-goals

- 不修改 `docs/`、历史 `tasks/*/task-spec.md` 或其他开发文档。
- 不修改变量名、函数名、类名、文件名或测试函数名。
- 不翻译协议字段、错误码、枚举值、数据库标识符、命令参数和机器解析固定文本。
- 不翻译用于覆盖英文或中英混合文本处理的测试夹具。
- 不翻译第三方返回的原始错误信息。

## Implementation Notes

- 保留 `url`、`pdf`、`ready`、`pending` 等固定协议值。
- 保留 JavaScript、Chrome DevTools 和 WebSocket 所需的 API 字段与固定值。
- 用户可见异常采用“中文上下文：第三方原始错误”的格式。
- 必要英文技术术语和产品名保留英文。

## Acceptance Criteria

- `src/` 中现有英文注释、docstring、内部错误和用户文案均按范围翻译。
- `tests/` 中现有英文注释、docstring 和相关失败断言均按范围翻译。
- PDF 来源标签使用中文格式。
- 固定协议值、代码标识符和英文处理测试夹具保持不变。
- 全量测试、Ruff 和 mypy 通过。

## Test Plan

- 运行 `uv run --no-editable pytest`。
- 运行 `uv run --no-editable ruff check .`。
- 运行 `uv run --no-editable mypy src tests`。
- 使用 `rg` 复查 `src/` 和 `tests/` 中剩余英文注释、docstring 与错误文本，确认均属于保留范围。

## Completion Notes

- 已翻译 `src/` 中的注释、docstring、内部错误信息、CLI/API 用户文案和浏览器桥接异常上下文。
- 已将 PDF 来源标签改为 `第 N 页，第 M 段`。
- 已翻译 `tests/` 中的测试说明、注释和相关错误断言，并新增 API 中文错误文案与浏览器原始错误保留的回归测试。
- 已保留代码标识符、协议字段、固定状态值、英文处理测试夹具和第三方原始错误。
- `uv run --no-editable pytest`：104 个测试通过。
- `uv run --no-editable ruff check .`：通过。
- `uv run --no-editable mypy src tests`：通过。
