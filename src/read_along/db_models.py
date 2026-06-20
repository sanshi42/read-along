from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from read_along.db_types import UTCDateTime
from read_along.models import AudioStatus, ImportJobStatus, SourceType

ID_LENGTH = 64
HASH_LENGTH = 64
ENUM_LENGTH = 16


class MaterialRow(SQLModel, table=True):
    """阅读材料数据库实体。"""

    __tablename__ = 'materials'  # pyrefly: ignore [bad-override]
    __table_args__ = (UniqueConstraint('content_hash', name='uq_materials_content_hash'),)

    id: str = Field(sa_column=Column(String(ID_LENGTH), primary_key=True, nullable=False))
    title: str = Field(sa_column=Column(Text, nullable=False))
    content_hash: str = Field(sa_column=Column(String(HASH_LENGTH), nullable=False))
    created_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
    updated_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))

    sources: list[MaterialSourceRow] = Relationship(
        sa_relationship=relationship('MaterialSourceRow', back_populates='material', passive_deletes=True),
    )
    paragraphs: list[ParagraphRow] = Relationship(
        sa_relationship=relationship('ParagraphRow', back_populates='material', passive_deletes=True),
    )
    sentences: list[SentenceRow] = Relationship(
        sa_relationship=relationship('SentenceRow', back_populates='material', passive_deletes=True),
    )
    progress: ReadingProgressRow | None = Relationship(
        sa_relationship=relationship('ReadingProgressRow', back_populates='material', passive_deletes=True),
    )


class MaterialSourceRow(SQLModel, table=True):
    """阅读材料来源身份数据库实体。"""

    __tablename__ = 'material_sources'  # pyrefly: ignore [bad-override]
    __table_args__ = (
        CheckConstraint("source_type IN ('url', 'pdf')", name='ck_material_sources_source_type'),
        CheckConstraint('is_primary IN (0, 1)', name='ck_material_sources_is_primary'),
        UniqueConstraint('source_type', 'source_key', name='uq_material_sources_identity'),
        Index(
            'ix_material_sources_one_primary',
            'material_id',
            unique=True,
            sqlite_where=text('is_primary = 1'),
        ),
        Index('ix_material_sources_material_id', 'material_id'),
    )

    id: str = Field(sa_column=Column(String(ID_LENGTH), primary_key=True, nullable=False))
    material_id: str = Field(
        sa_column=Column(
            String(ID_LENGTH),
            ForeignKey('materials.id', name='fk_material_sources_material_id', ondelete='CASCADE'),
            nullable=False,
        )
    )
    source_type: SourceType = Field(sa_column=Column(String(ENUM_LENGTH), nullable=False))
    source_key: str = Field(sa_column=Column(Text, nullable=False))
    source_uri: str = Field(sa_column=Column(Text, nullable=False))
    source_path: str | None = Field(default=None, sa_column=Column(Text))
    is_primary: bool = Field(sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))

    material: MaterialRow = Relationship(
        sa_relationship=relationship('MaterialRow', back_populates='sources', passive_deletes=True),
    )


class ParagraphRow(SQLModel, table=True):
    """阅读材料段落数据库实体。"""

    __tablename__ = 'paragraphs'  # pyrefly: ignore [bad-override]
    __table_args__ = (
        UniqueConstraint('material_id', 'index', name='uq_paragraphs_material_index'),
        UniqueConstraint('id', 'material_id', name='uq_paragraphs_identity'),
    )

    id: str = Field(sa_column=Column(String(ID_LENGTH), primary_key=True, nullable=False))
    material_id: str = Field(
        sa_column=Column(
            String(ID_LENGTH),
            ForeignKey('materials.id', name='fk_paragraphs_material_id', ondelete='CASCADE'),
            nullable=False,
        )
    )
    index: int = Field(sa_column=Column(Integer, nullable=False))
    text: str = Field(sa_column=Column(Text, nullable=False))
    source_label: str | None = Field(default=None, sa_column=Column(Text))

    material: MaterialRow = Relationship(
        sa_relationship=relationship('MaterialRow', back_populates='paragraphs', passive_deletes=True),
    )


