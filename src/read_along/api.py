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
from read_along.material_library import InvalidDraftError, MaterialLibrary, MaterialNotFoundError
from read_along.storage import StoragePaths


class AppState:
    def __init__(
        self,
        storage_paths: StoragePaths,
        material_library: MaterialLibrary,
    ) -> None:
        self.storage_paths = storage_paths
        self.material_library = material_library


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
    material_library = MaterialLibrary(storage_paths)
    _state = AppState(
        storage_paths=storage_paths,
        material_library=material_library,
    )
    return _state


def get_storage_paths() -> StoragePaths:
    state = _state
    assert state is not None, "应用状态尚未初始化"
    return state.storage_paths


def get_material_library() -> MaterialLibrary:
    state = _state
    assert state is not None, "应用状态尚未初始化"
    return state.material_library


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

    @app.get("/api/materials")
    def list_materials(
        *,
        library: MaterialLibrary = Depends(get_material_library),
    ) -> Any:
        return [material.model_dump(mode="json") for material in library.list_shelf()]

    @app.get("/api/materials/{material_id}")
    def get_material(
        material_id: str,
        *,
        library: MaterialLibrary = Depends(get_material_library),
    ) -> Any:
        try:
            return library.get(material_id).model_dump(mode="json")
        except MaterialNotFoundError as exc:
            return JSONResponse(
                status_code=404,
                content={"detail": str(exc)},
            )

    @app.post("/api/import/pdf")
    async def import_pdf_endpoint(
        file: UploadFile,
        *,
        library: MaterialLibrary = Depends(get_material_library),
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
                library=library,
            )
            return result.model_dump(mode="json")
        except (InvalidDraftError, ValueError) as exc:
            return JSONResponse(
                status_code=422,
                content={"detail": str(exc)},
            )
        finally:
            # 清理临时文件
            tmp_path.unlink(missing_ok=True)

    return app


app = create_app()
