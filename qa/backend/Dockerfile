# Образ qa-system (ADR-002). Контекст сборки — каталог qa/, чтобы позже добавить qa/autotests.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && useradd --uid 10001 --create-home qa
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app
# Демо-данные для `python -m app seed` (сервис qa-seed).
COPY dev/demo-seed ./demo-seed
ENV QA_SEED_DIR=/app/demo-seed
USER qa
EXPOSE 8000
CMD ["python", "-m", "app", "api"]
