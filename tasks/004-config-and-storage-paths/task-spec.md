# Task 004：配置与本地存储路径

## Task ID

`004-config-and-storage-paths`

## Task Title

建立本地数据目录配置和存储路径布局。

## Backlog Reference

`MVP-002`：本地存储；作为 SQLite schema 和 repository 的前置小任务。

## Goal

为 Read Along 提供统一、可测试的本地数据目录配置，并能创建后续存储所需的目录布局。

## Scope

- 新增应用配置模块，默认数据目录为 `~/.local/share/read-along/`。
- 支持通过 `READ_ALONG_HOME` 覆盖数据目录。
- 新增存储路径模块，统一派生 SQLite 文件、上传文件、音频和日志目录路径。
- 提供幂等的目录创建入口。
- 新增配置和存储路径相关自动测试。

## Non-goals

- 不初始化 SQLite schema 或创建 SQLite 文件。
- 不实现数据库连接、repository、材料模型或进度模型。
- 不实现上传、音频生成、日志写入或文件清理。
- 不新增其他环境变量或配置文件格式。

## Implementation Notes

- 配置读取保持无副作用；加载配置时不创建目录。
- 使用标准库 `pathlib.Path` 和 `dataclasses`，不新增配置依赖。
- 存储目录创建只包含根目录、`uploads/`、`audio/` 和 `logs/`。
- SQLite 文件路径固定为数据目录下的 `read-along.sqlite3`，由后续任务负责创建。

## Acceptance Criteria

- 未设置 `READ_ALONG_HOME` 时，数据目录为当前用户主目录下的 `.local/share/read-along/`。
- 设置 `READ_ALONG_HOME` 时，所有存储路径都基于覆盖后的目录。
- 可获得 `read-along.sqlite3`、`uploads/`、`audio/` 和 `logs/` 的统一路径。
- 目录创建入口可重复调用，且不会提前创建 SQLite 文件。
- 未实现当前任务非目标中的功能。

## Test Plan

- 验证默认数据目录。
- 验证 `READ_ALONG_HOME` 覆盖和 `~` 展开。
- 验证所有派生存储路径。
- 验证目录创建幂等，且不会创建 SQLite 文件。
- 运行：

```bash
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
```

## Completion Notes

已完成。

- 新增 `read_along.config`，默认使用 `~/.local/share/read-along/`，并支持 `READ_ALONG_HOME` 覆盖和 `~` 展开。
- 新增 `read_along.storage.StoragePaths`，统一派生 SQLite、上传、音频和日志路径。
- 新增幂等目录创建入口；配置加载和目录创建都不会提前创建 SQLite 文件。
- 已新增默认配置、环境覆盖、无副作用加载、路径派生和目录创建测试。

验证结果：

```text
uv run --no-editable pytest          16 passed
uv run --no-editable ruff check .    passed
uv run --no-editable mypy src tests  passed
git diff --check                     passed
```
