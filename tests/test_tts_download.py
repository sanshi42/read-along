from __future__ import annotations

import json
import tarfile
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

import read_along.tts.download as download_module
from read_along.tts.download import ModelDownloadError, download_kokoro_model


class FakeStreamingResponse:
    """模拟会在读取期间中断的 HTTP 响应。"""

    def __init__(self, chunks: list[bytes | BaseException], headers: dict[str, str], *, status: int = 200) -> None:
        self._chunks = iter(chunks)
        self.headers = headers
        self.status = status

    def read(self, _: int = -1) -> bytes:
        item = next(self._chunks, b'')
        if isinstance(item, BaseException):
            raise item
        return item

    def __enter__(self) -> FakeStreamingResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def close(self) -> None:
        return None

    def info(self) -> dict[str, str]:
        return self.headers

    def geturl(self) -> str:
        return 'https://models.example.test/kokoro.tar.bz2'


class RecordingProgress:
    def __init__(self) -> None:
        self.starts: list[tuple[int | None, int]] = []
        self.updates: list[int] = []
        self.retries: list[tuple[int, float]] = []

    def start(self, total_bytes: int | None, completed_bytes: int) -> None:
        self.starts.append((total_bytes, completed_bytes))

    def advance(self, completed_bytes: int) -> None:
        self.updates.append(completed_bytes)

    def retry(self, retry_number: int, delay_seconds: float, error: Exception) -> None:
        del error
        self.retries.append((retry_number, delay_seconds))


def make_kokoro_archive(
    tmp_path: Path,
    *,
    missing_tokens: bool = False,
    missing_zh_lexicon: bool = False,
) -> Path:
    root = tmp_path / 'kokoro-int8-multi-lang-v1_1'
    root.mkdir()
    (root / 'model.int8.onnx').write_bytes(b'model')
    (root / 'voices.bin').write_bytes(b'voices')
    if not missing_tokens:
        (root / 'tokens.txt').write_text('tokens', encoding='utf-8')
    (root / 'lexicon-us-en.txt').write_text('english lexicon', encoding='utf-8')
    if not missing_zh_lexicon:
        (root / 'lexicon-zh.txt').write_text('中文词典', encoding='utf-8')
    (root / 'espeak-ng-data').mkdir()
    (root / 'espeak-ng-data' / 'phontab').write_text('data', encoding='utf-8')
    archive = tmp_path / 'kokoro.tar.bz2'
    with tarfile.open(archive, 'w:bz2') as tar:
        tar.add(root, arcname=root.name)
    return archive


def test_download_kokoro_model_extracts_int8_release_archive_and_reports_env(tmp_path: Path) -> None:
    archive = make_kokoro_archive(tmp_path)
    target = tmp_path / 'models' / 'tts'

    result = download_kokoro_model(target, url=archive.as_uri())

    assert result.model_dir == target / 'kokoro-multi-lang-v1_1'
    assert result.model_path == result.model_dir / 'model.int8.onnx'
    assert result.voices_path == result.model_dir / 'voices.bin'
    assert result.tokens_path == result.model_dir / 'tokens.txt'
    assert result.data_dir == result.model_dir / 'espeak-ng-data'
    assert result.lexicon_us_en_path == result.model_dir / 'lexicon-us-en.txt'
    assert result.lexicon_zh_path == result.model_dir / 'lexicon-zh.txt'
    assert 'READ_ALONG_TTS_ENGINE=sherpa_onnx_tts' in result.env_text
    assert f'READ_ALONG_TTS_SHERPA_KOKORO_MODEL={result.model_path}' in result.env_text
    assert f'READ_ALONG_TTS_SHERPA_KOKORO_VOICES={result.voices_path}' in result.env_text
    assert f'READ_ALONG_TTS_SHERPA_KOKORO_TOKENS={result.tokens_path}' in result.env_text
    assert f'READ_ALONG_TTS_SHERPA_KOKORO_DATA_DIR={result.data_dir}' in result.env_text


