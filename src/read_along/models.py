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


class SentenceResponse(DataModel):
    """API 返回的阅读材料句子。"""

    id: str
    material_id: str
    paragraph_id: str
    index: int
    text: str
    audio_status: AudioStatus
    error_message: str | None

    @classmethod
    def from_sentence(cls, sentence: Sentence) -> SentenceResponse:
        """从材料库内部句子创建公开响应。"""
        return cls(
            id=sentence.id,
            material_id=sentence.material_id,
            paragraph_id=sentence.paragraph_id,
            index=sentence.index,
            text=sentence.text,
            audio_status=sentence.audio_status,
            error_message=sentence.error_message,
        )


class ReadingProgress(DataModel):
    """阅读材料播放进度。"""

    material_id: str
    sentence_id: str
    playback_rate: float = Field(gt=0)
    playback_completed: bool
    updated_at: datetime


class ParagraphDetail(Paragraph):
    """包含句子列表的段落详情。"""

    sentences: list[Sentence]


class ParagraphDetailResponse(Paragraph):
    """API 返回的包含句子列表的段落详情。"""

    sentences: list[SentenceResponse]

    @classmethod
    def from_detail(cls, paragraph: ParagraphDetail) -> ParagraphDetailResponse:
        """从材料库内部段落详情创建公开响应。"""
        return cls(
            id=paragraph.id,
            material_id=paragraph.material_id,
            index=paragraph.index,
            text=paragraph.text,
            source_label=paragraph.source_label,
            sentences=[SentenceResponse.from_sentence(sentence) for sentence in paragraph.sentences],
        )


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


class MaterialDetailResponse(Material):
    """API 返回的阅读材料详情。"""

    primary_source: MaterialSource
    sources: list[MaterialSource]
    progress: ReadingProgress | None
    paragraphs: list[ParagraphDetailResponse]

    @classmethod
    def from_detail(cls, material: MaterialDetail) -> MaterialDetailResponse:
        """从材料库内部详情创建公开响应。"""
        return cls(
            id=material.id,
            title=material.title,
            content_hash=material.content_hash,
            created_at=material.created_at,
            updated_at=material.updated_at,
            primary_source=material.primary_source,
            sources=material.sources,
            progress=material.progress,
            paragraphs=[ParagraphDetailResponse.from_detail(paragraph) for paragraph in material.paragraphs],
        )


class MaterialImportResult(DataModel):
    """包含结果原因和阅读材料的导入结果。"""

    outcome: ImportOutcome
    material: MaterialDetail


class MaterialImportResponse(DataModel):
    """API 返回的阅读材料导入结果。"""

    outcome: ImportOutcome
    material: MaterialDetailResponse

    @classmethod
    def from_result(cls, result: MaterialImportResult) -> MaterialImportResponse:
        """从材料库内部导入结果创建公开响应。"""
        return cls(
            outcome=result.outcome,
            material=MaterialDetailResponse.from_detail(result.material),
        )


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
