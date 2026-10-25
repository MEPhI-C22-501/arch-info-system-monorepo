"""PostgreSQL wire adapter for Cube's fixed public, read-only SQL catalog.

Read startup metadata from libpq rather than issuing PostgreSQL-extension and
transaction-discovery SQL that Cube does not need. Query execution remains the
normal psycopg2/PostgreSQL path; no data query or authentication is bypassed.
"""
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2


class CubeDialect(PGDialect_psycopg2):
    driver = 'psycopg2'
    supports_statement_cache = True

    def __init__(self, **kwargs):
        kwargs.setdefault('use_native_hstore', False)
        super().__init__(**kwargs)

    def _get_server_version_info(self, connection):
        raw = connection.connection
        version = getattr(raw, 'dbapi_connection', raw).server_version
        if version < 100000:
            raise RuntimeError('Unexpected Cube SQL protocol version')
        return version // 10000, version % 10000

    def _get_default_schema_name(self, connection):
        return 'public'

    def get_isolation_level(self, dbapi_connection):
        # Cube is a logical read API; engine_params selects AUTOCOMMIT.
        return 'READ COMMITTED'

    def _set_backslash_escapes(self, connection):
        self._backslash_escapes = False
