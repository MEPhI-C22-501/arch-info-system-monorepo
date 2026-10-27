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


@cache
def get_settings() -> Settings:
    settings = Settings(
        database_url=os.getenv(
            "DATABASE_URL", "postgresql+psycopg://qa:qa-local@localhost:5435/qa"
        ),
        app_env=os.getenv("APP_ENV", "development"),
        auth_mode=os.getenv("AUTH_MODE", "demo"),
    )
    if settings.auth_mode == "keycloak":
        raise RuntimeError("AUTH_MODE=keycloak ещё не реализован (TECH-09)")
    if settings.auth_mode != "demo":
        raise RuntimeError(f"Неизвестный AUTH_MODE: {settings.auth_mode}")
    if settings.app_env not in DEMO_AUTH_ENVS:
        raise RuntimeError(f"AUTH_MODE=demo запрещён при APP_ENV={settings.app_env}")
    return settings