def test_download_kokoro_model_reuses_existing_valid_model(tmp_path: Path) -> None:
    archive = make_kokoro_archive(tmp_path)
    target = tmp_path / 'models' / 'tts'
    first = download_kokoro_model(target, url=archive.as_uri())

    second = download_kokoro_model(target, url='file:///missing.tar.bz2')

    assert second == first


def test_download_kokoro_model_rolls_back_invalid_archive(tmp_path: Path) -> None:
    archive = make_kokoro_archive(tmp_path, missing_tokens=True)
    target = tmp_path / 'models' / 'tts'

    with pytest.raises(ModelDownloadError, match='tokens.txt'):
        download_kokoro_model(target, url=archive.as_uri())

    assert not (target / 'kokoro-multi-lang-v1_1').exists()
    assert not any(target.glob('.kokoro-download-*'))


def test_download_kokoro_model_rejects_archive_without_multilingual_lexicon(
    tmp_path: Path,
) -> None:
    archive = make_kokoro_archive(tmp_path, missing_zh_lexicon=True)
    target = tmp_path / 'models' / 'tts'

    with pytest.raises(ModelDownloadError, match='lexicon-zh.txt'):
        download_kokoro_model(target, url=archive.as_uri())

    assert not (target / 'kokoro-multi-lang-v1_1').exists()


