# Task 007：核心数据模型 DTO

## Task ID

`007-data-model-dtos`

## Task Title

建立与 repository 和后续材料详情 API 对齐的最小 Pydantic DTO。

## Backlog Reference

`MVP-003`：数据模型；在现有 SQLite schema 和 repository 基础上建立正式数据模型，为后续 PDF 导入、文本结构化和材料详情 API 提供稳定接口。

## Goal

用 Pydantic DTO 表达材料、段落、句子和阅读进度，使 repository 不再向调用方暴露无类型字典，并明确后续材料详情响应所需的嵌套正文结构。

## Scope

- 新增核心数据模型模块，定义材料、段落、句子和阅读进度 DTO。
- 用枚举约束现有 schema 中的来源类型、材料状态和音频状态。
- 定义段落详情和材料详情 DTO，使句子可按段落嵌套返回。
- repository 的读取方法返回正式 DTO 或 DTO 列表。
- 新增 DTO 校验、序列化、嵌套结构和 repository 类型返回相关自动测试。

## Non-goals

- 不实现材料详情 repository 查询或 API 路由。
- 不实现导入任务 DTO 或 import jobs repository。
- 不修改 SQLite schema、写入方法参数或数据库迁移方式。
- 不实现稳定 ID 的生成算法。
- 不实现 PDF、网页、文本切分、TTS 或前端功能。

## Implementation Notes

- 使用现有 Pydantic 依赖，不新增依赖。
- 核心 DTO 字段与现有 SQLite schema 保持一致；时间字段解析为带类型的 `datetime`。
- 状态枚举值与 SQLite `CHECK` 约束保持一致。
- repository 写入方法继续使用显式关键字参数；读取时通过 DTO 校验数据库行。
- `ParagraphDetail` 在段落 DTO 上增加句子列表；`MaterialDetail` 在材料 DTO 上增加可空进度和段落列表。
- 不在本任务中组装材料详情；后续详情查询任务负责按 repository 顺序构建嵌套 DTO。

## Acceptance Criteria

- 材料、段落、句子和阅读进度可从现有 repository 行数据校验为正式 DTO。
- 非法来源类型、材料状态、音频状态或非正播放倍速会被 DTO 拒绝。
- 材料详情 DTO 可以表达按段落嵌套的句子和可空阅读进度。
- repository 的单条查询返回 DTO 或 `None`，列表查询返回 DTO 列表。
- 现有 repository 持久化、排序和进度覆盖行为保持不变。
- 未实现当前任务非目标中的功能。

## Test Plan

- 验证核心 DTO 可校验现有 schema 行并序列化为 JSON 兼容数据。
- 验证状态枚举和播放倍速约束。
- 验证材料详情的段落和句子嵌套结构。
- 验证 repository 返回 DTO，同时保持缺失记录、列表顺序和进度更新行为。
- 运行：

```bash
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
uv run --no-editable read-along --help
git diff --check
```

## Completion Notes

已完成。

- 新增 `read_along.models`，定义材料、段落、句子、阅读进度以及材料详情嵌套 DTO。
- 来源类型、材料状态和音频状态使用与 SQLite schema 一致的枚举值。
- 阅读进度要求播放倍速为正数，所有 DTO 拒绝未声明字段。
- repository 单条和列表读取结果改为正式 DTO，写入接口和持久化行为保持不变。
- 新增模型校验、非法状态、播放倍速、材料详情嵌套以及 repository 类型返回测试。
- 未实现材料详情查询、API 路由或稳定 ID 生成；稳定 ID 生成保留为后续独立任务。

验证结果：

```text
uv run --no-editable pytest                    31 passed
uv run --no-editable ruff check .              passed
uv run --no-editable mypy src tests            passed
uv run --no-editable read-along --help         passed
git diff --check                               passed
```
