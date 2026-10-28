# Чистая среда

Предварительно нужны Linux, Docker Engine с Compose v2, доступ к реестрам образов и около 8 ГБ свободного диска на сборку MinIO. Пустая машина без этих требований стенд не поднимет.

```bash
cp .env.example .env   # необязательно: те же значения уже стоят по умолчанию в Compose
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
docker compose -f compose.yaml -f compose.dev.yaml -f compose.examples.yaml run --rm checks
```

Повторный запуск не удаляет тома. `docker compose down -v` стирает данные и сюда не входит.

Проверки: `infra/scripts/smoke.sh`.
