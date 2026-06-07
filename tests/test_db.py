import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from read_along.config import AppConfig
from read_along.db import connect_database, initialize_database
from read_along.storage import StoragePaths


EXPECTED_TABLES = {
    "import_jobs",
    "material_sources",
    "materials",
    "paragraphs",
    "reading_progress",
    "sentences",
}


def storage_paths(tmp_path: Path) -> StoragePaths:
    return StoragePaths.from_config(AppConfig(home=tmp_path / "data"))


def insert_material(connection: sqlite3.Connection, material_id: str = "mat-1") -> None:
    connection.execute(
        """
        INSERT INTO materials (id, title, content_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            material_id,
            "Example",
            f"hash-{material_id}",
            "2026-06-06T00:00:00Z",
            "2026-06-06T00:00:00Z",
        ),
    )


def test_initialize_database_creates_expected_schema(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)

    initialize_database(paths)

    assert paths.database.is_file()
    with closing(connect_database(paths.database)) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert {row["name"] for row in rows} == EXPECTED_TABLES


def test_initialize_database_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)
    with closing(connect_database(paths.database)) as connection:
        insert_material(connection)
        connection.commit()

    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        row = connection.execute(
            "SELECT title FROM materials WHERE id = ?",
            ("mat-1",),
        ).fetchone()
    assert row is not None
    assert row["title"] == "Example"


def test_connect_database_enables_foreign_keys(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO paragraphs (id, material_id, "index", text)
                VALUES (?, ?, ?, ?)
                """,
                ("paragraph-1", "missing-material", 1, "Text"),
            )

    assert foreign_keys is not None
    assert foreign_keys[0] == 1


def test_schema_rejects_cross_material_content_relationships(tmp_path: Path) -> None:
    paths = storage_paths(tmp_path)
    initialize_database(paths)

    with closing(connect_database(paths.database)) as connection:
        insert_material(connection, "mat-1")
        insert_material(connection, "mat-2")
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text)
            VALUES (?, ?, ?, ?)
            """,
            ("paragraph-1", "mat-1", 1, "Paragraph"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO sentences (
                    id, material_id, paragraph_id, "index", text, audio_status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("sentence-1", "mat-2", "paragraph-1", 1, "Sentence.", "pending"),
            )

        connection.execute(
            """
            INSERT INTO sentences (
                id, material_id, paragraph_id, "index", text, audio_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("sentence-1", "mat-1", "paragraph-1", 1, "Sentence.", "pending"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO reading_progress (
                    material_id, sentence_id, playback_rate, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                ("mat-2", "sentence-1", 1.0, "2026-06-06T00:00:00Z"),
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
                "source-1",
                "mat-1",
                "pdf",
                "source-key",
                "example.pdf",
                1,
                "2026-06-06T00:00:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text)
            VALUES (?, ?, ?, ?)
            """,
            ("paragraph-1", "mat-1", 1, "Paragraph"),
        )
        connection.execute(
            """
            INSERT INTO sentences (
                id, material_id, paragraph_id, "index", text, audio_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("sentence-1", "mat-1", "paragraph-1", 1, "Sentence.", "pending"),
        )
        connection.execute(
            """
            INSERT INTO reading_progress (
                material_id, sentence_id, playback_rate, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            ("mat-1", "sentence-1", 1.0, "2026-06-06T00:00:00Z"),
        )
        connection.execute("DELETE FROM materials WHERE id = ?", ("mat-1",))
        connection.commit()

        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("material_sources", "paragraphs", "sentences", "reading_progress")
        }

    assert counts == {
        "material_sources": 0,
        "paragraphs": 0,
        "sentences": 0,
        "reading_progress": 0,
    }
