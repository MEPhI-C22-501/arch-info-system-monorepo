#!/bin/sh
# runs once by the postgres image when the data directory is created (docker-entrypoint-initdb.d),
# creates the account of the service with data rights only: the schema belongs to the migrations account
# POSTGRES_USER, the service reads and writes rows and never changes the schema (NFR-RM-16, K-08),
# tables created later by the migrations get the rights through the default privileges of their owner
set -eu

: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v app_password="$POSTGRES_APP_PASSWORD" <<-'EOSQL'
	CREATE ROLE reference_manager_app LOGIN PASSWORD :'app_password';

	GRANT CONNECT ON DATABASE reference_manager TO reference_manager_app;
	GRANT USAGE ON SCHEMA public TO reference_manager_app;

	ALTER DEFAULT PRIVILEGES FOR ROLE reference_manager IN SCHEMA public
	    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO reference_manager_app;
	ALTER DEFAULT PRIVILEGES FOR ROLE reference_manager IN SCHEMA public
	    GRANT USAGE, SELECT ON SEQUENCES TO reference_manager_app;
EOSQL
