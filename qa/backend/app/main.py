from fastapi import APIRouter, FastAPI

from app import health
from app.admin.router import router as admin_router
from app.cases.router import router as cases_router
from app.config import get_settings
from app.errors import install_error_handling
from app.suites.router import router as suites_router
from app.templates.router import router as templates_router

API_PREFIX = "/api/v1"

# Роутеры модулей. Каждый модуль добавляет сюда одну строку.
MODULE_ROUTERS: list[APIRouter] = [
    cases_router,
    templates_router,
    suites_router,
    admin_router,
]


def create_app() -> FastAPI:
    get_settings()  # неверная конфигурация останавливает запуск
    app = FastAPI(
        title="QA System API",
        version="0.3.0-draft",  # = info.version в openapi.yaml (test_openapi_contract)
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
