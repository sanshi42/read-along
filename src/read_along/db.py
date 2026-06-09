from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit

from read_along.ids import generate_source_id
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


def connect_database(database: Path) -> sqlite3.Connection:
    """打开启用外键约束的 SQLite 连接。"""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def initialize_database(paths: StoragePaths) -> None:
    """初始化本地 SQLite schema。"""
    paths.ensure_directories()
    with closing(connect_database(paths.database)) as connection:
        _migrate_legacy_materials_schema(connection)
        _repair_material_sources_legacy_fk(connection)
        connection.executescript(SCHEMA)


def _migrate_legacy_materials_schema(connection: sqlite3.Connection) -> None:
    """将材料库拆分前的旧 materials 单表 schema 迁移到当前 schema。"""
    if not _table_exists(connection, 'materials'):
        return

    material_columns = _table_columns(connection, 'materials')
    legacy_columns = {'source_type', 'source_uri', 'status', 'error_message'}
    if not legacy_columns.issubset(material_columns):
        return

    legacy_tables = {
        table
        for table in ('material_sources', 'paragraphs', 'sentences', 'reading_progress', 'import_jobs')
        if _table_exists(connection, table)
    }
    connection.execute('PRAGMA foreign_keys = OFF')
    try:
        connection.execute('ALTER TABLE materials RENAME TO materials_legacy')
        for table in legacy_tables:
            connection.execute(f'ALTER TABLE {table} RENAME TO {table}_legacy')
        _drop_legacy_indexes(connection)
        connection.executescript(SCHEMA)

        legacy_materials = connection.execute(
            """
            SELECT id, source_type, source_uri, title, content_hash, created_at, updated_at
            FROM materials_legacy
            """
        ).fetchall()
        inserted_material_ids = _copy_legacy_materials(connection, legacy_materials)
        primary_material_ids, used_source_identities = _copy_legacy_material_sources(connection, legacy_tables)
        _copy_legacy_sources(
            connection,
            legacy_materials,
            inserted_material_ids,
            primary_material_ids,
            used_source_identities,
        )
        _copy_legacy_reading_body(connection, legacy_tables)
        _copy_legacy_import_jobs(connection, legacy_tables)

        for table in ('import_jobs', 'reading_progress', 'sentences', 'paragraphs', 'material_sources', 'materials'):
            legacy_table = f'{table}_legacy'
            if _table_exists(connection, legacy_table):
                connection.execute(f'DROP TABLE {legacy_table}')
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.execute('PRAGMA foreign_keys = ON')


def _repair_material_sources_legacy_fk(connection: sqlite3.Connection) -> None:
    """修复曾被迁移到引用 materials_legacy 的 material_sources 表。"""
    if not _table_exists(connection, 'material_sources'):
        return
    if 'materials_legacy' not in _foreign_key_tables(connection, 'material_sources'):
        return

    connection.execute('PRAGMA foreign_keys = OFF')
    try:
        connection.execute('ALTER TABLE material_sources RENAME TO material_sources_legacy')
        _drop_legacy_indexes(connection)
        connection.executescript(SCHEMA)
        _copy_legacy_material_sources(connection, {'material_sources'})
        connection.execute('DROP TABLE material_sources_legacy')
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.execute('PRAGMA foreign_keys = ON')


def _copy_legacy_materials(
    connection: sqlite3.Connection,
    legacy_materials: list[sqlite3.Row],
) -> set[str]:
    inserted_material_ids: set[str] = set()
    used_content_hashes: set[str] = set()
    for row in legacy_materials:
        content_hash = _legacy_content_hash(
            material_id=str(row['id']),
            content_hash=str(row['content_hash'] or ''),
            used_hashes=used_content_hashes,
        )
        connection.execute(
            """
            INSERT INTO materials (id, title, content_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row['id'],
                row['title'],
                content_hash,
                row['created_at'],
                row['updated_at'],
            ),
        )
        inserted_material_ids.add(str(row['id']))
    return inserted_material_ids


def _copy_legacy_sources(
    connection: sqlite3.Connection,
    legacy_materials: list[sqlite3.Row],
    inserted_material_ids: set[str],
    primary_material_ids: set[str],
    used_source_identities: set[tuple[str, str]],
) -> None:
    for row in legacy_materials:
        material_id = str(row['id'])
        if material_id not in inserted_material_ids or material_id in primary_material_ids:
            continue
        source_type = str(row['source_type'])
        source_uri = str(row['source_uri'])
        source_key = _legacy_source_key(source_type=source_type, source_uri=source_uri)
        identity = (source_type, source_key)
        if identity in used_source_identities:
            source_key = f'{source_key}#legacy-{material_id}'
        used_source_identities.add((source_type, source_key))
        connection.execute(
            """
            INSERT INTO material_sources (
                id, material_id, source_type, source_key, source_uri, source_path, is_primary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_source_id(source_type, source_key),
                material_id,
                source_type,
                source_key,
                source_uri,
                None,
                1,
                row['created_at'],
            ),
        )


