from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    """阅读材料来源类型。"""

    URL = 'url'
    PDF = 'pdf'


class AudioStatus(StrEnum):
    """句子音频生成状态。"""

    PENDING = 'pending'
    READY = 'ready'
    FAILED = 'failed'


class ImportJobStatus(StrEnum):
    """导入任务状态。"""

    QUEUED = 'queued'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'


class ImportOutcome(StrEnum):
    """阅读材料导入结果。"""

    CREATED = 'created'
    REUSED_SOURCE = 'reused_source'
    REUSED_CONTENT = 'reused_content'


class DataModel(BaseModel):
    """项目 DTO 的 Pydantic 基类。"""

    model_config = ConfigDict(extra='forbid')


class Material(DataModel):
    """阅读材料元数据。"""

    id: str
    title: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


class MaterialSource(DataModel):
    """阅读材料来源身份。"""

    id: str
    material_id: str
    source_type: SourceType
    source_key: str
    source_uri: str
    source_path: str | None
    is_primary: bool
    created_at: datetime


class Paragraph(DataModel):
    """阅读材料段落。"""

    id: str
    material_id: str
    index: int
    text: str
    source_label: str | None


class Sentence(DataModel):
    """阅读材料句子。"""

    id: str
    material_id: str
    paragraph_id: str
    index: int
    text: str
    audio_status: AudioStatus
    audio_path: str | None
    error_message: str | None


class ReadingProgress(DataModel):
    """阅读材料播放进度。"""

    material_id: str
    sentence_id: str
    playback_rate: float = Field(gt=0)
    updated_at: datetime


class ParagraphDetail(Paragraph):
    """包含句子列表的段落详情。"""

    sentences: list[Sentence]


class MaterialSummary(Material):
    """书架页材料摘要。"""

    primary_source: MaterialSource
    progress: ReadingProgress | None


class MaterialDetail(Material):
    """阅读页材料详情。"""

    primary_source: MaterialSource
    sources: list[MaterialSource]
    progress: ReadingProgress | None
    paragraphs: list[ParagraphDetail]


class MaterialImportResult(DataModel):
    """包含结果原因和阅读材料的导入结果。"""

    outcome: ImportOutcome
    material: MaterialDetail


class ReadingMaterialDraftParagraph(DataModel):
    """导入阶段的段落草稿。"""

    text: str
    source_label: str | None = None
    sentences: list[str]


class ReadingMaterialDraft(DataModel):
    """导入阶段的阅读材料草稿。"""

    source_type: SourceType
    source_uri: str
    title: str
    source_file: Path | None = None
    paragraphs: list[ReadingMaterialDraftParagraph]
