from __future__ import annotations

import hashlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.ids import generate_source_id
from read_along.material_library import (
    AudioGenerationError,
    AudioNotFoundError,
    InvalidDraftError,
    InvalidProgressError,
    MaterialLibrary,
    MaterialLibraryError,
    MaterialNotFoundError,
    SourceChangedError,
)
from read_along.models import (
    AudioStatus,
    ImportOutcome,
    ReadingMaterialDraft,
    ReadingMaterialDraftParagraph,
    SourceType,
)
from read_along.storage import StoragePaths
from read_along.tts import TTSGenerationError


def material_library(tmp_path: Path) -> tuple[MaterialLibrary, StoragePaths]:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / 'data'))
    initialize_database(paths)
    return MaterialLibrary(paths), paths


def paragraph(*sentences: str, source_label: str | None = None) -> ReadingMaterialDraftParagraph:
    return ReadingMaterialDraftParagraph(
        text=' '.join(sentences),
        source_label=source_label,
        sentences=list(sentences),
    )


def url_draft(
    *,
    url: str = 'https://example.com/article',
    title: str = '示例材料',
    sentences: tuple[str, ...] = ('第一句。', '第二句。'),
) -> ReadingMaterialDraft:
    return ReadingMaterialDraft(
        source_type=SourceType.URL,
        source_uri=url,
        title=title,
        paragraphs=[paragraph(*sentences)],
    )


def pdf_draft(tmp_path: Path, *, content: bytes = b'pdf bytes') -> ReadingMaterialDraft:
    source_file = tmp_path / 'example.pdf'
    source_file.write_bytes(content)
    return ReadingMaterialDraft(
        source_type=SourceType.PDF,
        source_uri='example.pdf',
        title='PDF 材料',
        source_file=source_file,
        paragraphs=[paragraph('PDF 正文。', source_label='第 1 页')],
    )


def test_save_persists_complete_material_and_owned_source_file(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)

    result = library.save(pdf_draft(tmp_path))
    reopened = MaterialLibrary(library.storage_paths).get(result.material.id)

    assert result.outcome is ImportOutcome.CREATED
    assert reopened.title == 'PDF 材料'
    assert reopened.primary_source.source_type is SourceType.PDF
    assert reopened.primary_source.is_primary is True
    assert reopened.primary_source.source_path is not None
    assert Path(reopened.primary_source.source_path).read_bytes() == b'pdf bytes'
    assert reopened.progress is None
    assert reopened.paragraphs[0].source_label == '第 1 页'
    assert reopened.paragraphs[0].sentences[0].text == 'PDF 正文。'


