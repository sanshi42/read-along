"""句子音频缓存和生成流程。"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import threading
import wave
from contextlib import closing
from pathlib import Path

from read_along.material_errors import AudioGenerationError, AudioNotFoundError, MaterialNotFoundError
from read_along.models import AudioStatus
from read_along.repository import Repository
from read_along.storage import StoragePaths
from read_along.tts import CachedAudio, TTSBackend
from read_along.tts.factory import normalize_tts_error


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


class MaterialAudioCache:
    """管理阅读材料句子音频缓存。"""

    def __init__(self, storage_paths: StoragePaths, *, repository: Repository, tts: TTSBackend) -> None:
        self.storage_paths = storage_paths
        self.repository = repository
        self.tts = tts
        self._locks_guard = threading.Lock()
        self._locks: dict[tuple[str, str], threading.Lock] = {}

    def get_or_generate_audio(self, material_id: str, sentence_id: str) -> CachedAudio:
        """返回句子缓存音频，缺失时同步生成。"""
        with self._audio_lock(material_id, sentence_id):
            return self._get_or_generate_audio_locked(material_id, sentence_id)

    def clear_material_audio_cache(self, material_id: str) -> None:
        """清理指定阅读材料的句子音频缓存，并重置句子音频状态。"""
        try:
            with closing(self.repository.connect()) as connection:
                if self.repository.get_material(connection, material_id) is None:
                    raise MaterialNotFoundError(f'阅读材料不存在：{material_id}')
                sentences = self.repository.list_sentences(connection, material_id)
        except sqlite3.Error as exc:
            raise AudioGenerationError('读取阅读材料失败') from exc

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
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())

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
