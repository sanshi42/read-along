# 应用启动时不自动迁移现有数据库

Read Along 是单用户本地应用，当前启动路径不自动执行历史 schema 修复、接管或 `alembic upgrade head`。应用只创建不存在的新数据库，并校验已存在数据库是否精确匹配当前真实六表结构；不匹配时输出明确错误并拒绝启动。SQLModel 与 Alembic baseline 保留为独立技术基线，未来若切换生产 schema 路径，必须通过新的明确决策重新评估兼容边界。