class SentenceRow(SQLModel, table=True):
    """阅读材料句子数据库实体。"""

    __tablename__ = 'sentences'  # pyrefly: ignore [bad-override]
    __table_args__ = (
        CheckConstraint("audio_status IN ('pending', 'ready', 'failed')", name='ck_sentences_audio_status'),
        CheckConstraint(
            'audio_duration_seconds IS NULL OR audio_duration_seconds >= 0',
            name='ck_sentences_audio_duration_seconds',
        ),
        UniqueConstraint('material_id', 'index', name='uq_sentences_material_index'),
        UniqueConstraint('id', 'material_id', name='uq_sentences_identity'),
        ForeignKeyConstraint(
            ('paragraph_id', 'material_id'),
            ('paragraphs.id', 'paragraphs.material_id'),
            name='fk_sentences_paragraph_material',
            ondelete='CASCADE',
        ),
        Index('ix_sentences_paragraph_id', 'paragraph_id'),
    )

    id: str = Field(sa_column=Column(String(ID_LENGTH), primary_key=True, nullable=False))
    material_id: str = Field(
        sa_column=Column(
            String(ID_LENGTH),
            ForeignKey('materials.id', name='fk_sentences_material_id', ondelete='CASCADE'),
            nullable=False,
        )
    )
    paragraph_id: str = Field(sa_column=Column(String(ID_LENGTH), nullable=False))
    index: int = Field(sa_column=Column(Integer, nullable=False))
    text: str = Field(sa_column=Column(Text, nullable=False))
    audio_status: AudioStatus = Field(sa_column=Column(String(ENUM_LENGTH), nullable=False))
    audio_path: str | None = Field(default=None, sa_column=Column(Text))
    audio_duration_seconds: float | None = Field(default=None, sa_column=Column(Float))
    error_message: str | None = Field(default=None, sa_column=Column(Text))

    material: MaterialRow = Relationship(
        sa_relationship=relationship('MaterialRow', back_populates='sentences', passive_deletes=True),
    )


class ReadingProgressRow(SQLModel, table=True):
    """阅读进度数据库实体。"""

    __tablename__ = 'reading_progress'  # pyrefly: ignore [bad-override]
    __table_args__ = (
        CheckConstraint('playback_rate > 0', name='ck_reading_progress_playback_rate'),
        CheckConstraint('sentence_offset_seconds >= 0', name='ck_reading_progress_sentence_offset_seconds'),
        CheckConstraint('playback_completed IN (0, 1)', name='ck_reading_progress_playback_completed'),
        ForeignKeyConstraint(
            ('sentence_id', 'material_id'),
            ('sentences.id', 'sentences.material_id'),
            name='fk_reading_progress_sentence_material',
            ondelete='CASCADE',
        ),
    )

    material_id: str = Field(
        sa_column=Column(
            String(ID_LENGTH),
            ForeignKey('materials.id', name='fk_reading_progress_material_id', ondelete='CASCADE'),
            primary_key=True,
            nullable=False,
        )
    )
    sentence_id: str = Field(sa_column=Column(String(ID_LENGTH), nullable=False))
    sentence_offset_seconds: float = Field(sa_column=Column(Float, nullable=False, server_default='0'))
    playback_rate: float = Field(sa_column=Column(Float, nullable=False))
    playback_completed: bool = Field(sa_column=Column(Integer, nullable=False))
    updated_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))

    material: MaterialRow = Relationship(
        sa_relationship=relationship('MaterialRow', back_populates='progress', passive_deletes=True),
    )


class ImportJobRow(SQLModel, table=True):
    """导入任务数据库实体。"""

    __tablename__ = 'import_jobs'  # pyrefly: ignore [bad-override]
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name='ck_import_jobs_status'),
    )

    id: str = Field(sa_column=Column(String(ID_LENGTH), primary_key=True, nullable=False))
    status: ImportJobStatus = Field(sa_column=Column(String(ENUM_LENGTH), nullable=False))
    material_id: str | None = Field(
        default=None,
        sa_column=Column(
            String(ID_LENGTH),
            ForeignKey('materials.id', name='fk_import_jobs_material_id', ondelete='SET NULL'),
        ),
    )
    message: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
    updated_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
