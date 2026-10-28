#!/bin/bash
# Первичная настройка репликации. Пароль берётся из окружения и не хранится в Git.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'replicator') THEN
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '${REPORTS_REPL_PASSWORD}';
  ELSE
    ALTER ROLE replicator WITH REPLICATION LOGIN PASSWORD '${REPORTS_REPL_PASSWORD}';
  END IF;
END
\$\$;
SQL
grep -q "host replication replicator" "$PGDATA/pg_hba.conf" || \
  echo "host replication replicator all scram-sha-256" >> "$PGDATA/pg_hba.conf"
