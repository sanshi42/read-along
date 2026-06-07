# Task 013：实现材料库持久化 Module

## Task ID

`013-material-library-module`

## Task Title

实现材料库持久化 Module。

## Backlog Reference

支撑 `MVP-002`、`MVP-003`、`MVP-004`、`MVP-015` 和 `MVP-020` 的共同材料库行为。

## Goal

将任务 `011-material-library-architecture` 收敛的设计落地为可用的 `MaterialLibrary`，让 PDF 等导入流程只生成 `ReadingMaterialDraft`，由材料库统一负责身份、重复判断、事务保存、完整读取、进度和删除生命周期。

## Scope

- 新增 `MaterialLibrary` 外部 Interface 和领域错误。
- 新增 `ReadingMaterialDraft`、来源身份、书架摘要等 DTO。
- 调整 SQLite schema，使阅读材料与多来源身份分离。
- 基于结构化正文生成 `content_hash` 和材料 ID。
- 实现 URL 规范化来源键和 PDF 文件字节来源键。
- 实现完整阅读材料的原子保存、重复导入处理、完整读取和书架列表。
- 实现经过归属与倍速校验的阅读进度保存。
- 实现幂等删除及源文件、音频缓存的尽力清理。
- 将 PDF 导入改为生成 Draft 后调用 `MaterialLibrary.save()`。

## Non-goals

- 不实现网页或得到导入。
- 不实现导入任务状态。
- 不实现前端页面。
- 不实现源内容刷新或覆盖已有阅读材料。
- 不为旧版开发期 SQLite schema 实现数据迁移。
- 不实现持久化的孤立文件清理重试队列。

## Implementation Notes

- `MaterialLibrary` 是通用调用方唯一使用的持久化 Interface；`Repository` 仅作为 Module 内部 SQLite 读写辅助。
- `content_hash` 只包含有序段落和句子正文，不包含来源 URI、标题或来源标记，使不同来源的相同结构化正文可复用同一阅读材料。
- 段落正文必须与其句子使用单个空格连接后的结果一致。
- 新阅读材料的主来源保存内部源文件副本；为现有阅读材料新增来源身份时不复制源文件。
- 源文件先复制到材料库临时路径，再在数据库提交前原子移动到最终路径；失败时回滚数据库并清理本次创建的文件。
- 删除提交后尽力清理材料库拥有的源文件和音频目录；清理失败不恢复数据库记录。

## Acceptance Criteria

- 保存合法 Draft 后可完整读取有序来源、段落、句子和空进度。
- 相同来源与正文重复保存返回已有阅读材料，不重复正文或源文件。
- 不同来源但正文相同会新增来源身份并复用阅读材料。
- 相同来源但正文变化会抛出 `SourceChangedError`，不修改已有阅读材料。
- 保存任一步失败时不会留下部分可见数据库记录。
- 书架按最近更新时间排序并返回主来源与进度摘要。
- 进度保存会拒绝不存在的材料、错误句子归属和非法倍速。
- 删除材料幂等，并级联删除正文、来源和进度。
- PDF API 继续可用，并通过材料库保存阅读材料。
- 全量测试、Ruff 和 mypy 通过。

## Test Plan

- 新增材料库单元测试，覆盖 Draft 校验、来源键、原子保存、重复导入、读取、书架、进度和删除。
- 更新 schema、模型、PDF 导入和 API 测试以匹配材料库 Interface。
- 运行 `uv run --no-editable pytest`。
- 运行 `uv run --no-editable ruff check .`。
- 运行 `uv run --no-editable mypy src tests`。

## Completion Notes

已完成。

- 新增 `MaterialLibrary`，实现原子保存、重复导入处理、书架列表、完整读取、进度保存和幂等删除。
- 新增 `ReadingMaterialDraft`、`MaterialSource`、`MaterialSummary` 等 DTO，并将阅读材料与来源身份分离。
- SQLite schema 新增 `material_sources`，约束正文哈希唯一、来源身份唯一和单一主来源。
- URL 来源键使用规范化 URL，PDF 来源键使用源文件字节 SHA-256；材料 ID 基于结构化正文哈希。
- PDF 导入改为生成 Draft 后调用材料库，API 依赖不再暴露细粒度 Repository。
- 新增材料库行为和 API 回归测试，覆盖 Draft 校验、来源复用、正文复用、来源冲突、事务回滚、文件清理、进度和删除。
- `uv run --no-editable pytest`：111 个测试通过。
- `uv run --no-editable ruff check .`：通过。
- `uv run --no-editable mypy src tests`：通过。
