from fastapi import APIRouter, FastAPI

from app import health
from app.config import get_settings
from app.errors import install_error_handling

API_PREFIX = "/api/v1"

# Роутеры модулей. Каждый модуль добавляет сюда одну строку.
MODULE_ROUTERS: list[APIRouter] = []


def create_app() -> FastAPI:
    get_settings()  # неверная конфигурация останавливает запуск
    app = FastAPI(
        title="QA System API",
        version="0.2.0-draft",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    install_error_handling(app)
    # /livez и /readyz — для проверок контейнера (165); те же пути под /api/v1 — по OpenAPI.
    app.include_router(health.router, include_in_schema=False)
    app.include_router(health.router, prefix=API_PREFIX)
    for router in MODULE_ROUTERS:
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
