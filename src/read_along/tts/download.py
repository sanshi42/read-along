from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

KOKORO_MODEL_NAME = 'kokoro-multi-lang-v1_1'
KOKORO_MODEL_URL = (
    'https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-int8-multi-lang-v1_1.tar.bz2'
)
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_MAX_DOWNLOAD_RETRIES = 3
_sleep = time.sleep


class ModelDownloadError(RuntimeError):
    """本地朗读模型下载失败。"""


class _InvalidModelArchiveError(RuntimeError):
    """下载归档无法解压或不包含可用模型。"""


class _IncompleteDownloadError(OSError):
    """HTTP 响应在预期字节数之前结束。"""


class DownloadProgress(Protocol):
    """下载进度的最小报告协议。"""

    def start(self, total_bytes: int | None, completed_bytes: int) -> None:
        """开始或重置当前下载显示。"""

    def advance(self, completed_bytes: int) -> None:
        """报告已写入的归档字节数。"""

    def retry(self, retry_number: int, delay_seconds: float, error: Exception) -> None:
        """报告一次可恢复下载错误。"""


@dataclass(frozen=True)
class KokoroModelPaths:
    """本地 Kokoro 模型文件路径。"""

    model_dir: Path
    model_path: Path
    voices_path: Path
    tokens_path: Path
    data_dir: Path

    @property
    def lexicon_us_en_path(self) -> Path:
        """返回默认模型的英文词典路径。"""
        return self.model_dir / 'lexicon-us-en.txt'

    @property
    def lexicon_zh_path(self) -> Path:
        """返回默认模型的中文词典路径。"""
        return self.model_dir / 'lexicon-zh.txt'

    @property
    def env_text(self) -> str:
        """返回应写入 `.env` 的配置片段。"""
        return '\n'.join(
            [
                'READ_ALONG_TTS_ENGINE=sherpa_onnx_tts',
                'READ_ALONG_TTS_SHERPA_MODEL_TYPE=kokoro',
                f'READ_ALONG_TTS_SHERPA_KOKORO_MODEL={self.model_path}',
                f'READ_ALONG_TTS_SHERPA_KOKORO_VOICES={self.voices_path}',
                f'READ_ALONG_TTS_SHERPA_KOKORO_TOKENS={self.tokens_path}',
                f'READ_ALONG_TTS_SHERPA_KOKORO_DATA_DIR={self.data_dir}',
                'READ_ALONG_TTS_SHERPA_PROVIDER=cpu',
                'READ_ALONG_TTS_SHERPA_NUM_THREADS=2',
                'READ_ALONG_TTS_SHERPA_SPEED=1.0',
                'READ_ALONG_TTS_SHERPA_SID=0',
            ]
        )


def download_kokoro_model(
    target_dir: Path,
    *,
    url: str = KOKORO_MODEL_URL,
    restart: bool = False,
    progress: DownloadProgress | None = None,
) -> KokoroModelPaths:
    """下载并解压默认 Kokoro 多语种模型。"""
    target_dir = Path(target_dir)
    model_dir = target_dir / KOKORO_MODEL_NAME
    existing = _model_paths(model_dir)
    if _is_valid(existing):
        return existing

    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = _partial_archive_path(target_dir)
    metadata_path = _partial_metadata_path(target_dir)
    if restart:
        _clear_partial_download(archive_path, metadata_path)
    for validation_attempt in range(2):
        try:
            _download_to_path(url, archive_path, progress=progress)
            _install_model_archive(archive_path, target_dir, model_dir)
        except _InvalidModelArchiveError as exc:
            if validation_attempt == 0:
                _clear_partial_download(archive_path, metadata_path)
                continue
            raise ModelDownloadError(
                f'Kokoro 模型归档完整性校验失败：{exc}；已重新下载一次，请使用 --restart 后重试。'
            ) from exc
        except Exception as exc:
            if model_dir.exists() and not _is_valid(_model_paths(model_dir)):
                shutil.rmtree(model_dir, ignore_errors=True)
            if isinstance(exc, ModelDownloadError):
                raise
            raise ModelDownloadError(f'下载 Kokoro 模型失败：{exc}') from exc
        else:
            archive_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            final = _model_paths(model_dir)
            _validate(final)
            return final

    raise AssertionError('模型归档重试循环未返回结果。')


