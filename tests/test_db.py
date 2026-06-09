import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from read_along.config import AppConfig
from read_along.db import connect_database, initialize_database
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
    assert {row['name'] for row in rows} == EXPECTED_TABLES


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


def test_initialize_database_migrates_legacy_material_schema(tmp_path: Path) -> None:
    """旧版 materials 单表 schema 应迁移到当前 materials/material_sources schema。"""
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

            CREATE INDEX idx_materials_source_uri
            ON materials (source_uri);

            CREATE INDEX idx_materials_content_hash
            ON materials (content_hash);

            CREATE TABLE paragraphs (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL REFERENCES materials (id) ON DELETE CASCADE,
                "index" INTEGER NOT NULL,
                text TEXT NOT NULL,
                source_label TEXT,
                UNIQUE (material_id, "index"),
                UNIQUE (id, material_id)
            );

            CREATE TABLE sentences (
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

            CREATE INDEX idx_sentences_paragraph_id
            ON sentences (paragraph_id);

            CREATE TABLE reading_progress (
                material_id TEXT PRIMARY KEY REFERENCES materials (id) ON DELETE CASCADE,
                sentence_id TEXT NOT NULL,
                playback_rate REAL NOT NULL CHECK (playback_rate > 0),
                updated_at TEXT NOT NULL,
                FOREIGN KEY (sentence_id, material_id)
                    REFERENCES sentences (id, material_id) ON DELETE CASCADE
            );

            CREATE TABLE import_jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
                material_id TEXT REFERENCES materials (id) ON DELETE SET NULL,
                message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO materials (
                id, source_type, source_uri, title, status, content_hash, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'legacy-mat',
                'url',
                'https://example.com/legacy',
                '旧材料',
                'ready',
                'legacy-hash',
                None,
                '2026-06-06T00:00:00Z',
                '2026-06-06T00:00:00Z',
            ),
        )
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text)
            VALUES (?, ?, ?, ?)
            """,
            ('legacy-para', 'legacy-mat', 1, '旧段落。'),
        )
        connection.execute(
            """
            INSERT INTO sentences (
                id, material_id, paragraph_id, "index", text, audio_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ('legacy-sentence', 'legacy-mat', 'legacy-para', 1, '旧段落。', 'pending'),
        )
        connection.execute(
            """
            INSERT INTO reading_progress (material_id, sentence_id, playback_rate, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ('legacy-mat', 'legacy-sentence', 1.0, '2026-06-06T00:00:00Z'),
        )
        connection.execute(
            """
            INSERT INTO import_jobs (id, status, material_id, message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                'legacy-job',
                'done',
                'legacy-mat',
                '已完成',
                '2026-06-06T00:00:00Z',
                '2026-06-06T00:00:00Z',
            ),
        )
        connection.commit()

    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        material_columns = {row['name'] for row in connection.execute('PRAGMA table_info(materials)').fetchall()}
        legacy_material = connection.execute(
            'SELECT title, content_hash FROM materials WHERE id = ?',
            ('legacy-mat',),
        ).fetchone()
        legacy_source = connection.execute(
            """
            SELECT source_type, source_uri, is_primary
            FROM material_sources
            WHERE material_id = ?
            """,
            ('legacy-mat',),
        ).fetchone()
        legacy_job = connection.execute(
            'SELECT status, material_id FROM import_jobs WHERE id = ?',
            ('legacy-job',),
        ).fetchone()
        import_job_fk_tables = {
            row['table'] for row in connection.execute('PRAGMA foreign_key_list(import_jobs)').fetchall()
        }
        connection.execute(
            """
            INSERT INTO materials (id, title, content_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                'new-mat',
                '新材料',
                'new-hash',
                '2026-06-08T00:00:00Z',
                '2026-06-08T00:00:00Z',
            ),
        )

    assert 'source_type' not in material_columns
    assert 'status' not in material_columns
    assert legacy_material is not None
    assert legacy_material['title'] == '旧材料'
    assert legacy_source is not None
    assert legacy_source['source_type'] == 'url'
    assert legacy_source['source_uri'] == 'https://example.com/legacy'
    assert legacy_source['is_primary'] == 1
    assert legacy_job is not None
    assert legacy_job['status'] == 'done'
    assert legacy_job['material_id'] == 'legacy-mat'
    assert 'materials' in import_job_fk_tables
    assert 'materials_legacy' not in import_job_fk_tables


def test_initialize_database_repairs_material_sources_legacy_foreign_key(tmp_path: Path) -> None:
    """曾被半迁移成引用 materials_legacy 的来源表应自动重建。"""
    paths = storage_paths(tmp_path)
    paths.ensure_directories()
    with closing(connect_database(paths.database)) as connection:
        connection.executescript(
            """
            CREATE TABLE materials (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

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
        connection.execute(
            """
            INSERT INTO materials (id, title, content_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                'existing-mat',
                '已有材料',
                'existing-hash',
                '2026-06-09T00:00:00Z',
                '2026-06-09T00:00:00Z',
            ),
        )
        connection.commit()
        connection.execute('PRAGMA foreign_keys = OFF')
        connection.execute(
            """
            INSERT INTO material_sources (
                id, material_id, source_type, source_key, source_uri, is_primary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'existing-source',
                'existing-mat',
                'url',
                'https://example.com/existing',
                'https://example.com/existing',
                1,
                '2026-06-09T00:00:00Z',
            ),
        )
        connection.commit()

    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        source_fk_tables = {
            row['table'] for row in connection.execute('PRAGMA foreign_key_list(material_sources)').fetchall()
        }
        source = connection.execute(
            'SELECT material_id, source_uri FROM material_sources WHERE id = ?',
            ('existing-source',),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO material_sources (
                id, material_id, source_type, source_key, source_uri, is_primary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                'second-source',
                'existing-mat',
                'url',
                'https://example.com/second',
                'https://example.com/second',
                0,
                '2026-06-09T00:00:00Z',
            ),
        )

    assert source_fk_tables == {'materials'}
    assert source is not None
    assert source['material_id'] == 'existing-mat'
    assert source['source_uri'] == 'https://example.com/existing'


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
                    material_id, sentence_id, playback_rate, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                ('mat-2', 'sentence-1', 1.0, '2026-06-06T00:00:00Z'),
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
                material_id, sentence_id, playback_rate, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            ('mat-1', 'sentence-1', 1.0, '2026-06-06T00:00:00Z'),
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
