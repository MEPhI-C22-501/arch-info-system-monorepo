import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI

from app import health
from app.admin.router import router as admin_router
from app.cases.router import router as cases_router
from app.config import get_settings
from app.defects.router import router as defects_router
from app.errors import install_error_handling
from app.plans.router import router as plans_router
from app.profiles import router as profiles_router, sync_forever
from app.reporting import router as reports_router
from app.runs.router import router as runs_router
from app.suites.router import router as suites_router
from app.templates.router import router as templates_router

API_PREFIX = "/api/v1"

# Роутеры модулей. Каждый модуль добавляет сюда одну строку.
MODULE_ROUTERS: list[APIRouter] = [
    cases_router,
    templates_router,
    suites_router,
    admin_router,
    runs_router,
    defects_router,
    plans_router,
    reports_router,
    profiles_router,
]


@asynccontextmanager
async def lifespan(_app):
    task = (
        asyncio.create_task(sync_forever())
        if (get_settings().auth_mode == "keycloak" and os.getenv("RM_BASE_URL"))
        else None
    )
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    get_settings()  # неверная конфигурация останавливает запуск
    app = FastAPI(
        title="QA System API",
        version="0.4.0-draft",  # = info.version в openapi.yaml (test_openapi_contract)
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.get(f"{API_PREFIX}/auth/config")
    def auth_config() -> dict[str, str]:
        settings = get_settings()
        return {"mode": settings.auth_mode, "issuer": settings.oidc_issuer, "clientId": "qa-system"}

    install_error_handling(app)
    # /livez и /readyz — для проверок контейнера (165); те же пути под /api/v1 — по OpenAPI.
    app.include_router(health.router, include_in_schema=False)
    app.include_router(health.router, prefix=API_PREFIX)
    for router in MODULE_ROUTERS:
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
