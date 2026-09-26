import asyncio
import threading
import wave
from pathlib import Path
from typing import Awaitable, Callable

import pymupdf
import pytest
from anyio.to_thread import current_default_thread_limiter
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import Message, Scope

import read_along.api as api
from read_along.api import create_app, get_material_library
from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.importers import UrlImportError
from read_along.material_audio import AudioLease
from read_along.material_library import MaterialLibrary
from read_along.models import MaterialImportResult, ReadingMaterialDraft, ReadingMaterialDraftParagraph, SourceType
from read_along.storage import StoragePaths
from read_along.tts import AudioFormat, GeneratedAudio, TTSGenerationError


def write_wav(path: Path, *, duration_seconds: float = 1.25, sample_rate: int = 8000) -> None:
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b'\0\0' * int(duration_seconds * sample_rate))


class FakeTTSBackend:
    engine_id = 'fake_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def fingerprint_parts(self) -> tuple[str, ...]:
        return (self.engine_id, self.audio_format)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        write_wav(output_path, duration_seconds=1.25)
        return GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get('/api/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'service': 'read-along'}


def test_app_dependencies_initialize_state_when_reload_worker_imports_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv('READ_ALONG_HOME', str(tmp_path / 'data'))
    monkeypatch.setenv('READ_ALONG_TTS_MODEL', 'kokoro-multi-lang-v1_1-int8')
    monkeypatch.setenv('READ_ALONG_TTS_VOICE_ID', '3')
    monkeypatch.setenv('READ_ALONG_TTS_PROVIDER', 'cpu')
    monkeypatch.setenv('READ_ALONG_TTS_NUM_THREADS', '2')
    monkeypatch.setenv('READ_ALONG_TTS_SPEED', '1.0')
    monkeypatch.setattr(api, '_state', None)
    client = TestClient(create_app())

    response = client.get('/api/materials')

    assert response.status_code == 200
    assert response.json() == []
    assert api._state is not None


def test_material_list_returns_empty_shelf(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get('/api/materials')

    assert response.status_code == 200
    assert response.json() == []


def test_material_list_returns_saved_material(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get('/api/materials')

    assert response.status_code == 200
    assert response.json()[0]['id'] == material.material.id
    assert response.json()[0]['title'] == '示例文章'
    assert response.json()[0]['primary_source']['source_uri'] == 'https://example.com/article'
    assert response.json()[0]['playback_position'] is None
    assert response.json()[0]['playback_time_position'] is None


def test_material_detail_returns_saved_material(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get(f'/api/materials/{material.material.id}')

    assert response.status_code == 200
    assert response.json()['id'] == material.material.id
    assert response.json()['playback_position'] is None
    assert response.json()['playback_time_position'] is None
    assert response.json()['navigation'] == {
        'first': {
            'content_hash': material.material.content_hash,
            'created_at': material.material.created_at.isoformat().replace('+00:00', 'Z'),
            'id': material.material.id,
            'title': material.material.title,
            'updated_at': material.material.updated_at.isoformat().replace('+00:00', 'Z'),
        },
        'previous': None,
        'next': None,
        'last': {
            'content_hash': material.material.content_hash,
            'created_at': material.material.created_at.isoformat().replace('+00:00', 'Z'),
            'id': material.material.id,
            'title': material.material.title,
            'updated_at': material.material.updated_at.isoformat().replace('+00:00', 'Z'),
        },
    }
    assert response.json()['paragraphs'][0]['sentences'][0]['text'] == '第一句。'
    assert response.json()['paragraphs'][0]['sentences'][0]['audio_duration_seconds'] is None
    assert 'audio_path' not in response.json()['paragraphs'][0]['sentences'][0]


def test_material_list_and_detail_return_playback_position(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    current_sentence = material.material.paragraphs[0].sentences[1]
    library.save_progress(material.material.id, current_sentence.id, 1.0, sentence_offset_seconds=2.5)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    shelf_response = client.get('/api/materials')
    detail_response = client.get(f'/api/materials/{material.material.id}')

    assert shelf_response.json()[0]['playback_position'] == {
        'sentence_index': 2,
        'sentence_count': 2,
    }
    assert detail_response.json()['playback_position'] == {
        'sentence_index': 2,
        'sentence_count': 2,
    }
    assert detail_response.json()['progress']['sentence_offset_seconds'] == 2.5


def test_material_detail_returns_chinese_not_found_error(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get('/api/materials/mat_missing')

    assert response.status_code == 404
    assert response.json() == {'detail': '阅读材料不存在：mat_missing'}


def test_delete_material_endpoint_removes_saved_material_idempotently(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    first = client.delete(f'/api/materials/{material.material.id}')
    second = client.delete(f'/api/materials/{material.material.id}')

    assert first.status_code == 204
    assert first.content == b''
    assert second.status_code == 204
    assert client.get(f'/api/materials/{material.material.id}').status_code == 404
    assert client.get('/api/materials').json() == []


def test_progress_endpoint_saves_current_sentence_rate_and_completion(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    sentence = material.material.paragraphs[0].sentences[-1]
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.put(
        f'/api/materials/{material.material.id}/progress',
        json={
            'sentence_id': sentence.id,
            'sentence_offset_seconds': 3.25,
            'playback_rate': 1.5,
            'playback_completed': True,
        },
    )

    assert response.status_code == 200
    assert response.json()['material_id'] == material.material.id
    assert response.json()['sentence_id'] == sentence.id
    assert response.json()['sentence_offset_seconds'] == 3.25
    assert response.json()['playback_rate'] == 1.5
    assert response.json()['playback_completed'] is True
    saved_progress = library.get(material.material.id).progress
    assert saved_progress is not None
    assert saved_progress.playback_completed is True
    assert saved_progress.sentence_offset_seconds == 3.25


def test_progress_endpoint_reports_invalid_material_and_sentence(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    first = _save_url_material(library, url='https://example.com/first')
    second = _save_url_material(library, url='https://example.com/second', sentences=['另一句。'])
    first_sentence = first.material.paragraphs[0].sentences[0]
    second_sentence = second.material.paragraphs[0].sentences[0]
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    missing = client.put(
        '/api/materials/missing/progress',
        json={
            'sentence_id': first_sentence.id,
            'sentence_offset_seconds': 0,
            'playback_rate': 1.0,
            'playback_completed': False,
        },
    )
    unrelated = client.put(
        f'/api/materials/{first.material.id}/progress',
        json={
            'sentence_id': second_sentence.id,
            'sentence_offset_seconds': 0,
            'playback_rate': 1.0,
            'playback_completed': False,
        },
    )

    assert missing.status_code == 404
    assert missing.json() == {'detail': '阅读材料不存在：missing'}
    assert unrelated.status_code == 422
    assert unrelated.json() == {'detail': '句子不属于指定阅读材料'}


def test_sentence_audio_endpoint_generates_and_reuses_wav(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['需要朗读。'])
    sentence = material.material.paragraphs[0].sentences[0]
    calls = 0

    def generate(text: str, output_path: Path) -> Path:
        nonlocal calls
        calls += 1
        write_wav(output_path, duration_seconds=1.5)
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)
    path = f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio'

    first = client.get(path)
    second = client.get(path)

    assert first.status_code == 200
    assert first.content.startswith(b'RIFF')
    assert first.headers['x-read-along-audio-duration-seconds'] == '1.5'
    assert first.headers['content-type'] == 'audio/wav'
    assert first.headers['cache-control'] == 'private, no-cache'
    assert second.status_code == 200
    assert second.content == first.content
    assert second.headers['x-read-along-audio-duration-seconds'] == '1.5'
    assert calls == 1


@pytest.mark.parametrize('clear_cache', [False, True], ids=['delete-material', 'clear-audio-cache'])
def test_sentence_audio_delivery_finishes_before_material_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clear_cache: bool,
) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['需要朗读。'])
    sentence = material.material.paragraphs[0].sentences[0]
    cached_audio = library.get_or_generate_audio(material.material.id, sentence.id)
    expected_audio = cached_audio.path.read_bytes()
    audio_path = f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio'
    operation_path = f'/api/materials/{material.material.id}'
    operation_name = 'delete'
    if clear_cache:
        operation_path += '/audio-cache'
        operation_name = 'clear_material_audio_cache'
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library

    async def run() -> None:
        limiter = current_default_thread_limiter()
        original_limit = limiter.total_tokens
        response_started = asyncio.Event()
        finish_start = asyncio.Event()
        removal_entered = threading.Event()
        audio_start_status: list[int] = []
        audio_messages: list[Message] = []
        removal_messages: list[Message] = []
        audio_task: asyncio.Task[list[Message]] | None = None
        removal_task: asyncio.Task[list[Message]] | None = None
        completed_with_one_worker = False
        original_operation = getattr(library, operation_name)

        def track_removal(material_id: str) -> None:
            removal_entered.set()
            original_operation(material_id)

        monkeypatch.setattr(library, operation_name, track_removal)

        async def hold_audio_start(message: Message) -> None:
            if message['type'] == 'http.response.start':
                audio_start_status.append(message['status'])
                response_started.set()
                await finish_start.wait()

        try:
            limiter.total_tokens = 1
            audio_task = asyncio.create_task(
                _send_asgi_request(
                    app,
                    'GET',
                    audio_path,
                    extensions={'http.response.pathsend': {}},
                    on_send=hold_audio_start,
                )
            )
            await asyncio.wait_for(response_started.wait(), 5)
            assert audio_start_status == [200]
            removal_task = asyncio.create_task(_send_asgi_request(app, 'DELETE', operation_path))
            assert await asyncio.wait_for(asyncio.to_thread(removal_entered.wait, 5), 6)
            assert not removal_task.done(), '音频尚未发送完毕，清理或删除已提前返回'
            finish_start.set()
            try:
                await asyncio.wait_for(asyncio.shield(audio_task), 1)
                completed_with_one_worker = True
            except TimeoutError:
                pass
        finally:
            limiter.total_tokens = original_limit
            finish_start.set()
            if audio_task is not None:
                audio_messages = await asyncio.wait_for(audio_task, 5)
            if removal_task is not None:
                removal_messages = await asyncio.wait_for(removal_task, 5)

        assert completed_with_one_worker, '清理或删除占满线程池，音频发送无法完成'
        assert audio_messages[0]['status'] == 200
        assert b''.join(message.get('body', b'') for message in audio_messages) == expected_audio
        assert all(message['type'] != 'http.response.pathsend' for message in audio_messages)
        assert removal_messages[0]['status'] == 204

    asyncio.run(run())


def test_sentence_audio_range_keeps_duration_and_cache_headers(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['需要朗读。'])
    sentence = material.material.paragraphs[0].sentences[0]
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get(
        f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio',
        headers={'Range': 'bytes=0-3'},
    )

    assert response.status_code == 206
    assert response.content == b'RIFF'
    assert response.headers['content-range'].startswith('bytes 0-3/')
    assert response.headers['content-length'] == '4'
    assert response.headers['x-read-along-audio-duration-seconds'] == '1.25'
    assert response.headers['cache-control'] == 'private, no-cache'


def test_sentence_audio_cancelled_delivery_releases_cache_for_clear(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['需要朗读。'])
    sentence = material.material.paragraphs[0].sentences[0]
    audio_path = f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio'
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library

    async def run_cancelled_delivery() -> None:
        response_started = asyncio.Event()
        continue_send = asyncio.Event()

        async def hold_audio_start(message: Message) -> None:
            if message['type'] == 'http.response.start':
                response_started.set()
                await continue_send.wait()

        request = asyncio.create_task(_send_asgi_request(app, 'GET', audio_path, on_send=hold_audio_start))
        await asyncio.wait_for(response_started.wait(), 5)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request

    asyncio.run(run_cancelled_delivery())

    result: list[int] = []
    finished = threading.Event()

    def clear_cache() -> None:
        try:
            response = TestClient(app).delete(f'/api/materials/{material.material.id}/audio-cache')
            result.append(response.status_code)
        finally:
            finished.set()

    threading.Thread(target=clear_cache, daemon=True).start()
    assert finished.wait(5), '取消音频响应后，清理缓存仍被占用的租约阻塞'
    assert result == [204]


def test_sentence_audio_send_error_releases_cache_for_clear(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['需要朗读。'])
    sentence = material.material.paragraphs[0].sentences[0]
    audio_path = f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio'
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library

    async def fail_send(message: Message) -> None:
        if message['type'] == 'http.response.start':
            raise RuntimeError('模拟音频发送失败')

    with pytest.raises(RuntimeError, match='模拟音频发送失败'):
        asyncio.run(_send_asgi_request(app, 'GET', audio_path, on_send=fail_send))

    result: list[int] = []
    finished = threading.Event()

    def clear_cache() -> None:
        try:
            result.append(TestClient(app).delete(f'/api/materials/{material.material.id}/audio-cache').status_code)
        finally:
            finished.set()

    threading.Thread(target=clear_cache, daemon=True).start()
    assert finished.wait(5), '音频发送异常后，清理缓存仍被占用的租约阻塞'
    assert result == [204]


def test_sentence_audio_cancelled_after_acquisition_releases_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['需要朗读。'])
    sentence = material.material.paragraphs[0].sentences[0]
    audio_path = f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio'
    cache_path = f'/api/materials/{material.material.id}/audio-cache'
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    acquired = threading.Event()
    return_from_worker = threading.Event()
    leases: list[AudioLease] = []
    original_acquire = library.acquire_sentence_audio

    def hold_acquired_lease(material_id: str, sentence_id: str) -> AudioLease:
        lease = original_acquire(material_id, sentence_id)
        leases.append(lease)
        acquired.set()
        return_from_worker.wait(5)
        return lease

    monkeypatch.setattr(library, 'acquire_sentence_audio', hold_acquired_lease)

    async def run() -> None:
        request = asyncio.create_task(_send_asgi_request(app, 'GET', audio_path))
        clear_request: asyncio.Task[list[Message]] | None = None
        clear_messages: list[Message] = []
        released_on_cancel = False
        try:
            assert await asyncio.wait_for(asyncio.to_thread(acquired.wait, 5), 6)
            request.cancel()
            return_from_worker.set()
            try:
                await asyncio.wait_for(request, 5)
            except asyncio.CancelledError:
                pass
            clear_request = asyncio.create_task(_send_asgi_request(app, 'DELETE', cache_path))
            try:
                clear_messages = await asyncio.wait_for(asyncio.shield(clear_request), 1)
                released_on_cancel = True
            except TimeoutError:
                pass
        finally:
            return_from_worker.set()
            for lease in leases:
                lease.close()
            if clear_request is not None:
                clear_messages = await asyncio.wait_for(clear_request, 5)

        assert released_on_cancel, '请求取消后租约未释放，清理缓存被阻塞'
        assert clear_messages[0]['status'] == 204

    asyncio.run(run())


async def _send_asgi_request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    extensions: dict[str, object] | None = None,
    on_send: Callable[[Message], Awaitable[None]] | None = None,
) -> list[Message]:
    messages: list[Message] = []
    scope: Scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'method': method,
        'path': path,
        'raw_path': path.encode(),
        'root_path': '',
        'query_string': b'',
        'headers': [],
        'extensions': extensions or {},
    }

    async def receive() -> Message:
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message: Message) -> None:
        messages.append(message)
        if on_send is not None:
            await on_send(message)

    await app(scope, receive, send)
    return messages


def test_clear_material_audio_endpoint_removes_current_material_audio_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['第一句。', '第二句。'])
    sentences = material.material.paragraphs[0].sentences

    def generate(text: str, output_path: Path) -> Path:
        write_wav(output_path)
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)
    for sentence in sentences:
        library.get_or_generate_audio(material.material.id, sentence.id)
    audio_dir = library.storage_paths.audio / material.material.id
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.delete(f'/api/materials/{material.material.id}/audio-cache')

    reopened_sentences = library.get(material.material.id).paragraphs[0].sentences
    assert response.status_code == 204
    assert not audio_dir.exists()
    assert all(sentence.audio_status.value == 'pending' for sentence in reopened_sentences)
    assert all(sentence.audio_duration_seconds is None for sentence in reopened_sentences)


