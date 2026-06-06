# Task 006：核心数据 Repository 基线

## Task ID

`006-repository-baseline`

## Task Title

建立材料、段落、句子和阅读进度的最小 repository。

## Backlog Reference

`MVP-002`：本地存储；完成核心阅读数据的持久化读写闭环，并为后续 `MVP-003` 数据模型和材料详情 API 提供基础。

## Goal

在现有 SQLite schema 之上提供一个轻量 repository，使材料、段落、句子和阅读进度可以被写入、重新打开数据库后读取，并保持正文顺序。

## Scope

- 新增 repository 模块，封装核心阅读数据的 SQLite 读写。
- 支持创建、获取和列出材料。
- 支持添加并按顺序读取材料的段落和句子。
- 支持保存、覆盖更新和读取每篇材料的阅读进度。
- 缺失的单条材料或阅读进度返回 `None`。
- 新增 repository 持久化、顺序读取和进度更新相关自动测试。

## Non-goals

- 不实现 `import_jobs` repository。
- 不实现 Pydantic DTO、领域模型或 API 响应结构。
- 不实现材料更新、删除、正文批量替换或导入事务编排。
- 不实现 PDF、网页、文本切分、TTS 或前端功能。
- 不引入 ORM、迁移框架或新依赖。

## Implementation Notes

- 使用 Python 标准库 `sqlite3` 和现有 `connect_database`。
- repository 以数据库文件路径构造；schema 初始化仍由现有 `initialize_database` 负责。
- 写入方法使用显式关键字参数，读取方法暂返回普通字典；后续任务再建立正式 DTO。
- 每次写入在方法成功结束时提交；数据库约束错误继续由 `sqlite3` 原样抛出。
- 材料列表按最近更新时间优先返回；段落和句子严格按各自 `"index"` 升序返回。
- 阅读进度以 `material_id` 为唯一键，重复保存时覆盖句子、倍速和更新时间。

## Acceptance Criteria

- 可以创建材料，并通过 ID 获取或列出材料。
- 关闭并重新打开 repository 后，材料、段落、句子和进度仍可读取。
- 段落和句子按 schema 定义的顺序返回，不依赖插入顺序。
- 同一材料重复保存阅读进度时，只保留最新值。
- 查询不存在的材料或进度时返回 `None`。
- 未实现当前任务非目标中的功能。

## Test Plan

- 验证材料创建、获取、列表顺序和跨 repository 实例持久化。
- 验证段落和句子按 `"index"` 升序读取。
- 验证阅读进度首次保存和重复覆盖更新。
- 验证查询不存在的材料和进度返回 `None`。
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

- 新增 `read_along.repository.Repository`，封装材料、段落、句子和阅读进度的 SQLite 读写。
- 材料支持创建、按 ID 获取和按最近更新时间列出。
- 段落和句子按各自 `"index"` 升序读取，不依赖插入顺序。
- 阅读进度按 `material_id` upsert，重复保存时覆盖为最新句子、倍速和更新时间。
- 读取结果暂使用普通字典，未提前实现后续任务的数据模型或 API。
- 新增 repository 持久化、缺失记录、顺序读取和进度覆盖更新测试。

验证结果：

```text
uv run --no-editable pytest                    25 passed
uv run --no-editable ruff check .              passed
uv run --no-editable mypy src tests            passed
uv run --no-editable read-along --help         passed
git diff --check                               passed
```