def test_save_rejects_invalid_draft(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    draft = url_draft()
    draft.paragraphs[0].text = '不一致的段落正文'

    with pytest.raises(InvalidDraftError, match='不一致'):
        library.save(draft)

    assert library.list_shelf() == []


def test_same_source_and_content_returns_existing_material(tmp_path: Path) -> None:
    library, paths = material_library(tmp_path)
    draft = pdf_draft(tmp_path)

    first = library.save(draft)
    second = library.save(draft)

    assert first.outcome is ImportOutcome.CREATED
    assert second.outcome is ImportOutcome.REUSED_SOURCE
    assert second.material.id == first.material.id
    assert len(second.material.sources) == 1
    assert len(list(paths.uploads.iterdir())) == 1


def test_same_content_from_different_source_adds_identity_without_replacing_title(
    tmp_path: Path,
) -> None:
    library, _ = material_library(tmp_path)
    first = library.save(url_draft(title='首次标题'))

    second = library.save(
        url_draft(
            url='https://other.example.com/copy',
            title='后续标题',
        )
    )

    assert first.outcome is ImportOutcome.CREATED
    assert second.outcome is ImportOutcome.REUSED_CONTENT
    assert second.material.id == first.material.id
    assert second.material.title == '首次标题'
    assert len(second.material.sources) == 2
    assert second.material.sources[1].is_primary is False
    assert second.material.sources[1].source_path is None


def test_normalized_url_identifies_same_source(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    first = library.save(url_draft(url='HTTPS://Example.COM:443/article#section'))

    second = library.save(url_draft(url='https://example.com/article'))

    assert second.outcome is ImportOutcome.REUSED_SOURCE
    assert second.material.id == first.material.id
    assert len(second.material.sources) == 1
    assert second.material.primary_source.source_key == 'https://example.com/article'


def test_same_source_with_changed_content_raises_conflict(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    original = library.save(url_draft())

    with pytest.raises(
        SourceChangedError,
        match='此来源的正文与已保存版本不同。为避免覆盖现有阅读材料，本次未导入。',
    ):
        library.save(url_draft(sentences=('新的正文。',)))

    assert library.get(original.material.id).paragraphs[0].sentences[0].text == '第一句。'


def test_save_failure_rolls_back_database_and_cleans_copied_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)

    def fail_insert(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError('测试写入失败')

    monkeypatch.setattr(library.repository, 'insert_sentence', fail_insert)

    with pytest.raises(MaterialLibraryError, match='保存阅读材料失败'):
        library.save(pdf_draft(tmp_path))

    assert library.list_shelf() == []
    assert list(paths.uploads.iterdir()) == []


def test_save_failure_does_not_delete_preexisting_final_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)
    draft = pdf_draft(tmp_path)
    source_key = hashlib.sha256(b'pdf bytes').hexdigest()
    final_path = paths.uploads / f'{generate_source_id("pdf", source_key)}.pdf'
    final_path.write_bytes(b'preexisting')

    def fail_insert(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError('测试写入失败')

    monkeypatch.setattr(library.repository, 'insert_sentence', fail_insert)

    with pytest.raises(MaterialLibraryError):
        library.save(draft)

    assert final_path.read_bytes() == b'preexisting'


def test_shelf_and_progress_follow_recent_activity(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    first = library.save(url_draft(url='https://example.com/first', sentences=('甲。',)))
    second = library.save(url_draft(url='https://example.com/second', sentences=('乙。',)))

    progress = library.save_progress(
        first.material.id,
        first.material.paragraphs[0].sentences[0].id,
        1.25,
    )
    shelf = library.list_shelf()

    assert progress.playback_rate == 1.25
    assert [item.id for item in shelf] == [first.material.id, second.material.id]
    assert shelf[0].progress is not None
    assert shelf[0].primary_source.source_uri == 'https://example.com/first'


def test_save_progress_persists_playback_completed_state(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    material = library.save(url_draft())
    last_sentence = material.material.paragraphs[0].sentences[-1]

    progress = library.save_progress(
        material.material.id,
        last_sentence.id,
        1.5,
        playback_completed=True,
    )
    reopened = MaterialLibrary(library.storage_paths).get(material.material.id)

    assert progress.playback_completed is True
    assert reopened.progress is not None
    assert reopened.progress.playback_completed is True


def test_save_progress_validates_material_sentence_and_rate(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    first = library.save(url_draft(url='https://example.com/first', sentences=('甲。',)))
    second = library.save(url_draft(url='https://example.com/second', sentences=('乙。',)))
    multi_sentence = library.save(url_draft(url='https://example.com/multi', sentences=('第一句。', '最后一句。')))

    with pytest.raises(MaterialNotFoundError):
        library.save_progress('missing', first.material.paragraphs[0].sentences[0].id, 1.0)
    with pytest.raises(InvalidProgressError, match='不属于'):
        library.save_progress(
            first.material.id,
            second.material.paragraphs[0].sentences[0].id,
            1.0,
        )
    with pytest.raises(InvalidProgressError, match='大于零'):
        library.save_progress(
            first.material.id,
            first.material.paragraphs[0].sentences[0].id,
            0,
        )
    with pytest.raises(InvalidProgressError, match='最后一句'):
        library.save_progress(
            multi_sentence.material.id,
            multi_sentence.material.paragraphs[0].sentences[0].id,
            1.0,
            playback_completed=True,
        )


def test_get_or_generate_audio_generates_and_persists_ready_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(url_draft(sentences=('需要朗读。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    original_updated_at = material.material.updated_at
    calls: list[tuple[str, Path]] = []

    def generate(text: str, output_path: Path) -> Path:
        calls.append((text, output_path))
        output_path.write_bytes(b'RIFFaudioWAVE')
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)

    audio_path = library.get_or_generate_audio(material.material.id, sentence.id)

    expected_path = paths.audio / material.material.id / f'{sentence.id}.wav'
    reopened = library.get(material.material.id)
    reopened_sentence = reopened.paragraphs[0].sentences[0]
    assert audio_path == expected_path
    assert calls == [('需要朗读。', expected_path)]
    assert reopened_sentence.audio_status is AudioStatus.READY
    assert reopened_sentence.audio_path == f'{material.material.id}/{sentence.id}.wav'
    assert reopened_sentence.error_message is None
    assert reopened.updated_at == original_updated_at


def test_get_or_generate_audio_reuses_existing_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, _ = material_library(tmp_path)
    material = library.save(url_draft(sentences=('需要缓存。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    calls = 0

    def generate(text: str, output_path: Path) -> Path:
        nonlocal calls
        calls += 1
        output_path.write_bytes(b'RIFFaudioWAVE')
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)

    first = library.get_or_generate_audio(material.material.id, sentence.id)
    second = library.get_or_generate_audio(material.material.id, sentence.id)

    assert first == second
    assert calls == 1


def test_get_or_generate_audio_repairs_state_when_cache_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(url_draft(sentences=('已经生成。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    expected_path = paths.audio / material.material.id / f'{sentence.id}.wav'
    expected_path.parent.mkdir()
    expected_path.write_bytes(b'RIFFaudioWAVE')
    with sqlite3.connect(paths.database) as connection:
        connection.execute(
            """
            UPDATE sentences
            SET audio_status = 'failed', audio_path = '../outside.wav', error_message = '旧错误'
            WHERE id = ?
            """,
            (sentence.id,),
        )

    monkeypatch.setattr(
        library.tts,
        'generate',
        lambda text, output_path: pytest.fail('已有缓存时不应再次生成'),
    )

    audio_path = library.get_or_generate_audio(material.material.id, sentence.id)

    reopened_sentence = library.get(material.material.id).paragraphs[0].sentences[0]
    assert audio_path == expected_path
    assert reopened_sentence.audio_status is AudioStatus.READY
    assert reopened_sentence.audio_path == f'{material.material.id}/{sentence.id}.wav'
    assert reopened_sentence.error_message is None


def test_get_or_generate_audio_regenerates_when_ready_cache_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(url_draft(sentences=('缓存丢失。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    relative_path = f'{material.material.id}/{sentence.id}.wav'
    with sqlite3.connect(paths.database) as connection:
        connection.execute(
            """
            UPDATE sentences
            SET audio_status = 'ready', audio_path = ?, error_message = NULL
            WHERE id = ?
            """,
            (relative_path, sentence.id),
        )
    calls = 0

    def generate(text: str, output_path: Path) -> Path:
        nonlocal calls
        calls += 1
        output_path.write_bytes(b'RIFFaudioWAVE')
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)

    audio_path = library.get_or_generate_audio(material.material.id, sentence.id)

    assert audio_path == paths.audio / relative_path
    assert calls == 1
    assert library.get(material.material.id).paragraphs[0].sentences[0].audio_status is AudioStatus.READY


def test_get_or_generate_audio_records_failure_and_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(url_draft(sentences=('不可暴露的正文。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    attempts = 0

    def generate(text: str, output_path: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TTSGenerationError(f'暂时失败：{paths.home}；{text}')
        output_path.write_bytes(b'RIFFaudioWAVE')
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)

    with pytest.raises(AudioGenerationError) as error:
        library.get_or_generate_audio(material.material.id, sentence.id)

    message = str(error.value)
    failed_sentence = library.get(material.material.id).paragraphs[0].sentences[0]
    assert str(paths.home) not in message
    assert sentence.text not in message
    assert failed_sentence.audio_status is AudioStatus.FAILED
    assert failed_sentence.audio_path is None
    assert failed_sentence.error_message == message

    audio_path = library.get_or_generate_audio(material.material.id, sentence.id)

    ready_sentence = library.get(material.material.id).paragraphs[0].sentences[0]
    assert audio_path.is_file()
    assert attempts == 2
    assert ready_sentence.audio_status is AudioStatus.READY
    assert ready_sentence.error_message is None


def test_get_or_generate_audio_hides_missing_material_and_sentence_identity(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    first = library.save(url_draft(url='https://example.com/first', sentences=('甲。',)))
    second = library.save(url_draft(url='https://example.com/second', sentences=('乙。',)))
    first_sentence_id = first.material.paragraphs[0].sentences[0].id
    second_sentence_id = second.material.paragraphs[0].sentences[0].id

    for material_id, sentence_id in (
        ('missing', first_sentence_id),
        (first.material.id, 'missing'),
        (first.material.id, second_sentence_id),
    ):
        with pytest.raises(AudioNotFoundError, match=r'^句子音频不存在。$'):
            library.get_or_generate_audio(material_id, sentence_id)


def test_get_or_generate_audio_reports_cache_directory_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(url_draft(sentences=('无法缓存。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    (paths.audio / material.material.id).write_text('占用目标目录')
    monkeypatch.setattr(
        library.tts,
        'generate',
        lambda text, output_path: pytest.fail('缓存目录不可用时不应调用 TTS'),
    )

    with pytest.raises(AudioGenerationError, match=r'^无法访问句子音频缓存。$') as error:
        library.get_or_generate_audio(material.material.id, sentence.id)

    failed_sentence = library.get(material.material.id).paragraphs[0].sentences[0]
    assert str(paths.home) not in str(error.value)
    assert failed_sentence.audio_status is AudioStatus.FAILED
    assert failed_sentence.error_message == '无法访问句子音频缓存。'


def test_get_or_generate_audio_reports_state_persistence_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, _ = material_library(tmp_path)
    material = library.save(url_draft(sentences=('无法写状态。',)))
    sentence = material.material.paragraphs[0].sentences[0]

    def fail_update(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError('不可暴露的数据库错误')

    monkeypatch.setattr(library.repository, 'update_sentence_audio', fail_update)
    monkeypatch.setattr(
        library.tts,
        'generate',
        lambda text, output_path: pytest.fail('状态写入失败时不应调用 TTS'),
    )

    with pytest.raises(AudioGenerationError, match=r'^无法更新句子音频状态。$'):
        library.get_or_generate_audio(material.material.id, sentence.id)


def test_get_or_generate_audio_reports_state_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, _ = material_library(tmp_path)
    material = library.save(url_draft(sentences=('无法读状态。',)))
    sentence = material.material.paragraphs[0].sentences[0]

    def fail_read(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError('不可暴露的数据库错误')

    monkeypatch.setattr(library.repository, 'get_sentence', fail_read)

    with pytest.raises(AudioGenerationError, match=r'^无法读取句子音频状态。$'):
        library.get_or_generate_audio(material.material.id, sentence.id)


def test_get_or_generate_audio_rejects_cache_path_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, _ = material_library(tmp_path)
    material = library.save(url_draft(sentences=('路径异常。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    escaped_sentence = sentence.model_copy(update={'material_id': '..'})
    monkeypatch.setattr(library.repository, 'get_sentence', lambda *args, **kwargs: escaped_sentence)
    monkeypatch.setattr(
        library.tts,
        'generate',
        lambda text, output_path: pytest.fail('缓存路径异常时不应调用 TTS'),
    )

    with pytest.raises(AudioGenerationError, match=r'^句子音频缓存路径不合法。$'):
        library.get_or_generate_audio('..', sentence.id)


def test_get_or_generate_audio_rejects_symlink_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(url_draft(sentences=('符号链接异常。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    outside = tmp_path / 'outside'
    outside.mkdir()
    (paths.audio / material.material.id).symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(
        library.tts,
        'generate',
        lambda text, output_path: pytest.fail('缓存路径逃逸时不应调用 TTS'),
    )

    with pytest.raises(AudioGenerationError, match=r'^句子音频缓存路径不合法。$'):
        library.get_or_generate_audio(material.material.id, sentence.id)

    assert list(outside.iterdir()) == []
    failed_sentence = library.get(material.material.id).paragraphs[0].sentences[0]
    assert failed_sentence.audio_status is AudioStatus.FAILED
    assert failed_sentence.error_message == '句子音频缓存路径不合法。'


def test_get_or_generate_audio_deduplicates_concurrent_requests_for_same_sentence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, _ = material_library(tmp_path)
    material = library.save(url_draft(sentences=('并发生成。',)))
    sentence = material.material.paragraphs[0].sentences[0]
    second_generation_started = threading.Event()
    count_lock = threading.Lock()
    calls = 0

    def generate(text: str, output_path: Path) -> Path:
        nonlocal calls
        with count_lock:
            calls += 1
            current_call = calls
        if current_call == 1:
            second_generation_started.wait(timeout=0.5)
        else:
            second_generation_started.set()
        output_path.write_bytes(b'RIFFaudioWAVE')
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(library.get_or_generate_audio, material.material.id, sentence.id) for _ in range(2)]
        paths = [future.result() for future in futures]

    assert paths[0] == paths[1]
    assert calls == 1


def test_get_or_generate_audio_allows_different_sentences_to_generate_concurrently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library, _ = material_library(tmp_path)
    material = library.save(url_draft(sentences=('第一句。', '第二句。')))
    sentences = material.material.paragraphs[0].sentences
    generation_barrier = threading.Barrier(2, timeout=1)

    def generate(text: str, output_path: Path) -> Path:
        generation_barrier.wait()
        output_path.write_bytes(b'RIFFaudioWAVE')
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(library.get_or_generate_audio, material.material.id, sentence.id) for sentence in sentences
        ]
        paths = [future.result() for future in futures]

    assert len(set(paths)) == 2
    assert all(path.is_file() for path in paths)


def test_delete_is_idempotent_and_cleans_owned_files(tmp_path: Path) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(pdf_draft(tmp_path))
    audio_dir = paths.audio / material.material.id
    audio_dir.mkdir()
    (audio_dir / 'sentence.aiff').write_bytes(b'audio')
    source_path = Path(material.material.primary_source.source_path or '')

    library.delete(material.material.id)
    library.delete(material.material.id)

    with pytest.raises(MaterialNotFoundError):
        library.get(material.material.id)
    assert not source_path.exists()
    assert not audio_dir.exists()
