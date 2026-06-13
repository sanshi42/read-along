from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from read_along.api import create_app, get_material_library
from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.importers import UrlImportError
from read_along.material_library import MaterialLibrary
from read_along.models import MaterialImportResult, ReadingMaterialDraft, ReadingMaterialDraftParagraph, SourceType
from read_along.storage import StoragePaths
from read_along.tts import TTSGenerationError


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get('/api/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'service': 'read-along'}


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


def test_material_detail_returns_saved_material(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get(f'/api/materials/{material.material.id}')

    assert response.status_code == 200
    assert response.json()['id'] == material.material.id
    assert response.json()['paragraphs'][0]['sentences'][0]['text'] == '第一句。'
    assert 'audio_path' not in response.json()['paragraphs'][0]['sentences'][0]


def test_material_detail_returns_chinese_not_found_error(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get('/api/materials/mat_missing')

    assert response.status_code == 404
    assert response.json() == {'detail': '阅读材料不存在：mat_missing'}


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
        output_path.write_bytes(b'RIFFaudioWAVE')
        return output_path

    monkeypatch.setattr(library.tts, 'generate', generate)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)
    path = f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio'

    first = client.get(path)
    second = client.get(path)

    assert first.status_code == 200
    assert first.content == b'RIFFaudioWAVE'
    assert first.headers['content-type'] == 'audio/wav'
    assert first.headers['cache-control'] == 'private, max-age=31536000, immutable'
    assert second.status_code == 200
    assert second.content == first.content
    assert calls == 1


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

    def fail_generation(text: str, output_path: Path) -> Path:
        raise TTSGenerationError('macOS say 暂时不可用。')

    monkeypatch.setattr(library.tts, 'generate', fail_generation)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get(f'/api/materials/{material.material.id}/sentences/{sentence.id}/audio')

    assert response.status_code == 503
    assert response.json() == {'detail': 'macOS say 暂时不可用。'}


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
    return MaterialLibrary(paths)


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
                    text=' '.join(sentences),
                    sentences=sentences,
                ),
            ],
        )
    )
