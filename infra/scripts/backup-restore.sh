#!/bin/bash
# Снимает таблицу demo_link и восстанавливает её в отдельном Postgres.
# Это учебная проверка FR-08, не копия на другом хосте.
set -euo pipefail
cd "$(dirname "$0")/../.."
DUMP="$(mktemp)"
trap 'rm -f "$DUMP"; docker rm -f reports-restore >/dev/null 2>&1 || true' EXIT
docker compose -f compose.yaml -f compose.dev.yaml exec -T reports-db \
  pg_dump -U reports -d reports --table=demo_link --no-owner --no-privileges > "$DUMP"
docker run -d --name reports-restore --network arch-info_data \
  -e POSTGRES_PASSWORD=restore-demo postgres:18.6@sha256:fc973eb97c9fd04bfa1840e0f510719a584ccb3be8debfe6a4144637a9dfe8cf >/dev/null
for _ in $(seq 1 30); do
  if docker exec reports-restore pg_isready -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec -i reports-restore psql -U postgres -v ON_ERROR_STOP=1 -d postgres < "$DUMP" >/dev/null
docker exec reports-restore psql -U postgres -tAc "SELECT count(*) FROM demo_link"
echo "restore drill finished"
