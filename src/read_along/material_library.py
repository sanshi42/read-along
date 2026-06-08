from __future__ import annotations

import hashlib
import json
import math
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit
from uuid import uuid4

from read_along.ids import (
    generate_material_id,
    generate_paragraph_id,
    generate_sentence_id,
    generate_source_id,
)
from read_along.models import (
    AudioStatus,
    Material,
    MaterialDetail,
    MaterialSummary,
    ParagraphDetail,
    ReadingMaterialDraft,
    ReadingProgress,
    Sentence,
    SourceType,
)
from read_along.repository import Repository
from read_along.storage import StoragePaths


class MaterialLibraryError(RuntimeError):
    """材料库操作失败。"""


class InvalidDraftError(MaterialLibraryError):
    """阅读材料 Draft 不合法。"""


class SourceChangedError(MaterialLibraryError):
    """已有来源身份对应的结构化正文发生变化。"""


class MaterialNotFoundError(MaterialLibraryError):
    """指定阅读材料不存在。"""


class InvalidProgressError(MaterialLibraryError):
    """阅读进度不合法。"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(draft: ReadingMaterialDraft) -> str:
    body = [paragraph.sentences for paragraph in draft.paragraphs]
    serialized = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise InvalidDraftError(f'来源 URL 不合法：{url}') from exc

    scheme = parsed.scheme.lower()
    if scheme not in {'http', 'https'} or parsed.hostname is None:
        raise InvalidDraftError(f'来源 URL 必须是有效的 HTTP 或 HTTPS URL：{url}')
    if parsed.username is not None or parsed.password is not None:
        raise InvalidDraftError('来源 URL 不得包含用户名或密码')

    host = parsed.hostname.lower()
    if ':' in host:
        host = f'[{host}]'
    default_port = (scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)
    netloc = host if port is None or default_port else f'{host}:{port}'
    normalized = SplitResult(
        scheme=scheme,
        netloc=netloc,
        path=parsed.path or '/',
        query=parsed.query,
        fragment='',
    )
    return urlunsplit(normalized)


class MaterialLibrary:
    """管理阅读材料的完整持久化生命周期。"""

    def __init__(self, storage_paths: StoragePaths) -> None:
        self.storage_paths = storage_paths
        self.repository = Repository(storage_paths.database)

    def save(self, draft: ReadingMaterialDraft) -> MaterialDetail:
        """原子保存阅读材料 Draft，重复导入时返回现有材料。"""
        self._validate_draft(draft)
        content_hash = _content_hash(draft)
        source_key = self._source_key(draft)
        material_id = generate_material_id(content_hash)
        source_id = generate_source_id(draft.source_type.value, source_key)
        now = _now_iso()
        temp_path: Path | None = None
        final_path: Path | None = None

        with closing(self.repository.connect()) as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                existing_source = self.repository.get_source_by_identity(
                    connection,
                    source_type=draft.source_type.value,
                    source_key=source_key,
                )
                if existing_source is not None:
                    existing_material = self.repository.get_material(
                        connection,
                        existing_source.material_id,
                    )
                    if existing_material is None:
                        raise MaterialLibraryError('来源身份关联的阅读材料不存在')
                    if existing_material.content_hash != content_hash:
                        raise SourceChangedError('相同来源的结构化正文已发生变化')
                    connection.rollback()
                    return self._detail(connection, existing_material)

                existing_material = self.repository.get_material_by_content_hash(
                    connection,
                    content_hash,
                )
                if existing_material is not None:
                    self.repository.insert_source(
                        connection,
                        source_id=source_id,
                        material_id=existing_material.id,
                        source_type=draft.source_type.value,
                        source_key=source_key,
                        source_uri=draft.source_uri,
                        source_path=None,
                        is_primary=False,
                        created_at=now,
                    )
                    self.repository.update_material_timestamp(
                        connection,
                        material_id=existing_material.id,
                        updated_at=now,
                    )
                    connection.commit()
                    return self.get(existing_material.id)

                if draft.source_file is not None:
                    temp_path, final_path = self._copy_source_file(
                        draft.source_file,
                        source_id,
                    )

                self.repository.insert_material(
                    connection,
                    material_id=material_id,
                    title=draft.title,
                    content_hash=content_hash,
                    created_at=now,
                    updated_at=now,
                )
                self.repository.insert_source(
                    connection,
                    source_id=source_id,
                    material_id=material_id,
                    source_type=draft.source_type.value,
                    source_key=source_key,
                    source_uri=draft.source_uri,
                    source_path=str(final_path) if final_path is not None else None,
                    is_primary=True,
                    created_at=now,
                )
                self._insert_body(connection, material_id, draft)

                if temp_path is not None and final_path is not None:
                    temp_path.replace(final_path)
                    temp_path = None

                connection.commit()
            except MaterialLibraryError:
                connection.rollback()
                self._cleanup_failed_save(temp_path, final_path)
                raise
            except (OSError, sqlite3.Error) as exc:
                connection.rollback()
                self._cleanup_failed_save(temp_path, final_path)
                raise MaterialLibraryError('保存阅读材料失败') from exc

        return self.get(material_id)

    def list_shelf(self) -> list[MaterialSummary]:
        """按最近活动时间返回书架材料摘要。"""
        try:
            with closing(self.repository.connect()) as connection:
                materials = self.repository.list_materials(connection)
                return [self._summary(connection, material) for material in materials]
        except sqlite3.Error as exc:
            raise MaterialLibraryError('读取书架失败') from exc

    def get(self, material_id: str) -> MaterialDetail:
        """返回单篇阅读材料详情。"""
        try:
            with closing(self.repository.connect()) as connection:
                material = self.repository.get_material(connection, material_id)
                if material is None:
                    raise MaterialNotFoundError(f'阅读材料不存在：{material_id}')
                return self._detail(connection, material)
        except sqlite3.Error as exc:
            raise MaterialLibraryError('读取阅读材料失败') from exc

    def save_progress(
        self,
        material_id: str,
        sentence_id: str,
        playback_rate: float,
    ) -> ReadingProgress:
        """保存指定材料的当前句子和播放倍速。"""
        if not math.isfinite(playback_rate) or playback_rate <= 0:
            raise InvalidProgressError('播放倍速必须是大于零的有限数值')

        now = _now_iso()
        with closing(self.repository.connect()) as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                if self.repository.get_material(connection, material_id) is None:
                    raise MaterialNotFoundError(f'阅读材料不存在：{material_id}')
                if not self.repository.sentence_belongs_to_material(
                    connection,
                    material_id=material_id,
                    sentence_id=sentence_id,
                ):
                    raise InvalidProgressError('句子不属于指定阅读材料')
                self.repository.save_progress(
                    connection,
                    material_id=material_id,
                    sentence_id=sentence_id,
                    playback_rate=playback_rate,
                    updated_at=now,
                )
                self.repository.update_material_timestamp(
                    connection,
                    material_id=material_id,
                    updated_at=now,
                )
                connection.commit()
            except MaterialLibraryError:
                connection.rollback()
                raise
            except sqlite3.Error as exc:
                connection.rollback()
                raise MaterialLibraryError('保存阅读进度失败') from exc

        progress = self.get(material_id).progress
        assert progress is not None
        return progress

    def delete(self, material_id: str) -> None:
        """幂等删除阅读材料及关联本地缓存。"""
        source_paths: list[Path] = []
        with closing(self.repository.connect()) as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                material = self.repository.get_material(connection, material_id)
                if material is None:
                    connection.rollback()
                    return
                source_paths = [
                    Path(source.source_path)
                    for source in self.repository.list_sources(connection, material_id)
                    if source.source_path is not None
                ]
                self.repository.delete_material(connection, material_id)
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise MaterialLibraryError('删除阅读材料失败') from exc

        for source_path in source_paths:
            try:
                source_path.unlink(missing_ok=True)
            except OSError:
                pass
        shutil.rmtree(self.storage_paths.audio / material_id, ignore_errors=True)

    def _validate_draft(self, draft: ReadingMaterialDraft) -> None:
        if not draft.title.strip():
            raise InvalidDraftError('阅读材料标题不能为空')
        if not draft.source_uri.strip():
            raise InvalidDraftError('来源 URI 不能为空')
        if not draft.paragraphs:
            raise InvalidDraftError('结构化正文不能为空')
        if draft.source_type is SourceType.PDF and draft.source_file is None:
            raise InvalidDraftError('PDF Draft 必须提供源文件')
        if draft.source_file is not None and not draft.source_file.is_file():
            raise InvalidDraftError(f'源文件不存在：{draft.source_file}')

        for paragraph in draft.paragraphs:
            if not paragraph.sentences:
                raise InvalidDraftError('段落必须包含至少一个句子')
            if any(not sentence.strip() for sentence in paragraph.sentences):
                raise InvalidDraftError('句子文本不能为空')
            if paragraph.text != ' '.join(paragraph.sentences):
                raise InvalidDraftError('段落正文与句子内容不一致')
            if paragraph.source_label is not None and not paragraph.source_label.strip():
                raise InvalidDraftError('来源标记不能为空字符串')

    def _source_key(self, draft: ReadingMaterialDraft) -> str:
        if draft.source_type is SourceType.URL:
            return _normalized_url(draft.source_uri)
        assert draft.source_file is not None
        try:
            return _file_hash(draft.source_file)
        except OSError as exc:
            raise MaterialLibraryError('读取 PDF 源文件失败') from exc

    def _copy_source_file(self, source_file: Path, source_id: str) -> tuple[Path, Path]:
        self.storage_paths.uploads.mkdir(parents=True, exist_ok=True)
        suffix = source_file.suffix.lower()
        temp_path = self.storage_paths.uploads / f'.{source_id}.{uuid4().hex}.tmp'
        final_path = self.storage_paths.uploads / f'{source_id}{suffix}'
        try:
            shutil.copy2(source_file, temp_path)
        except OSError:
            temp_path.unlink(missing_ok=True)
            raise
        return temp_path, final_path

    def _insert_body(
        self,
        connection: sqlite3.Connection,
        material_id: str,
        draft: ReadingMaterialDraft,
    ) -> None:
        sentence_index = 0
        for paragraph_index, paragraph in enumerate(draft.paragraphs, start=1):
            paragraph_id = generate_paragraph_id(material_id, paragraph_index)
            self.repository.insert_paragraph(
                connection,
                paragraph_id=paragraph_id,
                material_id=material_id,
                index=paragraph_index,
                text=paragraph.text,
                source_label=paragraph.source_label,
            )
            for sentence_text in paragraph.sentences:
                sentence_index += 1
                self.repository.insert_sentence(
                    connection,
                    sentence_id=generate_sentence_id(material_id, sentence_index),
                    material_id=material_id,
                    paragraph_id=paragraph_id,
                    index=sentence_index,
                    text=sentence_text,
                    audio_status=AudioStatus.PENDING.value,
                )

    def _summary(
        self,
        connection: sqlite3.Connection,
        material: Material,
    ) -> MaterialSummary:
        sources = self.repository.list_sources(connection, material.id)
        if not sources or not sources[0].is_primary:
            raise MaterialLibraryError('阅读材料缺少主来源')
        return MaterialSummary(
            **material.model_dump(),
            primary_source=sources[0],
            progress=self.repository.get_progress(connection, material.id),
        )

    def _detail(
        self,
        connection: sqlite3.Connection,
        material: Material,
    ) -> MaterialDetail:
        sources = self.repository.list_sources(connection, material.id)
        if not sources or not sources[0].is_primary:
            raise MaterialLibraryError('阅读材料缺少主来源')

        sentences_by_paragraph: dict[str, list[Sentence]] = {}
        for sentence in self.repository.list_sentences(connection, material.id):
            sentences_by_paragraph.setdefault(sentence.paragraph_id, []).append(sentence)
        paragraphs = [
            ParagraphDetail(
                **paragraph.model_dump(),
                sentences=sentences_by_paragraph.get(paragraph.id, []),
            )
            for paragraph in self.repository.list_paragraphs(connection, material.id)
        ]
        return MaterialDetail(
            **material.model_dump(),
            primary_source=sources[0],
            sources=sources,
            progress=self.repository.get_progress(connection, material.id),
            paragraphs=paragraphs,
        )

    def _cleanup_failed_save(
        self,
        temp_path: Path | None,
        final_path: Path | None,
    ) -> None:
        path = temp_path if temp_path is not None else final_path
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
