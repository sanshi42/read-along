from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    URL = "url"
    PDF = "pdf"


class AudioStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Material(DataModel):
    id: str
    title: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


class MaterialSource(DataModel):
    id: str
    material_id: str
    source_type: SourceType
    source_key: str
    source_uri: str
    source_path: str | None
    is_primary: bool
    created_at: datetime


class Paragraph(DataModel):
    id: str
    material_id: str
    index: int
    text: str
    source_label: str | None


class Sentence(DataModel):
    id: str
    material_id: str
    paragraph_id: str
    index: int
    text: str
    audio_status: AudioStatus
    audio_path: str | None
    error_message: str | None


class ReadingProgress(DataModel):
    material_id: str
    sentence_id: str
    playback_rate: float = Field(gt=0)
    updated_at: datetime


class ParagraphDetail(Paragraph):
    sentences: list[Sentence]


class MaterialSummary(Material):
    primary_source: MaterialSource
    progress: ReadingProgress | None


class MaterialDetail(Material):
    primary_source: MaterialSource
    sources: list[MaterialSource]
    progress: ReadingProgress | None
    paragraphs: list[ParagraphDetail]


class ReadingMaterialDraftParagraph(DataModel):
    text: str
    source_label: str | None = None
    sentences: list[str]


class ReadingMaterialDraft(DataModel):
    source_type: SourceType
    source_uri: str
    title: str
    source_file: Path | None = None
    paragraphs: list[ReadingMaterialDraftParagraph]
