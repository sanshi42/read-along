from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.ids import generate_source_id
from read_along.material_library import (
    InvalidDraftError,
    InvalidProgressError,
    MaterialLibrary,
    MaterialLibraryError,
    MaterialNotFoundError,
    SourceChangedError,
)
from read_along.models import (
    ReadingMaterialDraft,
    ReadingMaterialDraftParagraph,
    SourceType,
)
from read_along.storage import StoragePaths


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
    reopened = MaterialLibrary(library.storage_paths).get(result.id)

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

    assert second.id == first.id
    assert len(second.sources) == 1
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

    assert second.id == first.id
    assert second.title == '首次标题'
    assert len(second.sources) == 2
    assert second.sources[1].is_primary is False
    assert second.sources[1].source_path is None


def test_normalized_url_identifies_same_source(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    first = library.save(url_draft(url='HTTPS://Example.COM:443/article#section'))

    second = library.save(url_draft(url='https://example.com/article'))

    assert second.id == first.id
    assert len(second.sources) == 1
    assert second.primary_source.source_key == 'https://example.com/article'


def test_same_source_with_changed_content_raises_conflict(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    original = library.save(url_draft())

    with pytest.raises(SourceChangedError, match='发生变化'):
        library.save(url_draft(sentences=('新的正文。',)))

    assert library.get(original.id).paragraphs[0].sentences[0].text == '第一句。'


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

    progress = library.save_progress(first.id, first.paragraphs[0].sentences[0].id, 1.25)
    shelf = library.list_shelf()

    assert progress.playback_rate == 1.25
    assert [item.id for item in shelf] == [first.id, second.id]
    assert shelf[0].progress is not None
    assert shelf[0].primary_source.source_uri == 'https://example.com/first'


def test_save_progress_validates_material_sentence_and_rate(tmp_path: Path) -> None:
    library, _ = material_library(tmp_path)
    first = library.save(url_draft(url='https://example.com/first', sentences=('甲。',)))
    second = library.save(url_draft(url='https://example.com/second', sentences=('乙。',)))

    with pytest.raises(MaterialNotFoundError):
        library.save_progress('missing', first.paragraphs[0].sentences[0].id, 1.0)
    with pytest.raises(InvalidProgressError, match='不属于'):
        library.save_progress(first.id, second.paragraphs[0].sentences[0].id, 1.0)
    with pytest.raises(InvalidProgressError, match='大于零'):
        library.save_progress(first.id, first.paragraphs[0].sentences[0].id, 0)


def test_delete_is_idempotent_and_cleans_owned_files(tmp_path: Path) -> None:
    library, paths = material_library(tmp_path)
    material = library.save(pdf_draft(tmp_path))
    audio_dir = paths.audio / material.id
    audio_dir.mkdir()
    (audio_dir / 'sentence.aiff').write_bytes(b'audio')
    source_path = Path(material.primary_source.source_path or '')

    library.delete(material.id)
    library.delete(material.id)

    with pytest.raises(MaterialNotFoundError):
        library.get(material.id)
    assert not source_path.exists()
    assert not audio_dir.exists()
