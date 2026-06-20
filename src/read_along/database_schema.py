from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from read_along.storage import StoragePaths

CURRENT_SCHEMA_SQL = """
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
    audio_duration_seconds REAL CHECK (audio_duration_seconds IS NULL OR audio_duration_seconds >= 0),
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
    sentence_offset_seconds REAL NOT NULL DEFAULT 0 CHECK (sentence_offset_seconds >= 0),
    playback_rate REAL NOT NULL CHECK (playback_rate > 0),
    playback_completed INTEGER NOT NULL CHECK (playback_completed IN (0, 1)),
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


class SchemaSupport(StrEnum):
    """启动路径支持的数据库结构类别。"""

    CURRENT = 'current'
    PREVIOUS_TIME_NAVIGATION = 'previous_time_navigation'
    UNSUPPORTED = 'unsupported'


def create_current_schema(connection: sqlite3.Connection) -> None:
    """在空数据库中创建当前真实六表结构。"""
    connection.executescript(CURRENT_SCHEMA_SQL)


def classify_schema(connection: sqlite3.Connection) -> SchemaSupport:
    """判断现有数据库结构是否属于当前支持范围。"""
    signature = schema_signature(connection)
    if signature == _current_schema_signature():
        return SchemaSupport.CURRENT
    if signature == _previous_time_navigation_schema_signature():
        return SchemaSupport.PREVIOUS_TIME_NAVIGATION
    return SchemaSupport.UNSUPPORTED


def schema_signature(connection: sqlite3.Connection) -> SchemaSignature:
    """读取数据库对象签名，用于判断 schema 是否属于支持范围。"""
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
            str(row[0]),
            str(row[1]),
            str(row[2]),
            ' '.join(str(row[3]).split()),
        )
        for row in rows
    )


def migrate_previous_time_navigation_schema(paths: StoragePaths) -> None:
    """将唯一支持的上一版六表结构升级为当前结构。"""
    backup = _next_backup_path(paths.database.with_name(f'{paths.database.name}.before-time-navigation'))
    temporary = paths.database.with_name(f'.{paths.database.name}.time-navigation-migration')
    try:
        shutil.copy2(paths.database, backup)
        temporary.unlink(missing_ok=True)
        with closing(_connect_database(temporary)) as connection:
            create_current_schema(connection)
            connection.execute('ATTACH DATABASE ? AS legacy', (str(backup),))
            connection.executescript(
                """
                INSERT INTO materials (id, title, content_hash, created_at, updated_at)
                SELECT id, title, content_hash, created_at, updated_at
                FROM legacy.materials;

                INSERT INTO material_sources (
                    id, material_id, source_type, source_key, source_uri, source_path, is_primary, created_at
                )
                SELECT id, material_id, source_type, source_key, source_uri, source_path, is_primary, created_at
                FROM legacy.material_sources;

                INSERT INTO paragraphs (id, material_id, "index", text, source_label)
                SELECT id, material_id, "index", text, source_label
                FROM legacy.paragraphs;

                INSERT INTO sentences (
                    id, material_id, paragraph_id, "index", text, audio_status,
                    audio_path, audio_duration_seconds, error_message
                )
                SELECT id, material_id, paragraph_id, "index", text, audio_status,
                       audio_path, NULL, error_message
                FROM legacy.sentences;

                INSERT INTO reading_progress (
                    material_id, sentence_id, sentence_offset_seconds,
                    playback_rate, playback_completed, updated_at
                )
                SELECT material_id, sentence_id, 0, playback_rate, playback_completed, updated_at
                FROM legacy.reading_progress;

                INSERT INTO import_jobs (id, status, material_id, message, created_at, updated_at)
                SELECT id, status, material_id, message, created_at, updated_at
                FROM legacy.import_jobs;
                """
            )
            connection.execute('DETACH DATABASE legacy')
            if classify_schema(connection) is not SchemaSupport.CURRENT:
                raise DatabaseSchemaError('迁移后的数据库结构不符合当前应用要求。')
            violations = connection.execute('PRAGMA foreign_key_check').fetchall()
            if violations:
                raise DatabaseSchemaError('迁移后的数据库外键校验失败。')
            connection.commit()
        temporary.replace(paths.database)
    except (OSError, sqlite3.Error) as exc:
        temporary.unlink(missing_ok=True)
        raise DatabaseSchemaError(f'升级数据库失败：{paths.database}。原数据库已保留。') from exc
    except DatabaseSchemaError:
        temporary.unlink(missing_ok=True)
        raise


def _connect_database(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def _next_backup_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path
    index = 1
    while True:
        candidate = base_path.with_name(f'{base_path.name}.{index}')
        if not candidate.exists():
            return candidate
        index += 1


@lru_cache(maxsize=1)
def _current_schema_signature() -> SchemaSignature:
    with closing(sqlite3.connect(':memory:')) as connection:
        create_current_schema(connection)
        return schema_signature(connection)


@lru_cache(maxsize=1)
def _previous_time_navigation_schema_signature() -> SchemaSignature:
    duration_column = (
        '    audio_duration_seconds REAL CHECK (audio_duration_seconds IS NULL OR audio_duration_seconds >= 0),\n'
    )
    offset_column = '    sentence_offset_seconds REAL NOT NULL DEFAULT 0 CHECK (sentence_offset_seconds >= 0),\n'
    previous_schema = CURRENT_SCHEMA_SQL.replace(duration_column, '').replace(offset_column, '')
    with closing(sqlite3.connect(':memory:')) as connection:
        connection.executescript(previous_schema)
        return schema_signature(connection)
