# 应用启动时自动迁移本地数据库

Read Along 是单用户本地应用，不要求用户手动管理数据库版本。应用每次启动时自动执行 `alembic upgrade head`；存在待执行迁移时先备份 SQLite 文件，迁移失败则保留原库和备份并拒绝启动。新数据库同样通过 Alembic 创建，不使用 `SQLModel.metadata.create_all()`，从而保证所有数据库都经过同一条可测试的 schema 演进路径。