def _copy_legacy_material_sources(
    connection: sqlite3.Connection,
    legacy_tables: set[str],
) -> tuple[set[str], set[tuple[str, str]]]:
    primary_material_ids: set[str] = set()
    used_source_identities: set[tuple[str, str]] = set()
    if 'material_sources' not in legacy_tables:
        return primary_material_ids, used_source_identities

    legacy_sources = connection.execute(
        """
        SELECT id, material_id, source_type, source_key, source_uri, source_path, is_primary, created_at
        FROM material_sources_legacy
        WHERE material_id IN (SELECT id FROM materials)
        """
    ).fetchall()
    for row in legacy_sources:
        source_type = str(row['source_type'])
        source_key = str(row['source_key'])
        identity = (source_type, source_key)
        if identity in used_source_identities:
            continue
        used_source_identities.add(identity)
        if int(row['is_primary']) == 1:
            primary_material_ids.add(str(row['material_id']))
        connection.execute(
            """
            INSERT INTO material_sources (
                id, material_id, source_type, source_key, source_uri, source_path, is_primary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row['id'],
                row['material_id'],
                source_type,
                source_key,
                row['source_uri'],
                row['source_path'],
                row['is_primary'],
                row['created_at'],
            ),
        )
    return primary_material_ids, used_source_identities


def _copy_legacy_reading_body(
    connection: sqlite3.Connection,
    legacy_tables: set[str],
) -> None:
    if 'paragraphs' in legacy_tables:
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text, source_label)
            SELECT id, material_id, "index", text, source_label
            FROM paragraphs_legacy
            WHERE material_id IN (SELECT id FROM materials)
            """
        )
    if 'sentences' in legacy_tables:
        connection.execute(
            """
            INSERT INTO sentences (
                id, material_id, paragraph_id, "index", text, audio_status, audio_path, error_message
            )
            SELECT id, material_id, paragraph_id, "index", text, audio_status, audio_path, error_message
            FROM sentences_legacy
            WHERE material_id IN (SELECT id FROM materials)
              AND paragraph_id IN (SELECT id FROM paragraphs)
            """
        )
    if 'reading_progress' in legacy_tables:
        connection.execute(
            """
            INSERT INTO reading_progress (material_id, sentence_id, playback_rate, updated_at)
            SELECT material_id, sentence_id, playback_rate, updated_at
            FROM reading_progress_legacy
            WHERE material_id IN (SELECT id FROM materials)
              AND sentence_id IN (SELECT id FROM sentences)
            """
        )


def _copy_legacy_import_jobs(
    connection: sqlite3.Connection,
    legacy_tables: set[str],
) -> None:
    if 'import_jobs' not in legacy_tables:
        return
    connection.execute(
        """
        INSERT INTO import_jobs (id, status, material_id, message, created_at, updated_at)
        SELECT
            id,
            status,
            CASE WHEN material_id IN (SELECT id FROM materials) THEN material_id ELSE NULL END,
            message,
            created_at,
            updated_at
        FROM import_jobs_legacy
        """
    )


def _legacy_content_hash(
    *,
    material_id: str,
    content_hash: str,
    used_hashes: set[str],
) -> str:
    if content_hash and content_hash not in used_hashes:
        used_hashes.add(content_hash)
        return content_hash
    deduped = hashlib.sha256(f'{content_hash}:{material_id}'.encode()).hexdigest()
    used_hashes.add(deduped)
    return deduped


def _legacy_source_key(*, source_type: str, source_uri: str) -> str:
    if source_type != 'url':
        return source_uri
    try:
        parsed = urlsplit(source_uri)
        port = parsed.port
    except ValueError:
        return source_uri

    scheme = parsed.scheme.lower()
    if scheme not in {'http', 'https'} or parsed.hostname is None:
        return source_uri
    host = parsed.hostname.lower()
    if ':' in host:
        host = f'[{host}]'
    default_port = (scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)
    netloc = host if port is None or default_port else f'{host}:{port}'
    return urlunsplit(
        SplitResult(
            scheme=scheme,
            netloc=netloc,
            path=parsed.path or '/',
            query=parsed.query,
            fragment='',
        )
    )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _foreign_key_tables(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row['table'] for row in connection.execute(f'PRAGMA foreign_key_list({table_name})').fetchall()}


def _drop_legacy_indexes(connection: sqlite3.Connection) -> None:
    for index_name in (
        'idx_materials_source_uri',
        'idx_materials_content_hash',
        'idx_material_sources_one_primary',
        'idx_material_sources_material_id',
        'idx_sentences_paragraph_id',
    ):
        connection.execute(f'DROP INDEX IF EXISTS {index_name}')


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row['name'] for row in connection.execute(f'PRAGMA table_info({table_name})').fetchall()}
