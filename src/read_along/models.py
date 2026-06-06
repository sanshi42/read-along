from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    URL = "url"
    PDF = "pdf"


class MaterialStatus(StrEnum):
    IMPORTING = "importing"
    READY = "ready"
    FAILED = "failed"


class AudioStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Material(DataModel):
    id: str
    source_type: SourceType
    source_uri: str
    title: str
    status: MaterialStatus
    content_hash: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


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


class MaterialDetail(Material):
    progress: ReadingProgress | None
    paragraphs: list[ParagraphDetail]