def test_clear_material_audio_endpoint_reports_missing_material(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.delete('/api/materials/missing/audio-cache')

    assert response.status_code == 404
    assert response.json() == {'detail': '阅读材料不存在：missing'}


def test_sentence_audio_endpoint_hides_missing_identity(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    first = _save_url_material(library, url='https://example.com/first', sentences=['甲。'])
    second = _save_url_material(library, url='https://example.com/second', sentences=['乙。'])
    first_sentence_id = first.material.paragraphs[0].sentences[0].id
    second_sentence_id = second.material.paragraphs[0].sentences[0].id
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    for material_id, sentence_id in (
        ('missing', first_sentence_id),
        (first.material.id, 'missing'),
        (first.material.id, second_sentence_id),
    ):
        response = client.get(f'/api/materials/{material_id}/sentences/{sentence_id}/audio')

        assert response.status_code == 404
        assert response.json() == {'detail': '句子音频不存在。'}


def test_sentence_audio_endpoint_returns_retryable_generation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library, sentences=['生成失败。'])
    sentence = material.material.paragraphs[0].sentences[0]

    def fail_generation(text: str, output_path: Path) -> GeneratedAudio:
        raise TTSGenerationError('TTS 暂时不可用。')

    monkeypatch.setattr(library.tts, 'generate', fail_generation)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get(f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio')

    assert response.status_code == 503
    assert response.json() == {'detail': 'TTS 暂时不可用。'}


def test_pdf_import_rejects_non_pdf_with_chinese_detail() -> None:
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: None
    client = TestClient(app)

    response = client.post(
        '/api/import/pdf',
        files={'file': ('note.txt', b'plain text', 'text/plain')},
    )

    assert response.status_code == 400
    assert response.json() == {'detail': '仅支持 PDF 文件。'}


def test_pdf_import_uses_material_library(tmp_path: Path) -> None:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / 'data'))
    initialize_database(paths)
    library = MaterialLibrary(paths)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 50), 'Hello PDF.')
    content = document.tobytes()
    document.close()

    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.post(
        '/api/import/pdf',
        files={'file': ('example.pdf', content, 'application/pdf')},
    )

    assert response.status_code == 200
    assert response.json()['outcome'] == 'created'
    assert response.json()['material']['playback_position'] is None
    material_id = response.json()['material']['id']
    assert library.get(material_id).primary_source.source_uri == 'example.pdf'