def _install_model_archive(archive_path: Path, target_dir: Path, model_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix='.kokoro-download-', dir=target_dir) as temporary:
        extract_dir = Path(temporary) / 'extract'
        extract_dir.mkdir()
        try:
            with tarfile.open(archive_path, 'r:bz2') as archive:
                archive.extractall(extract_dir, filter='data')
        except (EOFError, tarfile.TarError) as exc:
            raise _InvalidModelArchiveError('Kokoro 模型压缩包无效。') from exc
        try:
            extracted_root = _find_extracted_root(extract_dir)
            candidate = _model_paths(extracted_root)
            _validate(candidate)
        except ModelDownloadError as exc:
            raise _InvalidModelArchiveError(str(exc)) from exc
        if model_dir.exists():
            shutil.rmtree(model_dir)
        shutil.move(str(extracted_root), model_dir)


def _download_to_path(url: str, destination: Path, *, progress: DownloadProgress | None) -> None:
    for attempt in range(_MAX_DOWNLOAD_RETRIES + 1):
        try:
            _download_to_path_once(url, destination, progress=progress)
            return
        except Exception as exc:
            if not _is_retryable_download_error(exc) or attempt == _MAX_DOWNLOAD_RETRIES:
                raise
            delay_seconds = float(2**attempt)
            if progress is not None:
                progress.retry(attempt + 1, delay_seconds, exc)
            _sleep(delay_seconds)


def _download_to_path_once(url: str, destination: Path, *, progress: DownloadProgress | None) -> None:
    metadata_path = _partial_metadata_path(destination.parent)
    for _ in range(2):
        metadata = _load_partial_metadata(metadata_path)
        offset = destination.stat().st_size if destination.is_file() else 0
        resume_metadata = metadata if offset > 0 and metadata is not None and metadata.get('url') == url else None
        headers: dict[str, str] = {}
        if resume_metadata is not None:
            headers['Range'] = f'bytes={offset}-'
            if etag := resume_metadata.get('etag'):
                headers['If-Range'] = str(etag)
            elif last_modified := resume_metadata.get('last_modified'):
                headers['If-Range'] = str(last_modified)

        request = urllib.request.Request(url, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as exc:
            completed_partial = resume_metadata is not None and _partial_download_is_complete(resume_metadata, offset)
            if exc.code == 416 and completed_partial:
                return
            raise
        with response:
            status = getattr(response, 'status', 200)
            response_etag = response.headers.get('ETag')
            if resume_metadata is not None and status == 206 and _content_range_start(response.headers) != offset:
                _clear_partial_download(destination, metadata_path)
                continue
            append = resume_metadata is not None and status == 206
            if not append:
                offset = 0
            total_bytes = _total_bytes(response.headers, offset)
            if (
                resume_metadata is not None
                and status == 206
                and (
                    _etag_changed(resume_metadata, response_etag) or _total_bytes_changed(resume_metadata, total_bytes)
                )
            ):
                _clear_partial_download(destination, metadata_path)
                continue
            _write_partial_metadata(
                metadata_path,
                {
                    'url': url,
                    'etag': response_etag,
                    'last_modified': response.headers.get('Last-Modified'),
                    'total_bytes': total_bytes,
                },
            )
            mode = 'ab' if append else 'wb'
            completed_bytes = offset
            if progress is not None:
                progress.start(total_bytes, completed_bytes)
            with destination.open(mode) as output:
                while chunk := response.read(_DOWNLOAD_CHUNK_SIZE):
                    output.write(chunk)
                    completed_bytes += len(chunk)
                    if progress is not None:
                        progress.advance(completed_bytes)
            if total_bytes is not None and completed_bytes != total_bytes:
                raise _IncompleteDownloadError(f'响应不完整：已收到 {completed_bytes} / {total_bytes} 字节。')
            return

    raise ModelDownloadError('下载源在续传期间发生变化，请重新开始下载。')


def _partial_archive_path(target_dir: Path) -> Path:
    return target_dir / f'.{KOKORO_MODEL_NAME}.tar.bz2.part'


def _partial_metadata_path(target_dir: Path) -> Path:
    return target_dir / f'.{KOKORO_MODEL_NAME}.tar.bz2.part.json'


def _load_partial_metadata(path: Path) -> dict[str, object] | None:
    try:
        loaded = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_partial_metadata(path: Path, values: dict[str, object]) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(values), encoding='utf-8')
    temporary.replace(path)


