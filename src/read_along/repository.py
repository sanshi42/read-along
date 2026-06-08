from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from read_along.db import connect_database
from read_along.models import (
    Material,
    MaterialSource,
    Paragraph,
    ReadingProgress,
    Sentence,
)

ModelT = TypeVar('ModelT', bound=BaseModel)


def _row_model(row: sqlite3.Row | None, model: type[ModelT]) -> ModelT | None:
    if row is None:
        return None
    return model.model_validate({key: row[key] for key in row.keys()})


def _rows_model(rows: list[sqlite3.Row], model: type[ModelT]) -> list[ModelT]:
    return [model.model_validate({key: row[key] for key in row.keys()}) for row in rows]


class Repository:
    """材料库 Module 内部使用的 SQLite 读写辅助。"""

    def __init__(self, database: Path) -> None:
        self.database = database

    def connect(self) -> sqlite3.Connection:
        """打开 repository 使用的 SQLite 连接。"""
        return connect_database(self.database)

    def get_material(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> Material | None:
        """按 ID 查询阅读材料。"""
        row = connection.execute(
            'SELECT * FROM materials WHERE id = ?',
            (material_id,),
        ).fetchone()
        return _row_model(row, Material)

    def get_material_by_content_hash(
        self,
        connection: sqlite3.Connection,
        content_hash: str,
    ) -> Material | None:
        """按结构化正文哈希查询阅读材料。"""
        row = connection.execute(
            'SELECT * FROM materials WHERE content_hash = ?',
            (content_hash,),
        ).fetchone()
        return _row_model(row, Material)

    def list_materials(self, connection: sqlite3.Connection) -> list[Material]:
        """按最近更新时间列出阅读材料。"""
        rows = connection.execute(
            """
            SELECT *
            FROM materials
            ORDER BY updated_at DESC, created_at DESC, id ASC
            """
        ).fetchall()
        return _rows_model(rows, Material)

    def insert_material(
        self,
        connection: sqlite3.Connection,
        *,
        material_id: str,
        title: str,
        content_hash: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        """插入阅读材料元数据。"""
        connection.execute(
            """
            INSERT INTO materials (id, title, content_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (material_id, title, content_hash, created_at, updated_at),
        )

    def update_material_timestamp(
        self,
        connection: sqlite3.Connection,
        *,
        material_id: str,
        updated_at: str,
    ) -> None:
        """更新阅读材料活动时间。"""
        connection.execute(
            'UPDATE materials SET updated_at = ? WHERE id = ?',
            (updated_at, material_id),
        )

    def get_source_by_identity(
        self,
        connection: sqlite3.Connection,
        *,
        source_type: str,
        source_key: str,
    ) -> MaterialSource | None:
        """按来源类型和来源键查询来源身份。"""
        row = connection.execute(
            """
            SELECT *
            FROM material_sources
            WHERE source_type = ? AND source_key = ?
            """,
            (source_type, source_key),
        ).fetchone()
        return _row_model(row, MaterialSource)

    def list_sources(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> list[MaterialSource]:
        """列出指定材料的全部来源身份。"""
        rows = connection.execute(
            """
            SELECT *
            FROM material_sources
            WHERE material_id = ?
            ORDER BY is_primary DESC, created_at ASC, id ASC
            """,
            (material_id,),
        ).fetchall()
        return _rows_model(rows, MaterialSource)

    def insert_source(
        self,
        connection: sqlite3.Connection,
        *,
        source_id: str,
        material_id: str,
        source_type: str,
        source_key: str,
        source_uri: str,
        source_path: str | None,
        is_primary: bool,
        created_at: str,
    ) -> None:
        """插入阅读材料来源身份。"""
        connection.execute(
            """
            INSERT INTO material_sources (
                id,
                material_id,
                source_type,
                source_key,
                source_uri,
                source_path,
                is_primary,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                material_id,
                source_type,
                source_key,
                source_uri,
                source_path,
                int(is_primary),
                created_at,
            ),
        )

    def insert_paragraph(
        self,
        connection: sqlite3.Connection,
        *,
        paragraph_id: str,
        material_id: str,
        index: int,
        text: str,
        source_label: str | None,
    ) -> None:
        """插入阅读材料段落。"""
        connection.execute(
            """
            INSERT INTO paragraphs (id, material_id, "index", text, source_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (paragraph_id, material_id, index, text, source_label),
        )

    def list_paragraphs(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> list[Paragraph]:
        """按顺序列出指定材料的段落。"""
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

    def insert_sentence(
        self,
        connection: sqlite3.Connection,
        *,
        sentence_id: str,
        material_id: str,
        paragraph_id: str,
        index: int,
        text: str,
        audio_status: str,
    ) -> None:
        """插入阅读材料句子。"""
        connection.execute(
            """
            INSERT INTO sentences (
                id,
                material_id,
                paragraph_id,
                "index",
                text,
                audio_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sentence_id,
                material_id,
                paragraph_id,
                index,
                text,
                audio_status,
            ),
        )

    def list_sentences(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> list[Sentence]:
        """按顺序列出指定材料的句子。"""
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

    def sentence_belongs_to_material(
        self,
        connection: sqlite3.Connection,
        *,
        material_id: str,
        sentence_id: str,
    ) -> bool:
        """判断句子是否属于指定阅读材料。"""
        row = connection.execute(
            """
            SELECT 1
            FROM sentences
            WHERE id = ? AND material_id = ?
            """,
            (sentence_id, material_id),
        ).fetchone()
        return row is not None

    def save_progress(
        self,
        connection: sqlite3.Connection,
        *,
        material_id: str,
        sentence_id: str,
        playback_rate: float,
        updated_at: str,
    ) -> None:
        """覆盖保存阅读进度。"""
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

    def get_progress(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> ReadingProgress | None:
        """读取指定材料的阅读进度。"""
        row = connection.execute(
            'SELECT * FROM reading_progress WHERE material_id = ?',
            (material_id,),
        ).fetchone()
        return _row_model(row, ReadingProgress)

    def delete_material(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> None:
        """删除阅读材料数据库记录。"""
        connection.execute('DELETE FROM materials WHERE id = ?', (material_id,))
