import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from read_along.config import AppConfig
from read_along.db import SCHEMA, DatabaseSchemaError, connect_database, initialize_database
from read_along.storage import StoragePaths

EXPECTED_TABLES = {
    'import_jobs',
    'material_sources',
    'materials',
    'paragraphs',
    'reading_progress',
    'sentences',
}


def storage_paths(tmp_path: Path) -> StoragePaths:
    return StoragePaths.from_config(AppConfig(home=tmp_path / 'data'))


def insert_material(connection: sqlite3.Connection, material_id: str = 'mat-1') -> None:
    connection.execute(
        """
        INSERT INTO materials (id, title, content_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            material_id,
            'Example',
            f'hash-{material_id}',
            '2026-06-06T00:00:00Z',
            '2026-06-06T00:00:00Z',
        ),
    )


def test_initialize_database_creates_expected_schema(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)

    initialize_database(paths)

    assert paths.database.is_file()
    with closing(connect_database(paths.database)) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        sentence_columns = {row['name']: row for row in connection.execute('PRAGMA table_info(sentences)').fetchall()}
        progress_columns = {
            row['name']: row for row in connection.execute('PRAGMA table_info(reading_progress)').fetchall()
        }
    assert {row['name'] for row in rows} == EXPECTED_TABLES
    assert sentence_columns['audio_duration_seconds']['notnull'] == 0
    assert progress_columns['sentence_offset_seconds']['notnull'] == 1
    assert progress_columns['sentence_offset_seconds']['dflt_value'] == '0'


def test_initialize_database_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)
    with closing(connect_database(paths.database)) as connection:
        insert_material(connection)
        connection.commit()

    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        row = connection.execute(
            'SELECT title FROM materials WHERE id = ?',
            ('mat-1',),
        ).fetchone()
    assert row is not None
    assert row['title'] == 'Example'


def test_initialize_database_rejects_legacy_material_schema_without_modifying_it(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    paths.ensure_directories()
    with closing(connect_database(paths.database)) as connection:
        connection.executescript(
            """
            CREATE TABLE materials (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL CHECK (source_type IN ('url', 'pdf')),
                source_uri TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('importing', 'ready', 'failed')),
                content_hash TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            """
        )
    before = paths.database.read_bytes()

    with pytest.raises(DatabaseSchemaError, match='不支持当前数据库结构'):
        initialize_database(paths)

    assert paths.database.read_bytes() == before


def test_initialize_database_rejects_half_migrated_schema_without_modifying_it(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)
    with closing(connect_database(paths.database)) as connection:
        connection.execute('DROP TABLE material_sources')
        connection.executescript(
            """
            CREATE TABLE material_sources (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL REFERENCES "materials_legacy" (id) ON DELETE CASCADE,
                source_type TEXT NOT NULL CHECK (source_type IN ('url', 'pdf')),
                source_key TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                source_path TEXT,
                is_primary INTEGER NOT NULL CHECK (is_primary IN (0, 1)),
                created_at TEXT NOT NULL,
                UNIQUE (source_type, source_key)
            );

            CREATE UNIQUE INDEX idx_material_sources_one_primary
            ON material_sources (material_id) WHERE is_primary = 1;

            CREATE INDEX idx_material_sources_material_id
            ON material_sources (material_id);
            """
        )
    before = paths.database.read_bytes()

    with pytest.raises(DatabaseSchemaError, match='不支持当前数据库结构'):
        initialize_database(paths)

    assert paths.database.read_bytes() == before


def test_initialize_database_rejects_schema_without_playback_completed_without_modifying_it(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    paths.ensure_directories()
    completed_column = '    playback_completed INTEGER NOT NULL CHECK (playback_completed IN (0, 1)),\n'
    legacy_schema = SCHEMA.replace(completed_column, '')
    assert legacy_schema != SCHEMA
    with closing(connect_database(paths.database)) as connection:
        connection.executescript(legacy_schema)
    before = paths.database.read_bytes()

    with pytest.raises(DatabaseSchemaError, match='不支持当前数据库结构'):
        initialize_database(paths)

    assert paths.database.read_bytes() == before


def test_initialize_database_migrates_previous_time_navigation_schema_with_backup(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    paths.ensure_directories()
    duration_column = (
        '    audio_duration_seconds REAL CHECK (audio_duration_seconds IS NULL OR audio_duration_seconds >= 0),\n'
    )
    offset_column = '    sentence_offset_seconds REAL NOT NULL DEFAULT 0 CHECK (sentence_offset_seconds >= 0),\n'
    legacy_schema = SCHEMA.replace(duration_column, '').replace(offset_column, '')
    assert legacy_schema != SCHEMA
    with closing(connect_database(paths.database)) as connection:
        connection.executescript(legacy_schema)
        insert_material(connection)
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text)
            VALUES (?, ?, ?, ?)
            """,
            ('paragraph-1', 'mat-1', 1, 'Paragraph'),
        )
        connection.execute(
            """
            INSERT INTO sentences (
                id, material_id, paragraph_id, "index", text, audio_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ('sentence-1', 'mat-1', 'paragraph-1', 1, 'Sentence.', 'pending'),
        )
        connection.execute(
            """
            INSERT INTO reading_progress (
                material_id, sentence_id, playback_rate, playback_completed, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ('mat-1', 'sentence-1', 1.0, 0, '2026-06-06T00:00:00Z'),
        )
        connection.commit()
    before = paths.database.read_bytes()
    backup = paths.database.with_name(f'{paths.database.name}.before-time-navigation')

    initialize_database(paths)

    assert backup.read_bytes() == before
    with closing(connect_database(paths.database)) as connection:
        sentence = connection.execute('SELECT audio_duration_seconds FROM sentences').fetchone()
        progress = connection.execute('SELECT sentence_offset_seconds FROM reading_progress').fetchone()
    assert sentence is not None
    assert sentence['audio_duration_seconds'] is None
    assert progress is not None
    assert progress['sentence_offset_seconds'] == 0


def test_initialize_database_migration_backup_does_not_overwrite_existing_backup(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    paths.ensure_directories()
    duration_column = (
        '    audio_duration_seconds REAL CHECK (audio_duration_seconds IS NULL OR audio_duration_seconds >= 0),\n'
    )
    offset_column = '    sentence_offset_seconds REAL NOT NULL DEFAULT 0 CHECK (sentence_offset_seconds >= 0),\n'
    legacy_schema = SCHEMA.replace(duration_column, '').replace(offset_column, '')
    with closing(connect_database(paths.database)) as connection:
        connection.executescript(legacy_schema)
    first_backup = paths.database.with_name(f'{paths.database.name}.before-time-navigation')
    first_backup.write_bytes(b'existing backup')

    initialize_database(paths)

    backup_paths = sorted(paths.database.parent.glob(f'{paths.database.name}.before-time-navigation*'))
    assert first_backup.read_bytes() == b'existing backup'
    assert len(backup_paths) == 2
    assert any(path.name.endswith('.1') for path in backup_paths)


def test_initialize_database_rejects_existing_empty_database(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    paths.ensure_directories()
    paths.database.touch()

    with pytest.raises(DatabaseSchemaError, match='不支持当前数据库结构'):
        initialize_database(paths)


def test_initialize_database_rejects_changed_current_schema(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)
    with closing(connect_database(paths.database)) as connection:
        connection.execute('DROP INDEX idx_sentences_paragraph_id')

    with pytest.raises(DatabaseSchemaError, match='不支持当前数据库结构'):
        initialize_database(paths)


def test_connect_database_enables_foreign_keys(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        foreign_keys = connection.execute('PRAGMA foreign_keys').fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO paragraphs (id, material_id, "index", text)
                VALUES (?, ?, ?, ?)
                """,
                ('paragraph-1', 'missing-material', 1, 'Text'),
            )

    assert foreign_keys is not None
    assert foreign_keys[0] == 1


def test_schema_rejects_cross_material_content_relationships(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        insert_material(connection, 'mat-1')
        insert_material(connection, 'mat-2')
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text)
            VALUES (?, ?, ?, ?)
            """,
            ('paragraph-1', 'mat-1', 1, 'Paragraph'),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO sentences (
                    id, material_id, paragraph_id, "index", text, audio_status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ('sentence-1', 'mat-2', 'paragraph-1', 1, 'Sentence.', 'pending'),
            )

        connection.execute(
            """
            INSERT INTO sentences (
                id, material_id, paragraph_id, "index", text, audio_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ('sentence-1', 'mat-1', 'paragraph-1', 1, 'Sentence.', 'pending'),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO reading_progress (
                    material_id, sentence_id, sentence_offset_seconds, playback_rate, playback_completed, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ('mat-2', 'sentence-1', 0, 1.0, 0, '2026-06-06T00:00:00Z'),
            )


def test_deleting_material_cascades_to_reading_content_and_progress(
    tmp_path: Path,
) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        insert_material(connection)
        connection.execute(
            """
            INSERT INTO material_sources (
                id, material_id, source_type, source_key, source_uri, is_primary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'source-1',
                'mat-1',
                'pdf',
                'source-key',
                'example.pdf',
                1,
                '2026-06-06T00:00:00Z',
            ),
        )
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text)
            VALUES (?, ?, ?, ?)
            """,
            ('paragraph-1', 'mat-1', 1, 'Paragraph'),
        )
        connection.execute(
            """
            INSERT INTO sentences (
                id, material_id, paragraph_id, "index", text, audio_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ('sentence-1', 'mat-1', 'paragraph-1', 1, 'Sentence.', 'pending'),
        )
        connection.execute(
            """
            INSERT INTO reading_progress (
                material_id, sentence_id, playback_rate, playback_completed, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ('mat-1', 'sentence-1', 1.0, 0, '2026-06-06T00:00:00Z'),
        )
        connection.execute('DELETE FROM materials WHERE id = ?', ('mat-1',))
        connection.commit()

        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            for table in ('material_sources', 'paragraphs', 'sentences', 'reading_progress')
        }

    assert counts == {
        'material_sources': 0,
        'paragraphs': 0,
        'sentences': 0,
        'reading_progress': 0,
    }
