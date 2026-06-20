---
status: done
priority: P1
created: 2026-06-20
---

# 当前六表 schema Module Proposal

## Goal

加深“当前真实六表 schema 与兼容策略”的 Module，让启动路径、schema 漂移检测和唯一允许的窄迁移例外集中在一个清晰 Interface 后面。

目标完成后，`db.py` 不再直接拥有 schema 签名和兼容判断细节；ADR 会明确记录 time-navigation 窄迁移为何是旧“不自动迁移”规则的受限例外。

## Boundary

### In

- 将当前六表 `SCHEMA`、schema signature、当前结构判断和上一版 time-navigation 兼容判断集中到独立 Module。
- 保持现有启动行为：新库创建当前六表结构；当前结构原样通过；上一版 time-navigation schema 执行已有备份迁移；其他结构拒绝启动且不修改。
- 调整测试，让 schema policy 的 Interface 被直接覆盖。
- 新增或更新 ADR，说明 time-navigation 窄迁移与“不自动迁移”决策的关系。

### Out

- 改变数据库表结构、字段、索引或外键。
- 引入新的迁移系统或自动执行 Alembic。
- 处理任意更旧历史数据库、半迁移库或异常 SQLite 的恢复。
- 重构 SQLModel metadata 或 Alembic baseline。
