from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from read_along.api import create_app, get_material_library
from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.material_library import MaterialLibrary
from read_along.storage import StoragePaths


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "read-along"}


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
