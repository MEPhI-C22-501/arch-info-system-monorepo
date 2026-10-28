from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.models import Base

config = context.config
url = config.get_main_option("sqlalchemy.url") or get_settings().database_url

if context.is_offline_mode():
    raise RuntimeError("Офлайн-режим не поддерживается: миграции выполняются на БД")

engine = create_engine(url, poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