def test_url_import_uses_material_library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    def fake_import_url(
        *,
        url: str,
        mode: str,
        library: MaterialLibrary,
    ) -> MaterialImportResult:
        assert url == 'https://example.com/article'
        assert mode == 'auto'
        return _save_url_material(library)

    monkeypatch.setattr('read_along.api.import_url', fake_import_url)

    response = client.post(
        '/api/import/url',
        json={'url': 'https://example.com/article'},
    )

    assert response.status_code == 200
    assert response.json()['outcome'] == 'created'
    assert response.json()['material']['title'] == '示例文章'
    assert response.json()['material']['primary_source']['source_type'] == 'url'
    assert response.json()['material']['playback_position'] is None
    assert response.json()['material']['paragraphs'][0]['sentences'][0]['text'] == '第一句。'
    assert 'audio_path' not in response.json()['material']['paragraphs'][0]['sentences'][0]


def test_url_import_reports_reused_source_and_reused_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    def fake_import_url(
        *,
        url: str,
        mode: str,
        library: MaterialLibrary,
    ) -> MaterialImportResult:
        return _save_url_material(library, url=url)

    monkeypatch.setattr('read_along.api.import_url', fake_import_url)

    first = client.post('/api/import/url', json={'url': 'https://example.com/article'})
    same_source = client.post('/api/import/url', json={'url': 'https://example.com/article'})
    same_content = client.post('/api/import/url', json={'url': 'https://example.com/copy'})

    assert first.status_code == 200
    assert first.json()['outcome'] == 'created'
    assert same_source.status_code == 200
    assert same_source.json()['outcome'] == 'reused_source'
    assert same_content.status_code == 200
    assert same_content.json()['outcome'] == 'reused_content'
    assert len(same_content.json()['material']['sources']) == 2