def _total_bytes(headers: object, offset: int) -> int | None:
    if not hasattr(headers, 'get'):
        return None
    content_range = headers.get('Content-Range')
    if isinstance(content_range, str) and '/' in content_range:
        total = content_range.rsplit('/', maxsplit=1)[1]
        if total.isdigit():
            return int(total)
    content_length = headers.get('Content-Length')
    if isinstance(content_length, str) and content_length.isdigit():
        return offset + int(content_length)
    return None


def _content_range_start(headers: object) -> int | None:
    if not hasattr(headers, 'get'):
        return None
    content_range = headers.get('Content-Range')
    if not isinstance(content_range, str) or not content_range.startswith('bytes '):
        return None
    range_part = content_range.removeprefix('bytes ').split('/', maxsplit=1)[0]
    start, _, _ = range_part.partition('-')
    return int(start) if start.isdigit() else None


def _etag_changed(metadata: dict[str, object], response_etag: str | None) -> bool:
    previous_etag = metadata.get('etag')
    return isinstance(previous_etag, str) and response_etag is not None and previous_etag != response_etag


def _total_bytes_changed(metadata: dict[str, object], total_bytes: int | None) -> bool:
    previous_total = metadata.get('total_bytes')
    return isinstance(previous_total, int) and total_bytes is not None and previous_total != total_bytes


def _partial_download_is_complete(metadata: dict[str, object], offset: int) -> bool:
    total_bytes = metadata.get('total_bytes')
    return isinstance(total_bytes, int) and offset == total_bytes


def _clear_partial_download(archive_path: Path, metadata_path: Path) -> None:
    archive_path.unlink(missing_ok=True)
    metadata_path.unlink(missing_ok=True)


def _is_retryable_download_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (ConnectionError, TimeoutError, OSError, urllib.error.URLError))


def _model_paths(model_dir: Path) -> KokoroModelPaths:
    return KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.int8.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )


def _is_valid(paths: KokoroModelPaths) -> bool:
    return (
        paths.model_path.is_file()
        and paths.voices_path.is_file()
        and paths.tokens_path.is_file()
        and paths.lexicon_us_en_path.is_file()
        and paths.lexicon_zh_path.is_file()
        and paths.data_dir.is_dir()
    )


def _validate(paths: KokoroModelPaths) -> None:
    missing: list[str] = []
    if not paths.model_path.is_file():
        missing.append('model.int8.onnx')
    if not paths.voices_path.is_file():
        missing.append('voices.bin')
    if not paths.tokens_path.is_file():
        missing.append('tokens.txt')
    if not paths.lexicon_us_en_path.is_file():
        missing.append('lexicon-us-en.txt')
    if not paths.lexicon_zh_path.is_file():
        missing.append('lexicon-zh.txt')
    if not paths.data_dir.is_dir():
        missing.append('espeak-ng-data')
    if missing:
        raise ModelDownloadError(f'Kokoro 模型缺少必要文件：{", ".join(missing)}')


def _find_extracted_root(extract_dir: Path) -> Path:
    children = [child for child in extract_dir.iterdir() if child.is_dir()]
    if len(children) != 1:
        raise ModelDownloadError('Kokoro 模型压缩包结构不符合预期。')
    return children[0]