def test_download_kokoro_model_keeps_partial_archive_after_connection_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    offset = len(content) // 2
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        if len(requests) > 1:
            return FakeStreamingResponse(
                [ConnectionResetError('连接被重置')],
                {
                    'Content-Length': str(len(content) - offset),
                    'Content-Range': f'bytes {offset}-{len(content) - 1}/{len(content)}',
                    'ETag': '"kokoro-v1"',
                },
                status=206,
            )
        return FakeStreamingResponse(
            [content[:offset], ConnectionResetError('连接被重置')],
            {'Content-Length': str(len(content)), 'ETag': '"kokoro-v1"'},
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    monkeypatch.setattr(download_module, '_sleep', lambda _: None, raising=False)

    with pytest.raises(ModelDownloadError, match='连接被重置'):
        download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    partial = target / '.kokoro-multi-lang-v1_1.tar.bz2.part'
    assert partial.read_bytes() == content[:offset]
    assert len(requests) == 4
    assert isinstance(requests[0], urllib.request.Request)
    assert requests[0].full_url == 'https://models.example.test/kokoro.tar.bz2'


def test_download_kokoro_model_resumes_matching_partial_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    target.mkdir(parents=True)
    offset = len(content) // 2
    partial = target / '.kokoro-multi-lang-v1_1.tar.bz2.part'
    partial.write_bytes(content[:offset])
    metadata = target / '.kokoro-multi-lang-v1_1.tar.bz2.part.json'
    metadata.write_text(
        json.dumps(
            {
                'url': 'https://models.example.test/kokoro.tar.bz2',
                'etag': '"kokoro-v1"',
                'last_modified': None,
                'total_bytes': len(content),
            }
        ),
        encoding='utf-8',
    )
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        return FakeStreamingResponse(
            [content[offset:]],
            {
                'Content-Length': str(len(content) - offset),
                'Content-Range': f'bytes {offset}-{len(content) - 1}/{len(content)}',
                'ETag': '"kokoro-v1"',
            },
            status=206,
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert requests[0].get_header('Range') == f'bytes={offset}-'
    assert requests[0].get_header('If-range') == '"kokoro-v1"'
    assert not partial.exists()
    assert not metadata.exists()


def test_download_kokoro_model_restarts_when_partial_archive_etag_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    target.mkdir(parents=True)
    offset = len(content) // 2
    partial = target / '.kokoro-multi-lang-v1_1.tar.bz2.part'
    partial.write_bytes(content[:offset])
    metadata = target / '.kokoro-multi-lang-v1_1.tar.bz2.part.json'
    metadata.write_text(
        json.dumps(
            {
                'url': 'https://models.example.test/kokoro.tar.bz2',
                'etag': '"kokoro-v1"',
                'last_modified': None,
                'total_bytes': len(content),
            }
        ),
        encoding='utf-8',
    )
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        if len(requests) == 1:
            return FakeStreamingResponse(
                [content[offset:]],
                {
                    'Content-Length': str(len(content) - offset),
                    'Content-Range': f'bytes {offset}-{len(content) - 1}/{len(content)}',
                    'ETag': '"kokoro-v2"',
                },
                status=206,
            )
        return FakeStreamingResponse(
            [content],
            {'Content-Length': str(len(content)), 'ETag': '"kokoro-v2"'},
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert requests[0].get_header('Range') == f'bytes={offset}-'
    assert requests[1].get_header('Range') is None


def test_download_kokoro_model_restarts_when_partial_archive_size_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    target.mkdir(parents=True)
    offset = len(content) // 2
    partial = target / '.kokoro-multi-lang-v1_1.tar.bz2.part'
    partial.write_bytes(content[:offset])
    metadata = target / '.kokoro-multi-lang-v1_1.tar.bz2.part.json'
    metadata.write_text(
        json.dumps(
            {
                'url': 'https://models.example.test/kokoro.tar.bz2',
                'etag': None,
                'last_modified': None,
                'total_bytes': len(content),
            }
        ),
        encoding='utf-8',
    )
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        if len(requests) == 1:
            return FakeStreamingResponse(
                [content[offset:]],
                {
                    'Content-Length': str(len(content) - offset),
                    'Content-Range': f'bytes {offset}-{len(content) - 1}/{len(content) + 1}',
                },
                status=206,
            )
        return FakeStreamingResponse(
            [content],
            {'Content-Length': str(len(content))},
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert requests[0].get_header('Range') == f'bytes={offset}-'
    assert requests[1].get_header('Range') is None


def test_download_kokoro_model_reports_byte_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    progress = RecordingProgress()

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del request, timeout
        return FakeStreamingResponse(
            [content],
            {'Content-Length': str(len(content)), 'ETag': '"kokoro-v1"'},
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(
        target,
        url='https://models.example.test/kokoro.tar.bz2',
        progress=progress,
    )

    assert result.model_dir.is_dir()
    assert progress.starts == [(len(content), 0)]
    assert progress.updates[-1] == len(content)


def test_download_kokoro_model_retries_once_after_invalid_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        if len(requests) == 1:
            invalid_archive = b'not a valid bzip2 archive'
            return FakeStreamingResponse([invalid_archive], {'Content-Length': str(len(invalid_archive))})
        return FakeStreamingResponse([content], {'Content-Length': str(len(content))})

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert len(requests) == 2
    assert requests[0].get_header('Range') is None
    assert requests[1].get_header('Range') is None


def test_download_kokoro_model_resumes_after_response_ends_before_content_length(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    offset = len(content) // 2
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        if len(requests) == 1:
            return FakeStreamingResponse(
                [content[:offset]],
                {'Content-Length': str(len(content)), 'ETag': '"kokoro-v1"'},
            )
        return FakeStreamingResponse(
            [content[offset:]],
            {
                'Content-Length': str(len(content) - offset),
                'Content-Range': f'bytes {offset}-{len(content) - 1}/{len(content)}',
                'ETag': '"kokoro-v1"',
            },
            status=206,
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    monkeypatch.setattr(download_module, '_sleep', lambda _: None)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert requests[1].get_header('Range') == f'bytes={offset}-'


def test_download_kokoro_model_restarts_from_full_response_when_server_ignores_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    target.mkdir(parents=True)
    offset = len(content) // 2
    partial = target / '.kokoro-multi-lang-v1_1.tar.bz2.part'
    partial.write_bytes(content[:offset])
    (target / '.kokoro-multi-lang-v1_1.tar.bz2.part.json').write_text(
        json.dumps(
            {
                'url': 'https://models.example.test/kokoro.tar.bz2',
                'etag': '"kokoro-v1"',
                'last_modified': None,
                'total_bytes': len(content),
            }
        ),
        encoding='utf-8',
    )
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        return FakeStreamingResponse(
            [content],
            {'Content-Length': str(len(content)), 'ETag': '"kokoro-v1"'},
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert requests[0].get_header('Range') == f'bytes={offset}-'


def test_download_kokoro_model_restart_discards_partial_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    target.mkdir(parents=True)
    (target / '.kokoro-multi-lang-v1_1.tar.bz2.part').write_bytes(b'broken partial archive')
    (target / '.kokoro-multi-lang-v1_1.tar.bz2.part.json').write_text(
        json.dumps({'url': 'https://models.example.test/kokoro.tar.bz2'}), encoding='utf-8'
    )
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        return FakeStreamingResponse([content], {'Content-Length': str(len(content))})

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2', restart=True)

    assert result.model_dir.is_dir()
    assert requests[0].get_header('Range') is None


def test_download_kokoro_model_installs_complete_partial_after_range_416(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    target.mkdir(parents=True)
    partial = target / '.kokoro-multi-lang-v1_1.tar.bz2.part'
    partial.write_bytes(content)
    (target / '.kokoro-multi-lang-v1_1.tar.bz2.part.json').write_text(
        json.dumps(
            {
                'url': 'https://models.example.test/kokoro.tar.bz2',
                'etag': '"kokoro-v1"',
                'last_modified': None,
                'total_bytes': len(content),
            }
        ),
        encoding='utf-8',
    )
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        raise urllib.error.HTTPError(request.full_url, 416, 'Range Not Satisfiable', Message(), None)

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert requests[0].get_header('Range') == f'bytes={len(content)}-'


def test_download_kokoro_model_retries_server_error_with_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    progress = RecordingProgress()
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        if len(requests) == 1:
            raise urllib.error.HTTPError(request.full_url, 503, 'Service Unavailable', Message(), None)
        return FakeStreamingResponse([content], {'Content-Length': str(len(content))})

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    monkeypatch.setattr(download_module, '_sleep', lambda _: None)

    result = download_kokoro_model(
        target,
        url='https://models.example.test/kokoro.tar.bz2',
        progress=progress,
    )

    assert result.model_dir.is_dir()
    assert len(requests) == 2
    assert progress.retries == [(1, 1.0)]


def test_download_kokoro_model_restarts_when_content_range_starts_at_wrong_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_kokoro_archive(tmp_path)
    content = archive.read_bytes()
    target = tmp_path / 'models' / 'tts'
    target.mkdir(parents=True)
    offset = len(content) // 2
    (target / '.kokoro-multi-lang-v1_1.tar.bz2.part').write_bytes(content[:offset])
    (target / '.kokoro-multi-lang-v1_1.tar.bz2.part.json').write_text(
        json.dumps(
            {
                'url': 'https://models.example.test/kokoro.tar.bz2',
                'etag': '"kokoro-v1"',
                'last_modified': None,
                'total_bytes': len(content),
            }
        ),
        encoding='utf-8',
    )
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: str | urllib.request.Request,
        _: bytes | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del timeout
        assert isinstance(request, urllib.request.Request)
        requests.append(request)
        if len(requests) == 1:
            return FakeStreamingResponse(
                [content[offset:]],
                {
                    'Content-Length': str(len(content) - offset),
                    'Content-Range': f'bytes {offset + 1}-{len(content) - 1}/{len(content)}',
                    'ETag': '"kokoro-v1"',
                },
                status=206,
            )
        return FakeStreamingResponse(
            [content],
            {'Content-Length': str(len(content)), 'ETag': '"kokoro-v1"'},
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = download_kokoro_model(target, url='https://models.example.test/kokoro.tar.bz2')

    assert result.model_dir.is_dir()
    assert requests[0].get_header('Range') == f'bytes={offset}-'
    assert requests[1].get_header('Range') is None
