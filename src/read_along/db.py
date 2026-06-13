from __future__ import annotations

import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from read_along.storage import StoragePaths

SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS material_sources (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials (id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('url', 'pdf')),
    source_key TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    source_path TEXT,
    is_primary INTEGER NOT NULL CHECK (is_primary IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (source_type, source_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_material_sources_one_primary
ON material_sources (material_id) WHERE is_primary = 1;

CREATE INDEX IF NOT EXISTS idx_material_sources_material_id
ON material_sources (material_id);

CREATE TABLE IF NOT EXISTS paragraphs (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials (id) ON DELETE CASCADE,
    "index" INTEGER NOT NULL,
    text TEXT NOT NULL,
    source_label TEXT,
    UNIQUE (material_id, "index"),
    UNIQUE (id, material_id)
);

CREATE TABLE IF NOT EXISTS sentences (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials (id) ON DELETE CASCADE,
    paragraph_id TEXT NOT NULL,
    "index" INTEGER NOT NULL,
    text TEXT NOT NULL,
    audio_status TEXT NOT NULL CHECK (audio_status IN ('pending', 'ready', 'failed')),
    audio_path TEXT,
    error_message TEXT,
    UNIQUE (material_id, "index"),
    UNIQUE (id, material_id),
    FOREIGN KEY (paragraph_id, material_id)
        REFERENCES paragraphs (id, material_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sentences_paragraph_id
ON sentences (paragraph_id);

CREATE TABLE IF NOT EXISTS reading_progress (
    material_id TEXT PRIMARY KEY REFERENCES materials (id) ON DELETE CASCADE,
    sentence_id TEXT NOT NULL,
    playback_rate REAL NOT NULL CHECK (playback_rate > 0),
    updated_at TEXT NOT NULL,
    FOREIGN KEY (sentence_id, material_id)
        REFERENCES sentences (id, material_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    material_id TEXT REFERENCES materials (id) ON DELETE SET NULL,
    message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SchemaSignature = tuple[tuple[str, str, str, str], ...]


class DatabaseSchemaError(RuntimeError):
    """现有数据库结构不受当前应用支持。"""


def connect_database(database: Path) -> sqlite3.Connection:
    """打开启用外键约束的 SQLite 连接。"""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def initialize_database(paths: StoragePaths) -> None:
    """创建新数据库，或确认现有数据库使用当前六表结构。"""
    paths.ensure_directories()
    if not paths.database.exists():
        with closing(connect_database(paths.database)) as connection:
            connection.executescript(SCHEMA)
        return

    with closing(connect_database(paths.database)) as connection:
        if _schema_signature(connection) != _current_schema_signature():
            raise DatabaseSchemaError(
                f'不支持当前数据库结构：{paths.database}。请先移走或删除该数据库文件，再重新启动 Read Along。'
            )


def _schema_signature(connection: sqlite3.Connection) -> SchemaSignature:
    rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    return tuple(
        (
            str(row['type']),
            str(row['name']),
            str(row['tbl_name']),
            ' '.join(str(row['sql']).split()),
        )
        for row in rows
    )


@lru_cache(maxsize=1)
def _current_schema_signature() -> SchemaSignature:
    with closing(sqlite3.connect(':memory:')) as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA)
        return _schema_signature(connection)
