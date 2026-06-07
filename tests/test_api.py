from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from read_along.api import create_app, get_material_library
from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.importers import UrlImportError
from read_along.material_library import MaterialLibrary
from read_along.models import MaterialDetail, ReadingMaterialDraft, ReadingMaterialDraftParagraph, SourceType
from read_along.storage import StoragePaths


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "read-along"}


def test_material_list_returns_empty_shelf(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get("/api/materials")

    assert response.status_code == 200
    assert response.json() == []


def test_material_list_returns_saved_material(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get("/api/materials")

    assert response.status_code == 200
    assert response.json()[0]["id"] == material.id
    assert response.json()[0]["title"] == "示例文章"
    assert response.json()[0]["primary_source"]["source_uri"] == "https://example.com/article"


def test_material_detail_returns_saved_material(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    material = _save_url_material(library)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get(f"/api/materials/{material.id}")

    assert response.status_code == 200
    assert response.json()["id"] == material.id
    assert response.json()["paragraphs"][0]["sentences"][0]["text"] == "第一句。"


def test_material_detail_returns_chinese_not_found_error(tmp_path: Path) -> None:
    library = _make_library(tmp_path)
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.get("/api/materials/mat_missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "阅读材料不存在：mat_missing"}


def test_pdf_import_rejects_non_pdf_with_chinese_detail() -> None:
    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: None
    client = TestClient(app)

    response = client.post(
        "/api/import/pdf",
        files={"file": ("note.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "仅支持 PDF 文件。"}


def test_pdf_import_uses_material_library(tmp_path: Path) -> None:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / "data"))
    initialize_database(paths)
    library = MaterialLibrary(paths)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 50), "Hello PDF.")
    content = document.tobytes()
    document.close()

    app = create_app()
    app.dependency_overrides[get_material_library] = lambda: library
    client = TestClient(app)

    response = client.post(
        "/api/import/pdf",
        files={"file": ("example.pdf", content, "application/pdf")},
    )

    assert response.status_code == 200
    material_id = response.json()["id"]
    assert library.get(material_id).primary_source.source_uri == "example.pdf"


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
    ) -> MaterialDetail:
        assert url == "https://example.com/article"
        assert mode == "auto"
        return _save_url_material(library)

    monkeypatch.setattr("read_along.api.import_url", fake_import_url)

    response = client.post(
        "/api/import/url",
        json={"url": "https://example.com/article"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "示例文章"
    assert response.json()["primary_source"]["source_type"] == "url"
    assert response.json()["paragraphs"][0]["sentences"][0]["text"] == "第一句。"


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
    ) -> MaterialDetail:
        raise UrlImportError("网页正文为空或无法抽取。")

    monkeypatch.setattr("read_along.api.import_url", fail_import_url)

    response = client.post(
        "/api/import/url",
        json={"url": "https://example.com/empty"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "网页正文为空或无法抽取。"}


def _make_library(tmp_path: Path) -> MaterialLibrary:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / "data"))
    initialize_database(paths)
    return MaterialLibrary(paths)


def _save_url_material(library: MaterialLibrary) -> MaterialDetail:
    return library.save(
        ReadingMaterialDraft(
            source_type=SourceType.URL,
            source_uri="https://example.com/article",
            title="示例文章",
            paragraphs=[
                ReadingMaterialDraftParagraph(
                    text="第一句。 第二句。",
                    sentences=["第一句。", "第二句。"],
                ),
            ],
        )
    )
