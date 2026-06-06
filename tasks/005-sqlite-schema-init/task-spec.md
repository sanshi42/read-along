# Task 005：SQLite schema 初始化

## Task ID

`005-sqlite-schema-init`

## Task Title

基于本地存储路径初始化 SQLite schema。

## Backlog Reference

`MVP-002`：本地存储；为后续 `MVP-003` 数据模型和 repository 提供持久化基础。

## Goal

提供一个可重复调用的 SQLite 初始化入口，创建技术方案约定的材料、段落、句子、阅读进度和导入任务表。

## Scope

- 新增数据库模块，统一建立 SQLite 连接并启用外键约束。
- 初始化 `materials`、`paragraphs`、`sentences`、`reading_progress` 和 `import_jobs` 表。
- 为按材料顺序读取段落和句子、按 URL 或正文哈希查重增加必要索引。
- 初始化前创建所需本地存储目录。
- 新增 schema 初始化、幂等性、约束和持久化相关自动测试。

## Non-goals

- 不实现材料、段落、句子、进度或导入任务的 repository。
- 不实现数据迁移框架或 schema 版本升级。
- 不实现 API、导入、文本切分、PDF、网页或 TTS 功能。
- 不创建示例材料或业务数据。

## Implementation Notes

- 使用 Python 标准库 `sqlite3`，不新增依赖。
- schema 字段和状态值与 `docs/tech-design.md` 保持一致。
- 外键删除行为使用级联删除，保证未来删除材料时关联正文和进度可一并清理。
- `connect_database` 每次连接时启用 `PRAGMA foreign_keys = ON`。
- `initialize_database` 使用 `CREATE TABLE/INDEX IF NOT EXISTS`，可安全重复调用。

## Acceptance Criteria

- 初始化入口会创建数据库文件和五张约定表。
- 初始化入口可重复调用，不会删除或覆盖已有数据。
- 新连接启用 SQLite 外键约束。
- 段落、句子和阅读进度不能引用不存在的父记录。
- 关闭并重新打开数据库后，已写入的数据仍可读取。
- 未实现当前任务非目标中的功能。

## Test Plan

- 验证初始化会创建数据库文件和全部约定表。
- 验证重复初始化保留已有数据。
- 验证连接启用外键约束，非法父记录引用会失败。
- 验证关闭并重新打开数据库后数据仍存在。
- 运行：

```bash
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
git diff --check
```

## Completion Notes

已完成。

- 新增 `read_along.db`，提供统一 SQLite 连接和幂等 schema 初始化入口。
- 初始化 `materials`、`paragraphs`、`sentences`、`reading_progress` 和 `import_jobs` 五张表。
- 启用外键、级联删除、材料归属组合约束，并新增来源 URI、正文哈希和句子段落索引。
- 初始化会先创建本地存储目录，不会创建示例数据或实现 repository。
- 新增建表、幂等初始化、重启持久化、外键、跨材料关系和级联删除测试。

验证结果：

```text
uv run --no-editable pytest                    21 passed
uv run --no-editable ruff check .              passed
uv run --no-editable mypy src tests            passed
uv run --no-editable read-along --help         passed
git diff --check                               passed
```
