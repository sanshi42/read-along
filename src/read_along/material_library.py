from __future__ import annotations

import hashlib
import json
import math
import shutil
import sqlite3
import threading
import wave
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
    ImportOutcome,
    Material,
    MaterialDetail,
    MaterialImportResult,
    MaterialNavigation,
    MaterialNavigationItem,
    MaterialSummary,
    ParagraphDetail,
    PlaybackPosition,
    PlaybackTimePosition,
    ReadingMaterialDraft,
    ReadingProgress,
    Sentence,
    SourceType,
)
from read_along.playback_position import playback_time_position as derive_playback_time_position
from read_along.repository import Repository
from read_along.storage import StoragePaths
from read_along.tts import CachedAudio, TTSBackend, create_default_tts_backend
from read_along.tts.factory import normalize_tts_error


class MaterialLibraryError(RuntimeError):
    """材料库操作失败。"""


class InvalidDraftError(MaterialLibraryError):
    """阅读材料 Draft 不合法。"""


class SourceChangedError(MaterialLibraryError):
    """已有来源身份对应的结构化正文发生变化。"""


class MaterialNotFoundError(MaterialLibraryError):
    """指定阅读材料不存在。"""


class AudioGenerationError(MaterialLibraryError):
    """句子音频暂时无法生成或访问。"""


class AudioNotFoundError(MaterialLibraryError):
    """指定句子音频不存在或不属于指定材料。"""


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


def _clean_audio_error(message: str, *, sensitive_text: str, storage_home: Path) -> str:
    cleaned = ' '.join(message.split())
    normalized_sensitive_text = ' '.join(sensitive_text.split())
    if normalized_sensitive_text:
        cleaned = cleaned.replace(normalized_sensitive_text, '[正文已隐藏]')
    return cleaned.replace(str(storage_home), '[本地数据目录]') or '句子音频生成失败。'


def _audio_relative_path(material_id: str, sentence_id: str, audio_format: str) -> Path:
    for identity in (material_id, sentence_id):
        identity_path = Path(identity)
        if not identity or identity in {'.', '..'} or identity_path.is_absolute() or identity_path.parts != (identity,):
            raise AudioGenerationError('句子音频缓存路径不合法。')
    if audio_format not in {'wav', 'mp3'}:
        raise AudioGenerationError(f'句子音频格式不支持：{audio_format}')
    return Path(material_id) / f'{sentence_id}.{audio_format}'


def _audio_cache_path_escaped(path: Path, audio_root: Path) -> bool:
    try:
        return path.is_symlink() or not path.resolve().is_relative_to(audio_root)
    except (OSError, RuntimeError):
        return True


def _audio_fingerprint_path(output_path: Path) -> Path:
    return output_path.with_name(f'{output_path.name}.tts-input')


def _audio_cache_matches_tts_input(output_path: Path, fingerprint: str) -> bool:
    try:
        return _audio_fingerprint_path(output_path).read_text() == fingerprint
    except OSError:
        return False


def _discard_audio_cache(output_path: Path) -> None:
    output_path.unlink(missing_ok=True)
    _audio_fingerprint_path(output_path).unlink(missing_ok=True)


def _discard_other_sentence_audio_cache(material_audio_dir: Path, sentence_id: str, keep_path: Path) -> None:
    for candidate in material_audio_dir.glob(f'{sentence_id}.*'):
        if candidate == keep_path or candidate == _audio_fingerprint_path(keep_path):
            continue
        if candidate.name.endswith('.tts-input'):
            candidate.unlink(missing_ok=True)
            continue
        if candidate.suffix.lower() in {'.wav', '.mp3'}:
            _discard_audio_cache(candidate)


def _write_audio_cache_fingerprint(output_path: Path, fingerprint: str) -> None:
    try:
        _audio_fingerprint_path(output_path).write_text(fingerprint)
    except OSError as exc:
        raise AudioGenerationError('无法保存句子音频缓存元数据。') from exc


def _wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), 'rb') as audio:
            frame_rate = audio.getframerate()
            frame_count = audio.getnframes()
    except (EOFError, OSError, wave.Error) as exc:
        raise AudioGenerationError('无法读取句子音频时长。') from exc
    if frame_rate <= 0 or frame_count < 0:
        raise AudioGenerationError('无法读取句子音频时长。')
    return frame_count / frame_rate


