from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from read_along.db import connect_database
from read_along.models import Material, Paragraph, ReadingProgress, Sentence


ModelT = TypeVar("ModelT", bound=BaseModel)


def _row_model(row: sqlite3.Row | None, model: type[ModelT]) -> ModelT | None:
    if row is None:
        return None
    return model.model_validate({key: row[key] for key in row.keys()})


def _rows_model(rows: list[sqlite3.Row], model: type[ModelT]) -> list[ModelT]:
    return [
        model.model_validate({key: row[key] for key in row.keys()})
        for row in rows
    ]


class Repository:
    def __init__(self, database: Path) -> None:
        self.database = database

    def create_material(
        self,
        *,
        material_id: str,
        source_type: str,
        source_uri: str,
        title: str,
        status: str,
        content_hash: str,
        error_message: str | None,
        created_at: str,
        updated_at: str,
    ) -> None:
        with closing(connect_database(self.database)) as connection:
            connection.execute(
                """
                INSERT INTO materials (
                    id,
                    source_type,
                    source_uri,
                    title,
                    status,
                    content_hash,
                    error_message,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material_id,
                    source_type,
                    source_uri,
                    title,
                    status,
                    content_hash,
                    error_message,
                    created_at,
                    updated_at,
                ),
            )
            connection.commit()

    def get_material(self, material_id: str) -> Material | None:
        with closing(connect_database(self.database)) as connection:
            row = connection.execute(
                "SELECT * FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
        return _row_model(row, Material)

    def list_materials(self) -> list[Material]:
        with closing(connect_database(self.database)) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM materials
                ORDER BY updated_at DESC, created_at DESC, id ASC
                """
            ).fetchall()
        return _rows_model(rows, Material)

    def add_paragraph(
        self,
        *,
        paragraph_id: str,
        material_id: str,
        index: int,
        text: str,
        source_label: str | None,
    ) -> None:
        with closing(connect_database(self.database)) as connection:
            connection.execute(
                """
                INSERT INTO paragraphs (id, material_id, "index", text, source_label)
                VALUES (?, ?, ?, ?, ?)
                """,
                (paragraph_id, material_id, index, text, source_label),
            )
            connection.commit()

    def list_paragraphs(self, material_id: str) -> list[Paragraph]:
        with closing(connect_database(self.database)) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM paragraphs
                WHERE material_id = ?
                ORDER BY "index" ASC, id ASC
                """,
                (material_id,),
            ).fetchall()
        return _rows_model(rows, Paragraph)

    def add_sentence(
        self,
        *,
        sentence_id: str,
        material_id: str,
        paragraph_id: str,
        index: int,
        text: str,
        audio_status: str,
        audio_path: str | None,
        error_message: str | None,
    ) -> None:
        with closing(connect_database(self.database)) as connection:
            connection.execute(
                """
                INSERT INTO sentences (
                    id,
                    material_id,
                    paragraph_id,
                    "index",
                    text,
                    audio_status,
                    audio_path,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sentence_id,
                    material_id,
                    paragraph_id,
                    index,
                    text,
                    audio_status,
                    audio_path,
                    error_message,
                ),
            )
            connection.commit()

    def list_sentences(self, material_id: str) -> list[Sentence]:
        with closing(connect_database(self.database)) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM sentences
                WHERE material_id = ?
                ORDER BY "index" ASC, id ASC
                """,
                (material_id,),
            ).fetchall()
        return _rows_model(rows, Sentence)

    def save_progress(
        self,
        *,
        material_id: str,
        sentence_id: str,
        playback_rate: float,
        updated_at: str,
    ) -> None:
        with closing(connect_database(self.database)) as connection:
            connection.execute(
                """
                INSERT INTO reading_progress (
                    material_id,
                    sentence_id,
                    playback_rate,
                    updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT (material_id) DO UPDATE SET
                    sentence_id = excluded.sentence_id,
                    playback_rate = excluded.playback_rate,
                    updated_at = excluded.updated_at
                """,
                (material_id, sentence_id, playback_rate, updated_at),
            )
            connection.commit()

    def get_progress(self, material_id: str) -> ReadingProgress | None:
        with closing(connect_database(self.database)) as connection:
            row = connection.execute(
                "SELECT * FROM reading_progress WHERE material_id = ?",
                (material_id,),
            ).fetchone()
        return _row_model(row, ReadingProgress)
