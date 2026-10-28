#!/bin/bash
# Поднимает hot standby из pg_basebackup, если каталог данных пуст.
# Повторный запуск сохраняет уже принятый каталог.
set -euo pipefail

: "${REPORTS_REPL_PASSWORD:?}"
export PGDATA="${PGDATA:-/var/lib/postgresql/18/docker}"
mkdir -p "$(dirname "$PGDATA")" "$PGDATA"
chown -R postgres:postgres /var/lib/postgresql

if [[ ! -s "$PGDATA/PG_VERSION" ]]; then
  rm -rf "$PGDATA"
  mkdir -p "$PGDATA"
  chown postgres:postgres "$PGDATA"
  chmod 700 "$PGDATA"
  until pg_isready -h reports-db -U reports -d reports; do
    sleep 1
  done
  export PGPASSWORD="$REPORTS_REPL_PASSWORD"
  gosu postgres pg_basebackup -h reports-db -D "$PGDATA" -U replicator -Fp -Xs -P -R
  unset PGPASSWORD
fi
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

exec gosu postgres postgres -c hot_standby=on -c hot_standby_feedback=on