def _mp3_duration_seconds(path: Path) -> float:
    try:
        from mutagen.mp3 import MP3

        duration = MP3(path).info.length
    except Exception as exc:
        raise AudioGenerationError('无法读取句子音频时长。') from exc
    if duration < 0:
        raise AudioGenerationError('无法读取句子音频时长。')
    return duration


def _audio_duration_seconds(path: Path) -> float:
    suffix = path.suffix.lower()
    if suffix == '.wav':
        return _wav_duration_seconds(path)
    if suffix == '.mp3':
        return _mp3_duration_seconds(path)
    raise AudioGenerationError('无法读取句子音频时长。')


def _tts_cache_fingerprint(text: str, tts: TTSBackend) -> str:
    payload = {'text': text, 'tts': list(tts.fingerprint_parts())}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


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

    def __init__(self, storage_paths: StoragePaths, *, tts: TTSBackend | None = None) -> None:
        self.storage_paths = storage_paths
        self.repository = Repository(storage_paths.database)
        self.tts = tts or create_default_tts_backend()
        self._audio_locks_guard = threading.Lock()
        self._audio_locks: dict[tuple[str, str], threading.Lock] = {}

    def save(self, draft: ReadingMaterialDraft) -> MaterialImportResult:
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
                        raise SourceChangedError('此来源的正文与已保存版本不同。为避免覆盖现有阅读材料，本次未导入。')
                    connection.rollback()
                    return MaterialImportResult(
                        outcome=ImportOutcome.REUSED_SOURCE,
                        material=self._detail(connection, existing_material),
                    )

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
                    return MaterialImportResult(
                        outcome=ImportOutcome.REUSED_CONTENT,
                        material=self.get(existing_material.id),
                    )

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

        return MaterialImportResult(
            outcome=ImportOutcome.CREATED,
            material=self.get(material_id),
        )

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
        *,
        sentence_offset_seconds: float = 0,
        playback_completed: bool = False,
    ) -> ReadingProgress:
        """保存指定材料的当前句子和播放倍速。"""
        if not math.isfinite(playback_rate) or playback_rate <= 0:
            raise InvalidProgressError('播放倍速必须是大于零的有限数值')
        if not math.isfinite(sentence_offset_seconds) or sentence_offset_seconds < 0:
            raise InvalidProgressError('句内播放位置必须是大于或等于零的有限数值')

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
                if playback_completed and not self.repository.is_last_sentence(
                    connection,
                    material_id=material_id,
                    sentence_id=sentence_id,
                ):
                    raise InvalidProgressError('只有最后一句可以标记为朗读完成')
                self.repository.save_progress(
                    connection,
                    material_id=material_id,
                    sentence_id=sentence_id,
                    sentence_offset_seconds=sentence_offset_seconds,
                    playback_rate=playback_rate,
                    playback_completed=playback_completed,
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

    def get_or_generate_audio(self, material_id: str, sentence_id: str) -> CachedAudio:
        """返回句子缓存音频，缺失时同步生成。"""
        with self._audio_lock(material_id, sentence_id):
            return self._get_or_generate_audio_locked(material_id, sentence_id)

    def clear_material_audio_cache(self, material_id: str) -> None:
        """清理指定阅读材料的句子音频缓存，并重置句子音频状态。"""
        try:
            with closing(self.repository.connect()) as connection:
                material = self.repository.get_material(connection, material_id)
                if material is None:
                    raise MaterialNotFoundError(f'阅读材料不存在：{material_id}')
                sentences = self.repository.list_sentences(connection, material_id)
        except sqlite3.Error as exc:
            raise MaterialLibraryError('读取阅读材料失败') from exc

        audio_dir = self.storage_paths.audio / material_id
        try:
            if audio_dir.is_symlink() or audio_dir.is_file():
                audio_dir.unlink()
            else:
                shutil.rmtree(audio_dir, ignore_errors=True)
        except OSError as exc:
            raise AudioGenerationError('无法清理句子音频缓存。') from exc

        try:
            with closing(self.repository.connect()) as connection:
                try:
                    connection.execute('BEGIN IMMEDIATE')
                    for sentence in sentences:
                        self.repository.update_sentence_audio(
                            connection,
                            material_id=material_id,
                            sentence_id=sentence.id,
                            audio_status=AudioStatus.PENDING.value,
                            audio_path=None,
                            audio_duration_seconds=None,
                            error_message=None,
                        )
                    connection.commit()
                except sqlite3.Error:
                    connection.rollback()
                    raise
        except sqlite3.Error as exc:
            raise AudioGenerationError('无法更新句子音频状态。') from exc

    def _get_or_generate_audio_locked(self, material_id: str, sentence_id: str) -> CachedAudio:
        try:
            with closing(self.repository.connect()) as connection:
                sentence = self.repository.get_sentence(
                    connection,
                    material_id=material_id,
                    sentence_id=sentence_id,
                )
        except sqlite3.Error as exc:
            raise AudioGenerationError('无法读取句子音频状态。') from exc
        if sentence is None:
            raise AudioNotFoundError('句子音频不存在。')

        relative_path = _audio_relative_path(material_id, sentence_id, self.tts.audio_format)
        output_path = self.storage_paths.audio / relative_path
        fingerprint = _tts_cache_fingerprint(sentence.text, self.tts)
        audio_root = self.storage_paths.audio.resolve()
        material_audio_dir = self.storage_paths.audio / material_id
        try:
            material_audio_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            message = '无法访问句子音频缓存。'
            self._update_audio_state(
                material_id,
                sentence_id,
                audio_status=AudioStatus.FAILED,
                audio_path=None,
                audio_duration_seconds=None,
                error_message=message,
            )
            raise AudioGenerationError(message) from exc
        if _audio_cache_path_escaped(material_audio_dir, audio_root):
            message = '句子音频缓存路径不合法。'
            self._update_audio_state(
                material_id,
                sentence_id,
                audio_status=AudioStatus.FAILED,
                audio_path=None,
                audio_duration_seconds=None,
                error_message=message,
            )
            raise AudioGenerationError(message)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            message = '无法访问句子音频缓存。'
            self._update_audio_state(
                material_id,
                sentence_id,
                audio_status=AudioStatus.FAILED,
                audio_path=None,
                audio_duration_seconds=None,
                error_message=message,
            )
            raise AudioGenerationError(message) from exc
        if _audio_cache_path_escaped(output_path.parent, audio_root):
            message = '句子音频缓存路径不合法。'
            self._update_audio_state(
                material_id,
                sentence_id,
                audio_status=AudioStatus.FAILED,
                audio_path=None,
                audio_duration_seconds=None,
                error_message=message,
            )
            raise AudioGenerationError(message)
        _discard_other_sentence_audio_cache(material_audio_dir, sentence_id, output_path)
        if output_path.is_file() and not output_path.is_symlink():
            if _audio_cache_matches_tts_input(output_path, fingerprint):
                duration = self._read_audio_duration(material_id, sentence_id, output_path)
                self._update_audio_state(
                    material_id,
                    sentence_id,
                    audio_status=AudioStatus.READY,
                    audio_path=relative_path.as_posix(),
                    audio_duration_seconds=duration,
                    error_message=None,
                )
                return CachedAudio(
                    path=output_path,
                    audio_format=self.tts.audio_format,
                    media_type=self.tts.media_type,
                    duration_seconds=duration,
                )
            _discard_audio_cache(output_path)
        self._update_audio_state(
            material_id,
            sentence_id,
            audio_status=AudioStatus.PENDING,
            audio_path=None,
            audio_duration_seconds=None,
            error_message=None,
        )
        try:
            self.tts.generate(sentence.text, output_path)
        except Exception as exc:
            generation_error = normalize_tts_error(exc)
            message = _clean_audio_error(
                str(generation_error),
                sensitive_text=sentence.text,
                storage_home=self.storage_paths.home,
            )
            self._update_audio_state(
                material_id,
                sentence_id,
                audio_status=AudioStatus.FAILED,
                audio_path=None,
                audio_duration_seconds=None,
                error_message=message,
            )
            raise AudioGenerationError(message) from generation_error
        duration = self._read_audio_duration(material_id, sentence_id, output_path)
        try:
            _write_audio_cache_fingerprint(output_path, fingerprint)
        except AudioGenerationError as exc:
            output_path.unlink(missing_ok=True)
            self._update_audio_state(
                material_id,
                sentence_id,
                audio_status=AudioStatus.FAILED,
                audio_path=None,
                audio_duration_seconds=None,
                error_message=str(exc),
            )
            raise
        self._update_audio_state(
            material_id,
            sentence_id,
            audio_status=AudioStatus.READY,
            audio_path=relative_path.as_posix(),
            audio_duration_seconds=duration,
            error_message=None,
        )
        return CachedAudio(
            path=output_path,
            audio_format=self.tts.audio_format,
            media_type=self.tts.media_type,
            duration_seconds=duration,
        )

    def _read_audio_duration(self, material_id: str, sentence_id: str, output_path: Path) -> float:
        try:
            return _audio_duration_seconds(output_path)
        except AudioGenerationError as exc:
            output_path.unlink(missing_ok=True)
            self._update_audio_state(
                material_id,
                sentence_id,
                audio_status=AudioStatus.FAILED,
                audio_path=None,
                audio_duration_seconds=None,
                error_message=str(exc),
            )
            raise

    def _audio_lock(self, material_id: str, sentence_id: str) -> threading.Lock:
        key = (material_id, sentence_id)
        with self._audio_locks_guard:
            return self._audio_locks.setdefault(key, threading.Lock())

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
        progress = self.repository.get_progress(connection, material.id)
        return MaterialSummary(
            **material.model_dump(),
            primary_source=sources[0],
            progress=progress,
            playback_position=self._playback_position(connection, material.id),
            playback_time_position=self._playback_time_position(connection, material.id),
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
            playback_position=self._playback_position(connection, material.id),
            playback_time_position=self._playback_time_position(connection, material.id),
            navigation=self._navigation(connection, material.id),
            paragraphs=paragraphs,
        )

    def _playback_position(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> PlaybackPosition | None:
        position = self.repository.get_playback_position(connection, material_id)
        if position is None:
            return None
        sentence_index, sentence_count = position
        return PlaybackPosition(
            sentence_index=sentence_index,
            sentence_count=sentence_count,
        )

    def _playback_time_position(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> PlaybackTimePosition | None:
        progress = self.repository.get_progress(connection, material_id)
        if progress is None:
            return None
        return derive_playback_time_position(
            self.repository.list_sentences(connection, material_id),
            progress,
        )

    def _navigation(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> MaterialNavigation:
        materials = self.repository.list_materials_by_creation(connection)
        current_index = next((index for index, material in enumerate(materials) if material.id == material_id), None)
        if current_index is None:
            return MaterialNavigation(first=None, previous=None, next=None, last=None)
        first_material = materials[0] if materials else None
        last_material = materials[-1] if materials else None
        previous_material = materials[current_index - 1] if current_index > 0 else None
        next_material = materials[current_index + 1] if current_index < len(materials) - 1 else None
        return MaterialNavigation(
            first=MaterialNavigationItem.model_validate(first_material.model_dump()) if first_material else None,
            previous=(
                MaterialNavigationItem.model_validate(previous_material.model_dump()) if previous_material else None
            ),
            next=MaterialNavigationItem.model_validate(next_material.model_dump()) if next_material else None,
            last=MaterialNavigationItem.model_validate(last_material.model_dump()) if last_material else None,
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

    def _update_audio_state(
        self,
        material_id: str,
        sentence_id: str,
        *,
        audio_status: AudioStatus,
        audio_path: str | None,
        audio_duration_seconds: float | None,
        error_message: str | None,
    ) -> None:
        try:
            with closing(self.repository.connect()) as connection:
                self.repository.update_sentence_audio(
                    connection,
                    material_id=material_id,
                    sentence_id=sentence_id,
                    audio_status=audio_status.value,
                    audio_path=audio_path,
                    audio_duration_seconds=audio_duration_seconds,
                    error_message=error_message,
                )
                connection.commit()
        except sqlite3.Error as exc:
            raise AudioGenerationError('无法更新句子音频状态。') from exc
