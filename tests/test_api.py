from fastapi.testclient import TestClient

from read_along.api import create_app, get_repository, get_storage_paths


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "read-along"}


def test_pdf_import_rejects_non_pdf_with_chinese_detail() -> None:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: None
    app.dependency_overrides[get_storage_paths] = lambda: None
    client = TestClient(app)

    response = client.post(
        "/api/import/pdf",
        files={"file": ("note.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "仅支持 PDF 文件。"}
