# 只接受当前真实六表数据库结构

Read Along 当前只接受 `src/read_along/database_schema.py` 中 `CURRENT_SCHEMA_SQL` 对应的真实六表结构。数据库文件不存在时创建新库；数据库文件已存在但结构不匹配时，应用保持文件不变并拒绝启动。项目不再识别、接管、修复或备份旧五表、半迁移、Alembic baseline 或其他历史结构，以降低本地个人工具的维护复杂度。

ADR-0004 对 time-navigation 之前的上一版真实六表结构记录了一个受限兼容例外；该例外不改变本决策对未知结构和任意历史结构的默认拒绝策略。
