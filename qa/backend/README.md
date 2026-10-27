# QA System — серверная часть

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 18 ([ADR-001, ADR-002](../docs/145.architecture-decisions.md)). Зависимости — uv.

## Запуск

```bash
# Всё в контейнерах; Swagger — http://127.0.0.1:8090/api/v1/docs
docker compose -f qa/compose.yaml up -d --build --wait qa-api

# Разработка: БД в контейнере с портом 127.0.0.1:5435, приложение локально
docker compose -f qa/compose.yaml -f qa/compose.dev.yaml up -d --wait qa-db
cd qa/backend
uv sync
uv run python -m app migrate
uv run uvicorn app.main:app --reload --port 8090

# Проверки
uv run black --check . && uv run flake8
uv run pytest

# Хук перед коммитом: black и flake8 для файлов qa/backend (один раз на клон, из корня репозитория)
uv run --project qa/backend pre-commit install
```

Black и flake8 настроены на длину строки 100: [`pyproject.toml`](pyproject.toml) и [`.flake8`](.flake8). Чтобы VS Code показывал то же самое, выберите интерпретатор `qa/backend/.venv/bin/python` и добавьте в настройки рабочей области `"flake8.args": ["--config=qa/backend/.flake8"]`.

Авторизация пока демонстрационная: `Authorization: Bearer demo-<роль>` или `demo-<роль>@<пользователь>`, например `demo-qa-lead@ivanov`. Роли — [070](../docs/070.role-matrix.md). В Swagger токен вводится кнопкой Authorize.

## Структура

| Путь | Что | Владелец |
| --- | --- | --- |
| `app/main.py` | Сборка приложения, список `MODULE_ROUTERS` | общий |
| `app/config.py`, `app/db.py` | Настройки из окружения, сессия БД | общий |
| `app/errors.py` | `ApiError`, `not_found`, `conflict`; формат ошибок и `X-Request-Id` по [130](../docs/130.api-contracts.md) | общий |
| `app/auth.py` | `Role`, `require_roles(...)` | общий |
| `app/schemas.py` | `ApiModel` (camelCase), `Page`, `PageParams`, `paginate` | общий |
| `app/keys.py` | `next_key(session, "RUN")` → `RUN-01` | общий |
| `app/models/` | Модели всех таблиц [120](../docs/120.data-model.md); `enums.py` — значения статусов | `cases.py`, `plans.py` — A; `runs.py`, `defects.py` — B |
| `migrations/versions/` | Миграции Alembic | — |
| `tests/` | `conftest.py`: фикстуры `db_session`, `client`, `auth` | общий |

## Правила

- **Модуль** — пакет `app/<модуль>/` с `router.py`, `service.py`, `schemas.py`. Роутер подключается одной строкой в `MODULE_ROUTERS`.
- **Транзакции** фиксирует сервис явным `session.commit()`; изменение, связанная запись в `outbox_message` и история — в одной транзакции.
- **Схема меняется только новой миграцией**: правка модели, затем `uv run alembic revision --autogenerate -m "<что>"` при поднятой БД, затем просмотр файла. Начальную миграцию `0001` не правим. Тест `test_models_match_migrations` падает, если модель изменена без миграции. Если две ветки создали миграции от одной ревизии, вливающийся вторым меняет `down_revision` своей на чужую.
- **Ошибки** — только `ApiError` с кодами из 130, раздел 5.
- **Тесты** работают в транзакции, которая откатывается: данные между тестами не переносятся.
