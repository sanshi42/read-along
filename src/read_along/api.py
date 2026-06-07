from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import Depends, FastAPI, UploadFile
from fastapi.responses import JSONResponse

from read_along import __version__
from read_along.config import load_config
from read_along.db import initialize_database
from read_along.importers import import_pdf
from read_along.repository import Repository
from read_along.storage import StoragePaths


class AppState:
    def __init__(self, storage_paths: StoragePaths, repository: Repository) -> None:
        self.storage_paths = storage_paths
        self.repository = repository


# 应用使用前由 cli.py 设置的全局状态
_state: AppState | None = None


def init_app_state() -> AppState:
    global _state
    if _state is not None:
        return _state
    config = load_config()
    storage_paths = StoragePaths.from_config(config)
    storage_paths.ensure_directories()
    initialize_database(storage_paths)
    repository = Repository(storage_paths.database)
    _state = AppState(storage_paths=storage_paths, repository=repository)
    return _state


def get_storage_paths() -> StoragePaths:
    state = _state
    assert state is not None, "应用状态尚未初始化"
    return state.storage_paths


def get_repository() -> Repository:
    state = _state
    assert state is not None, "应用状态尚未初始化"
    return state.repository


def create_app() -> FastAPI:
    app = FastAPI(
        title="Read Along API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "read-along"}

    @app.post("/api/import/pdf")
    async def import_pdf_endpoint(
        file: UploadFile,
        *,
        repo: Repository = Depends(get_repository),
        storage_paths: StoragePaths = Depends(get_storage_paths),
    ) -> Any:
        """上传文本型 PDF 并将其导入为阅读材料。"""
        if file.filename is None or not file.filename.lower().endswith(".pdf"):
            return JSONResponse(
                status_code=400,
                content={"detail": "仅支持 PDF 文件。"},
            )

        # 将上传文件保存到临时位置
        suffix = ".pdf"
        with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            content = await file.read()
            tmp.write(content)

        try:
            result = import_pdf(
                file_path=tmp_path,
                filename=file.filename,
                repo=repo,
                uploads_dir=storage_paths.uploads,
            )
            return result.model_dump(mode="json")
        except ValueError as exc:
            return JSONResponse(
                status_code=422,
                content={"detail": str(exc)},
            )
        finally:
            # 清理临时文件
            tmp_path.unlink(missing_ok=True)

    return app


app = create_app()
