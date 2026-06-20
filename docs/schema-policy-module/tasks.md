# 当前六表 schema Module Tasks

## Task 1: Schema policy Interface

Goal: 新增 schema policy Module，让当前结构、上一版 time-navigation 兼容结构和不支持结构的判断可直接测试。

Depends on: none

Verification: 聚焦测试覆盖 policy Interface 的三类判断。

Status: Done

## Task 2: 启动路径接入

Goal: 让 `initialize_database` 通过 schema policy Module 决策，保持现有创建、通过、窄迁移和拒绝行为不变。

Depends on: Task 1

Verification: `tests/test_db.py` 继续覆盖启动路径行为。

Status: Done

## Task 3: ADR 例外记录与整体验证

Goal: 记录 time-navigation 窄迁移是“不自动迁移”规则的受限例外，并完成 Topic 级验证。

Depends on: Task 2

Verification: 文档之间不再冲突；运行 `make check`。

Status: Done
