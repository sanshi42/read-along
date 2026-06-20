from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from read_along.database_schema import (
    CURRENT_SCHEMA_SQL,
    DatabaseSchemaError,
    SchemaSupport,
    classify_schema,
    create_current_schema,
    migrate_previous_time_navigation_schema,
)
from read_along.storage import StoragePaths

SCHEMA = CURRENT_SCHEMA_SQL


def connect_database(database: Path) -> sqlite3.Connection:
    """打开启用外键约束的 SQLite 连接。"""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def initialize_database(paths: StoragePaths) -> None:
    """创建新数据库，或确认现有数据库使用当前结构。"""
    paths.ensure_directories()
    if not paths.database.exists():
        with closing(connect_database(paths.database)) as connection:
            create_current_schema(connection)
        return

    with closing(connect_database(paths.database)) as connection:
        support = classify_schema(connection)
    if support is SchemaSupport.CURRENT:
        return
    if support is SchemaSupport.PREVIOUS_TIME_NAVIGATION:
        migrate_previous_time_navigation_schema(paths)
        return
    raise DatabaseSchemaError(
        f'不支持当前数据库结构：{paths.database}。请先移走或删除该数据库文件，再重新启动 Read Along。'
    )
