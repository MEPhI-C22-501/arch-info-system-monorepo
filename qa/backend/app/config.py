"""Настройки из переменных окружения (165, раздел 4)."""

import os
from dataclasses import dataclass
from functools import cache

DEMO_AUTH_ENVS = {"development", "test"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_env: str
    auth_mode: str
    # false — опрос Task Tracker выключен, статусы разработки ставит QA-лид вручную (ADR-008).
    tracker_sync_enabled: bool = True
    # Адрес интерфейса для ссылок testRunUrl и testCaseUrl в «Ошибке» (130, раздел 6.1).
    ui_base_url: str = "http://localhost:8090"


@cache
def get_settings() -> Settings:
    settings = Settings(
        database_url=os.getenv(
            "DATABASE_URL", "postgresql+psycopg://qa:qa-local@localhost:5435/qa"
        ),
        app_env=os.getenv("APP_ENV", "development"),
        auth_mode=os.getenv("AUTH_MODE", "demo"),
        tracker_sync_enabled=os.getenv("TRACKER_SYNC_ENABLED", "true").lower() != "false",
        ui_base_url=os.getenv("UI_BASE_URL", "http://localhost:8090"),
    )
    if settings.auth_mode == "keycloak":
        raise RuntimeError("AUTH_MODE=keycloak ещё не реализован (TECH-09)")
    if settings.auth_mode != "demo":
        raise RuntimeError(f"Неизвестный AUTH_MODE: {settings.auth_mode}")
    if settings.app_env not in DEMO_AUTH_ENVS:
        raise RuntimeError(f"AUTH_MODE=demo запрещён при APP_ENV={settings.app_env}")
    return settings
