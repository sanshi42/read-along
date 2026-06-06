# Task 000：建立单任务推进工作流

## Task ID

`000-project-workflow`

## Task Title

建立单任务推进工作流文档。

## Backlog Reference

支撑性工作；对应 `docs/sprint-plan.md` 中 Sprint 0 的项目准备方向，不直接对应某个 MVP 用户故事。

## Goal

为后续敏捷开发建立清晰的执行规范：

- 每次只完成一个小任务。
- 每个任务都有独立 `task-spec.md`。
- 用 `progress.md` 记录当前完成情况和下一步。
- 用 `AGENTS.md` 指导未来协作者或代理继续工作。

## Scope

- 新增根目录 `AGENTS.md`。
- 新增 `tasks/progress.md`。
- 新增当前任务规格：`tasks/000-project-workflow/task-spec.md`。
- 明确任务目录命名、任务规格内容、进度更新规则和开发边界。

## Non-goals

- 不实现 Read Along 后端。
- 不实现前端。
- 不新增依赖。
- 不修改现有业务代码。
- 不变更 MVP 范围、backlog 或 Sprint 切分。

## Implementation Notes

- `AGENTS.md` 是项目级协作规则入口。
- `tasks/progress.md` 是滚动进度记录。
- 每个任务使用独立目录，避免多个任务共用同名 `task-spec.md`。
- 后续任务应从 `001-reader-service-skeleton` 开始，先实现 `MVP-001`。

## Acceptance Criteria

- 根目录存在 `AGENTS.md`。
- 存在 `tasks/progress.md`。
- 存在 `tasks/000-project-workflow/task-spec.md`。
- `AGENTS.md` 明确一次只做一个任务。
- `progress.md` 明确已完成任务和下一步建议。
- `task-spec.md` 明确本任务目标、范围、不做什么和验收标准。

## Test Plan

- 检查文件路径是否存在。
- 检查文档是否引用现有 `docs/` 下的规划文档。
- 检查本任务没有修改业务代码。

## Completion Notes

- 已完成。
- 后续开发应先创建 `tasks/001-reader-service-skeleton/task-spec.md`，再实现 Read Along 后端空服务和健康检查。
