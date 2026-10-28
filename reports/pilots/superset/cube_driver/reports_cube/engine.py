"""Register only reports_cube+psycopg2; ordinary PostgreSQL is unchanged."""
from superset.db_engine_specs.postgres import PostgresEngineSpec


class CubeEngineSpec(PostgresEngineSpec):
    engine_name = 'Reports Cube SQL API'
    engine_aliases = {'reports_cube'}
    drivers = {'psycopg2': 'Reports Cube PostgreSQL wire adapter'}
    default_driver = 'psycopg2'

    @classmethod
    def supports_backend(cls, backend, driver=None):
        return backend == 'reports_cube' and driver in {None, 'psycopg2'}
    supports_dynamic_schema = False
    supports_catalog = False
    supports_dynamic_catalog = False

    @classmethod
    def get_default_schema(cls, database, catalog=None):
        return 'public'
