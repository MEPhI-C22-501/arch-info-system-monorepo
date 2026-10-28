#!/bin/bash
# Повторяемые проверки стенда. Секреты не печатает.
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE=(docker compose -f compose.yaml -f compose.dev.yaml)

echo "bootstrap again"
"${COMPOSE[@]}" run --rm --no-deps keycloak-bootstrap
"${COMPOSE[@]}" run --rm --no-deps minio-bootstrap
"${COMPOSE[@]}" run --rm --no-deps --user 1000:1000 kafka-bootstrap

echo "examples"
docker compose -f compose.yaml -f compose.dev.yaml -f compose.examples.yaml run --rm checks

echo "replica"
"${COMPOSE[@]}" exec -T reports-db psql -U reports -d reports -c \
  "INSERT INTO demo_link (stable_id, entity_kind, label, source_note) VALUES ('10000000-0000-4000-8000-000000000099', 'lag-probe', 'probe', 'smoke') ON CONFLICT DO NOTHING;"
found=0
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T reports-db-replica psql -U reports -d reports -tAc \
    "SELECT 1 FROM demo_link WHERE stable_id = '10000000-0000-4000-8000-000000000099'" | grep -q 1; then
    found=1
    break
  fi
  sleep 1
done
if [[ "$found" != 1 ]]; then
  echo "replica did not receive the probe row" >&2
  exit 1
fi
"${COMPOSE[@]}" exec -T reports-db-replica psql -U reports -d reports -c \
  "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS lag_seconds;"
if "${COMPOSE[@]}" exec -T reports-db-replica psql -U reports -d reports -c "CREATE TABLE replica_write_should_fail(id int);" ; then
  echo "replica accepted a write" >&2
  exit 1
fi
echo "replica is read-only"

echo "restart keeps the realm user"
"${COMPOSE[@]}" restart keycloak
"${COMPOSE[@]}" run --rm --no-deps keycloak-bootstrap >/dev/null
echo "smoke finished"