def test_url_import_reports_source_change_without_overwriting_material(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)
    sentences = iter((['第一句。'], ['正文变化。']))

    def fake_import_url(
        *,
        url: str,
        mode: str,
        library: MaterialLibrary,
    ) -> MaterialImportResult:
        return _save_url_material(library, url=url, sentences=next(sentences))

    monkeypatch.setattr('read_along.api.import_url', fake_import_url)

    first = client.post('/api/import/url', json={'url': 'https://example.com/article'})
    changed = client.post('/api/import/url', json={'url': 'https://example.com/article'})

    assert first.status_code == 200
    assert changed.status_code == 409
    assert changed.json() == {'detail': '此来源的正文与已保存版本不同。为避免覆盖现有阅读材料，本次未导入。'}
    material_id = first.json()['material']['id']
    assert library.get(material_id).paragraphs[0].sentences[0].text == '第一句。'


def test_url_import_returns_chinese_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    def fail_import_url(
        *,
        url: str,
        mode: str,
        library: MaterialLibrary,
    ) -> MaterialImportResult:
        raise UrlImportError('网页正文为空或无法抽取。')

    monkeypatch.setattr('read_along.api.import_url', fail_import_url)

    response = client.post(
        '/api/import/url',
        json={'url': 'https://example.com/empty'},
    )

    assert response.status_code == 422
    assert response.json() == {'detail': '网页正文为空或无法抽取。'}


def _make_library(tmp_path: Path) -> MaterialLibrary:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / 'data'))
    initialize_database(paths)
    return MaterialLibrary(paths, tts=FakeTTSBackend())


def _save_url_material(
    library: MaterialLibrary,
    *,
    url: str = 'https://example.com/article',
    sentences: list[str] | None = None,
) -> MaterialImportResult:
    sentences = sentences or ['第一句。', '第二句。']
    return library.save(
        ReadingMaterialDraft(
            source_type=SourceType.URL,
            source_uri=url,
            title='示例文章',
            paragraphs=[
                ReadingMaterialDraftParagraph(
                    sentences=sentences,
                ),
            ],
        )
    )
