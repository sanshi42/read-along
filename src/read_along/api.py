from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from read_along import __version__


class HealthResponse(BaseModel):
    status: str
    service: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="Read Along API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="read-along")

    return app


app = create_app()
